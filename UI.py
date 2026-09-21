import bpy
import os
from bpy.props import (
    BoolProperty,
    # EnumProperty,
    FloatProperty,
    # FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup
from .util import Const
from .i18n import msgid




# Disabled with the legacy Unreal Scene import UI.
# def run_import_json_op(self, context):
#     """当ui参数改变时，运行对应的operator"""
#     bpy.ops.ubio.import_unreal_scene("INVOKE_DEFAULT")


class UBIO_PG_Params(PropertyGroup):
    """UI参数"""
    ubio_json_path: StringProperty(
        name=msgid("prop.ubio_json_path.name"),
        description=msgid("prop.ubio_json_path.desc"),
        default=Const.DEFAULT_IO_TEMP_DIR + "*.json",
        maxlen=1024,
        subtype="FILE_PATH",
        options={'HIDDEN'},
        # Disabled with the legacy Unreal Scene import UI.
        # update=run_import_json_op,
        
)

    ubio_ue_project_path: StringProperty(
        name=msgid("prop.ue_project_path.name"),
        description=msgid("prop.ue_project_path.desc"),
        default="",
        maxlen=1024,
        subtype="DIR_PATH",
        options={'HIDDEN'},
    )

    ubio_static_mesh_session_path: StringProperty(
        name=msgid("prop.static_mesh_session_path.name"),
        description=msgid("prop.static_mesh_session_path.desc"),
        default=os.path.join(Const.BP_STATIC_MESH_SESSION_DIR, Const.STATIC_MESH_SESSION_FILE),
        maxlen=1024,
        subtype="FILE_PATH",
        options={'HIDDEN'},
    )
        

    collision_max_hulls: IntProperty(name=msgid('prop.collision.max_hulls.name'), description=msgid('prop.collision.max_hulls.desc'), default=16, min=1, max=256)
    collision_error: FloatProperty(name=msgid('prop.collision.error.name'), description=msgid('prop.collision.error.desc'), default=0.2, min=0.001, max=1, precision=3)
    collision_min_volume: FloatProperty(name=msgid('prop.collision.min_volume.name'), description=msgid('prop.collision.min_volume.desc'), default=0.000001, min=0, precision=6)
    collision_min_thickness: FloatProperty(name=msgid('prop.collision.min_thickness.name'), description=msgid('prop.collision.min_thickness.desc'), default=0.005, min=0, precision=3)
    collision_feature_size: FloatProperty(name=msgid('prop.collision.feature_size.name'), description=msgid('prop.collision.feature_size.desc'), default=0.1, min=0, precision=3)
    collision_ground: BoolProperty(name=msgid('prop.collision.ground.name'), description=msgid('prop.collision.ground.desc'), default=False)
    collision_preserve_openings: BoolProperty(name=msgid('prop.collision.preserve_openings.name'), description=msgid('prop.collision.preserve_openings.desc'), default=True)


class UBIO_PT_ToolPanel(bpy.types.Panel):
    bl_idname = "UBIO_PT_tool_panel"
    bl_label = msgid("panel.main_title")
    bl_category = "UBIO"  # Custom tab name
    bl_space_type = "VIEW_3D"  # Space type where the panel will be displayed
    bl_region_type = "UI"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box_column = box.column()
        box_column.label(text=msgid("panel.main_title"))
        # Disabled legacy Unreal Scene import controls.
        # box_column.prop(context.scene.ubio_params, "ubio_json_path", text=msgid("panel.path_label"))
        box_column.operator("ubio.import_latest_unreal_scene", icon="IMPORT")
        # box_column.operator("ubio.import_unreal_scene", icon="IMPORT")
        box_column.operator("ubio.export_unreal_scene_json", icon="EXPORT")
        # box_column.operator("ubio.clean_tempfiles", icon="FILE_REFRESH")

        box_column.separator()
        box_column.label(text=msgid("panel.tools_title"))
        box_column.operator("ubio.add_proxy_pivot", icon="EMPTY_ARROWS")
        box_column.operator("ubio.mirror_copy_actors", icon="MOD_MIRROR")
        box_column.operator("ubio.select_same_class_actors", icon="MESH_DATA")

        collision_column = layout.box().column(align=True)
        collision_column.label(text=msgid("panel.collision.title"))
        for name in ('max_hulls', 'error', 'min_volume', 'min_thickness', 'feature_size', 'preserve_openings', 'ground'):
            collision_column.prop(context.scene.ubio_params, 'collision_' + name)
        collision_column.separator()
        collision_column.label(text=msgid("panel.collision.manual_hint"), icon="INFO")
        collision_column.operator("ubio.generate_collision", icon="MOD_PHYSICS")

        static_mesh_box = layout.box()
        static_mesh_column = static_mesh_box.column()
        static_mesh_column.label(text=msgid("panel.static_mesh_title"))
        # Disabled manual session path/import controls.
        # static_mesh_column.prop(
        #     context.scene.ubio_params,
        #     "ubio_static_mesh_session_path",
        #     text=msgid("panel.session_path_label"),
        # )
        static_mesh_column.operator("ubio.import_latest_static_mesh_session", icon="IMPORT")
        static_mesh_column.operator("ubio.make_collision", icon="MESH_ICOSPHERE")
        # static_mesh_column.operator("ubio.import_static_mesh_session", icon="FILE_FOLDER")
        static_mesh_column.operator("ubio.export_static_mesh_session", icon="EXPORT")

        

        
        # box_column.operator("ubio.make_ue_actor_instance")

        
