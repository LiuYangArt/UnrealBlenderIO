import unreal
import os
import json
import traceback
from datetime import datetime
#constants
DEFAULT_IO_TEMP_DIR = r"C:\Temp\UBIO"
STATIC_MESH_SESSION_DIR = os.path.join(DEFAULT_IO_TEMP_DIR, "StaticMeshSessions")
STATIC_MESH_SESSION_FILE = "session.json"
STATIC_MESH_SOURCE_FBX = "source.fbx"
STATIC_MESH_EDITED_FBX = "edited.fbx"
STATIC_MESH_SESSION_TYPE = "static_mesh_roundtrip"
STATIC_MESH_SCHEMA_VERSION = "1.0"
STATIC_MESH_STATUS_EXPORTED_FROM_UE = "EXPORTED_FROM_UE"
STATIC_MESH_STATUS_IMPORTED_IN_BLENDER = "IMPORTED_IN_BLENDER"
STATIC_MESH_STATUS_EXPORTED_FROM_BLENDER = "EXPORTED_FROM_BLENDER"
STATIC_MESH_STATUS_REIMPORTED_IN_UE = "REIMPORTED_IN_UE"
STATIC_MESH_STATUS_FAILED = "FAILED"
STATIC_MESH_LOG_PREFIX = "[UBIO StaticMesh]"
BL_FLAG = "Blender"
BL_NEW = "NewActor"
BL_DEL = "Removed"

editor_subsys= unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level_subsys = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_subsys= unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
# unreal.EditorAssetSubsystem.set_dirty_flag

editor_util = unreal.EditorUtilityLibrary
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_lib = unreal.EditorAssetLibrary


def log_static_mesh_info(message):
    unreal.log(f"{STATIC_MESH_LOG_PREFIX} {message}")


def log_static_mesh_error(message):
    unreal.log_error(f"{STATIC_MESH_LOG_PREFIX} {message}")


def get_iso_timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_directory(path):
    os.makedirs(path, exist_ok=True)
    return path


def make_safe_name(value):
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(value))
    safe = safe.strip("_")
    return safe or "StaticMesh"


def get_session_file_path(session_dir):
    return os.path.join(session_dir, STATIC_MESH_SESSION_FILE)


def get_static_mesh_source_fbx_path(session_dir):
    return os.path.join(session_dir, STATIC_MESH_SOURCE_FBX)


def get_static_mesh_edited_fbx_path(session_dir):
    return os.path.join(session_dir, STATIC_MESH_EDITED_FBX)


