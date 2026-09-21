"""Verify manual generation and scene settings in real Blender, without desktop automation."""
import sys, json
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
import bpy
import UnrealBlenderIO as addon
from UnrealBlenderIO import collision_generation as gen, i18n
from UnrealBlenderIO.util import Const as C
OUT=ROOT/'artifacts/collision'
OUT.mkdir(parents=True,exist_ok=True)
i18n.register_translations()
addon.auto_load.register()
bpy.types.Scene.ubio_params=bpy.props.PointerProperty(type=addon.UBIO_PG_Params)
assert gen.UBIO_OT_GenerateCollision.bl_options=={'UNDO'}
params=bpy.context.scene.ubio_params
assert params.collision_max_hulls==16 and abs(params.collision_error-.2)<1e-6
assert abs(params.collision_feature_size-.1)<1e-6
source=bpy.context.active_object
before_vertices=[tuple(v.co) for v in source.data.vertices]
real_generate=gen.generate_asset
with patch.object(gen,'generate_asset',wraps=real_generate) as generate:
    for value in (.1,.2,.3):
        params.collision_error=value
        bpy.context.view_layer.update()
    assert generate.call_count==0
    assert bpy.ops.ubio.generate_collision('INVOKE_DEFAULT')=={'FINISHED'}
    assert generate.call_count==1
    assert abs(generate.call_args.args[3]['error']-.3)<1e-6
    old={o.as_pointer() for o in bpy.data.objects if o.get(C.STATIC_MESH_PROP_COLLISION_TARGET_NAME)==source.name}
    assert len(old)==1
    params.collision_error=.4
    params.collision_max_hulls=8
    params.collision_feature_size=.15
    params.collision_ground=True
    params.collision_preserve_openings=False
    params.collision_min_volume=.000002
    params.collision_min_thickness=.01
    bpy.context.view_layer.update()
    assert generate.call_count==1
    assert old=={o.as_pointer() for o in bpy.data.objects if o.get(C.STATIC_MESH_PROP_COLLISION_TARGET_NAME)==source.name}
    # Keep the second real calculation on the deterministic box path.
    params.collision_preserve_openings=True
    assert bpy.ops.ubio.generate_collision('EXEC_DEFAULT')=={'FINISHED'}
    assert generate.call_count==2
    assert abs(generate.call_args.args[3]['error']-.4)<1e-6
    assert generate.call_args.args[3]['max_hulls']==8
assert before_vertices==[tuple(v.co) for v in source.data.vertices]
labels={}
for lang in ('zh_HANS','en_US'):
    bpy.context.preferences.view.language=lang
    labels[lang]=i18n.tr('panel.collision.title')
    assert labels[lang]==i18n._TRANSLATIONS[lang]['panel.collision.title']
i18n._validate_translations(i18n._TRANSLATIONS)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'panel_settings.blend'))
bpy.context.scene.ubio_params.collision_error=.9
bpy.ops.wm.open_mainfile(filepath=str(OUT/'panel_settings.blend'))
assert abs(bpy.context.scene.ubio_params.collision_error-.4)<1e-6
result=dict(passed=True,parameter_edits_do_not_generate=True,explicit_clicks=2,
            scene_settings_used=True,previous_collision_unchanged_while_editing=True,
            saved_settings_restored=True,source_unchanged=True,labels=labels)
(OUT/'panel_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PANEL_VALIDATION_PASS',json.dumps(result,ensure_ascii=False),flush=True)
del bpy.types.Scene.ubio_params
addon.auto_load.unregister()
i18n.unregister_translations()
