import bpy
from mathutils import Vector
from math import radians
from math import pi
import shutil
import os
import json
import hashlib
from datetime import datetime, timezone
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
    STATIC_MESH_SESSION_DIR = os.path.join(DEFAULT_IO_TEMP_DIR, "StaticMeshSessions")
    BP_STATIC_MESH_SESSION_DIR = os.path.join(DEFAULT_IO_TEMP_DIR, "BPStaticMeshSessions")
    STATIC_MESH_SESSION_FILE = "session.json"
    STATIC_MESH_SOURCE_FBX = "source.fbx"
    STATIC_MESH_EDITED_FBX = "edited.fbx"
    BP_STATIC_MESH_ASSETS_DIR_NAME = "assets"
    BP_STATIC_MESH_LOGS_DIR_NAME = "logs"
    STATIC_MESH_SESSION_TYPE = "static_mesh_roundtrip"
    BP_STATIC_MESH_SESSION_TYPE = "bp_static_mesh_roundtrip"
    STATIC_MESH_SESSION_SCHEMA_VERSION = "1.0"
    BP_STATIC_MESH_SESSION_SCHEMA_VERSION = "2.2"
    STATIC_MESH_COLLECTION_PREFIX = "UBIO_StaticMesh"
    BP_STATIC_MESH_COLLECTION_PREFIX = "UBIO_BP"
    STATIC_MESH_PROP_SESSION_ID = "ubio_session_id"
    STATIC_MESH_PROP_SESSION_DIR = "ubio_session_dir"
    STATIC_MESH_PROP_SESSION_FILE = "ubio_session_file"
    STATIC_MESH_PROP_SOURCE_ASSET_PATH = "ubio_source_asset_path"
    STATIC_MESH_PROP_SOURCE_ACTOR_GUID = "ubio_source_actor_guid"
    STATIC_MESH_PROP_ROUNDTRIP_TYPE = "ubio_roundtrip_type"
    STATIC_MESH_PROP_COLLECTION = "ubio_session_collection"
    STATIC_MESH_ROUNDTRIP_TYPE = "StaticMesh"
    BP_STATIC_MESH_ROUNDTRIP_TYPE = "BPStaticMesh"
    BP_STATIC_MESH_PROP_SESSION_ID = "ubio_bp_session_id"
    BP_STATIC_MESH_PROP_SESSION_FILE = "ubio_bp_session_file"
    BP_STATIC_MESH_PROP_ASSET_KEY = "ubio_bp_asset_key"
    BP_STATIC_MESH_PROP_COMPONENT_KEY = "ubio_bp_component_key"
    BP_STATIC_MESH_PROP_SOURCE_ASSET_PATH = "ubio_bp_source_asset_path"
    BP_STATIC_MESH_PROP_COLLECTION_ROLE = "ubio_bp_collection_role"
    BP_STATIC_MESH_PROP_ROUNDTRIP_TYPE = "ubio_bp_roundtrip_type"
    BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME = "ubio_bp_canonical_object_name"
    BP_STATIC_MESH_ROLE_SESSION_ROOT = "SESSION_ROOT"
    BP_STATIC_MESH_ROLE_SOURCES_ROOT = "SOURCES_ROOT"
    BP_STATIC_MESH_ROLE_SOURCE_ASSET = "SOURCE_ASSET"
    BP_STATIC_MESH_ROLE_LAYOUT_ROOT = "LAYOUT_ROOT"
    BP_STATIC_MESH_ROLE_LAYOUT_INSTANCE = "LAYOUT_INSTANCE"
    BP_STATIC_MESH_ROLE_INTERNAL_ROOT = "INTERNAL_ROOT"
    BP_STATIC_MESH_ROLE_CANONICAL_ROOT = "CANONICAL_ROOT"
    BP_STATIC_MESH_ROLE_CANONICAL_OBJECT = "CANONICAL_OBJECT"
    BP_STATIC_MESH_ROLE_COMPONENT_WRAPPER = "COMPONENT_WRAPPER"
    BP_STATIC_MESH_ROLE_COMPONENT_OBJECT = "COMPONENT_OBJECT"
    STATIC_MESH_STATUS_EXPORTED_FROM_UE = "EXPORTED_FROM_UE"
    STATIC_MESH_STATUS_IMPORTED_IN_BLENDER = "IMPORTED_IN_BLENDER"
    STATIC_MESH_STATUS_EXPORTED_FROM_BLENDER = "EXPORTED_FROM_BLENDER"
    STATIC_MESH_STATUS_REIMPORTED_IN_UE = "REIMPORTED_IN_UE"
    STATIC_MESH_STATUS_PARTIAL_FAILED = "PARTIAL_FAILED"
    STATIC_MESH_STATUS_FAILED = "FAILED"


