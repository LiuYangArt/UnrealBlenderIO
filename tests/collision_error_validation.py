"""Blender --background --factory-startup --python-exit-code 1 --python tests/collision_error_validation.py."""
import builtins
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.dont_write_bytecode = True
import bpy
import numpy as np
from UnrealBlenderIO import collision_generation as gen, collision_backend as backend, i18n
from UnrealBlenderIO.collision_preprocess import _box
from UnrealBlenderIO.util import Const as C
from UnrealBlenderIO.UI import UBIO_PG_Params
bpy.utils.register_class(UBIO_PG_Params)
bpy.types.Scene.ubio_params = bpy.props.PointerProperty(type=UBIO_PG_Params)

settings = dict(max_hulls=32, error=.02, min_volume=.000001, min_thickness=.005,
                feature_size=.02, ground=False, preserve_openings=True)
reports = []
op = SimpleNamespace(**settings, report=lambda level, text: reports.append((level, text)))
source = bpy.context.active_object
source[C.STATIC_MESH_PROP_SOURCE_ASSET_PATH] = '/Game/ErrorTest.ErrorTest'
path = gen.asset_path(source)
checks = []


def propagates(name, callback, error):
    reports.clear()
    try:
        callback()
    except Exception as actual:
        assert actual is error, (name, actual)
        assert not reports, reports
        stack = traceback.format_exc()
        assert type(error).__name__ in stack and str(error) in stack
        checks.append(dict(name=name, traceback=stack))
    else:
        raise AssertionError(name + ': swallowed exception')


for name, target, error in (
    ('asset_grouping', 'asset_groups', ValueError('unexpected asset metadata')),
    ('decomposition', 'generate_asset', RuntimeError('native backend diagnostic')),
):
    with patch.object(gen, target, side_effect=error):
        propagates(name, lambda: gen.UBIO_OT_GenerateCollision.execute(op, bpy.context), error)

source[C.STATIC_MESH_PROP_SESSION_FILE] = str(ROOT/'artifacts/collision/error-session.json')
error = PermissionError('diagnostic log cannot be written')
with patch.object(gen, 'generate_asset', return_value={'hulls': 1}), patch.object(Path, 'write_text', side_effect=error):
    propagates('log_write', lambda: gen.UBIO_OT_GenerateCollision.execute(op, bpy.context), error)

real_import = builtins.__import__
for error in (ModuleNotFoundError('No module named coacd'), OSError('DLL load failed: original loader detail')):
    def fail_import(name, *args, **kwargs):
        if name == 'coacd':
            raise error
        return real_import(name, *args, **kwargs)
    with patch.object(builtins, '__import__', side_effect=fail_import):
        propagates(type(error).__name__, lambda: backend.decompose([], [], settings), error)

vertices, faces = _box(np.array([-1., -1., -1.]), np.array([1., 1., 1.]))
old = gen.replace_collisions(bpy.context, path, [[source]], [(vertices, faces)])
before = ([o.as_pointer() for o in bpy.data.objects], [m.as_pointer() for m in bpy.data.meshes],
          [c.as_pointer() for c in bpy.data.collections])
error = RuntimeError('binding failed after allocating collision mesh')
with patch.object(gen, 'set_collision_target', side_effect=error):
    propagates('rollback', lambda: gen.replace_collisions(bpy.context, path, [[source]], [(vertices, faces)]), error)
after = ([o.as_pointer() for o in bpy.data.objects], [m.as_pointer() for m in bpy.data.meshes],
         [c.as_pointer() for c in bpy.data.collections])
assert before == after, 'Rollback changed original data or leaked objects/meshes/collections'
assert old[0].name in bpy.data.objects

i18n._validate_translations(i18n._TRANSLATIONS)
i18n.register_translations()
for lang in ('en_US', 'zh_HANS'):
    bpy.context.preferences.view.language = lang
    message = i18n.tr('report.collision.generated', count=1, hulls=2)
    assert '{' not in message and '1' in message and '2' in message
result = dict(passed=True, checks=checks)
out = ROOT/'artifacts/collision/error_validation.json'
out.write_text(json.dumps(result, indent=2), encoding='utf-8')
print('COLLISION_ERROR_VALIDATION_PASS', len(checks), flush=True)

del bpy.types.Scene.ubio_params
bpy.utils.unregister_class(UBIO_PG_Params)
