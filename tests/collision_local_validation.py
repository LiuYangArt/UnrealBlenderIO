"""Run in a clean Blender process; exercises ordinary meshes via the registered operator."""
import json
import sys
import time
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'collision'
OUT.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True
with zipfile.ZipFile(next((ROOT / 'wheels').glob('coacd-*.whl'))) as wheel:
    wheel.extractall(OUT / 'python')
sys.path[:0] = [str(OUT / 'python'), str(ROOT.parent)]
import bpy
import numpy as np
from mathutils import Matrix
import UnrealBlenderIO as addon
from UnrealBlenderIO import collision_generation as gen, i18n
from UnrealBlenderIO.util import Const as C

i18n.register_translations()
addon.auto_load.register()
bpy.types.Scene.ubio_params = bpy.props.PointerProperty(type=addon.UBIO_PG_Params)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_monkey_add()
source = bpy.context.object
source.name = 'Suzanne.001'
source.matrix_world = Matrix.Translation((3, 4, 5)) @ Matrix.Rotation(.4, 4, 'Z') @ Matrix.Diagonal((-2, .5, 1, 1))
bpy.context.view_layer.update()
source_vertices = np.array([tuple(v.co) for v in source.data.vertices])
source_faces = [tuple(f.vertices) for f in source.data.polygons]
source_properties = dict(source.items())
assert gen.UBIO_OT_GenerateCollision.poll(bpy.context)
assert not gen.asset_path(source)
start = time.perf_counter()
assert bpy.ops.ubio.generate_collision('EXEC_DEFAULT') == {'FINISHED'}
elapsed = time.perf_counter() - start
colliders = [o for o in bpy.data.objects if o.get(C.STATIC_MESH_PROP_COLLISION_TARGET_NAME) == source.name]
assert 1 <= len(colliders) <= 32
for obj in colliders:
    assert obj.name.startswith('UCX_Suzanne.001_') and '/' not in obj.name
    assert obj.parent == source
    assert np.allclose(obj.matrix_world, source.matrix_world)
    assert not gen.asset_path(obj)
    assert not obj.get(C.BP_STATIC_MESH_PROP_COLLECTION_ROLE)
    obj.data.calc_loop_triangles()
    gen.validate_hull(np.array([tuple(v.co) for v in obj.data.vertices]),
                      np.array([tuple(t.vertices) for t in obj.data.loop_triangles]))
assert np.array_equal(source_vertices, [tuple(v.co) for v in source.data.vertices])
assert source_faces == [tuple(f.vertices) for f in source.data.polygons]
assert source_properties == dict(source.items())

# Plain meshes with shared mesh data remain independent generation targets.
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.mesh.primitive_cube_add(location=(8, 0, 0))
cube = bpy.context.object
cube2 = cube.copy()
cube2.data = cube.data
bpy.context.scene.collection.objects.link(cube2)
cube2.location.x += 4
cube2.select_set(True)
assert len(gen.asset_groups(bpy.context)) == 2
assert bpy.ops.ubio.generate_collision('EXEC_DEFAULT') == {'FINISHED'}
old = {o.as_pointer() for o in bpy.data.objects if o.get(C.STATIC_MESH_PROP_COLLISION_TARGET_NAME) in {cube.name, cube2.name}}
assert len(old) == 2
assert bpy.ops.ubio.generate_collision('EXEC_DEFAULT') == {'FINISHED'}
new = {o.as_pointer() for o in bpy.data.objects if o.get(C.STATIC_MESH_PROP_COLLISION_TARGET_NAME) in {cube.name, cube2.name}}
assert len(new) == 2 and not old.intersection(new)
assert all(o.name in bpy.data.objects for o in colliders)
bpy.ops.object.select_all(action='DESELECT')
colliders[0].select_set(True)
assert not gen.UBIO_OT_GenerateCollision.poll(bpy.context)

result = dict(passed=True, blender=bpy.app.version_string, source_vertices=len(source_vertices),
              source_faces=len(source_faces), monkey_seconds=elapsed, monkey_hulls=len(colliders),
              source_unchanged=True, ordinary_mesh_grouping=True, replacement=True,
              transformed_parent=True, convex_hulls_valid=True)
(OUT/'local_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('LOCAL_MESH_VALIDATION', json.dumps(result), flush=True)
del bpy.types.Scene.ubio_params
addon.auto_load.unregister()
i18n.unregister_translations()
