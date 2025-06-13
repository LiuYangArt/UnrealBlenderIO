import bpy
import blf
from mathutils import Vector
from bpy.props import EnumProperty
from .util import (Const,find_level_asset_coll, set_proxy_pivot_properties, get_transform_from_obj, set_actor_transform
)

class UBIOAddProxyPivotOperator(bpy.types.Operator):
    bl_idname = "ubio.add_proxy_pivot"
    bl_label = "Set Proxy Pivot"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "为选中的对象添加Proxy Pivot"
    def execute(self, context):
        ubio_coll = bpy.data.collections.get(Const.UECOLL)
        level_asset_coll = None
        if ubio_coll:
            level_asset_coll = find_level_asset_coll(Const.UECOLL, 'Level')
        if not level_asset_coll:
            self.report({"ERROR"}, "未找到Level Asset Collection")
            return {"CANCELLED"}
        active_obj = context.active_object
        has_pivot = False
        bpy.ops.object.select_all(action='DESELECT')
        for obj in level_asset_coll.objects:
            if obj.type == 'EMPTY' and obj.name == Const.PROXY_PIVOT_OBJ:
                has_pivot = True
                break
        if has_pivot:
            pivot = obj
            set_proxy_pivot_properties(pivot)
        else:
            pivot = bpy.data.objects.new(Const.PROXY_PIVOT_OBJ, None)
            if active_obj:
                pivot.location = active_obj.location
            else:
                pivot.location = (0, 0, 0)
            level_asset_coll.objects.link(pivot)
            set_proxy_pivot_properties(pivot)
        pivot.select_set(True)
        self.report({"INFO"}, "已添加Proxy Pivot到Level Asset Collection")
        return {"FINISHED"}