def write_json_file(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def read_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_static_mesh_session_files():
    if not os.path.isdir(STATIC_MESH_SESSION_DIR):
        return []

    session_files = []
    for entry in os.scandir(STATIC_MESH_SESSION_DIR):
        if not entry.is_dir():
            continue
        session_file = get_session_file_path(entry.path)
        if os.path.isfile(session_file):
            session_files.append(session_file)

    session_files.sort(key=os.path.getmtime, reverse=True)
    return session_files


def find_latest_static_mesh_session_file():
    session_files = list_static_mesh_session_files()
    if not session_files:
        return None
    return session_files[0]


def load_static_mesh_session(session_file):
    session_data = read_json_file(session_file)
    session_dir = os.path.dirname(session_file)
    session_data.setdefault("schema_version", STATIC_MESH_SCHEMA_VERSION)
    session_data.setdefault("session_type", STATIC_MESH_SESSION_TYPE)
    session_data.setdefault("paths", {})
    session_data["paths"].setdefault("source_fbx", get_static_mesh_source_fbx_path(session_dir))
    session_data["paths"].setdefault("edited_fbx", get_static_mesh_edited_fbx_path(session_dir))
    session_data.setdefault("timestamps", {})
    return session_data


def save_static_mesh_session(session_file, session_data):
    session_dir = os.path.dirname(session_file)
    session_data.setdefault("paths", {})
    session_data["paths"]["source_fbx"] = session_data["paths"].get(
        "source_fbx", get_static_mesh_source_fbx_path(session_dir)
    )
    session_data["paths"]["edited_fbx"] = session_data["paths"].get(
        "edited_fbx", get_static_mesh_edited_fbx_path(session_dir)
    )
    write_json_file(session_file, session_data)


def update_static_mesh_session_status(session_data, status, timestamp_key):
    session_data["status"] = status
    session_data.setdefault("timestamps", {})
    session_data["timestamps"][timestamp_key] = get_iso_timestamp()


def split_object_path(asset_path):
    object_name = asset_path.rsplit(".", 1)[-1]
    package_path = asset_path.rsplit("/", 1)[0]
    return package_path, object_name


def get_static_mesh_from_actor(actor):
    if actor is None:
        return None

    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None:
        return None

    static_mesh = component.get_editor_property("static_mesh")
    if static_mesh is None:
        return None

    return static_mesh


def get_selected_static_mesh_source():
    selected_actors = actor_subsys.get_selected_level_actors()
    log_static_mesh_info(f"Selected level actors: {len(selected_actors)}")
    if len(selected_actors) == 1:
        actor = selected_actors[0]
        static_mesh = get_static_mesh_from_actor(actor)
        if static_mesh is not None:
            log_static_mesh_info(
                f"Resolved level actor selection: actor={actor.get_actor_label()} mesh={static_mesh.get_path_name()}"
            )
            return {
                "selection_source": "level_actor",
                "actor": actor,
                "static_mesh": static_mesh,
            }
        log_static_mesh_info(
            f"Selected actor has no StaticMeshComponent/static mesh: {actor.get_actor_label()}"
        )
    elif len(selected_actors) > 1:
        actor_names = [actor.get_actor_label() for actor in selected_actors]
        log_static_mesh_info(f"Multiple level actors selected: {actor_names}")

    selected_assets = editor_util.get_selected_assets()
    log_static_mesh_info(f"Selected content browser assets: {len(selected_assets)}")
    static_mesh_assets = []
    for asset in selected_assets:
        asset_class = asset.get_class().get_name() if asset else "None"
        asset_path = asset.get_path_name() if asset else "None"
        log_static_mesh_info(f"Content Browser selection: class={asset_class} path={asset_path}")
        if asset and asset_class == "StaticMesh":
            static_mesh_assets.append(asset)

    if len(static_mesh_assets) == 1:
        static_mesh = static_mesh_assets[0]
        log_static_mesh_info(
            f"Resolved content browser selection: mesh={static_mesh.get_path_name()}"
        )
        return {
            "selection_source": "content_browser_asset",
            "actor": None,
            "static_mesh": static_mesh,
        }

    if len(static_mesh_assets) > 1:
        raise RuntimeError("multiple_static_mesh_assets_selected")

    if len(selected_actors) != 1:
        raise RuntimeError("expected_single_selected_actor")

    raise RuntimeError("selected_source_has_no_static_mesh")


def build_static_mesh_session_data(actor, static_mesh, session_id, session_dir, selection_source):
    actor_label = ""
    actor_guid = ""
    if actor is not None:
        try:
            actor_label = str(actor.get_actor_label())
        except Exception:
            actor_label = ""
    try:
        actor_guid = str(actor.actor_guid) if actor is not None else ""
    except Exception:
        actor_guid = ""

    return {
        "schema_version": STATIC_MESH_SCHEMA_VERSION,
        "session_type": STATIC_MESH_SESSION_TYPE,
        "session_id": session_id,
        "ue_version": str(unreal.SystemLibrary.get_engine_version()),
        "blender_version": "5.0",
        "status": STATIC_MESH_STATUS_EXPORTED_FROM_UE,
        "selection_source": selection_source,
        "source_actor": {
            "label": actor_label,
            "guid": actor_guid,
        },
        "source_asset": {
            "asset_name": str(static_mesh.get_name()),
            "asset_path": str(static_mesh.get_path_name()),
        },
        "paths": {
            "source_fbx": get_static_mesh_source_fbx_path(session_dir),
            "edited_fbx": get_static_mesh_edited_fbx_path(session_dir),
        },
        "export_options": {
            "axis": "UE_TO_BLENDER_DEFAULT",
            "unit": "CENTIMETERS",
        },
        "timestamps": {
            "exported_from_ue": get_iso_timestamp(),
            "imported_in_blender": None,
            "exported_from_blender": None,
            "reimported_in_ue": None,
        },
    }


def export_static_mesh_asset_to_fbx(static_mesh, output_fbx_path):
    output_dir = os.path.dirname(output_fbx_path)
    ensure_directory(output_dir)
    log_static_mesh_info(
        f"Exporting static mesh asset to FBX: asset={static_mesh.get_path_name()} output={output_fbx_path}"
    )

    export_options = unreal.FbxExportOption()
    export_options.export_source_mesh = True
    export_options.vertex_color = False
    export_options.level_of_detail = False
    export_options.collision = False

    export_task = unreal.AssetExportTask()
    export_task.object = static_mesh
    export_task.filename = output_fbx_path
    export_task.automated = True
    export_task.prompt = False
    export_task.replace_identical = True
    export_task.options = export_options
    static_mesh_exporter = unreal.StaticMeshExporterFBX()
    export_task.exporter = static_mesh_exporter
    result = static_mesh_exporter.run_asset_export_task(export_task)
    export_errors = list(export_task.errors or [])
    if export_errors:
        for error_message in export_errors:
            log_static_mesh_error(f"Exporter message: {error_message}")

    log_static_mesh_info(f"Exporter returned: {result}")

    if not result or not os.path.isfile(output_fbx_path):
        if os.path.isfile(output_fbx_path):
            file_size = os.path.getsize(output_fbx_path)
            log_static_mesh_info(f"Unexpected partial FBX output exists: {output_fbx_path} ({file_size} bytes)")
        else:
            log_static_mesh_error(f"FBX file was not created: {output_fbx_path}")
        raise RuntimeError("static_mesh_export_failed")
    file_size = os.path.getsize(output_fbx_path)
    log_static_mesh_info(f"FBX export complete: {output_fbx_path} ({file_size} bytes)")
    return output_fbx_path


def build_static_mesh_import_options():
    options = unreal.FbxImportUI()
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)

    static_mesh_import_data = options.get_editor_property("static_mesh_import_data")
    static_mesh_import_data.set_editor_property("combine_meshes", True)
    static_mesh_import_data.set_editor_property("auto_generate_collision", False)
    return options