def get_ubio_temp_dir() -> str:
    return os.path.abspath(os.path.normpath(Const.DEFAULT_IO_TEMP_DIR))


def _is_safe_ubio_temp_dir(dir_path: str) -> bool:
    normalized_path = os.path.abspath(os.path.normpath(dir_path))
    tail = os.path.splitdrive(normalized_path)[1]
    if tail in ("", "\\", "/"):
        return False

    parts = [part for part in normalized_path.replace("/", "\\").split("\\") if part]
    return len(parts) >= 2 and parts[-1].upper() == "UBIO"


def clean_ubio_temp_dir() -> tuple[str, int]:
    target_dir = get_ubio_temp_dir()
    if not _is_safe_ubio_temp_dir(target_dir):
        raise ValueError(f"Refusing to clean unsafe temp dir: {target_dir}")

    if not os.path.isdir(target_dir):
        return target_dir, 0

    removed_entries = 0
    for entry in os.scandir(target_dir):
        try:
            if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)
            removed_entries += 1
        except FileNotFoundError:
            continue

    os.makedirs(target_dir, exist_ok=True)
    return target_dir, removed_entries


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


def get_iso_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_directory(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def make_safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(value))
    safe = safe.strip("_")
    return safe or "StaticMesh"


def make_short_hash(value: str, length: int = 6) -> str:
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()[:length]


def get_bp_static_mesh_assets_dir(session_dir: str) -> str:
    return os.path.join(session_dir, Const.BP_STATIC_MESH_ASSETS_DIR_NAME)


def get_bp_static_mesh_logs_dir(session_dir: str) -> str:
    return os.path.join(session_dir, Const.BP_STATIC_MESH_LOGS_DIR_NAME)


def get_bp_static_mesh_asset_dir(session_dir: str, asset_key: str) -> str:
    return os.path.join(get_bp_static_mesh_assets_dir(session_dir), asset_key)


def get_bp_static_mesh_source_fbx(session_dir: str, asset_key: str) -> str:
    return os.path.join(get_bp_static_mesh_asset_dir(session_dir, asset_key), Const.STATIC_MESH_SOURCE_FBX)


def get_bp_static_mesh_edited_fbx(session_dir: str, asset_key: str) -> str:
    return os.path.join(get_bp_static_mesh_asset_dir(session_dir, asset_key), Const.STATIC_MESH_EDITED_FBX)


def get_bp_static_mesh_log_path(session_dir: str, log_name: str) -> str:
    return os.path.join(get_bp_static_mesh_logs_dir(session_dir), log_name)


def get_static_mesh_session_file(session_dir: str) -> str:
    return os.path.join(session_dir, Const.STATIC_MESH_SESSION_FILE)


def get_static_mesh_source_fbx(session_dir: str) -> str:
    return os.path.join(session_dir, Const.STATIC_MESH_SOURCE_FBX)


def get_static_mesh_edited_fbx(session_dir: str) -> str:
    return os.path.join(session_dir, Const.STATIC_MESH_EDITED_FBX)


