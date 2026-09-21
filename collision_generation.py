"""Asset-scoped collision generation and transactional Blender scene updates."""
import json
import time
import hashlib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

from .collision import create_component_collision, set_collision_target
from .collision_backend import decompose, MAX_HULL_VERTICES
from .collision_preprocess import prepare_mesh, try_rectangular_wall, _closed, _volume, _components
from .i18n import msgid, tr
from .util import Const

GENERATED = 'ubio_generated_collision'


def asset_path(obj):
    return obj.get(Const.BP_STATIC_MESH_PROP_SOURCE_ASSET_PATH) or obj.get(Const.STATIC_MESH_PROP_SOURCE_ASSET_PATH, '')


def is_render(obj):
    return (obj.type == 'MESH'
            and not obj.get(Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME)
            and not obj.name.upper().startswith(('UCX_', 'UBX_', 'USP_', 'UCP_')))


def asset_groups(context):
    selected = [obj for obj in context.selected_objects if is_render(obj)]
    paths = {asset_path(obj) for obj in selected if asset_path(obj)}
    result = {'blender:' + obj.name: [[obj]] for obj in sorted(selected, key=lambda obj: obj.name) if not asset_path(obj)}
    for path in sorted(paths):
        canonical = [obj for obj in bpy.data.objects if is_render(obj) and asset_path(obj) == path
                     and obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) != Const.BP_STATIC_MESH_ROLE_COMPONENT_OBJECT]
        sessions = {}
        for obj in canonical:
            sessions.setdefault(obj.get(Const.STATIC_MESH_PROP_SESSION_ID, ''), []).append(obj)
        if not sessions:
            raise ValueError('conflicting_asset')
        result[path] = [sorted(objects, key=lambda obj: obj.name) for objects in sessions.values()]
    return result


def asset_frame(objects):
    obj = objects[0]
    if not asset_path(obj):
        return obj.matrix_world.copy(), obj
    if obj.get(Const.BP_STATIC_MESH_PROP_ASSET_KEY):
        root = obj.parent
        while root and root.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) != Const.BP_STATIC_MESH_ROLE_CANONICAL_ROOT:
            root = root.parent
        if root is None:
            raise ValueError('conflicting_asset')
        return root.matrix_world.copy(), root
    return Matrix.Identity(4), None


def validate_hull(vertices, triangles):
    v, t = np.asarray(vertices), np.asarray(triangles)
    if (len(v) < 4 or len(v) > MAX_HULL_VERTICES or not np.isfinite(v).all()
            or not _closed(t) or _volume(v, t) <= 1e-12):
        raise ValueError('invalid_hull')
    center = v.mean(axis=0)
    tolerance = max(float(np.ptp(v, axis=0).max()) * 1e-5, 1e-7)
    for face in t:
        a, b, c = v[face]
        normal = np.cross(b-a, c-a)
        length = np.linalg.norm(normal)
        if length <= 1e-14:
            raise ValueError('invalid_hull')
        normal /= length
        if np.dot(normal, center-a) > 0:
            normal = -normal
        if np.max((v-a) @ normal) > tolerance:
            raise ValueError('invalid_hull')


def _remove(objects):
    meshes = set()
    for obj in objects:
        if obj.data:
            meshes.add(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def replace_collisions(context, path, sessions, parts):
    if asset_path(sessions[0][0]):
        targets = {obj.name for obj in bpy.data.objects if is_render(obj) and asset_path(obj) == path}
    else:
        targets = {obj.name for objects in sessions for obj in objects}
    old = [obj for obj in bpy.data.objects if obj.type == 'MESH'
           and obj.get(Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME) in targets]
    # Allocate the complete replacement before touching editable previous results.
    created, collections, allocated_meshes = [], [], []
    desired_names = []
    try:
        for objects in sessions:
            target = objects[0]
            frame, root = asset_frame(objects)
            session_id = target.get(Const.STATIC_MESH_PROP_SESSION_ID, '')
            collection_key = path + ':' + session_id
            collection = next((c for c in bpy.data.collections if c.get('ubio_collision_collection') == collection_key), None)
            if collection is None:
                collection = bpy.data.collections.new(tr('panel.collision.collection'))
                collection['ubio_collision_collection'] = collection_key
                context.scene.collection.children.link(collection)
                collections.append(collection)
            instances = [obj for obj in bpy.data.objects
                         if obj.get(Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME) == target.name
                         and obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) == Const.BP_STATIC_MESH_ROLE_COMPONENT_OBJECT]
            for index, (vertices, faces) in enumerate(parts):
                mesh = bpy.data.meshes.new('UBIO_UCX')
                allocated_meshes.append(mesh)
                mesh.from_pydata((vertices / context.scene.unit_settings.scale_length).tolist(), [], faces.tolist())
                mesh.update()
                obj = bpy.data.objects.new('UBIO_PENDING_UCX', mesh)
                created.append(obj)
                collection.objects.link(obj)
                for key in target.keys():
                    if key.startswith('ubio_'):
                        obj[key] = target[key]
                obj[GENERATED] = True
                obj.parent = root
                obj.matrix_world = frame
                set_collision_target(obj, target)
                if target.get(Const.BP_STATIC_MESH_PROP_ASSET_KEY):
                    obj[Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE] = Const.BP_STATIC_MESH_ROLE_CANONICAL_COLLISION
                    obj[Const.STATIC_MESH_PROP_COLLISION_ASSET_KEY] = target.get(Const.BP_STATIC_MESH_PROP_ASSET_KEY, '')
                obj.hide_render = True
                name = path.rsplit('.', 1)[-1] if asset_path(target) else target.name
                desired_names.append((obj, f'UCX_{name}_{index:02d}'))
                for instance_index, target_instance in enumerate(instances):
                    clone = create_component_collision(obj, target_instance, collection, 'UBIO_PENDING_INSTANCE')
                    created.append(clone)
                    wrapper = target_instance.parent
                    while wrapper and wrapper.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) != Const.BP_STATIC_MESH_ROLE_COMPONENT_WRAPPER:
                        wrapper = wrapper.parent
                    if wrapper is None:
                        raise ValueError('conflicting_asset')
                    clone.parent = wrapper
                    clone.matrix_local = Matrix.Identity(4)
                    desired_names.append((clone, f'COL_{target_instance.name}_{index:02d}'))
                if instances:
                    obj.hide_set(True)
        context.view_layer.update()
    except Exception:
        for obj in created:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in allocated_meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for collection in collections:
            if not collection.objects:
                bpy.data.collections.remove(collection)
        raise
    _remove(old)
    # Rebind instance names after Blender resolves scene-wide name collisions.
    references = {obj.name: obj for obj in created}
    for obj, name in desired_names:
        obj.name = name
    for obj in created:
        canonical = references.get(obj.get(Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME, ''))
        if canonical is not None:
            obj[Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME] = canonical.name
    return created


