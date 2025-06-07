import bpy
from mathutils import Vector
import addon_utils

# constants | 常值

ADDON_NAME = "Unreal Blender IO"
# for mod in addon_utils.modules():
#     if mod.bl_info["name"] == ADDON_NAME:
#         filepath = mod.__file__
#         path = filepath.split("\__init__.py")[0]
#         path = path.replace("\\", "/")
#         preset_path = path + "/PresetFiles/Presets.blend"
# GROUP_MOD = "CAT_MeshGroup"
# MIRROR_MOD = "CAT_Mirror"
# ARRAY_MOD = "CAT_Array"
# DISPLACE_MOD = "CAT_DecalDisplace"
# GROUP_NODE = "MeshGroup"
# INST_PREFIX = "Inst_"
# CUSTOM_NAME = "CAT"
# PIVOT_NAME = "CAT_Inst_Pivot"
# DECAL_NAME = "CAT_Decal"
# INSTANCE_NAME = "CAT_Inst"
# TEMP_MESH = "cat_meshgruop_tempmesh"
# OFFSET_ATTR = "CAT_Offset"
# WORLD_ORIGIN = Vector((0, 0, 0))
# MG_SOCKET_GROUP = "Socket_2"
# MG_SOCKET_REALIZE = "Socket_3"
# MG_SOCKET_OFFSET = "Socket_7"
# DECAL_OFFSET = 0.008
DEFAULT_IO_TEMP_DIR="C:\\Temp\\UBIO\\"

# functions
# def import_node_group(file_path, node_name) -> bpy.types.NodeGroup:
#     """从文件载入NodeGroup"""

#     INNER_PATH = "/NodeTree"
#     FULL_PATH = str(file_path) + INNER_PATH
#     node_exist = False
#     for node in bpy.data.node_groups:
#         if node_name not in node.name:
#             node_exist = False
#         else:
#             node_exist = True
#             node_import = node
#             break

#     if node_exist is False:  # 如果没有导入，导入
#         bpy.ops.wm.append(
#             filepath=str(file_path),
#             directory=FULL_PATH,
#             filename=node_name,
#         )

#     for node in bpy.data.node_groups:
#         if node.name == node_name:
#             node_import = node
#             break

#     return node_import


# def add_meshgroup_modifier(mesh, target_group=None, offset=Vector((0, 0, 0))):
#     """添加Geometry Nodes MeshGroup Modifier"""

#     check_modifier = False
#     offset = Vector(offset)
#     offset = WORLD_ORIGIN - offset

#     for modifier in mesh.modifiers:
#         if modifier.name == GROUP_MOD:
#             check_modifier = True
#             break

#     if check_modifier is False:
#         geo_node_modifier = mesh.modifiers.new(name=GROUP_MOD, type="NODES")
#         geo_node_modifier.node_group = bpy.data.node_groups[GROUP_NODE]
#     else:
#         geo_node_modifier = mesh.modifiers[GROUP_MOD]
#         geo_node_modifier.node_group = bpy.data.node_groups[GROUP_NODE]

#     # set Collection Instance to target group
#     geo_node_modifier[MG_SOCKET_GROUP] = target_group
#     # set offset
#     geo_node_modifier[MG_SOCKET_OFFSET] = offset

#     return geo_node_modifier


# def add_mirror_modifier(mesh, axis=0):
#     """添加DataTransfer Modifier传递顶点色"""

#     # proxy_object = bpy.data.objects[TRANSFERPROXY_PREFIX + mesh.name]
#     check_modifier = False
#     pivot_object = mesh.parent

#     for modifier in mesh.modifiers:  # 检查是否有modifier
#         if modifier.name == MIRROR_MOD:
#             check_modifier = True
#             break

#     if check_modifier is False:  # 如果没有则添加
#         mirror_modifier = mesh.modifiers.new(name=MIRROR_MOD, type="MIRROR")
#         mirror_modifier.mirror_object = pivot_object
#         mirror_modifier.use_axis[axis] = True
#         mirror_modifier.use_bisect_axis[axis] = True
#         mirror_modifier.use_mirror_merge = True


# def add_array_modifier(mesh):
#     """添加Array Modifier"""
#     check_modifier = False

#     for modifier in mesh.modifiers:  # 检查是否有modifier
#         if modifier.name == ARRAY_MOD:
#             check_modifier = True
#             break

#     if check_modifier is False:  # 如果没有则添加
#         array_modifier = mesh.modifiers.new(name="CAT_Array", type="ARRAY")


# def realize_meshgroup_modifier(mesh, realize=True):
#     """Realize Geometry Nodes MeshGroup Modifier"""
#     # check if the mesh has the modifier
#     check_modifier = False

#     for modifier in mesh.modifiers:
#         if modifier.name == GROUP_MOD:
#             check_modifier = True
#             geo_node_modifier = mesh.modifiers[GROUP_MOD]
#             geo_node_modifier[MG_SOCKET_REALIZE] = realize
#             # 刷新gn， 否则结果不会更新
#             mesh.modifiers[GROUP_MOD].show_viewport = True
#             break