def reimport_static_mesh_from_fbx(static_mesh_asset_path, source_fbx_path):
    package_path, asset_name = split_object_path(static_mesh_asset_path)
    task = unreal.AssetImportTask()
    task.filename = source_fbx_path
    task.destination_path = package_path
    task.destination_name = asset_name
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.save = True
    task.options = build_static_mesh_import_options()

    asset_tools.import_asset_tasks([task])

    reimported_asset = unreal.load_asset(static_mesh_asset_path)
    if reimported_asset is None:
        raise RuntimeError("static_mesh_reimport_failed")

    editor_asset_lib.save_loaded_asset(reimported_asset, only_if_is_dirty=False)
    return reimported_asset


def get_default_object(asset) -> unreal.Object:
    bp_gen_class = unreal.load_object(None, asset.generated_class().get_path_name())
    default_object = unreal.get_default_object(bp_gen_class)
    return default_object

def get_blueprint_class(path: str) -> unreal.Class:
    blueprint_asset = unreal.load_asset(path)
    blueprint_class = unreal.load_object(
        None, blueprint_asset.generated_class().get_path_name()
    )
    return blueprint_class

def get_actor_type(actor, class_name):
    """
    获取Actor的更有意义的类型描述。
    
    Args:
        actor: Actor对象
        class_name: Actor的类名
        
    Returns:
        str: 更有意义的类型描述
    """
    # 检查是否是常见的Actor类型
    if class_name == "StaticMeshActor":
        return "StaticMesh"
    elif class_name == "SkeletalMeshActor":
        return "SkeletalMesh"
    elif class_name == "CameraActor":
        return "Camera"
    elif class_name == "DirectionalLight":
        return "DirectionalLight"
    elif class_name == "PointLight":
        return "PointLight"
    elif class_name == "SpotLight":
        return "SpotLight"
    elif class_name == "SkyLight":
        return "SkyLight"
    elif class_name == "ReflectionCapture":
        return "ReflectionCapture"
    elif class_name == "PackedLevelActor":
        return "PackedLevel"
    elif class_name == "LevelInstance":
        return "LevelInstance"
    
    # 检查是否是蓝图Actor
    if "_C" in class_name:
        # 尝试获取父类
        try:
            parent_class = actor.get_class().get_super_class()
            if parent_class:
                parent_name = parent_class.get_name()
                if parent_name == "Actor":
                    # 如果父类是Actor，尝试检查组件
                    return get_actor_type_from_components(actor, class_name)
                else:
                    # 返回父类名称
                    return f"Blueprint ({parent_name})"
        except:
            pass
        
        # 如果无法获取更多信息，至少标记为蓝图
        return "Blueprint"
    
    # 默认返回原始类名
    return class_name

