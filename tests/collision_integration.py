"""Run with Blender --background --factory-startup --python tests/collision_integration.py."""
import sys, json, traceback, zipfile, math, inspect
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'collision'
OUT.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True
with zipfile.ZipFile(next((ROOT / 'wheels').glob('coacd-*.whl'))) as wheel:
    wheel.extractall(OUT / 'python')
sys.path[:0] = [str(OUT / 'python'), str(ROOT.parent)]
import bpy
import numpy as np
from mathutils import Matrix, Vector
import UnrealBlenderIO as addon
from UnrealBlenderIO import collision_generation as gen, collision_preprocess as prep, i18n
from UnrealBlenderIO.util import Const as C, apply_bp_static_mesh_session_metadata
SET = dict(max_hulls=32, error=.02, min_volume=.000001, min_thickness=.005, feature_size=.02, ground=False, preserve_openings=True)
results = {'blender': bpy.app.version_string, 'checks': [], 'metrics': []}

def record(name, fn):
    try:
        detail = fn()
        results['checks'].append(dict(name=name, status='PASS', detail=detail))
    except Exception:
        results['checks'].append(dict(name=name, status='FAIL', detail=traceback.format_exc()))
        traceback.print_exc()
    (OUT / 'collision_integration.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')

def reset():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.scene.unit_settings.scale_length = 1

