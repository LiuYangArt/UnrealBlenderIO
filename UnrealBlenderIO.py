import bpy
import os
import random
import json
from mathutils import Color
# import blf
# from mathutils import Vector
# from math import radians
from .util import (
    get_all_children,
    # find_level_asset_coll,
    set_proxy_pivot_properties,
    get_transform_from_obj,
    # set_actor_transform,
    # is_obj_transform_equal,
    Const
)
# from .Toolsl import UBIOAddProxyPivotOperator, UBIOMirrorCopyActorsOperator



# =====================
# 工具函数
# =====================

def make_collection(collection_name: str, type: str = "") -> bpy.types.Collection:
    """
    创建指定名称的Collection，并可选设置自定义属性
    参数：
        collection_name (str): 集合名称
        type (str): 可选，自定义类型标记
    返回：
        bpy.types.Collection: 新建或已存在的集合对象
    """
    if collection_name not in bpy.data.collections:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)
        coll[Const.UECOLL] = type
    else:
        coll = bpy.data.collections[collection_name]
    return coll


def move_objs_to_collection(objs, collection_name: str) -> None:
    """
    将指定对象移动到指定集合中
    参数：
        objs (list[bpy.types.Object]): 需要移动的对象列表
        collection_name (str): 目标集合名称
    返回：
        无
    """
    coll = make_collection(collection_name)
    for obj in objs:
        for c in obj.users_collection:
            c.objects.unlink(obj)
        coll.objects.link(obj)


def get_name_from_ue_path(path: str) -> str:
    """
    从UE路径中提取名称
    参数：
        path (str): UE资源路径
    返回：
        str: 路径中的名称部分
    """
    return path.split(".")[-1]


def convert_to_actor_instance(actor_obj):
    """
    把UE FBX导入actor的empty集合转换成更适合在Blender中使用的collection instance
    参数：
        actor_obj (bpy.types.Object): 需要转换的actor对象
    返回：
        bpy.types.Object: 新的collection instance对象
    """
    actor_name = actor_obj.name
    target_collection = actor_obj.users_collection[0]
    temp_scene = bpy.data.scenes.new(actor_name)
    actor_type = actor_obj.get(Const.ACTORTYPE, None)
    actor_guid = actor_obj.get(Const.GUID, None)
    actor_fname = actor_obj.get(Const.FNAME, None)
    actor_class = actor_obj.get(Const.ACTORCLASS, None)
    if actor_obj.type == "EMPTY":
        if actor_obj.instance_collection is not None:
            return None
        if actor_type is None:
            return None
        target_location = actor_obj.location.copy()
        target_rotation = actor_obj.rotation_euler.copy()
        target_scale = actor_obj.scale.copy()
        target_objs = get_all_children(actor_obj)
    else:
        return None
    for target_obj in target_objs:
        for c in target_obj.users_collection:
            c.objects.unlink(target_obj)
        if target_obj.type == "EMPTY":
            target_obj.empty_display_size = 0.01
    scene_coll = temp_scene.collection
    new_coll = bpy.data.collections.new(actor_name)
    scene_coll.children.link(new_coll)
    for o in target_objs:
        new_coll.objects.link(o)
    bpy.data.objects.remove(actor_obj)
    bpy.ops.object.collection_instance_add(
        collection=new_coll.name,
        location=target_location,
        rotation=target_rotation,
        scale=target_scale,
    )
    bpy.data.scenes.remove(temp_scene)
    new_actor_obj = bpy.data.objects[actor_name]
    new_actor_obj[Const.GUID] = actor_guid
    new_actor_obj[Const.FNAME] = actor_fname
    new_actor_obj[Const.ACTORTYPE] = actor_type
    new_actor_obj[Const.ACTORCLASS] = actor_class
    new_actor_obj.empty_display_size = 0.1
    new_actor_obj.users_collection[0].objects.unlink(new_actor_obj)
    target_collection.objects.link(new_actor_obj)
    return new_actor_obj

# =====================
# 新增工具函数（集合与Actor相关）
# =====================