def get_actor_type_from_components(actor, class_name):
    """
    通过检查Actor的组件来确定其类型。
    
    Args:
        actor: Actor对象
        class_name: Actor的类名
        
    Returns:
        str: 基于组件的类型描述
    """
    try:
        # 获取所有组件
        components = actor.get_components_by_class(unreal.SceneComponent)
        
        # 检查是否有StaticMeshComponent
        static_mesh_components = [c for c in components if c.get_class().get_name() == "StaticMeshComponent"]
        if static_mesh_components:
            return "Blueprint (StaticMesh)"
        
        # 检查是否有SkeletalMeshComponent
        skeletal_mesh_components = [c for c in components if c.get_class().get_name() == "SkeletalMeshComponent"]
        if skeletal_mesh_components:
            return "Blueprint (SkeletalMesh)"
        
        # 检查是否有CameraComponent
        camera_components = [c for c in components if c.get_class().get_name() == "CameraComponent"]
        if camera_components:
            return "Blueprint (Camera)"
        
        # 检查是否有LightComponent
        light_components = [c for c in components if "LightComponent" in c.get_class().get_name()]
        if light_components:
            return "Blueprint (Light)"
    except:
        pass
    
    # 如果无法确定具体类型，返回通用蓝图类型
    return "Blueprint"

def is_transform_close(actor, location, rotation, scale, tol=0.01):
    actor_transform = actor.get_actor_transform()
    loc = actor_transform.translation
    rot = actor_transform.rotation.rotator()
    scl = actor_transform.scale3d

    def is_close(a, b, tol=tol):
        return abs(a - b) < tol

    loc_match = (
        is_close(loc.x, location.get("x", 0)) and
        is_close(loc.y, location.get("y", 0)) and
        is_close(loc.z, location.get("z", 0))
    )
    rot_match = (
        is_close(rot.roll, rotation.get("x", 0)) and
        is_close(rot.pitch, rotation.get("y", 0)) and
        is_close(rot.yaw, rotation.get("z", 0))
    )
    scl_match = (
        is_close(scl.x, scale.get("x", 1)) and
        is_close(scl.y, scale.get("y", 1)) and
        is_close(scl.z, scale.get("z", 1))
    )
    return loc_match and rot_match and scl_match

def get_level_asset(type="EDITOR"):
    """ 获取Level Asset
    type='EDITOR' 时输出当前打开的Level的World对象
    type='CONTENTBROWSER' 时输出在Content Browser中选中的Level
    """
    if type == "EDITOR":
        # 获取当前打开的Level
        current_level = level_subsys.get_current_level()
        # 从Level获取World对象
        if current_level:
            outer = current_level.get_outer()
            if outer:
                if outer.get_class().get_name() == "World":
                    # print(f"Current Active Level Asset: {outer}")
                    return outer

        
    if type == "CONTENTBROWSER":
        level_assets=[]
        editor_util = unreal.EditorUtilityLibrary
        selected_assets = editor_util.get_selected_assets()
        for asset in selected_assets:
        #检查是否是LevelAsset
            asset_class = asset.get_class().get_name()
            if asset_class=="World":
                level_assets.append(asset)
        return level_assets


