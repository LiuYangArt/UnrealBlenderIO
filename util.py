import bpy
from mathutils import Vector
from math import radians
from math import pi
import shutil
import os
# import addon_utils

# =====================
# 全局常量（供全项目使用）
# =====================

class Const:
    # Blender/Unreal通用常量
    GUID = "ue_guid"
    FNAME = "ue_fname"
    ACTORTYPE = "ue_actortype"
    ACTORCLASS = "ue_class"
    UECOLL = "UnrealIO"
    MAINLEVEL = "MainLevel"
    COLL_ROOT = "Root"
    COLL_MAIN = "Main"
    COLL_LEVEL = "Level"
    UECOLL_COLOR = "COLOR_06"
    COLLINST_TYPES = ["Blueprint"]
    BL_FLAG = "Blender"
    BL_NEW = "NewActor"
    BL_DEL = "Removed"
    PROXY_PIVOT = "UBIOProxyPivot"
    PROXY_PIVOT_OBJ = "Pivot"
    CUSTOM_VAR = "UBIO"
    # 其它常量
    ADDON_NAME = "Unreal Blender IO"
    DEFAULT_IO_TEMP_DIR = "C:\\Temp\\UBIO\\"


def find_objs_bb_center(objs) -> Vector:
    """查找所有对象Bounding Box的中心点"""

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
    """查找所有对象Bounding Box的最低中心点"""

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
    """在物体模式下，查找选中物体的中心点。
    在编辑模式下，查找所有选中Mesh物体中选中顶点的中心点。
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
    将对象的原点(pivot)设置到指定的世界坐标位置。
    """

    offset = location - obj.location
    obj.location += offset

    if obj.type == "MESH":
        mesh = obj.data
        for v in mesh.vertices:
            v.co -= offset



def clean_user(target_object: bpy.types.Object) -> None:
    """如果所选object有多个user，转为single user"""
    if target_object.users > 1:
        target_object.data = target_object.data.copy()


def get_all_children(obj):
    """
    递归获取所有子对象
    参数：
        obj (bpy.types.Object): 父对象对象
    返回：
        list[bpy.types.Object]: 所有子对象的列表
    """
    children = []
    for child in obj.children:
        children.append(child)
        children.extend(get_all_children(child))
    return children


def find_level_asset_coll(uecoll: str, coll_level: str):
    """
    查找Level Asset Collection
    参数：
        uecoll (str): 根集合名称（如Const.UECOLL）
        coll_level (str): Level集合类型标记（如Const.COLL_LEVEL）
    返回：
        bpy.types.Collection or None: Level Asset集合对象或None
    """
    ubio_coll = bpy.data.collections.get(uecoll)
    if not ubio_coll:
        return None
    sub_colls = get_all_children(ubio_coll)
    for coll in sub_colls:
        coll_type = coll.get(uecoll, None)
        if coll_type == coll_level:
            return coll
    return None


def set_proxy_pivot_properties(pivot):
    """
    设置Proxy Pivot对象的显示属性和自定义属性
    参数：
        pivot (bpy.types.Object): 需要设置的pivot对象
    返回：
        无
    """
    pivot.hide_viewport = False
    pivot.hide_select = False
    pivot.empty_display_type = 'ARROWS'
    pivot.empty_display_size = 0.2
    pivot.show_name = True
    pivot.show_in_front = True
    pivot[Const.CUSTOM_VAR] = Const.PROXY_PIVOT


def get_transform_from_obj(obj):
    """
    从Blender对象获取UE风格的transform字典（自动处理坐标/角度/缩放转换）
    参数：
        obj (bpy.types.Object): 目标对象
    返回：
        dict: 包含location/rotation/scale的UE风格transform字典
    """
    loc = obj.location * 100
    rot = obj.rotation_euler
    rot_deg = [((r * 180.0 / pi) % 360) for r in rot]
    scale = obj.scale
    return {
        "location": {
            "x": loc.x,
            "y": -loc.y,
            "z": loc.z
        },
        "rotation": {
            "x": rot_deg[0],
            "y": -rot_deg[1],
            "z": -rot_deg[2]
        },
        "scale": {
            "x": scale.x,
            "y": scale.y,
            "z": scale.z
        }
    }


def set_actor_transform(obj, transform):
    """
    设置Blender对象的transform，自动处理UE/Blender坐标系转换
    参数：
        obj (bpy.types.Object): 目标对象
        transform (dict): UE风格transform字典（包含location/rotation/scale）
    返回：
        无
    """

    loc = transform["location"]
    rot = transform["rotation"]
    scale = transform["scale"]
    obj.location = Vector((loc["x"]/100, -loc["y"]/100, loc["z"]/100))
    obj.rotation_euler = (
        radians(rot["x"]),
        -radians(rot["y"]),
        -radians(rot["z"])
    )
    obj.scale = Vector((scale["x"], scale["y"], scale["z"]))


def is_obj_transform_equal(obj, transform, tol=0.01):
    """
    判断Blender对象与transform字典的transform是否近似相等
    参数：
        obj (bpy.types.Object): 目标对象
        transform (dict): UE风格transform字典
        tol (float): 容差，默认0.01
    返回：
        bool: 是否近似相等
    """
    ue_transform = get_transform_from_obj(obj)
    def is_close(a, b):
        return abs(a - b) < tol
    for key in ["location", "rotation", "scale"]:
        for axis in ["x", "y", "z"]:
            if not is_close(ue_transform[key][axis], transform[key][axis]):
                return False
    return True


def copy_unreal_assets(source_dir: str, target_dir: str):
    """将UnrealAsset目录下的内容复制到UE工程目录下。
    参数：
        source_dir (str): UnrealAsset源目录的路径。
        target_dir (str): UE工程目标目录的路径。
    """
    if not os.path.exists(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        return

    # 确保目标目录存在，如果不存在则创建
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for item in os.listdir(source_dir):
        s = os.path.join(source_dir, item)
        d = os.path.join(target_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    print(f"成功将 {source_dir} 复制到 {target_dir}")