#     if check_modifier is False:
#         print("Mesh does not have the MeshGroup modifier")

#     return check_modifier


# def check_is_meshgroup_inst(obj):
#     """Check if the object is a mesh-group instance"""
#     is_meshgroup = False

#     if obj.type == "MESH":
#         try:
#             if obj[CUSTOM_NAME] == INSTANCE_NAME:
#                 # if has mesh group modifier
#                 for modifier in obj.modifiers:
#                     if modifier.type == "NODES":
#                         if modifier.node_group.name == GROUP_NODE:
#                             is_meshgroup = True
#         except:
#             pass
#     return is_meshgroup


# def set_work_mode(type):
#     """Set the work mode of the viewport"""
#     match type:
#         case "MODELING":
#             for collection in bpy.data.collections:
#                 if collection.name.startswith("_"):
#                      collection.hide_select=True
#                 if collection.name=="_localfog":
#                     collection.hide_viewport=True
#                 if collection.name=="Plasticity":
#                     collection.hide_viewport=False
#                     collection.hide_select=False
#             bpy.context.space_data.overlay.show_overlays = True

#             bpy.context.space_data.overlay.show_cursor = False

#             bpy.context.space_data.overlay.show_extras = False
#             bpy.context.space_data.overlay.show_floor = False
#             bpy.context.space_data.overlay.show_axis_x = False
#             bpy.context.space_data.overlay.show_axis_y = False
#             bpy.context.space_data.overlay.show_axis_z = False

#             bpy.context.space_data.show_object_select_light_probe = False
#             bpy.context.space_data.show_object_select_camera = False
#             bpy.context.space_data.show_object_select_light = False
#             bpy.context.space_data.show_object_select_volume = False

#             bpy.context.space_data.show_object_select_mesh = True
#             bpy.context.space_data.show_object_select_curve = True
#             bpy.context.space_data.show_object_select_surf = True
#             bpy.context.space_data.show_object_select_meta = True
#             bpy.context.space_data.show_object_select_font = True
#             bpy.context.space_data.show_object_select_curves = True
#             bpy.context.space_data.show_object_select_pointcloud = True
#             bpy.context.space_data.show_object_select_grease_pencil = True
#             bpy.context.space_data.show_object_select_armature = True
#             bpy.context.space_data.show_object_select_lattice = True
#             bpy.context.space_data.show_object_select_empty = True

#         case "LIGHTING":
#             no_select_collections=[]
#             for collection in bpy.data.collections:
#                 if collection.name==("_env"):
#                     collection.hide_select=False
#                     collection.hide_viewport=False
#                 if collection.name.startswith("_localfog"):
#                      collection.hide_select=True
#                      collection.hide_viewport=False
#                 # if collection.name=="Plasticity" or "Decal" in collection.name:
#                 #     no_select_collections.append(collection)
#             for collection in no_select_collections:
#                 collection.hide_select=True
#             bpy.context.space_data.overlay.show_overlays = True

#             bpy.context.space_data.overlay.show_cursor = False
#             bpy.context.space_data.overlay.show_extras = True
#             bpy.context.space_data.overlay.show_floor = False
#             bpy.context.space_data.overlay.show_axis_x = False
#             bpy.context.space_data.overlay.show_axis_y = False
#             bpy.context.space_data.overlay.show_axis_z = False

#             bpy.context.space_data.show_object_select_light_probe = True
#             bpy.context.space_data.show_object_select_camera = False
#             bpy.context.space_data.show_object_select_light = True

#             bpy.context.space_data.show_object_select_volume = False
#             bpy.context.space_data.show_object_select_mesh = False
#             bpy.context.space_data.show_object_select_curve = False
#             bpy.context.space_data.show_object_select_surf = False
#             bpy.context.space_data.show_object_select_meta = False
#             bpy.context.space_data.show_object_select_font = False
#             bpy.context.space_data.show_object_select_curves = False
#             bpy.context.space_data.show_object_select_pointcloud = False
#             bpy.context.space_data.show_object_select_grease_pencil = False
#             bpy.context.space_data.show_object_select_armature = False
#             bpy.context.space_data.show_object_select_lattice = False
#             bpy.context.space_data.show_object_select_empty = False

#         case "LOCALFOG":
#             no_select_collections=[]
#             for collection in bpy.data.collections:
#                 if collection.name.startswith("_localfog"):
#                      collection.hide_select=False
#                      collection.hide_viewport=False
#                 if collection.name=="Plasticity":
#                     no_select_collections.append(collection)
#             for collection in no_select_collections:
#                 collection.hide_select=True
#             bpy.context.space_data.overlay.show_overlays = True

#             bpy.context.space_data.overlay.show_extras = False
#             bpy.context.space_data.overlay.show_floor = False
#             bpy.context.space_data.overlay.show_axis_x = False
#             bpy.context.space_data.overlay.show_axis_y = False
#             bpy.context.space_data.overlay.show_axis_z = False

#             bpy.context.space_data.show_object_select_light_probe = True
#             bpy.context.space_data.show_object_select_camera = False
#             bpy.context.space_data.show_object_select_light = False

