import bpy
import blf
from mathutils import Vector
from bpy.props import EnumProperty
from .util import (
    Const,
    find_level_asset_coll,
    set_proxy_pivot_properties,
    get_transform_from_obj,
    set_actor_transform,
)
from .i18n import msgid, tr
from .collision import set_collision_target


def _is_ubio_static_mesh(obj):
    if obj is None or obj.type != "MESH":
        return False
    if obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) in {
        Const.BP_STATIC_MESH_ROLE_COMPONENT_COLLISION,
        Const.BP_STATIC_MESH_ROLE_CANONICAL_COLLISION,
    }:
        return False
    return bool(
        obj.get(Const.STATIC_MESH_PROP_SESSION_ID)
        and (
            obj.get(Const.STATIC_MESH_PROP_ROUNDTRIP_TYPE)
            or obj.get(Const.BP_STATIC_MESH_PROP_ROUNDTRIP_TYPE)
        )
    )


class UBIO_OT_MakeCollision(bpy.types.Operator):
    bl_idname = "ubio.make_collision"
    bl_label = msgid("op.make_collision.label")
    bl_description = msgid("op.make_collision.desc")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and len(context.selected_objects) >= 2

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if len(selected_meshes) < 2:
            self.report({"ERROR"}, tr("report.collision.need_meshes"))
            return {"CANCELLED"}

        targets = [obj for obj in selected_meshes if _is_ubio_static_mesh(obj)]
        sources = [obj for obj in selected_meshes if not _is_ubio_static_mesh(obj)]
        if len(targets) != 1 or not sources:
            self.report({"ERROR"}, tr("report.collision.need_one_ubio_mesh"))
            return {"CANCELLED"}

        selected_target_obj = targets[0]
        target_obj = selected_target_obj
        empty_collision_objects = [obj for obj in sources if len(obj.data.polygons) == 0]
        if empty_collision_objects:
            self.report({"ERROR"}, tr("report.collision.empty_mesh"))
            return {"CANCELLED"}
        if target_obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) == Const.BP_STATIC_MESH_ROLE_COMPONENT_OBJECT:
            canonical_name = target_obj.get(Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME, "")
            canonical_obj = bpy.data.objects.get(canonical_name) if canonical_name else None
            if canonical_obj is None:
                self.report({"ERROR"}, tr("report.collision.canonical_not_found"))
                return {"CANCELLED"}
            target_obj = canonical_obj
        session_id = target_obj.get(Const.STATIC_MESH_PROP_SESSION_ID, "")
        asset_key = target_obj.get(Const.BP_STATIC_MESH_PROP_ASSET_KEY, "")
        existing_count = sum(
            1 for obj in bpy.data.objects
            if obj.get(Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME) == target_obj.name
        )

        target_collection = target_obj.users_collection[0] if target_obj.users_collection else context.collection
        for index, collision_obj in enumerate(sources, start=existing_count):
            collision_to_target = selected_target_obj.matrix_world.inverted_safe() @ collision_obj.matrix_world
            collision_world = target_obj.matrix_world @ collision_to_target
            collision_obj.name = f"UBIO_COLLISION_{target_obj.name}_{index:02d}"
            collision_obj.parent = target_obj.parent
            collision_obj.matrix_world = collision_world
            set_collision_target(collision_obj, target_obj)
            collision_obj[Const.STATIC_MESH_PROP_SESSION_ID] = session_id
            collision_obj[Const.STATIC_MESH_PROP_SESSION_FILE] = target_obj.get(
                Const.STATIC_MESH_PROP_SESSION_FILE, ""
            )
            collision_obj[Const.STATIC_MESH_PROP_ROUNDTRIP_TYPE] = target_obj.get(
                Const.STATIC_MESH_PROP_ROUNDTRIP_TYPE, ""
            )
            if asset_key:
                collision_obj[Const.STATIC_MESH_PROP_COLLISION_ASSET_KEY] = asset_key
                collision_obj[Const.BP_STATIC_MESH_PROP_ASSET_KEY] = asset_key
                collision_obj[Const.BP_STATIC_MESH_PROP_SESSION_ID] = target_obj.get(
                    Const.BP_STATIC_MESH_PROP_SESSION_ID, session_id
                )
                collision_obj[Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE] = Const.BP_STATIC_MESH_ROLE_CANONICAL_COLLISION

            for collection in list(collision_obj.users_collection):
                collection.objects.unlink(collision_obj)
            target_collection.objects.link(collision_obj)
            collision_obj.select_set(True)

        context.view_layer.objects.active = sources[-1]
        self.report({"INFO"}, tr("report.collision.created_many", count=len(sources)))
        return {"FINISHED"}

class UBIO_OT_AddProxyPivot(bpy.types.Operator):
    bl_idname = "ubio.add_proxy_pivot"
    bl_label = msgid("op.add_proxy_pivot.label")
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = msgid("op.add_proxy_pivot.desc")
    def execute(self, context):
        ubio_coll = bpy.data.collections.get(Const.UECOLL)
        level_asset_coll = None
        if ubio_coll:
            level_asset_coll = find_level_asset_coll(Const.UECOLL, 'Level')
        if not level_asset_coll:
            self.report({"ERROR"}, tr("report.tools.level_asset_not_found"))
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
        self.report({"INFO"}, tr("report.tools.proxy_pivot_added"))
        return {"FINISHED"}