def list_session_files_in_root(session_root: str):
    if not os.path.isdir(session_root):
        return []

    session_files = []
    for entry in os.scandir(session_root):
        if not entry.is_dir():
            continue
        session_file = get_static_mesh_session_file(entry.path)
        if os.path.isfile(session_file):
            session_files.append(session_file)
    return session_files


def list_static_mesh_session_files():
    session_files = []
    for session_root in (Const.STATIC_MESH_SESSION_DIR, Const.BP_STATIC_MESH_SESSION_DIR):
        session_files.extend(list_session_files_in_root(session_root))

    session_files.sort(key=os.path.getmtime, reverse=True)
    return session_files


def find_latest_static_mesh_session_file():
    session_files = list_static_mesh_session_files()
    if not session_files:
        return None
    return session_files[0]


def load_json_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(file_path: str, data: dict) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_default_bp_static_mesh_transform() -> dict:
    return {
        "location": {"x": 0, "y": 0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1},
    }


def get_default_bp_static_mesh_import_policy() -> dict:
    return {
        "root_at_world_origin": True,
        "component_transform_mode": "ACTOR_LOCAL_BAKED",
        "component_hierarchy_mode": "FLAT_UNDER_ROOT",
        "instance_mode": "LINKED_DATA",
        "canonical_storage": "INTERNAL_HIDDEN",
    }


def normalize_bp_static_mesh_session_data(session_data: dict, session_dir: str) -> dict:
    session_data.setdefault("schema_version", Const.BP_STATIC_MESH_SESSION_SCHEMA_VERSION)
    session_data.setdefault("assets", [])
    session_data.setdefault("components", [])
    session_data.setdefault("paths", {})
    session_data.setdefault("source_actor", {})
    session_data.setdefault("timestamps", {})
    session_data["paths"].setdefault("assets_dir", get_bp_static_mesh_assets_dir(session_dir))
    session_data["paths"].setdefault("logs_dir", get_bp_static_mesh_logs_dir(session_dir))

    if "source_actor_world_transform" not in session_data and "root_transform" in session_data:
        session_data["source_actor_world_transform"] = session_data.get("root_transform")
    session_data.setdefault("source_actor_world_transform", get_default_bp_static_mesh_transform())

    import_policy = session_data.get("blender_import_policy")
    if not isinstance(import_policy, dict):
        import_policy = {}
        session_data["blender_import_policy"] = import_policy
    for key, value in get_default_bp_static_mesh_import_policy().items():
        import_policy.setdefault(key, value)

    for asset in session_data["assets"]:
        asset_key = asset.get("asset_key", "")
        if not asset_key:
            continue
        asset.setdefault("source_fbx", get_bp_static_mesh_source_fbx(session_dir, asset_key))
        asset.setdefault("edited_fbx", get_bp_static_mesh_edited_fbx(session_dir, asset_key))
        asset.setdefault("component_keys", [])
        if "canonical_object_names" not in asset and "source_object_names" in asset:
            asset["canonical_object_names"] = list(asset.get("source_object_names") or [])
        asset.setdefault("canonical_object_names", [])
        asset.setdefault("source_object_names", list(asset.get("canonical_object_names") or []))
        asset.setdefault("edited_object_names", [])
        asset.setdefault(
            "canonical_root_name",
            f"SRC_{make_safe_name(asset.get('asset_name') or asset_key or 'StaticMesh')}_ROOT",
        )
        asset.setdefault("reimport_status", "PENDING")

    for component in session_data["components"]:
        component.setdefault("component_name", component.get("component_key", ""))
        component.setdefault("component_class", "StaticMeshComponent")
        component.setdefault(
            "actor_local_transform",
            component.get("relative_transform", get_default_bp_static_mesh_transform()),
        )
        component.setdefault("parent_component_key", None)
        component.setdefault("relative_transform", get_default_bp_static_mesh_transform())
        component.setdefault("world_transform", get_default_bp_static_mesh_transform())
        component.setdefault("attach_chain", [component.get("component_name") or component.get("component_key") or ""])
        component.setdefault("visible", True)

    session_data["root_transform"] = session_data.get("source_actor_world_transform", get_default_bp_static_mesh_transform())
    return session_data


