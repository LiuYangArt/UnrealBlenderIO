import bpy

from .util import Const


COLLISION_PREFIXES = ("UCX_", "UBX_", "UCP_", "USP_")


def is_ue_collision_object(obj: bpy.types.Object) -> bool:
    return obj.type == "MESH" and obj.name.upper().startswith(COLLISION_PREFIXES)


def collision_prefix(name: str) -> str:
    upper_name = name.upper()
    for prefix in COLLISION_PREFIXES:
        if upper_name.startswith(prefix):
            return prefix
    return "UCX_"


def style_collision_object(obj: bpy.types.Object) -> None:
    obj.color = (0.04, 0.35, 0.04, 1.0)
    obj.display_type = "WIRE"
    obj.show_name = True


def set_collision_target(obj: bpy.types.Object, target_obj: bpy.types.Object) -> None:
    obj[Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME] = target_obj.name
    style_collision_object(obj)


def copy_local_transform(source_obj: bpy.types.Object, target_obj: bpy.types.Object) -> None:
    target_obj.location = source_obj.location.copy()
    target_obj.rotation_mode = source_obj.rotation_mode
    if source_obj.rotation_mode == "QUATERNION":
        target_obj.rotation_quaternion = source_obj.rotation_quaternion.copy()
    elif source_obj.rotation_mode == "AXIS_ANGLE":
        target_obj.rotation_axis_angle = tuple(source_obj.rotation_axis_angle)
    else:
        target_obj.rotation_euler = source_obj.rotation_euler.copy()
    target_obj.scale = source_obj.scale.copy()


def create_component_collision(
    canonical_collision: bpy.types.Object,
    component_target: bpy.types.Object,
    collection: bpy.types.Collection,
    name: str,
) -> bpy.types.Object:
    clone = canonical_collision.copy()
    clone.data = canonical_collision.data
    clone.animation_data_clear()
    clone.name = name
    collection.objects.link(clone)
    clone.parent = component_target.parent
    copy_local_transform(canonical_collision, clone)
    clone[Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME] = component_target.name
    clone[Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME] = canonical_collision.name
    clone[Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE] = Const.BP_STATIC_MESH_ROLE_COMPONENT_COLLISION
    canonical_collision[Const.STATIC_MESH_PROP_COLLISION_INSTANCE_COUNT] = (
        int(canonical_collision.get(Const.STATIC_MESH_PROP_COLLISION_INSTANCE_COUNT, 0)) + 1
    )
    style_collision_object(clone)
    return clone


def sync_component_collision_to_canonical(canonical_collision: bpy.types.Object) -> None:
    visible_copies = [
        obj for obj in bpy.data.objects
        if obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) == Const.BP_STATIC_MESH_ROLE_COMPONENT_COLLISION
        and obj.get(Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME) == canonical_collision.name
    ]
    if not visible_copies:
        return
    visible_copies.sort(key=lambda obj: obj.name)
    source = visible_copies[0]
    canonical_collision.data = source.data
    copy_local_transform(source, canonical_collision)


def reconcile_component_collisions(
    canonical_collisions: list[bpy.types.Object],
) -> tuple[list[bpy.types.Object], list[str]]:
    kept = []
    deleted_names = []
    for canonical_collision in canonical_collisions:
        visible_copies = [
            obj for obj in bpy.data.objects
            if obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) == Const.BP_STATIC_MESH_ROLE_COMPONENT_COLLISION
            and obj.get(Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME) == canonical_collision.name
        ]
        expected_count = int(
            canonical_collision.get(Const.STATIC_MESH_PROP_COLLISION_INSTANCE_COUNT, 0)
        )
        if expected_count > 0 and len(visible_copies) < expected_count:
            deleted_names.append(canonical_collision.name)
            for visible_copy in visible_copies:
                bpy.data.objects.remove(visible_copy, do_unlink=True)
            bpy.data.objects.remove(canonical_collision, do_unlink=True)
            continue
        if visible_copies:
            sync_component_collision_to_canonical(canonical_collision)
        kept.append(canonical_collision)
    return kept, deleted_names
