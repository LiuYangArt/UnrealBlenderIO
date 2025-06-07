import bpy
import os
import json
import blf

from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import Vector, Euler
from math import radians

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
BL_FLAG= "Blender"
BL_NEW="NewActor"
BL_DEL="Removed"
PROXY_PIVOT = "UBIOProxyPivot"
PROXY_PIVOT_OBJ ="Pivot"


def make_collection(collection_name: str, type:str="") -> bpy.types.Collection:
    """建立指定名称的Collection，并可选设置自定义属性"""
    if collection_name not in bpy.data.collections:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)
        coll[UECOLL] = type
    else:
        coll = bpy.data.collections[collection_name]
    
    return coll


def move_objs_to_collection(objs, collection_name: str) -> None:
    """将指定对象移动到指定集合中"""
    coll = make_collection(collection_name)
    for obj in objs:
        # 先从所有已链接的collection移除
        for c in obj.users_collection:
            c.objects.unlink(obj)
        coll.objects.link(obj)


def get_name_from_ue_path(path: str) -> str:
    """从UE路径中提取名称"""

    name = path.split(".")[-1]
    return name


class UBIO_OT_ImportUnrealScene(bpy.types.Operator):
    bl_idname = "ubio.import_unreal_scene"
    bl_label = "Import Unreal Scene"
    bl_description = "Import FBX and JSON exported from Unreal Engine"
    bl_options = {"UNDO"}

    def execute(self, context):
        params = context.scene.ubio_params
        json_path = params.ubio_json_path
        # 检查是否为json文件

        with open(json_path, "r") as f:
            scene_data = json.load(f)

        # 构建FBX文件路径
        fbx_path = os.path.splitext(json_path)[0] + ".fbx"
        # 检查FBX文件是否存在
        if not os.path.exists(fbx_path):
            self.report({"ERROR"}, f"找不到对应的FBX文件: {fbx_path}")
            return {"CANCELLED"}

        # 从json获得 main_level 和 level_path 两个数据
        main_level = scene_data.get("main_level", None)
        level_path = scene_data.get("level_path", None)
        main_level_name = get_name_from_ue_path(main_level)
        if main_level == level_path:
            level_path_name = MAINLEVEL
        else:
            level_path_name=get_name_from_ue_path(level_path)
        

        # make collections
        ubio_coll = make_collection(UECOLL,type=COLL_ROOT)
        main_level_coll = make_collection(main_level_name,type=COLL_MAIN)
        level_path_coll = make_collection(level_path_name,type=COLL_LEVEL)

        ubio_coll.color_tag = UECOLL_COLOR


        # 设置从属关系: ubio_coll > main_level_coll > level_path_coll
        if main_level_coll.name not in [c.name for c in ubio_coll.children]:
            ubio_coll.children.link(main_level_coll)
        if level_path_coll.name not in [c.name for c in main_level_coll.children]:
            main_level_coll.children.link(level_path_coll)
        scene_coll = bpy.context.scene.collection
        for coll in [main_level_coll, level_path_coll]:
            if coll.name in [c.name for c in scene_coll.children]:
                scene_coll.children.unlink(bpy.data.collections[coll.name])

        existing_objs = set(bpy.data.objects)

        bpy.ops.import_scene.fbx(
            filepath=fbx_path,
            use_custom_normals=True,
            use_custom_props=False,
            use_image_search=False,
            use_anim=False,
            bake_space_transform=True,
        )

        # 导入后得到新对象
        ubio_objs = [obj for obj in bpy.data.objects if obj not in existing_objs]
        move_objs_to_collection(ubio_objs, level_path_coll.name)
        
        # 检查Blender单位设置
        if bpy.context.scene.unit_settings.length_unit != "CENTIMETERS":
            self.report({"WARNING"}, "Blender单位不是厘米，可能会导致比例不一致")
        vaild_actors = []
        # 处理每个actor
        level_instance_objs = []
        for obj in ubio_objs:
            if obj.type == "EMPTY" and "LevelInstanceEditorInstanceActor" in obj.name:
                level_instance_objs.append(obj)

        for actor in scene_data["actors"]:
            # print(f"处理 {actor['name']},type {actor['actor_type']}")
            obj = bpy.data.objects.get(actor["name"])
            if obj:
                # 设置自定义属性
                obj[GUID] = str(actor["fguid"])
                obj[FNAME] = actor["fname"]
                obj[ACTORTYPE] = actor["actor_type"]
                obj[ACTORCLASS] = actor["class"]

                is_coll_inst = False
                is_light = False
                # 如果 obj[ACTORTYPE] 属于 COLLINST_TYPES中的任意一种, convert_to_actor_instance(obj)
                if obj[ACTORTYPE] in COLLINST_TYPES:
                    is_coll_inst = True
                elif obj[ACTORTYPE] == "LevelInstance":
                    #find levelinstance obj
                    for inst in level_instance_objs:
                        if obj.location == inst.location:
                            inst.parent = obj
                            inst.location = (0, 0, 0)
                            inst.rotation_euler = (0, 0, 0)
                            inst.scale = (1, 1, 1)
                            is_coll_inst = True
                elif "Light" in obj[ACTORTYPE]:
                    is_light = True
                else:
                    continue

                if is_coll_inst:
                    if obj in ubio_objs:
                        ubio_objs.remove(obj)
                    actor_obj = convert_to_actor_instance(obj)
                    vaild_actors.append(actor_obj)
                elif is_light:
                    # vaild_actors.append(obj)
                    obj.hide_select = True

        
        for obj in ubio_objs:
            if obj.type == "EMPTY" and len(obj.children) == 0:
                obj.hide_viewport = True
                obj.hide_select = True

        self.report({"INFO"}, f"成功导入Unreal场景: {os.path.basename(json_path)}")
        return {"FINISHED"}

    def invoke(self, context, event):
        params = context.scene.ubio_params
        json_path = params.ubio_json_path

        # 检查json_path是否存在
        if not os.path.exists(json_path):
            self.report({"ERROR"}, f"找不到JSON文件: {json_path}")
            return {"CANCELLED"}
        if not json_path.lower().endswith(".json"):
            self.report({"ERROR"}, "请选择一个 .json 文件")
            return {"CANCELLED"}

        # 解析JSON文件
        with open(json_path, "r") as f:
            scene_data = json.load(f)

        # 获取main_level和level_path
        main_level = scene_data.get("main_level", None)
        level_path = scene_data.get("level_path", None)
        main_level_name = get_name_from_ue_path(main_level)
        if main_level == level_path:
            level_path_name = MAINLEVEL
        else:
            level_path_name = get_name_from_ue_path(level_path)

        # 检查UECOLL、main_level_coll、level_path_coll是否存在
        ubio_coll = bpy.data.collections.get(UECOLL)
        main_level_coll = bpy.data.collections.get(main_level_name)
        level_path_coll = bpy.data.collections.get(level_path_name)

        # 如果都存在，说明资源已导入，先清除
        if ubio_coll and main_level_coll and level_path_coll:
            # 先移除level_path_coll下的所有对象
            objs_to_remove = [obj for obj in level_path_coll.objects]
            for obj in objs_to_remove:
                bpy.data.objects.remove(obj, do_unlink=True)
            # 再移除collection的嵌套关系
            if level_path_coll.name in [c.name for c in main_level_coll.children]:
                main_level_coll.children.unlink(level_path_coll)
                
            if main_level_coll.name in [c.name for c in ubio_coll.children]:
                ubio_coll.children.unlink(main_level_coll)
            # 移除collection本身
            bpy.data.collections.remove(level_path_coll)
            bpy.data.collections.remove(main_level_coll)
            # 如果UECOLL没有其他子collection，也移除
            if not ubio_coll.children:
                bpy.data.collections.remove(ubio_coll)
            bpy.ops.outliner.orphans_purge(do_local_ids=True)

        return self.execute(context)