def get_or_create_main_collections(scene_data: dict):
    """
    根据scene_data获取或创建主集合、main_level集合、level_asset集合
    参数：
        scene_data (dict): UE导出json解析后的数据
    返回：
        (ubio_coll, main_level_coll, level_asset_coll): 三个集合对象
    """
    main_level = scene_data.get("main_level", None)
    level_path = scene_data.get("level_path", None)
    main_level_name = get_name_from_ue_path(main_level)
    level_path_name = Const.MAINLEVEL if main_level == level_path else get_name_from_ue_path(level_path)
    ubio_coll = make_collection(Const.UECOLL, type=Const.COLL_ROOT)
    main_level_coll = make_collection(main_level_name, type=Const.COLL_MAIN)
    level_asset_coll = make_collection(level_path_name, type=Const.COLL_LEVEL)
    return ubio_coll, main_level_coll, level_asset_coll


def setup_collection_hierarchy(ubio_coll: bpy.types.Collection, main_level_coll: bpy.types.Collection, level_asset_coll: bpy.types.Collection) -> None:
    """
    设置集合的父子层级关系
    参数：
        ubio_coll (bpy.types.Collection): 根集合
        main_level_coll (bpy.types.Collection): 主关卡集合
        level_asset_coll (bpy.types.Collection): 资源集合
    返回：
        无
    """
    if main_level_coll.name not in [c.name for c in ubio_coll.children]:
        ubio_coll.children.link(main_level_coll)
    if level_asset_coll.name not in [c.name for c in main_level_coll.children]:
        main_level_coll.children.link(level_asset_coll)
    scene_coll = bpy.context.scene.collection
    for coll in [main_level_coll, level_asset_coll]:
        if coll.name in [c.name for c in scene_coll.children]:
            scene_coll.children.unlink(bpy.data.collections[coll.name])


def set_actor_custom_props(obj: bpy.types.Object, actor_dict: dict) -> None:
    """
    设置actor的自定义属性
    参数：
        obj (bpy.types.Object): 目标对象
        actor_dict (dict): UE actor信息字典
    返回：
        无
    """
    obj[Const.GUID] = str(actor_dict["fguid"])
    obj[Const.FNAME] = actor_dict["fname"]
    obj[Const.ACTORTYPE] = actor_dict["actor_type"]
    obj[Const.ACTORCLASS] = actor_dict["class"]


def clear_collection_and_children(coll: bpy.types.Collection) -> None:
    """
    清空集合下所有对象和子集合，并移除集合本身
    参数：
        coll (bpy.types.Collection): 需要清理的集合
    返回：
        无
    """
    objs_to_remove = [obj for obj in coll.objects]
    for obj in objs_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)
    for child in list(coll.children):
        clear_collection_and_children(child)
    bpy.data.collections.remove(coll)


def clear_imported_scene(ubio_coll: bpy.types.Collection, main_level_coll: bpy.types.Collection, level_path_coll: bpy.types.Collection) -> None:
    """
    清理已导入的资源集合及其对象
    参数：
        ubio_coll (bpy.types.Collection): 根集合
        main_level_coll (bpy.types.Collection): 主关卡集合
        level_path_coll (bpy.types.Collection): 资源集合
    返回：
        无
    """
    objs_to_remove = [obj for obj in level_path_coll.objects]
    for obj in objs_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)
    if level_path_coll.name in [c.name for c in main_level_coll.children]:
        main_level_coll.children.unlink(level_path_coll)
    if main_level_coll.name in [c.name for c in ubio_coll.children]:
        ubio_coll.children.unlink(main_level_coll)
    bpy.data.collections.remove(level_path_coll)
    bpy.data.collections.remove(main_level_coll)
    if not ubio_coll.children:
        bpy.data.collections.remove(ubio_coll)
    bpy.ops.outliner.orphans_purge(do_local_ids=True)
    
