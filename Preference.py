import bpy
import os
from . import util
from .i18n import msgid, tr

#TODO: blender 插件设置界面。  功能： 选择ue工程路径位置。 复制UnrealAsset下的内容到工程目录下， 复制到工程目录下的Content/UBIO 和 Content/Python.   添加一个按钮，点击后，自动执行.   添加一个使用说明文字段。

class UBIO_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    ue_project_path: bpy.props.StringProperty(
        name=msgid("pref.ue_project_path.name"),
        description=msgid("pref.ue_project_path.desc"),
        subtype='DIR_PATH',
        default='D:\\UE5Projects\\TargetProject\\'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ue_project_path")

        layout.operator(UBIO_OT_CopyAssets.bl_idname)
        layout.separator()
        box = layout.box()
        box.label(text=msgid("pref.guide.title"))
        box.label(text=msgid("pref.guide.step1"))
        box.label(text=msgid("pref.guide.step2"))
        box.label(text=msgid("pref.guide.step3"))
        box.label(text=msgid("pref.guide.step4"))


class UBIO_OT_CopyAssets(bpy.types.Operator):
    bl_idname = "ubio.copy_assets"
    bl_label = msgid("op.copy_assets.label")
    bl_description = msgid("op.copy_assets.desc")
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        prefs = context.preferences.addons[__package__].preferences
        if not prefs.ue_project_path or not os.path.isdir(prefs.ue_project_path):
            self.report({'ERROR'}, tr("report.pref.invalid_ue_project_path"))
            return {'CANCEL'}
        
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        ue_project_path = prefs.ue_project_path

        current_dir = os.path.dirname(os.path.abspath(__file__))
        unreal_asset_source_dir = os.path.join(current_dir, "UnrealAsset")

        # 复制到Content/UBIO
        target_ubio_dir = os.path.join(ue_project_path, "Content")
        util.copy_unreal_assets(unreal_asset_source_dir, target_ubio_dir)

        # 复制到Content/Python (假设UnrealAsset中包含Python目录)
        # 如果UnrealAsset下没有Python目录，则需要单独处理或告知用户
        unreal_python_source_dir = os.path.join(unreal_asset_source_dir, "Python")
        target_python_dir = os.path.join(ue_project_path, "Content", "Python")
        
        if os.path.exists(unreal_python_source_dir):
            util.copy_unreal_assets(unreal_python_source_dir, target_python_dir)
        else:
            self.report({'WARNING'}, tr("report.pref.python_folder_missing"))

        self.report({'INFO'}, tr("report.pref.assets_copied"))
        return {'FINISHED'}