def load_static_mesh_session(session_file: str):
    session_data = load_json_file(session_file)
    session_dir = os.path.dirname(session_file)
    session_type = session_data.get("session_type", Const.STATIC_MESH_SESSION_TYPE)
    session_data.setdefault("session_type", session_type)
    session_data.setdefault("timestamps", {})

    if session_type == Const.BP_STATIC_MESH_SESSION_TYPE:
        return normalize_bp_static_mesh_session_data(session_data, session_dir)

    session_data.setdefault("schema_version", Const.STATIC_MESH_SESSION_SCHEMA_VERSION)
    session_data.setdefault("paths", {})
    session_data["paths"].setdefault("source_fbx", get_static_mesh_source_fbx(session_dir))
    session_data["paths"].setdefault("edited_fbx", get_static_mesh_edited_fbx(session_dir))
    return session_data


def save_static_mesh_session(session_file: str, session_data: dict) -> None:
    session_dir = os.path.dirname(session_file)
    session_type = session_data.get("session_type", Const.STATIC_MESH_SESSION_TYPE)
    session_data.setdefault("paths", {})

    if session_type == Const.BP_STATIC_MESH_SESSION_TYPE:
        normalize_bp_static_mesh_session_data(session_data, session_dir)
        session_data["paths"]["assets_dir"] = session_data["paths"].get(
            "assets_dir", get_bp_static_mesh_assets_dir(session_dir)
        )
        session_data["paths"]["logs_dir"] = session_data["paths"].get(
            "logs_dir", get_bp_static_mesh_logs_dir(session_dir)
        )
        session_data["root_transform"] = session_data.get(
            "source_actor_world_transform", get_default_bp_static_mesh_transform()
        )
        for asset in session_data.get("assets", []):
            asset_key = asset.get("asset_key", "")
            if not asset_key:
                continue
            asset["source_fbx"] = asset.get("source_fbx", get_bp_static_mesh_source_fbx(session_dir, asset_key))
            asset["edited_fbx"] = asset.get("edited_fbx", get_bp_static_mesh_edited_fbx(session_dir, asset_key))
            asset.setdefault("component_keys", [])
            asset.setdefault("canonical_object_names", [])
            asset["source_object_names"] = list(asset.get("canonical_object_names") or [])
            asset.setdefault("edited_object_names", [])
            asset.setdefault(
                "canonical_root_name",
                f"SRC_{make_safe_name(asset.get('asset_name') or asset_key or 'StaticMesh')}_ROOT",
            )
            asset.setdefault("reimport_status", "PENDING")
        save_json_file(session_file, session_data)
        return

    session_data["paths"]["source_fbx"] = session_data["paths"].get(
        "source_fbx", get_static_mesh_source_fbx(session_dir)
    )
    session_data["paths"]["edited_fbx"] = session_data["paths"].get(
        "edited_fbx", get_static_mesh_edited_fbx(session_dir)
    )
    save_json_file(session_file, session_data)

def update_static_mesh_session_status(
    session_data: dict,
    status: str,
    timestamp_key: str,
) -> None:
    session_data["status"] = status
    session_data.setdefault("timestamps", {})
    session_data["timestamps"][timestamp_key] = get_iso_timestamp()


def build_static_mesh_collection_name(session_data: dict) -> str:
    asset_name = (
        session_data.get("source_asset", {}).get("asset_name")
        or session_data.get("session_id")
        or "StaticMesh"
    )
    session_suffix = str(session_data.get("session_id", "session"))[-8:]
    return f"{Const.STATIC_MESH_COLLECTION_PREFIX}_{asset_name}_{session_suffix}"