def find_gpro_objs(objs):
    """
    在给定对象列表中查找具有"GPro_Instance"几何节点修改器的对象，
    并返回这些修改器中"Instanced Collection"输入所引用的集合中的所有对象。
    参数：
        objs (list[bpy.types.Object]): 需要检查的对象列表
    返回：
        list[bpy.types.Object]: 从Geometry Nodes修改器中"Instanced Collection"获取的所有对象
    """
    gpro_instances = []
    for obj in objs:
        if obj.modifiers:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.node_group:
                    if mod.node_group.name == "GPro_Instance" or mod.node_group.name == "CAT_MeshGroup":
                        # 查找名为 "Instanced Collection" 的输入
                        for input_socket in mod.node_group.inputs:
                            if input_socket.name == "Instanced Collection" and input_socket.type == 'COLLECTION':
                                # 获取引用的集合
                                if input_socket.default_value:
                                    collection = input_socket.default_value
                                    gpro_instances.extend(collection.all_objects)
    return gpro_instances

def gen_random_color():
    h = random.random()  # 色相
    s = random.uniform(0.2, 0.7)  # 饱和度范围
    v = random.uniform(0.5, 1.0)  # 亮度范围
    
    temp_color = Color()
    temp_color.hsv = (h, s, v)
    color = (temp_color.r, temp_color.g, temp_color.b, 1.0)
    return color

def set_random_color_by_class(target_objs):
    class_objects = {}
    for obj in target_objs:
        if Const.ACTORCLASS in obj:
            actor_class = obj[Const.ACTORCLASS]
            if actor_class not in class_objects:
                class_objects[actor_class] = []
            class_objects[actor_class].append(obj)

    # 为每个Class生成一个随机颜色，并设置对象颜色
    
    assigned_colors = set()

    for actor_class, objects in class_objects.items():
        # 生成一个独特的随机颜色
        color = gen_random_color()
        # 确保颜色在一定程度上是独特的，避免过于相近的颜色
        while color in assigned_colors:
            color = gen_random_color()
        
        assigned_colors.add(color)

        for obj in objects:
            obj.color=color
    
    #Set View Mode
    bpy.context.space_data.shading.color_type = 'OBJECT'
    bpy.context.space_data.shading.type = 'SOLID'
    bpy.context.space_data.shading.light = 'MATCAP'
    



# =====================
# 主要操作类
# =====================