class UBIO_OT_MirrorCopyActors(bpy.types.Operator):
    bl_idname = "ubio.mirror_copy_actors"
    bl_label = msgid("op.mirror_copy_actors.label")
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = msgid("op.mirror_copy_actors.desc")

    mirror_axis: EnumProperty(
        name=msgid("prop.mirror_axis.name"),
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
            self.report({'WARNING'}, tr("report.tools.no_actor_selected"))
            return {'CANCELLED'}
        ubio_coll = bpy.data.collections.get(Const.UECOLL)
        self.level_asset_coll = None
        if ubio_coll:
            self.level_asset_coll = find_level_asset_coll(Const.UECOLL, 'Level')
        if not self.level_asset_coll:
            self.report({'ERROR'}, tr("report.tools.level_asset_not_found"))
            return {'CANCELLED'}
        self.proxy_pivot = None
        for obj in self.level_asset_coll.objects:
            if obj.type == 'EMPTY' and obj.name == Const.PROXY_PIVOT_OBJ:
                self.proxy_pivot = obj
                break
        if not self.proxy_pivot:
            self.report({'ERROR'}, tr("report.tools.proxy_pivot_not_found"))
            return {'CANCELLED'}
        self._axis = 'X'  # 默认X轴
        self.mirrored_objs = []
        self._do_mirror(context, self._axis)
        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_callback, (context,), 'WINDOW', 'POST_PIXEL'
        )
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, tr("report.tools.mirror_axis_switch_hint"))
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
            self._remove_mirrored()
            self._do_mirror(context, self._axis)
            self.report({'INFO'}, tr("report.tools.current_mirror_axis", axis=self._axis))
            return {'RUNNING_MODAL'}
        elif event.shift and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            axis_order = ['X', 'Y', 'Z']
            current_idx = axis_order.index(self._axis)
            if event.type == 'WHEELUPMOUSE':
                next_idx = (current_idx + 1) % 3
            else:
                next_idx = (current_idx - 1 + 3) % 3
            self._axis = axis_order[next_idx]
            self._remove_mirrored()
            self._do_mirror(context, self._axis)
            self.report({'INFO'}, tr("report.tools.current_mirror_axis", axis=self._axis))
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
            self.report({'INFO'}, tr("report.tools.mirror_done", axis=self._axis))
            return {'FINISHED'}
        elif event.type == 'ESC':
            self._remove_draw_handle()
            self._remove_mirrored()
            self.report({'INFO'}, tr("report.tools.mirror_cancelled"))
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _draw_callback(self, context): 
        font_id = 0
        blf.size(font_id, 18)
        blf.color(font_id, 0.8, 0.8, 0.8, 0.8)
        blf.position(font_id, 60, 80, 0)
        blf.draw(font_id, tr("hint.tools.mirror_switch_axis"))
        blf.position(font_id, 60, 60, 0)
        blf.draw(font_id, tr("hint.tools.confirm"))
        blf.position(font_id, 60, 40, 0)
        blf.draw(font_id, tr("hint.tools.cancel"))

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
            self.report({'ERROR'}, tr("report.tools.unknown_mirror_axis", axis=axis))
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

    def _remove_mirrored(self):
        for obj in self.mirrored_objs:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        self.mirrored_objs.clear() 



class UBIO_OT_SelectSameClassActors(bpy.types.Operator):
    bl_idname = "ubio.select_same_class_actors"
    bl_label = msgid("op.select_same_class.label")
    bl_description  = msgid("op.select_same_class.desc")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        selected_obj = context.active_object
        if not selected_obj:
            self.report({'WARNING'}, tr("report.tools.select_need_active"))
            return {'CANCELLED'}

        # 检查选中对象是否具有ACTORCLASS属性
        if Const.ACTORCLASS not in selected_obj:
            self.report(
                {'WARNING'},
                tr(
                    "report.tools.select_missing_actorclass",
                    name=selected_obj.name,
                    prop=Const.ACTORCLASS,
                ),
            )
            return {'CANCELLED'}

        target_actor_class = selected_obj[Const.ACTORCLASS]

        # 查找Level Asset集合
        level_asset_coll = find_level_asset_coll(Const.UECOLL, Const.COLL_LEVEL)
        if not level_asset_coll:
            self.report({'WARNING'}, tr("report.tools.select_level_asset_not_found"))
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

        self.report({'INFO'}, tr("report.tools.select_same_class_done", count=selected_count))
        return {"FINISHED"}
    


class UBIO_OT_ArrayCopyActors(bpy.types.Operator):
    bl_idname = "ubio.array_copy_actors"
    bl_label = msgid("op.array_copy.label")

    def execute(self, context):
        #TODO: 1. 参考mirror copy operator的实现。做一个array。 2. 参数a 控制array的间隔。 参数b 控制array的方向(xyz)。参数c  控制array的个数。 3. 操控：鼠标位置控制间隔， x键切换方向， 滚轮控制个数  

        return {"FINISHED"}