def apply_static_mesh_session_metadata(
    target,
    session_file: str,
    session_data: dict,
    collection_name: str = "",
) -> None:
    session_dir = os.path.dirname(session_file)
    target[Const.STATIC_MESH_PROP_SESSION_ID] = session_data.get("session_id", "")
    target[Const.STATIC_MESH_PROP_SESSION_DIR] = session_dir
    target[Const.STATIC_MESH_PROP_SESSION_FILE] = session_file
    target[Const.STATIC_MESH_PROP_SOURCE_ASSET_PATH] = session_data.get(
        "source_asset", {}
    ).get("asset_path", "")
    target[Const.STATIC_MESH_PROP_SOURCE_ACTOR_GUID] = session_data.get(
        "source_actor", {}
    ).get("guid", "")
    target[Const.STATIC_MESH_PROP_ROUNDTRIP_TYPE] = Const.STATIC_MESH_ROUNDTRIP_TYPE
    if collection_name:
        target[Const.STATIC_MESH_PROP_COLLECTION] = collection_name


def apply_bp_static_mesh_session_metadata(
    target,
    session_file: str,
    session_data: dict,
    collection_role: str = "",
    asset_key: str = "",
    component_key: str = "",
    source_asset_path: str = "",
    collection_name: str = "",
) -> None:
    apply_static_mesh_session_metadata(
        target,
        session_file,
        session_data,
        collection_name=collection_name,
    )
    target[Const.STATIC_MESH_PROP_ROUNDTRIP_TYPE] = Const.BP_STATIC_MESH_ROUNDTRIP_TYPE
    target[Const.BP_STATIC_MESH_PROP_SESSION_ID] = session_data.get("session_id", "")
    target[Const.BP_STATIC_MESH_PROP_SESSION_FILE] = session_file
    target[Const.BP_STATIC_MESH_PROP_ROUNDTRIP_TYPE] = Const.BP_STATIC_MESH_ROUNDTRIP_TYPE
    if collection_role:
        target[Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE] = collection_role
    if asset_key:
        target[Const.BP_STATIC_MESH_PROP_ASSET_KEY] = asset_key
    if component_key:
        target[Const.BP_STATIC_MESH_PROP_COMPONENT_KEY] = component_key
    if source_asset_path:
        target[Const.BP_STATIC_MESH_PROP_SOURCE_ASSET_PATH] = source_asset_path


def build_bp_static_mesh_collection_name(session_data: dict) -> str:
    actor_label = (
        session_data.get("source_actor", {}).get("label")
        or session_data.get("session_id")
        or "Blueprint"
    )
    actor_safe = make_safe_name(actor_label)
    session_suffix = str(session_data.get("session_id", "session"))[-8:]
    return f"{Const.BP_STATIC_MESH_COLLECTION_PREFIX}_{actor_safe}_{session_suffix}"


def build_bp_static_mesh_asset_collection_name(asset_data: dict) -> str:
    asset_name = make_safe_name(asset_data.get("asset_name") or asset_data.get("asset_key") or "StaticMesh")
    asset_key = str(asset_data.get("asset_key", "asset"))
    asset_suffix = asset_key[-6:] if len(asset_key) >= 6 else asset_key
    return f"{asset_name}__{asset_suffix}"


def get_static_mesh_session_file_from_object(obj: bpy.types.Object):
    if obj is None:
        return None
    return obj.get(Const.STATIC_MESH_PROP_SESSION_FILE) or obj.get(Const.BP_STATIC_MESH_PROP_SESSION_FILE)


def find_static_mesh_session_objects(session_id: str):
    if not session_id:
        return []
    matched = []
    for obj in bpy.data.objects:
        if obj.get(Const.STATIC_MESH_PROP_SESSION_ID) == session_id:
            matched.append(obj)
    return matched