def get_all_children(obj):
    children = []
    for child in obj.children:
        children.append(child)
        children.extend(get_all_children(child))
    return children


def convert_to_actor_instance(actor_obj):
    """把ue fbx导入actor的empty集合转换成更适合在blender中使用的collection instance"""
    actor_name = actor_obj.name
    target_collection = actor_obj.users_collection[0]
    temp_scene = bpy.data.scenes.new(actor_name)
    # 检查是否存在 actor_type 属性
    actor_type = actor_obj.get(ACTORTYPE, None)
    actor_guid = actor_obj.get(GUID, None)
    actor_fname = actor_obj.get(FNAME, None)
    actor_class = actor_obj.get(ACTORCLASS, None)
    # actor object 判断
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

    # 从原scene中移出，添加到临时scene的新collection中
    for target_obj in target_objs:
        for c in target_obj.users_collection:
            c.objects.unlink(target_obj)
        if target_obj.type == "EMPTY":
            # 修改empty的显示，size=0.01
            target_obj.empty_display_size = 0.01

    scene_coll = temp_scene.collection
    new_coll = bpy.data.collections.new(actor_name)
    scene_coll.children.link(new_coll)
    for o in target_objs:
        new_coll.objects.link(o)
        # o.location = o.location

    # 删除原对象
    bpy.data.objects.remove(actor_obj)
    # 在场景中添加collection instance
    bpy.ops.object.collection_instance_add(
        collection=new_coll.name,
        location=target_location,
        rotation=target_rotation,
        scale=target_scale,
    )
    bpy.data.scenes.remove(temp_scene)
    # 写入自定义属性用于后续json导出
    new_actor_obj = bpy.data.objects[actor_name]
    new_actor_obj[GUID] = actor_guid
    new_actor_obj[FNAME] = actor_fname
    new_actor_obj[ACTORTYPE] = actor_type
    new_actor_obj[ACTORCLASS] = actor_class
    new_actor_obj.empty_display_size=0.1
    # 移动到原collection
    new_actor_obj.users_collection[0].objects.unlink(new_actor_obj)
    target_collection.objects.link(new_actor_obj)
    return new_actor_obj


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
        ubio_coll = bpy.data.collections.get(UECOLL)
        if not ubio_coll:
            self.report({"ERROR"}, f"找不到集合: {UECOLL}")
            return {"CANCELLED"}

        # 找到UECOLL的子collection（level_asset_coll），以及main_level
        level_asset_coll = None
        main_level_coll = None
        is_mainlevel = False
        sub_colls = get_all_children(ubio_coll)
        for coll in sub_colls:
            coll_type = coll.get(UECOLL, None)
            print(coll.name)
            print(coll_type)
            if coll_type == COLL_MAIN:
                main_level_coll = coll
            elif coll_type == COLL_LEVEL:
                level_asset_coll = coll
        if level_asset_coll.name == MAINLEVEL:
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
            fname = obj.get(FNAME, None)
            actortype = obj.get(ACTORTYPE, "")
            guid = str(obj.get(GUID, ""))
            if fname and actortype in ["StaticMesh", "Blueprint", "LevelInstance"]:
                key = (obj.name, str(obj.get(ACTORTYPE, "")), str(fname), guid)
                if key not in existing_actor_keys:
                    # 添加到json
                    loc = obj.location * 100
                    rot = obj.rotation_euler
                    rot_deg = [((r * 180.0 / 3.141592653589793) % 360) for r in rot]
                    scale = obj.scale
                    # 检查object name中的.，替换为_
                    safe_name = obj.name.replace('.', '_')
                    if obj.name != safe_name:
                        # 检查是否已存在同名对象，避免重名
                        if safe_name not in bpy.data.objects:
                            obj.name = safe_name
                        else:
                            # 若已存在，添加后缀避免冲突
                            idx = 1
                            new_name = f"{safe_name}_{idx}"
                            while new_name in bpy.data.objects:
                                idx += 1
                                new_name = f"{safe_name}_{idx}"
                            obj.name = new_name
                        safe_name = obj.name
                    print(safe_name, obj.name)
                    new_actor = {
                        "name": safe_name,
                        "actor_type": obj.get(ACTORTYPE, ""),
                        "fname": fname,
                        "fguid": guid,
                        "class": obj.get(ACTORCLASS, ""),
                        "transform": {
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
                        },
                        "Blender": "NewActor"
                    }
                    scene_data["actors"].append(new_actor)
        # 遍历json中的actors，检查其在Blender中是否存在
        for actor in scene_data.get("actors", []):
            actor_name = actor.get("name")
            actor_type = actor.get("actor_type")
            actor_fname = actor.get("fname")
            actor_guid = str(actor.get("fguid"))

            # 检查Blender中是否有对应对象
            found = False
            for obj in level_actor_objs:
                if (
                    obj.name == actor_name
                    and str(obj.get(ACTORTYPE, "")) == actor_type
                    and str(obj.get(FNAME, "")) == actor_fname
                    and str(obj.get(GUID, "")) == actor_guid
                ):
                    # 匹配成功，更新json中的transform为Blender中的transform
                    found = True
                    # print(f"匹配到对象：{obj.name}")
                    loc = obj.location * 100
                    rot = obj.rotation_euler
                    # Blender和UE坐标系：Y轴取反
                    # 角度转换
                    rot_deg = [((r * 180.0 / 3.141592653589793) % 360) for r in rot]
                    scale = obj.scale

                    # 写入到json的transform字段
                    actor["transform"] = {
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

                    break
            # 如果没有找到，标记为Blender:Removed
            if not found:
                # 添加Blender:Removed字段，值为"Removed"
                actor["Blender"] = "Removed"  # 中文注释：标记此actor在Blender中不存在

        # 保存修改后的json
        with open(json_path, "w") as f:
            json.dump(scene_data, f, indent=4)

        self.report({"INFO"}, "已同步Blender对象变换到JSON文件")
        return {"FINISHED"}


class CleanUBIOTempFilesOperator(bpy.types.Operator):
    bl_idname = "ubio.ubio_tempfiles"
    bl_label = "CleanUBIOTempFiles"
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


def find_level_asset_coll():
    ubio_coll = bpy.data.collections.get(UECOLL)
    sub_colls = get_all_children(ubio_coll)
    for coll in sub_colls:
        coll_type = coll.get(UECOLL, None)
        if coll_type == COLL_LEVEL:
            return coll
    return None

class UBIOAddProxyPivotOperator(bpy.types.Operator):
    bl_idname = "ubio.add_proxy_pivot"
    bl_label = "Set Proxy Pivot"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "为选中的对象添加Proxy Pivot"
    def execute(self, context):
        # 1. 获取level asset collection
        ubio_coll = bpy.data.collections.get(UECOLL)
        level_asset_coll = None
        if ubio_coll:
            level_asset_coll = find_level_asset_coll()
        if not level_asset_coll:
            self.report({"ERROR"}, "未找到Level Asset Collection")
            return {"CANCELLED"}
        active_obj = context.active_object
        # 2. 检查是否已存在proxy pivot（name=Pivot, type=EMPTY）
        has_pivot = False
        bpy.ops.object.select_all(action='DESELECT')
        for obj in level_asset_coll.objects:
            if obj.type == 'EMPTY' and obj.name == PROXY_PIVOT_OBJ:
                has_pivot = True
                break
        if has_pivot:
            pivot = obj
            pivot.hide_viewport = False
            pivot.hide_select = False

        else:
            pivot = bpy.data.objects.new(PROXY_PIVOT_OBJ, None)
            if active_obj:
                pivot.location = active_obj.location
            else:
                pivot.location = (0, 0, 0)
            level_asset_coll.objects.link(pivot)

        pivot.empty_display_type = 'ARROWS'
        pivot.empty_display_size = 0.2
        pivot.show_name = True
        pivot.show_in_front = True
        pivot["CAT"] = PROXY_PIVOT  # 标记自定义属性
        pivot.select_set(True)
        self.report({"INFO"}, "已添加Proxy Pivot到Level Asset Collection")
        return {"FINISHED"}

class UBIOMirrorCopyActorsOperator(bpy.types.Operator):
    bl_idname = "ubio.mirror_copy_actors"
    bl_label = "Mirror Copy Actors"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "镜像复制选中的对象，以Proxy Pivot为轴"

    mirror_axis: bpy.props.EnumProperty(
        name="Mirror Axis",
        items=[
            ("X", "X", "X"),
            ("Y", "Y", "Y"),
            ("Z", "Z", "Z"),
        ],
        default="X"
    )

    def invoke(self, context, event):
        self.selected_objs = [obj for obj in context.selected_objects if FNAME in obj]
        if not self.selected_objs:
            self.report({'WARNING'}, '未选中任何actor对象（缺少ue_fname属性）')
            return {'CANCELLED'}
        ubio_coll = bpy.data.collections.get(UECOLL)
        self.level_asset_coll = None
        if ubio_coll:
            self.level_asset_coll = find_level_asset_coll()
        if not self.level_asset_coll:
            self.report({'ERROR'}, '未找到Level Asset Collection')
            return {'CANCELLED'}
        self.proxy_pivot = None
        for obj in self.level_asset_coll.objects:
            if obj.type == 'EMPTY' and obj.name == PROXY_PIVOT_OBJ:
                self.proxy_pivot = obj
                break
        if not self.proxy_pivot:
            self.report({'ERROR'}, '未找到Proxy Pivot（Pivot）')
            return {'CANCELLED'}
        self._axis = 'X'  # 默认X轴
        self.mirrored_objs = []
        self._do_mirror(context, self._axis)
        # 注册draw handler
        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_callback, (context,), 'WINDOW', 'POST_PIXEL'
        )
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "按 X 切换轴，空格/Enter/右键确认，ESC撤销")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """ 按键输入切换轴向及确认取消 """
        # 鼠标和修饰键透传，允许正常操作视角和选择
        if (
            event.type in {'LEFTMOUSE', 'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
            or event.ctrl or event.alt or event.shift
        ):
            return {'PASS_THROUGH'}
        if event.type == 'X' and event.value == 'PRESS':
            # 循环切换 X->Y->Z->X
            axis_order = ['X', 'Y', 'Z']
            current_idx = axis_order.index(self._axis)
            next_idx = (current_idx + 1) % 3
            self._axis = axis_order[next_idx]
            self._remove_mirrored(context)
            self._do_mirror(context, self._axis)
            self.report({'INFO'}, f"当前镜像轴: {self._axis}")
            return {'RUNNING_MODAL'}
        elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._remove_draw_handle()
            # 选中并激活新对象，强制刷新视图
            if self.mirrored_objs:
                for o in self.mirrored_objs:
                    o.select_set(True)
                context.view_layer.objects.active = self.mirrored_objs[0]
            context.view_layer.update()
            import bpy
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
            self.mirrored_objs = []  # 清空引用，防止后续误删
            self.report({'INFO'}, f"完成{self._axis}轴镜像复制")
            return {'FINISHED'}
        elif event.type == 'ESC':
            self._remove_draw_handle()
            self._remove_mirrored(context)
            self.report({'INFO'}, "已撤销镜像")
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _draw_callback(self, context): 
        """ 左下角提示信息 """
        font_id = 0
        blf.size(font_id, 18)
        blf.color(font_id, 0.8, 0.8, 0.8, 0.8)
        blf.position(font_id, 60, 80, 0)
        blf.draw(font_id, "按下 X 切换镜像轴")
        blf.position(font_id, 60, 60, 0)
        blf.draw(font_id, "空格 / Enter / 右键 确认")
        blf.position(font_id, 60, 40, 0)
        blf.draw(font_id, "ESC 取消")

    def _remove_draw_handle(self):
        """ 清理UI绘制 """
        if hasattr(self, '_draw_handle') and self._draw_handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self._draw_handle = None

    def _do_mirror(self, context, axis):
        """ 核心复制部分 """
        mirror_vec = [1, 1, 1]
        if axis == 'X':
            mirror_vec[0] = -1
        elif axis == 'Y':
            mirror_vec[1] = -1
        elif axis == 'Z':
            mirror_vec[2] = -1
        else:
            self.report({'ERROR'}, f'未知镜像轴: {axis}')
            return
        self.mirrored_objs = []
        for obj in self.selected_objs:
            rel_loc = obj.location - self.proxy_pivot.location
            mirrored_loc = self.proxy_pivot.location + Vector((
                rel_loc.x * mirror_vec[0],
                rel_loc.y * mirror_vec[1],
                rel_loc.z * mirror_vec[2],
            ))
            new_obj = obj.copy()
            if obj.data:
                new_obj.data = obj.data.copy()
            new_obj.location = mirrored_loc
            new_rot = list(obj.rotation_euler)
            if axis == 'X':
                new_rot[1] = -new_rot[1]
                new_rot[2] = -new_rot[2]
            elif axis == 'Y':
                new_rot[0] = -new_rot[0]
                new_rot[2] = -new_rot[2]
            elif axis == 'Z':
                new_rot[0] = -new_rot[0]
                new_rot[1] = -new_rot[1]
            new_obj.rotation_euler = new_rot
            new_obj.scale = Vector((
                obj.scale.x * mirror_vec[0],
                obj.scale.y * mirror_vec[1],
                obj.scale.z * mirror_vec[2],
            ))
            for key in obj.keys():
                if key not in {'_RNA_UI'}:
                    value = obj[key]
                    if isinstance(value, (str, int, float, bool)):
                        new_obj[key] = value
            self.level_asset_coll.objects.link(new_obj)
            self.mirrored_objs.append(new_obj)
        # bpy.ops.object.select_all(action='DESELECT')
        for o in self.mirrored_objs:
            o.select_set(True)
        for obj in self.selected_objs:
            o.select_set(True)

    def _remove_mirrored(self, context):
        """ 撤销清理数据 """
        for obj in self.mirrored_objs:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        self.mirrored_objs.clear()