def mesh(name, verts, faces, path, matrix=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj[C.STATIC_MESH_PROP_SOURCE_ASSET_PATH] = path
    obj[C.STATIC_MESH_PROP_SESSION_ID] = 'integration'
    if matrix is not None:
        obj.matrix_world = matrix
    bpy.context.view_layer.update()
    return obj

def box(name, low, high, path, matrix=None):
    v, t = prep._box(low, high)
    return mesh(name, v.tolist(), t.tolist(), path, matrix)

def select(*objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

def collisions(path):
    return [o for o in bpy.data.objects if gen.asset_path(o)==path and o.get(C.STATIC_MESH_PROP_COLLISION_TARGET_NAME)]

def generate(*objects, settings=None):
    select(*objects)
    groups = gen.asset_groups(bpy.context)
    for path, sessions in groups.items():
        results['metrics'].append(gen.generate_asset(bpy.context, path, sessions, settings or SET))
    return groups

def register():
    i18n.register_translations()
    addon.auto_load.register()
    bpy.types.Scene.ubio_params = bpy.props.PointerProperty(type=addon.UBIO_PG_Params)
    assert gen.UBIO_OT_GenerateCollision.is_registered
    assert gen.UBIO_OT_GenerateCollision.bl_options == {'UNDO'}
    assert 'return self.execute(context)' in inspect.getsource(gen.UBIO_OT_GenerateCollision.invoke)
    assert not any('cleanup_ubio' in str(h) for h in getattr(bpy.app.handlers,'exit_pre',[]))
    return 'All auto-loaded classes registered; UNDO and explicit generation from scene settings; exit cleanup not installed.'

def languages():
    texts = {}
    for lang in ('en_US','zh_HANS'):
        bpy.context.preferences.view.language = lang
        texts[lang] = i18n.tr('op.generate_collision.label')
        assert texts[lang] == i18n._TRANSLATIONS[lang]['op.generate_collision.label']
        assert '{' not in i18n.tr('report.collision.generated',count=1,hulls=2,failed=0)
    assert texts['en_US'] != texts['zh_HANS']
    i18n._validate_translations(i18n._TRANSLATIONS)
    bpy.context.preferences.view.language = 'en_US'
    return texts

def transaction():
    reset()
    p='/Game/Integration/SM_Multi.SM_Multi'
    a=box('Left',[-2,-.2,0],[-1,.2,2],p)
    b=box('Right',[1,-.2,0],[2,.2,2],p)
    other=box('Other',[-1,-1,-1],[1,1,1],'/Game/Integration/SM_Other.SM_Other')
    generate(a)
    assert len(collisions(p))==2
    assert not collisions(gen.asset_path(other))
    old=list(collisions(p)); ids={o.as_pointer() for o in old}
    generate(a)
    assert len(collisions(p))==2 and not ids.intersection(o.as_pointer() for o in collisions(p))
    before={o.name: o.as_pointer() for o in collisions(p)}
    original=gen.decompose
    def failing(*args): raise RuntimeError('injected backend failure')
    gen.decompose=failing
    try:
        try: generate(a,settings={**SET,'preserve_openings':False})
        except RuntimeError: pass
        else: raise AssertionError('failure not surfaced')
    finally: gen.decompose=original
    assert before=={o.name:o.as_pointer() for o in collisions(p)}
    select(a)
    for key, value in SET.items():
        setattr(bpy.context.scene.ubio_params, 'collision_' + key, value)
    assert bpy.ops.ubio.generate_collision('EXEC_DEFAULT')=={'FINISHED'}
    assert len(collisions(p))==2
    return 'Single selected mesh gathers both asset meshes; other asset untouched; replacement has no duplicates; backend failure preserves editable previous collisions; registered operator executes.'

def transformed():
    reset(); p='/Game/Integration/SM_Transformed.SM_Transformed'
    bpy.context.scene.unit_settings.scale_length=.01
    transform=Matrix.Translation((35,-80,120)) @ Matrix.Rotation(.36,4,'Z') @ Matrix.Diagonal((-2,.5,1.5,1))
    a=box('TransformMesh',[-50,-30,-10],[50,30,10],p,transform)
    generate(a)
    m=results['metrics'][-1]
    assert m['backend']=='coacd'
    assert np.allclose(m['input_bounds_m'], m['output_bounds_m'], atol=.025)
    assert len(collisions(p))>=1
    return m

def bp_instances():
    reset(); p='/Game/Integration/SM_BP.SM_BP'
    root=bpy.data.objects.new('CanonicalRoot',None); bpy.context.scene.collection.objects.link(root)
    root[C.BP_STATIC_MESH_PROP_COLLECTION_ROLE]=C.BP_STATIC_MESH_ROLE_CANONICAL_ROOT
    root.matrix_world=Matrix.Translation((10,3,1)) @ Matrix.Rotation(.4,4,'Z')
    a=box('CanonicalMesh',[-1,-.2,0],[1,.2,2],p)
    a[C.BP_STATIC_MESH_PROP_ASSET_KEY]='asset_bp'
    a[C.BP_STATIC_MESH_PROP_COLLECTION_ROLE]=C.BP_STATIC_MESH_ROLE_CANONICAL_OBJECT
    a.parent=root; a.matrix_local=Matrix.Identity(4)
    inst=[]
    for index in range(2):
        wrapper=bpy.data.objects.new('Wrapper'+str(index),None); bpy.context.scene.collection.objects.link(wrapper)
        wrapper[C.BP_STATIC_MESH_PROP_COLLECTION_ROLE]=C.BP_STATIC_MESH_ROLE_COMPONENT_WRAPPER
        wrapper.matrix_world=Matrix.Translation((index*4,10,3)) @ Matrix.Diagonal((-1-index,2,.5,1))
        obj=a.copy(); obj.data=a.data; bpy.context.scene.collection.objects.link(obj)
        obj.name='Instance'+str(index); obj.parent=wrapper; obj.matrix_local=Matrix.Identity(4)
        obj[C.BP_STATIC_MESH_PROP_COLLECTION_ROLE]=C.BP_STATIC_MESH_ROLE_COMPONENT_OBJECT
        obj[C.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME]=a.name
        inst.append(obj)
    bpy.context.view_layer.update()
    generate(inst[0])
    cols=collisions(p)
    canonical=[o for o in cols if o.get(C.BP_STATIC_MESH_PROP_COLLECTION_ROLE)==C.BP_STATIC_MESH_ROLE_CANONICAL_COLLISION]
    copies=[o for o in cols if o.get(C.BP_STATIC_MESH_PROP_COLLECTION_ROLE)==C.BP_STATIC_MESH_ROLE_COMPONENT_COLLISION]
    assert len(canonical)==1 and len(copies)==2
    for c in copies:
        assert c.data==canonical[0].data
        assert c[C.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME]==canonical[0].name
        target=bpy.data.objects[c[C.STATIC_MESH_PROP_COLLISION_TARGET_NAME]]
        assert np.allclose(c.matrix_world,target.parent.matrix_world)
    canonical[0].data.vertices[0].co.x-=.1
    assert all(c.data.vertices[0].co.x==canonical[0].data.vertices[0].co.x for c in copies)
    generate(inst[1]); assert len(collisions(p))==3
    return 'Selecting BP instance generates one canonical collision with two shared-data instances; negative/nonuniform wrapper transform and rerun verified.'

def concave_generation():
    reset(); p='/Game/Integration/SM_Concave.SM_Concave'
    polygon=[(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]
    verts=[(x,y,z) for z in (0,.4) for x,y in polygon]
    faces=[tuple(reversed(range(6))),tuple(range(6,12))]+[(i,(i+1)%6,(i+1)%6+6,i+6) for i in range(6)]
    a=mesh('Concave',verts,faces,p,Matrix.Rotation(.31,4,'Z'))
    generate(a); m=results['metrics'][-1]
    assert m['backend']=='coacd' and m['hulls']>=2
    cols=collisions(p)
    for obj in cols:
        obj.data.calc_loop_triangles()
        gen.validate_hull(np.array([tuple(v.co) for v in obj.data.vertices]),
                          np.array([tuple(t.vertices) for t in obj.data.loop_triangles]))
    return {'hulls':len(cols),'bounds':m['output_bounds_m']}


def bp_session_isolation():
    reset(); p='/Game/Integration/SM_Shared.SM_Shared'; objects=[]
    for index in range(2):
        root=bpy.data.objects.new('SessionRoot'+str(index),None); bpy.context.scene.collection.objects.link(root)
        root[C.BP_STATIC_MESH_PROP_COLLECTION_ROLE]=C.BP_STATIC_MESH_ROLE_CANONICAL_ROOT
        root.matrix_world=Matrix.Translation((index*20,0,0))
        a=box('SessionMesh'+str(index),[-1,-.2,0],[1,.2,2],p)
        session=dict(session_id='bp-session-'+str(index),session_type=C.BP_STATIC_MESH_SESSION_TYPE,
                     assets=[dict(asset_key='asset_shared',asset_path=p,asset_name='SM_Shared')])
        session_file=str(OUT/('bp_session_'+str(index)+'.json'))
        apply_bp_static_mesh_session_metadata(a,session_file,session,collection_role=C.BP_STATIC_MESH_ROLE_CANONICAL_OBJECT,asset_key='asset_shared',source_asset_path=p)
        apply_bp_static_mesh_session_metadata(root,session_file,session,collection_role=C.BP_STATIC_MESH_ROLE_CANONICAL_ROOT,asset_key='asset_shared',source_asset_path=p)
        a.parent=root; a.matrix_local=Matrix.Identity(4); objects.append(a)
    bpy.context.view_layer.update(); select(objects[0])
    groups=gen.asset_groups(bpy.context)
    assert len(groups[p])==2, 'BP session IDs must partition same-asset canonical roots'
    generate(objects[0])
    cols=collisions(p)
    assert len(cols)==2 and {o.parent for o in cols}=={o.parent for o in objects}
    assert len({o.users_collection[0] for o in cols})==2
    return 'Two real BP sessions retain independent asset frames and collections.'

def undo_redo():
    reset(); p='/Game/Integration/SM_Undo.SM_Undo'
    obj=box('UndoSource',[-1,-.2,0],[1,.2,2],p); select(obj)
    bpy.context.preferences.edit.use_global_undo=True
    bpy.ops.ed.undo_push(message='Integration before collision')
    for key, value in SET.items():
        setattr(bpy.context.scene.ubio_params, 'collision_' + key, value)
    assert bpy.ops.ubio.generate_collision('EXEC_DEFAULT')=={'FINISHED'}
    assert len(collisions(p))==1
    bpy.ops.ed.undo_push(message='Integration after collision')
    assert bpy.ops.ed.undo()=={'FINISHED'}
    assert len(collisions(p))==0 and bpy.data.objects.get('UndoSource') is not None
    assert bpy.ops.ed.redo()=={'FINISHED'}
    assert len(collisions(p))==1
    return 'Real Blender undo removes generated collision and redo restores it; source survives.'
record('registration_redo_contract',register)
record('locale_switch',languages)
record('asset_grouping_replacement_failure_operator',transaction)
record('negative_nonuniform_transform_unit_scale',transformed)
record('bp_instances_shared_mesh',bp_instances)
record('real_coacd_concave_generation',concave_generation)
record('bp_session_isolation',bp_session_isolation)
record('real_undo_redo',undo_redo)
results['passed']=all(c['status']=='PASS' for c in results['checks'])
(OUT/'collision_integration.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
print('COLLISION_INTEGRATION_RESULT',json.dumps(results,ensure_ascii=False))
del bpy.types.Scene.ubio_params
addon.auto_load.unregister(); i18n.unregister_translations()
if not results['passed']: raise RuntimeError('Collision integration failed; inspect JSON')