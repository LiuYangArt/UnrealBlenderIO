import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup
from .util import DEFAULT_IO_TEMP_DIR




def run_import_json_op(self, context):
    """当ui参数改变时，运行对应的operator"""
    bpy.ops.ubio.import_unreal_scene("INVOKE_DEFAULT")


class UIParams(PropertyGroup):
    """UI参数"""
    ubio_json_path: StringProperty(
        name="UBIO JSON Path",
        description="UBIO JSON文件路径",
        default=DEFAULT_IO_TEMP_DIR + "*.json",
        maxlen=1024,
        subtype="FILE_PATH",
        options={'HIDDEN'},
        update=run_import_json_op,
        
)

class UBIOToolPanel(bpy.types.Panel):
    bl_idname = "UBIO_PT_tool_panel"
    bl_label = "Unreal Blender IO"
    bl_category = "UBIO"  # Custom tab name
    bl_space_type = "VIEW_3D"  # Space type where the panel will be displayed
    bl_region_type = "UI"
    bl_order = 0

    def draw(self, context):
        parameters = context.scene.ubio_params
        layout = self.layout
        box = layout.box()
        box_column = box.column()
        box_column.label(text="Unreal Blender IO")
        box_column.prop(parameters, "ubio_json_path", text="Path")
        box_column.operator("ubio.import_unreal_scene", icon="IMPORT")
        box_column.operator("ubio.export_unreal_scene_json", icon="EXPORT")
        box_column.operator("ubio.clean_ubio_tempfiles", icon="FILE_REFRESH")
        box_column.separator()
        box_column.label(text="UBIO Tools")
        box_column.operator("ubio.add_proxy_pivot", icon="EMPTY_ARROWS")
        box_column.operator("ubio.mirror_copy_actors", icon="MOD_MIRROR")
        # box_column.operator("ubio.make_ue_actor_instance")
        