class UBIOMirrorCopyActorsOperator(bpy.types.Operator):
    bl_idname = "ubio.mirror_copy_actors"
    bl_label = "Mirror Copy Actors"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "镜像复制选中的对象，以Proxy Pivot为轴"

    mirror_axis: EnumProperty(
        name="Mirror Axis",
        items=[
            ("X", "X", "X"),
            ("Y", "Y", "Y"),
            ("Z", "Z", "Z"),
        ],
        default="X"
    )

    def invoke(self, context, event):
        self.selected_objs = [obj for obj in context.selected_objects if Const.FNAME in obj]
        if not self.selected_objs:
            self.report({'WARNING'}, '未选中任何actor对象（缺少ue_fname属性）')
            return {'CANCELLED'}
        ubio_coll = bpy.data.collections.get(Const.UECOLL)
        self.level_asset_coll = None
        if ubio_coll:
            self.level_asset_coll = find_level_asset_coll(Const.UECOLL, 'Level')
        if not self.level_asset_coll:
            self.report({'ERROR'}, '未找到Level Asset Collection')
            return {'CANCELLED'}
        self.proxy_pivot = None
        for obj in self.level_asset_coll.objects:
            if obj.type == 'EMPTY' and obj.name == Const.PROXY_PIVOT_OBJ:
                self.proxy_pivot = obj
                break
        if not self.proxy_pivot:
            self.report({'ERROR'}, '未找到Proxy Pivot（Pivot）')
            return {'CANCELLED'}
        self._axis = 'X'  # 默认X轴
        self.mirrored_objs = []
        self._do_mirror(context, self._axis)
        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_callback, (context,), 'WINDOW', 'POST_PIXEL'
        )
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "连续按 X 或Shift+鼠标滚轮切换镜像轴")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if (
            event.type in {'LEFTMOUSE', 'MIDDLEMOUSE'}
            or event.ctrl or event.alt
            or (event.shift and event.type not in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'})
        ):
            return {'PASS_THROUGH'}
        elif event.type == 'X' and event.value == 'PRESS':
            axis_order = ['X', 'Y', 'Z']
            current_idx = axis_order.index(self._axis)
            next_idx = (current_idx + 1) % 3
            self._axis = axis_order[next_idx]
            self._remove_mirrored(context)
            self._do_mirror(context, self._axis)
            self.report({'INFO'}, f"当前镜像轴: {self._axis}")
            return {'RUNNING_MODAL'}
        elif event.shift and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            axis_order = ['X', 'Y', 'Z']
            current_idx = axis_order.index(self._axis)
            if event.type == 'WHEELUPMOUSE':
                next_idx = (current_idx + 1) % 3
            else:
                next_idx = (current_idx - 1 + 3) % 3
            self._axis = axis_order[next_idx]
            self._remove_mirrored(context)
            self._do_mirror(context, self._axis)
            self.report({'INFO'}, f"当前镜像轴: {self._axis}")
            return {'RUNNING_MODAL'}
        elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._remove_draw_handle()
            if self.mirrored_objs:
                for o in self.mirrored_objs:
                    o.select_set(True)
                context.view_layer.objects.active = self.mirrored_objs[0]
            context.view_layer.update()
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
            self.mirrored_objs = []
            self.report({'INFO'}, f"完成{self._axis}轴镜像复制")
            return {'FINISHED'}
        elif event.type == 'ESC':
            self._remove_draw_handle()
            self._remove_mirrored(context)
            self.report({'INFO'}, "已撤销镜像")
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _draw_callback(self, context): 
        font_id = 0
        blf.size(font_id, 18)
        blf.color(font_id, 0.8, 0.8, 0.8, 0.8)
        blf.position(font_id, 60, 80, 0)
        blf.draw(font_id, "连续按 X 或Shift+鼠标滚轮切换镜像轴")
        blf.position(font_id, 60, 60, 0)
        blf.draw(font_id, "空格 / Enter / 右键 确认")
        blf.position(font_id, 60, 40, 0)
        blf.draw(font_id, "ESC 取消")

    def _remove_draw_handle(self):
        if hasattr(self, '_draw_handle') and self._draw_handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self._draw_handle = None

    def _do_mirror(self, context, axis):
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
            orig_transform = get_transform_from_obj(obj)
            mirrored_transform = {
                "location": {
                    "x": mirrored_loc.x * 100,
                    "y": -mirrored_loc.y * 100,
                    "z": mirrored_loc.z * 100
                },
                "rotation": {
                    "x": orig_transform["rotation"]["x"],
                    "y": orig_transform["rotation"]["y"],
                    "z": orig_transform["rotation"]["z"]
                },
                "scale": {
                    "x": obj.scale.x * mirror_vec[0],
                    "y": obj.scale.y * mirror_vec[1],
                    "z": obj.scale.z * mirror_vec[2]
                }
            }
            if axis == 'X':
                mirrored_transform["rotation"]["y"] = -mirrored_transform["rotation"]["y"]
                mirrored_transform["rotation"]["z"] = -mirrored_transform["rotation"]["z"]
            elif axis == 'Y':
                mirrored_transform["rotation"]["x"] = -mirrored_transform["rotation"]["x"]
                mirrored_transform["rotation"]["z"] = -mirrored_transform["rotation"]["z"]
            elif axis == 'Z':
                mirrored_transform["rotation"]["x"] = -mirrored_transform["rotation"]["x"]
                mirrored_transform["rotation"]["y"] = -mirrored_transform["rotation"]["y"]
            set_actor_transform(new_obj, mirrored_transform)
            for key in obj.keys():
                if key not in {'_RNA_UI'}:
                    value = obj[key]
                    if isinstance(value, (str, int, float, bool)):
                        new_obj[key] = value
            self.level_asset_coll.objects.link(new_obj)
            self.mirrored_objs.append(new_obj)
        for o in self.mirrored_objs:
            o.select_set(True)
        for obj in self.selected_objs:
            o.select_set(True)

    def _remove_mirrored(self, context):
        for obj in self.mirrored_objs:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        self.mirrored_objs.clear() 



class SelectSameClassActorsOperator(bpy.types.Operator):
    bl_idname = "ubio.select_same_class_actors"
    bl_label = "Select Same Class Actors"
    bl_description  = "批量选择同样class的对象"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        selected_obj = context.active_object
        if not selected_obj:
            self.report({'WARNING'}, "请先选择一个对象。")
            return {'CANCELLED'}

        # 检查选中对象是否具有ACTORCLASS属性
        if Const.ACTORCLASS not in selected_obj:
            self.report({'WARNING'}, f"选中的对象 '{selected_obj.name}' 没有 '{Const.ACTORCLASS}' 属性。")
            return {'CANCELLED'}

        target_actor_class = selected_obj[Const.ACTORCLASS]

        # 查找Level Asset集合
        level_asset_coll = find_level_asset_coll(Const.UECOLL, Const.COLL_LEVEL)
        if not level_asset_coll:
            self.report({'WARNING'}, "未找到 Level Asset Collection。请确保场景中存在UnrealIO/Level集合。")
            return {'CANCELLED'}

        # 清除所有选中
        bpy.ops.object.select_all(action='DESELECT')

        selected_count = 0
        for obj in level_asset_coll.objects:
            if Const.ACTORCLASS in obj and obj[Const.ACTORCLASS] == target_actor_class:
                obj.select_set(True)
                selected_count += 1
        
        # 重新激活原选中对象
        context.view_layer.objects.active = selected_obj

        self.report({'INFO'}, f"成功选中 {selected_count} 个具有相同 Class 的对象。")
        return {"FINISHED"}
    


class ActorArrayOperator(bpy.types.Operator):
    bl_idname = "ubio.array_copy_actors"
    bl_label = "Array Copy Actors"

    def execute(self, context):
        #TODO: 1. 参考mirror copy operator的实现。做一个array。 2. 参数a 控制array的间隔。 参数b 控制array的方向(xyz)。参数c  控制array的个数。 3. 操控：鼠标位置控制间隔， x键切换方向， 滚轮控制个数  

        return {"FINISHED"}