#             bpy.context.space_data.show_object_select_volume = True
#             bpy.context.space_data.show_object_select_mesh = True
#             bpy.context.space_data.show_object_select_curve = False
#             bpy.context.space_data.show_object_select_surf = False
#             bpy.context.space_data.show_object_select_meta = False
#             bpy.context.space_data.show_object_select_font = False
#             bpy.context.space_data.show_object_select_curves = False
#             bpy.context.space_data.show_object_select_pointcloud = False
#             bpy.context.space_data.show_object_select_grease_pencil = False
#             bpy.context.space_data.show_object_select_armature = False
#             bpy.context.space_data.show_object_select_lattice = False
#             bpy.context.space_data.show_object_select_empty = False

#         case "BLENDER DEFAULT":

#             for collection in bpy.data.collections:
#                 if collection.name.startswith("_"):
#                      collection.hide_select=False

#             bpy.context.space_data.overlay.show_overlays = True

#             bpy.context.space_data.overlay.show_extras = True
#             bpy.context.space_data.overlay.show_floor = True
#             bpy.context.space_data.overlay.show_axis_x = True
#             bpy.context.space_data.overlay.show_axis_y = True
#             bpy.context.space_data.overlay.show_axis_z = False

#             bpy.context.space_data.show_object_select_light_probe = True
#             bpy.context.space_data.show_object_select_camera = True
#             bpy.context.space_data.show_object_select_light = True
#             bpy.context.space_data.show_object_select_volume = True

#             bpy.context.space_data.show_object_select_mesh = True
#             bpy.context.space_data.show_object_select_curve = True
#             bpy.context.space_data.show_object_select_surf = True
#             bpy.context.space_data.show_object_select_meta = True
#             bpy.context.space_data.show_object_select_font = True
#             bpy.context.space_data.show_object_select_curves = True
#             bpy.context.space_data.show_object_select_pointcloud = True
#             bpy.context.space_data.show_object_select_grease_pencil = True
#             bpy.context.space_data.show_object_select_armature = True
#             bpy.context.space_data.show_object_select_lattice = True
#             bpy.context.space_data.show_object_select_empty = True


def find_objs_bb_center(objs) -> Vector:
    """Find the center of the bounding box of all objects"""

    all_coords = []
    for o in objs:
        bb = o.bound_box
        mat = o.matrix_world
        for vert in bb:
            coord = mat @ Vector(vert)
            all_coords.append(coord)

    if not all_coords:
        return Vector((0, 0, 0))

    center = sum(all_coords, Vector((0, 0, 0))) / len(all_coords)
    return center


def find_objs_bb_lowest_center(objs) -> Vector:
    """Find the lowest_center of the bounding box of all objects"""

    all_coords = []
    for o in objs:
        bb = o.bound_box
        mat = o.matrix_world
        for vert in bb:
            coord = mat @ Vector(vert)
            all_coords.append(coord)

    if not all_coords:
        return Vector((0, 0, 0))

    # Find the lowest Z value among all bounding box coordinates
    lowest_z = min(coord.z for coord in all_coords)
    # Find the center in X and Y
    center_xy = sum(
        (Vector((coord.x, coord.y, 0)) for coord in all_coords), Vector((0, 0, 0))
    ) / len(all_coords)
    center = Vector((center_xy.x, center_xy.y, lowest_z))
    return center


def find_selected_element_center() -> Vector:
    """When in object mode, find the center of the selected objects.
    When in edit mode, find the center of the selected vertices in all selected mesh objects.
    """

    selected_objects = bpy.context.selected_objects
    if len(selected_objects) == 0:
        return None

    # Check if any selected object is in edit mode and is a mesh
    edit_mode_meshes = [
        obj for obj in selected_objects if obj.type == "MESH" and obj.mode == "EDIT"
    ]
    if edit_mode_meshes:
        all_selected_verts = []
        # Switch all edit mode objects to object mode to access their mesh data
        for obj in edit_mode_meshes:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="OBJECT")
            all_selected_verts.extend(
                [obj.matrix_world @ v.co for v in obj.data.vertices if v.select]
            )
        # Restore the first object to edit mode
        bpy.context.view_layer.objects.active = edit_mode_meshes[0]
        bpy.ops.object.mode_set(mode="EDIT")
        if not all_selected_verts:
            return None
        center = sum(all_selected_verts, Vector((0, 0, 0))) / len(all_selected_verts)
        return center
    else:
        # Get the center of the selected objects in object mode
        center = find_objs_bb_center(selected_objects)
        return center


def set_object_pivot_location(obj, location: Vector):
    """
    Set the object's origin (pivot) to the specified world location.
    """

    offset = location - obj.location
    obj.location += offset
    # Move all vertices in the opposite direction to keep the mesh in place
    if obj.type == "MESH":
        mesh = obj.data
        for v in mesh.vertices:
            v.co -= offset
    # For other object types, additional handling may be needed


def clean_user(target_object: bpy.types.Object) -> None:
    """如果所选object有多个user，转为single user"""
    if target_object.users > 1:
        target_object.data = target_object.data.copy()