def export_level_to_fbx(level_asset,output_path):
    """
    导出Level到指定的FBX文件路径。
    Args:
        level_asset: World对象或Level对象
        output_path (str): 导出的FBX文件的完整路径，包括文件名和扩展名（.fbx）。
    Returns:
        str: 成功导出后返回FBX文件的完整路径，否则返回None。
    """
    
    # 确保输出目录存在
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        print(f"创建输出目录: {output_path}")

    if level_asset is None:
        print("错误: level_asset 为 None")
        return None

    current_level = level_asset
    print(f"Export object: {current_level}")
    print(f"Export object class: {current_level.get_class().get_name()}")
    
    # 如果传入的是Level对象，尝试获取World对象
    if current_level.get_class().get_name() == "Level":
        print("检测到Level对象，尝试获取对应的World对象...")
        world = get_level_asset(type="EDITOR")
        if world:
            current_level = world
            print(f"使用World对象: {current_level}")
        else:
            print("警告: 无法获取World对象，将尝试使用Level对象导出")
    
    level_name = current_level.get_name()

    # 设置导出选项
    export_options = unreal.FbxExportOption()
    # 这里可以根据需要设置更多的导出选项，例如：
    export_options.export_source_mesh=True
    export_options.vertex_color = False
    export_options.level_of_detail = False
    export_options.collision = False
    
    
    # 构建完整的输出文件路径
    fbx_file_path = os.path.join(output_path, f"{level_name}.fbx")
    print(f"导出路径: {fbx_file_path}")
    
    # 导出Level到FBX
    export_task = unreal.AssetExportTask()
    export_task.object = current_level
    export_task.filename = fbx_file_path
    export_task.automated = True
    export_task.prompt = False
    export_task.options = export_options
    
    # 使用正确的导出器
    fbx_exporter = unreal.LevelExporterFBX()
    export_task.exporter = fbx_exporter
    
    # 执行导出任务
    result = fbx_exporter.run_asset_export_task(export_task)
    
    # 检查导出结果
    if result:
        print(f"✓ 成功导出 Level: {level_name} 到 {fbx_file_path}")
        # 验证文件是否存在
        if os.path.exists(fbx_file_path):
            file_size = os.path.getsize(fbx_file_path)
            print(f"  文件大小: {file_size} bytes")
            return fbx_file_path
        else:
            print(f"  警告: 导出报告成功但文件不存在!")
            return None
    else:
        print(f"✗ 导出 Level 失败: {level_name}")
        return None