class UBIO_OT_ImportUnrealScene(bpy.types.Operator):
    bl_idname = "ubio.import_unreal_scene"
    bl_label = "Import Unreal Scene"
    bl_description = "Import FBX and JSON exported from Unreal Engine"
    bl_options = {"UNDO"}

    def execute(self, context):
        params = context.scene.ubio_params
        json_path = params.ubio_json_path
        with open(json_path, "r") as f:
            json_scene_data = json.load(f)
        fbx_path = os.path.splitext(json_path)[0] + ".fbx"
        if not os.path.exists(fbx_path):
            self.report({"ERROR"}, f"找不到对应的FBX文件: {fbx_path}")
            return {"CANCELLED"}
        # 使用新函数
        ubio_coll, main_level_coll, level_asset_coll = get_or_create_main_collections(json_scene_data)
        ubio_coll.color_tag = Const.UECOLL_COLOR
        setup_collection_hierarchy(ubio_coll, main_level_coll, level_asset_coll)
        existing_objs = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(
            filepath=fbx_path,
            use_custom_normals=True,
            use_custom_props=False,
            use_image_search=False,
            use_anim=False,
            bake_space_transform=True,
        )
        ubio_objs = [obj for obj in bpy.data.objects if obj not in existing_objs]
        move_objs_to_collection(ubio_objs, level_asset_coll.name)
        if bpy.context.scene.unit_settings.length_unit != "CENTIMETERS":
            self.report({"WARNING"}, "Blender单位不是厘米，可能会导致比例不一致")
        vaild_actors = []
        level_instance_objs = [obj for obj in ubio_objs if obj.type == "EMPTY" and "LevelInstanceEditorInstanceActor" in obj.name]
        for actor in json_scene_data["actors"]:
            obj = bpy.data.objects.get(actor["name"])
            if obj:
                set_actor_custom_props(obj, actor)
                is_coll_inst = False
                is_light = False
                if obj[Const.ACTORTYPE] in Const.COLLINST_TYPES:
                    is_coll_inst = True
                elif obj[Const.ACTORTYPE] == "LevelInstance":
                    for inst in level_instance_objs:
                        if obj.location == inst.location:
                            inst.parent = obj
                            inst.location = (0, 0, 0)
                            inst.rotation_euler = (0, 0, 0)
                            inst.scale = (1, 1, 1)
                            is_coll_inst = True
                elif "Light" in obj[Const.ACTORTYPE]:
                    is_light = True
                else:
                    continue
                if is_coll_inst:
                    if obj in ubio_objs:
                        ubio_objs.remove(obj)
                    actor_obj = convert_to_actor_instance(obj)
                    vaild_actors.append(actor_obj)
                elif is_light:
                    obj.hide_select = True
        for obj in ubio_objs:
            if obj.type == "EMPTY" and len(obj.children) == 0:
                obj.hide_viewport = True
                obj.hide_select = True
        # 检查并设置Proxy Pivot属性
        for obj in level_asset_coll.objects:
            if obj.type == 'EMPTY' and obj.name == Const.PROXY_PIVOT_OBJ:
                set_proxy_pivot_properties(obj)

        set_random_color_by_class(level_asset_coll.objects)


        self.report({"INFO"}, f"成功导入Unreal场景: {os.path.basename(json_path)}")
        return {"FINISHED"}

    def invoke(self, context, event):
        params = context.scene.ubio_params
        json_path = params.ubio_json_path
        if not os.path.exists(json_path):
            self.report({"ERROR"}, f"找不到JSON文件: {json_path}")
            return {"CANCELLED"}
        if not json_path.lower().endswith(".json"):
            self.report({"ERROR"}, "请选择一个 .json 文件")
            return {"CANCELLED"}
        with open(json_path, "r") as f:
            scene_data = json.load(f)
        main_level = scene_data.get("main_level", None)
        level_path = scene_data.get("level_path", None)
        main_level_name = get_name_from_ue_path(main_level)
        if main_level == level_path:
            level_path_name = Const.MAINLEVEL
        else:
            level_path_name = get_name_from_ue_path(level_path)
        ubio_coll = bpy.data.collections.get(Const.UECOLL)
        main_level_coll = bpy.data.collections.get(main_level_name)
        level_path_coll = bpy.data.collections.get(level_path_name)
        if ubio_coll and main_level_coll and level_path_coll:
            clear_imported_scene(ubio_coll, main_level_coll, level_path_coll)
        return self.execute(context)