def generate_asset(context, path, sessions, settings):
    start = time.perf_counter()
    objects = sessions[0]
    frame, _ = asset_frame(objects)
    v, t, metrics = prepare_mesh(context, objects, frame, settings)
    for other in sessions[1:]:
        other_frame, _ = asset_frame(other)
        ov, ot, _ = prepare_mesh(context, other, other_frame, settings)
        if ov.shape != v.shape or ot.shape != t.shape or not np.allclose(v, ov) or not np.array_equal(t, ot):
            raise ValueError('conflicting_asset')
    parts = try_rectangular_wall(v, t, settings) if settings['preserve_openings'] else None
    method = 'orthogonal_boxes' if parts else 'coacd'
    if parts is None:
        parts = []
        # Disconnected solids must not consume a joint concavity budget or bridge empty space.
        components = list(_components(t))
        if len(components) > settings['max_hulls']:
            raise ValueError('hull_budget')
        for component_index, indices in enumerate(components):
            used, remap = np.unique(t[indices], return_inverse=True)
            cv, ct = v[used], remap.reshape(-1, 3).astype(np.int32)
            component_parts = try_rectangular_wall(cv, ct, settings) if settings['preserve_openings'] else None
            if component_parts is None:
                remaining_budget = settings['max_hulls'] - len(parts) - (len(components) - component_index - 1)
                component_parts = decompose(cv, ct, {**settings, 'max_hulls': remaining_budget})
            parts.extend(component_parts)
            if len(parts) > settings['max_hulls']:
                raise ValueError('hull_budget')
    if len(parts) > settings['max_hulls']:
        raise ValueError('hull_budget')
    for pv, pt in parts:
        validate_hull(pv, pt)
    replace_collisions(context, path, sessions, parts)
    output = np.concatenate([pv for pv, _ in parts])
    metrics.update(asset=path, backend=method, seconds=time.perf_counter()-start,
                   hulls=len(parts), hull_vertices=[len(pv) for pv, _ in parts],
                   input_bounds_m=[v.min(axis=0).tolist(), v.max(axis=0).tolist()],
                   output_bounds_m=[output.min(axis=0).tolist(), output.max(axis=0).tolist()])
    if method != 'orthogonal_boxes':
        metrics['opening_measurement'] = 'unsupported'
        metrics.pop('openings_after', None)
    print('[UBIO Collision] ' + json.dumps(metrics))
    return metrics


class UBIO_OT_GenerateCollision(bpy.types.Operator):
    bl_idname = 'ubio.generate_collision'
    bl_label = msgid('op.generate_collision.label')
    bl_description = msgid('op.generate_collision.desc')
    # Settings live on the scene; adjusting them must never rerun expensive generation.
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(is_render(obj) for obj in context.selected_objects)

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        groups = asset_groups(context)
        if not groups:
            self.report({'ERROR'}, tr('report.collision.no_assets'))
            return {'CANCELLED'}
        settings = {key: getattr(context.scene.ubio_params, 'collision_' + key) for key in ('max_hulls', 'error', 'min_volume', 'min_thickness', 'feature_size', 'ground', 'preserve_openings')}
        hulls = 0
        for path, sessions in groups.items():
            print('[UBIO Collision] ' + json.dumps(dict(asset=path, settings=settings,
                  objects=[[obj.name for obj in objects] for objects in sessions])), flush=True)
            result = generate_asset(context, path, sessions, settings)
            hulls += result['hulls']
            for objects in sessions:
                session_file = objects[0].get(Const.STATIC_MESH_PROP_SESSION_FILE, '')
                if session_file:
                    log_dir = Path(session_file).parent / 'logs'
                    log_dir.mkdir(parents=True, exist_ok=True)
                    key = hashlib.sha256(path.encode()).hexdigest()[:12]
                    (log_dir / f'collision_{key}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        self.report({'INFO'}, tr('report.collision.generated', count=len(groups), hulls=hulls))
        return {'FINISHED'}