def export_current_level_json(output_path):
    """
    导出当前关卡的世界信息和所有Actor的信息到JSON文件。
    Actor信息包括Transform, 类型, FName和FGuid。
    """

    try:
        # 1. 获取当前编辑器世界和关卡信息
        main_level=editor_subsys.get_editor_world()
        
        current_level = level_subsys.get_current_level()
        
        if current_level:
            print(current_level)
            level_asset = current_level.get_outer()
        if not current_level:
        #     outer = current_level.get_outer():
            unreal.log_error("无法获取当前编辑器世界。请确保在编辑器中打开了一个关卡。")
            return
        main_level_path = main_level.get_path_name()
        level_asset_path = level_asset.get_path_name()
        print (f"当前关卡: {level_asset_path}")
        # 使用关卡名作为文件名（去除路径和前缀，使其更简洁）
        level_name_for_file = unreal.SystemLibrary.get_object_name(level_asset).replace(" ", "_")
        # print (f"关卡名: {level_name_for_file}")
        unreal.log(f"开始导出关卡: {level_asset.get_name()}")
        # 2. 获取当前活动子关卡中的所有Actor
        # 使用get_actors_from_level方法，只获取特定关卡中的Actor
        all_actors = []
        
        all_actors = actor_subsys.get_all_level_actors()
        # 过滤出属于当前关卡的Actor
        if level_asset_path != main_level_path:
            filtered_actors = []
            for actor in all_actors:
                if actor and actor.get_level() == current_level:
                    filtered_actors.append(actor)
            all_actors = filtered_actors
            unreal.log(f"通过过滤获取到 {len(all_actors)} 个属于当前关卡的Actor")
        else:
            unreal.log(f"当前关卡为主关卡，不进行过滤,获取到{len(all_actors)}个Actor")
        actors_data = []
        # 3. 遍历所有Actor并提取信息
        for actor in all_actors:
            # print(actor.get_actor_label())
            if actor is None: # 避免处理无效的actor
                continue
            actor_info = {}
            
            # Actor FName (对象实例名)
            actor_info["name"] = str(actor.get_actor_label())
            actor_info["fname"] = str(actor.get_fname())
            
            # Actor FGuid (全局唯一ID)
            actor_guid = actor.actor_guid
            actor_info["fguid"] = str(actor_guid)

            # Actor 类型 (类名)
            actor_class = actor.get_class()
            class_name = actor_class.get_name() if actor_class else "Unknown"
            
            # 获取更有意义的类型信息
            actor_type = get_actor_type(actor, class_name)

            actor_info["class"] = class_name  # 保留原始类名
            actor_info["actor_type"] = actor_type  # 添加更有意义的类型描述
            # Actor Transform
            transform = actor.get_actor_transform()
            location = transform.translation # unreal.Vector
            rotation = transform.rotation.rotator() # unreal.Rotator
            scale = transform.scale3d # unreal.Vector
            actor_info["transform"] = {
                "location": {"x": location.x, "y": location.y, "z": location.z},
                "rotation": {"x": rotation.roll,"y": rotation.pitch, "z": rotation.yaw},
                "scale": {"x": scale.x, "y": scale.y, "z": scale.z}
            }
            
            actors_data.append(actor_info)
        # 4. 组织最终的JSON数据
        level_export_data = {
            "main_level": main_level_path,
            "level_path": level_asset_path,
            "level_name_for_file": level_name_for_file,
            "export_path": output_path,
            "actor_count": len(actors_data),
            "actors": actors_data
        }
        # 5. 定义输出路径并写入JSON文件

        if not os.path.exists(output_path):
            os.makedirs(output_path)
            print(f"创建输出目录: {output_path}")
        
        file_path = os.path.join(output_path, f"{level_name_for_file}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(level_export_data, f, indent=4, ensure_ascii=False)
        unreal.log(f"成功导出关卡数据到: {file_path}")
        return file_path
    except Exception as e:
        unreal.log_error(f"导出关卡数据时发生错误: {e}")
        import traceback
        unreal.log_error(traceback.format_exc())
        return None
def import_json(file_path):
    """
    1. 从json导入数据
    2. 检查json的关卡是否与目前打开的关卡一致（根据main_level和level_path校验是否同一个关卡）
    3. 检查json里actor的transform是否与level中actor的transform一致（根据name, fname和guid校验是否同一个actor）
    4. 如果json里有新actor，根据guid，创建一个actor，根据transform，设置actor的位置，旋转，缩放
    """

    # 1. 读取JSON文件
    if not os.path.exists(file_path):
        unreal.log_error(f"找不到JSON文件: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        unreal.log(f"成功读取JSON文件: {file_path}")

    # 2. 校验关卡
    main_level = editor_subsys.get_editor_world()
    level_asset = get_level_asset(type="EDITOR")
    main_level_path = main_level.get_path_name()
    level_asset_path = level_asset.get_path_name()

    json_main_level = json_data.get("main_level", "")
    json_level_path = json_data.get("level_path", "")

    if main_level_path != json_main_level or level_asset_path != json_level_path:
        unreal.log_error("JSON中的关卡与当前打开的关卡不一致，导入终止。")
        return

    # 3. 获取当前关卡所有Actor，建立fname映射
    all_actors = actor_subsys.get_all_level_actors()
    fname_to_actor = {}
    match_count = 0
    for actor in all_actors:
        if hasattr(actor, "get_fname"):
            actor_fname = str(actor.get_fname())
            actor_name = str(actor.get_actor_label())
            fname_to_actor[actor_fname] = actor
            match_count += 1
    print(f"matched count: {match_count}")
    # print(fname_to_actor)

    # 4. 遍历JSON中的actors
    json_actors_data = json_data.get("actors", [])
    # 先遍历一遍，收集需要处理的对象到不同列表
    bl_new_list = []   # 存储需要新建的actor信息
    bl_del_list = []   # 存储需要删除的actor信息
    other_ops = []     # 存储其他需要同步transform的actor信息

    for actor_info in json_actors_data:
        guid = actor_info.get("fguid")
        name = actor_info.get("name")
        fname = actor_info.get("fname")
        actor_type = actor_info.get("actor_type")
        blender_flag = actor_info.get(BL_FLAG, None)
        if "Light" in actor_type:  # 忽略灯光
            continue
        transform_data = actor_info.get("transform", {})
        location = transform_data.get("location", {})
        rotation = transform_data.get("rotation", {})
        scale = transform_data.get("scale", {})

        # 分类收集BL_NEW、BL_DEL和其他操作
        if blender_flag == BL_NEW:
            bl_new_list.append((actor_info, location, rotation, scale))
        elif blender_flag == BL_DEL:
            bl_del_list.append((actor_info, actor_type, name))
        else:
            other_ops.append((actor_info, location, rotation, scale))

    # 先统一处理所有BL_NEW，避免被提前删除
    for actor_info, location, rotation, scale in bl_new_list:
        name = actor_info.get("name")
        fname = actor_info.get("fname")
        actor_type = actor_info.get("actor_type")
        name_exists = False
        same_type = False
        # 检查场景中是否有同名actor
        for a in fname_to_actor.values():
            if a.get_actor_label() == name:
                name_exists = True
                a_type = get_actor_type(a, a.get_class().get_name())
                if a_type == actor_type:
                    same_type = True
                    # 只修改transform
                    new_transform = unreal.Transform(
                        unreal.Vector(location.get("x", 0), location.get("y", 0), location.get("z", 0)),
                        unreal.Rotator(rotation.get("x", 0), rotation.get("y", 0), rotation.get("z", 0)),
                        unreal.Vector(scale.get("x", 1), scale.get("y", 1), scale.get("z", 1))
                    )
                    a.set_actor_transform(new_transform, sweep=False, teleport=True)
                    unreal.log(f"已更新同名Actor: {name} 的Transform")
                    break
        # 如果是新Actor且没有找到同名同类型的actor
        if not name_exists or not same_type:
            # fname找原资源并复制
            src_actor = None
            for a in fname_to_actor.values():
                if str(a.get_fname()) == fname:
                    src_actor = a
                    break
            if src_actor:
                # 复制actor
                new_actor = actor_subsys.duplicate_actor(src_actor)
                if new_actor:
                    new_actor.set_actor_label(name)
                    new_transform = unreal.Transform(
                        unreal.Vector(location.get("x", 0), location.get("y", 0), location.get("z", 0)),
                        unreal.Rotator(rotation.get("x", 0), rotation.get("y", 0), rotation.get("z", 0)),
                        unreal.Vector(scale.get("x", 1), scale.get("y", 1), scale.get("z", 1))
                    )
                    new_actor.set_actor_transform(new_transform, sweep=False, teleport=True)
                    unreal.log(f"已新增Blender新Actor: {name} 并设置Transform")
                else:
                    unreal.log_error(f"无法复制原Actor: {name}")
            else:
                unreal.log_error(f"找不到原资源Actor用于复制: {name}")

    # 再统一处理所有BL_DEL，确保不会提前删除新建目标
    for actor_info, actor_type, name in bl_del_list:
        # 检查场景中是否有同名actor且类型一致
        for a in fname_to_actor.values():
            if a.get_actor_label() == name:
                a_type = get_actor_type(a, a.get_class().get_name())
                if a_type == actor_type:
                    # 找到匹配的actor，删除它
                    unreal.log(f"删除Actor: {name} (类型: {actor_type})")
                    a.destroy_actor()
                    break

    # 最后处理其他操作（如transform同步）
    for actor_info, location, rotation, scale in other_ops:
        name = actor_info.get("name")
        fname = actor_info.get("fname")
        actor_type = actor_info.get("actor_type")
        actor = None
        # 只有当 fname 和 name 都匹配时才认为是同一个 actor
        if fname in fname_to_actor:
            candidate = fname_to_actor[fname]
            if candidate.get_actor_label() == name:
                actor = candidate
        if actor:
            # 检查transform是否一致
            if not is_transform_close(actor, location, rotation, scale):
                new_transform = unreal.Transform(
                    unreal.Vector(location.get("x", 0), location.get("y", 0), location.get("z", 0)),
                    unreal.Rotator(rotation.get("x", 0), rotation.get("y", 0), rotation.get("z", 0)),
                    unreal.Vector(scale.get("x", 1), scale.get("y", 1), scale.get("z", 1))
                )
                actor.set_actor_transform(new_transform, sweep=False, teleport=True)
                unreal.log(f"已更新Actor: {name} 的Transform")
    # unreal.EditorLevelLibrary.editor_screen_refresh()
    unreal.log("关卡数据导入完成。")
    return


def ubio_export_selected_static_mesh_to_blender():
    try:
        log_static_mesh_info("ubio_export_selected_static_mesh_to_blender started")
        selection = get_selected_static_mesh_source()
        actor = selection["actor"]
        static_mesh = selection["static_mesh"]
        selection_source = selection["selection_source"]
        session_suffix = make_safe_name(static_mesh.get_name())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{timestamp}_{session_suffix}"
        session_dir = ensure_directory(os.path.join(STATIC_MESH_SESSION_DIR, session_id))
        source_fbx_path = get_static_mesh_source_fbx_path(session_dir)
        session_file_path = get_session_file_path(session_dir)

        log_static_mesh_info(
            f"Session prepared: source={selection_source} session_id={session_id} session_dir={session_dir}"
        )
        session_data = build_static_mesh_session_data(
            actor,
            static_mesh,
            session_id,
            session_dir,
            selection_source,
        )
        export_static_mesh_asset_to_fbx(static_mesh, source_fbx_path)
        save_static_mesh_session(session_file_path, session_data)

        log_static_mesh_info(f"StaticMesh session exported successfully: {session_file_path}")
        return session_file_path
    except Exception as exc:
        log_static_mesh_error(f"Export to Blender failed: {exc}")
        log_static_mesh_error(traceback.format_exc())
        return None


def ubio_reimport_static_mesh_from_blender(session_file_path=""):
    session_file = session_file_path or ""
    try:
        session_file = session_file_path or find_latest_static_mesh_session_file()
        if not session_file or not os.path.isfile(session_file):
            raise RuntimeError("static_mesh_session_not_found")

        session_data = load_static_mesh_session(session_file)
        if session_data.get("session_type") != STATIC_MESH_SESSION_TYPE:
            raise RuntimeError("invalid_static_mesh_session")

        edited_fbx_path = session_data.get("paths", {}).get("edited_fbx", "")
        if not edited_fbx_path or not os.path.isfile(edited_fbx_path):
            raise RuntimeError(f"edited_fbx_missing: {edited_fbx_path}")

        asset_path = session_data.get("source_asset", {}).get("asset_path", "")
        if not asset_path:
            raise RuntimeError("missing_source_asset_path")

        source_asset = unreal.load_asset(asset_path)
        if source_asset is None:
            raise RuntimeError(f"source_asset_not_found: {asset_path}")

        reimport_static_mesh_from_fbx(asset_path, edited_fbx_path)
        update_static_mesh_session_status(
            session_data,
            STATIC_MESH_STATUS_REIMPORTED_IN_UE,
            "reimported_in_ue",
        )
        save_static_mesh_session(session_file, session_data)

        unreal.log(f"已重新导入 StaticMesh 资产: {asset_path}")
        return asset_path
    except Exception as exc:
        unreal.log_error(f"导入 Blender 返回的 StaticMesh 失败: {exc}")
        if session_file and os.path.isfile(session_file):
            try:
                failed_session = load_static_mesh_session(session_file)
                update_static_mesh_session_status(
                    failed_session,
                    STATIC_MESH_STATUS_FAILED,
                    "reimported_in_ue",
                )
                save_static_mesh_session(session_file, failed_session)
            except Exception:
                pass
        unreal.log_error(traceback.format_exc())
        return None


# 主执行部分

def ubio_export():
    json_path=export_current_level_json(DEFAULT_IO_TEMP_DIR)
    level_asset = get_level_asset(type="EDITOR")
    if level_asset:
        fbx_path=export_level_to_fbx(level_asset, DEFAULT_IO_TEMP_DIR)
    else:
        print("无法获取Level资产")

    #     print(f"导出名字不匹配，请检查")

def ubio_import():
    main_level=editor_subsys.get_editor_world()
    level_asset=get_level_asset(type="EDITOR")
    level_asset_path = level_asset.get_path_name()
    # print (f"当前关卡: {level_asset_path}")
    level_name_for_file = unreal.SystemLibrary.get_object_name(level_asset).replace(" ", "_")
    json_path=DEFAULT_IO_TEMP_DIR+"\\"+level_name_for_file+".json"
    print(f"从{json_path}导入")
    import_json(json_path) 
# ubio_import()


if __name__ == "__main__":
    ubio_export_selected_static_mesh_to_blender()