class UBIO_OT_ExportUnrealJSON(bpy.types.Operator):
    bl_idname = "ubio.export_unreal_scene_json"
    bl_label = "Export Unreal Scene JSON"
    bl_description = "Export Unreal Scene JSON"
    bl_options = {"UNDO"}

    def execute(self, context):
        params = context.scene.ubio_params
        json_path = params.ubio_json_path

        # 检查json文件是否存在
        if not os.path.exists(json_path):
            self.report({"ERROR"}, f"找不到JSON文件: {json_path}")
            return {"CANCELLED"}
        
        # 解析JSON文件
        with open(json_path, "r") as f:
            scene_data = json.load(f)

        # 找到UECOLL下的collection
        ubio_coll = bpy.data.collections.get(Const.UECOLL)
        if not ubio_coll:
            self.report({"ERROR"}, f"找不到集合: {Const.UECOLL}")
            return {"CANCELLED"}

        # 找到UECOLL的子collection（level_asset_coll），以及main_level
        level_asset_coll = None
        main_level_coll = None
        is_mainlevel = False
        sub_colls = get_all_children(ubio_coll)
        for coll in sub_colls:
            coll_type = coll.get(Const.UECOLL, None)
            print(coll.name)
            print(coll_type)
            if coll_type == Const.COLL_MAIN:
                main_level_coll = coll
            elif coll_type == Const.COLL_LEVEL:
                level_asset_coll = coll
        if level_asset_coll.name == Const.MAINLEVEL:
            is_mainlevel = True
            print(f"{main_level_coll.name} is mainlevel")

        # 获取json中的main_level和level_path
        main_level_path = scene_data.get("main_level", None)
        level_path = scene_data.get("level_path", None)
        main_level_name = get_name_from_ue_path(main_level_path)
        level_name = get_name_from_ue_path(level_path)
        is_match_json = False
        if main_level_coll.name==main_level_name:
            if is_mainlevel:
                is_match_json = True
            else:
                if level_asset_coll.name==level_name:
                    is_match_json = True
        if not is_match_json:
            self.report({'WARNING'}, "当前场景与ubio JSON不匹配")
            return {"CANCELLED"}

        # 获取level_asset_coll下的所有对象
        if level_asset_coll is None:
            self.report({'ERROR'}, "未找到Level Asset Collection")
            return {"CANCELLED"}
        level_actor_objs = [obj for obj in level_asset_coll.all_objects]
        # 找出所有有 fname 的 object，且在 json 中没有对应的
        existing_actor_keys = set(
            (str(a.get("name")), str(a.get("actor_type")), str(a.get("fname")), str(a.get("fguid")))
            for a in scene_data.get("actors", [])
        )
        for obj in level_actor_objs:
            fname = obj.get(Const.FNAME, None)
            actortype = obj.get(Const.ACTORTYPE, "")
            guid = str(obj.get(Const.GUID, ""))
            if fname and actortype in ["StaticMesh", "Blueprint", "LevelInstance"]:
                key = (obj.name, str(obj.get(Const.ACTORTYPE, "")), str(fname), guid)
                if key not in existing_actor_keys:
                    # 添加到json
                    safe_name = obj.name.replace('.', '_')
                    if obj.name != safe_name:
                        if safe_name not in bpy.data.objects:
                            obj.name = safe_name
                        else:
                            idx = 1
                            new_name = f"{safe_name}_{idx}"
                            while new_name in bpy.data.objects:
                                idx += 1
                                new_name = f"{safe_name}_{idx}"
                            obj.name = new_name
                        safe_name = obj.name
                    new_actor = {
                        "name": safe_name,
                        "actor_type": obj.get(Const.ACTORTYPE, ""),
                        "fname": fname,
                        "fguid": guid,
                        "class": obj.get(Const.ACTORCLASS, ""),
                        "transform": get_transform_from_obj(obj),
                        "Blender": "NewActor"
                    }
                    scene_data["actors"].append(new_actor)
        # 遍历json中的actors，检查其在Blender中是否存在
        for actor in scene_data.get("actors", []):
            actor_name = actor.get("name")
            actor_type = actor.get("actor_type")
            actor_fname = actor.get("fname")
            actor_guid = str(actor.get("fguid"))
            found = False
            for obj in level_actor_objs:
                if (
                    obj.name == actor_name
                    and str(obj.get(Const.ACTORTYPE, "")) == actor_type
                    and str(obj.get(Const.FNAME, "")) == actor_fname
                    and str(obj.get(Const.GUID, "")) == actor_guid
                ):
                    found = True
                    actor["transform"] = get_transform_from_obj(obj)
                    break
            if not found:
                actor["Blender"] = "Removed"  # 标记此actor在Blender中不存在

        # 保存修改后的json
        with open(json_path, "w") as f:
            json.dump(scene_data, f, indent=4)

        self.report({"INFO"}, "已同步Blender对象变换到JSON文件")
        return {"FINISHED"}


class CleanUBIOTempFilesOperator(bpy.types.Operator):
    bl_idname = "ubio.clean_tempfiles"
    bl_label = "Clean UBIO Temp-Files"
    bl_description = "Clean UBIO Temp Files"

    def execute(self, context):
        params = context.scene.ubio_params
        json_path = params.ubio_json_path
        dir_path = os.path.dirname(json_path)
        for file in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        self.report({"INFO"}, f"已清理UBIO临时文件: {dir_path}") 
        
        return {"FINISHED"}














