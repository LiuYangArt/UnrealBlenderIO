import bpy
import addon_utils
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
# Enable through Blender so the manifest, wheel installation and class discovery all run.
addon_utils.enable('bl_ext.ubio_test.ubio', default_set=False, persistent=False)
import bl_ext.ubio_test.ubio as addon
addon._unregister_exit_handler()
import coacd
from bl_ext.ubio_test.ubio.collision_backend import decompose
from bl_ext.ubio_test.ubio.collision_preprocess import _box
v, f = _box((-1,-1,-1),(1,1,1))
parts = decompose(v, f, {'error': .02, 'max_hulls': 4})
assert len(parts) == 1
assert bpy.ops.ubio.generate_collision.get_rna_type()
result = {'passed': True, 'blender': bpy.app.version_string, 'coacd': coacd.__file__, 'hulls': len(parts)}
(root/'artifacts/collision/package-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
addon_utils.disable('bl_ext.ubio_test.ubio',default_set=False)
print('PACKAGE_RUNTIME_PASS',result)