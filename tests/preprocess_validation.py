import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import numpy as np
from mathutils import Matrix
from collision_preprocess import prepare_mesh, try_rectangular_wall, _box, _volume

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
def object_mesh(name, vertices, faces):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def cube(name, low, high):
    v,t=_box(np.array(low,dtype=float),np.array(high,dtype=float))
    return object_mesh(name,v.tolist(),t.tolist())

settings={'min_volume':1e-7,'min_thickness':0.001,'feature_size':0.1,'ground':False,'preserve_openings':True}
obj=cube('box',(0,0,0),(2,1,3))
obj.location=(5,7,9)
bpy.context.view_layer.update()
v,t,m=prepare_mesh(bpy.context,[obj],obj.matrix_world,settings)
assert np.allclose(v.min(axis=0),0) and np.isclose(m['volume'],6)
assert len(try_rectangular_wall(v,t,settings))==1
bpy.context.scene.unit_settings.scale_length=0.01
v,t,m=prepare_mesh(bpy.context,[obj],obj.matrix_world,{**settings,'min_volume':0,'min_thickness':0})
assert np.isclose(v.max(),0.03) and np.isclose(m['volume'],6e-6)
bpy.context.scene.unit_settings.scale_length=1
# A single extrusion around a door, with welded shared surface edges.
outline=[(0,0),(1,0),(1,2),(2,2),(2,0),(3,0),(3,3),(0,3)]
vertices=[(x,y,z) for y in (0,0.2) for x,z in outline]
faces=[]
# Front/back use three rectangles; extra collinear points preserve watertight topology.
front=[(0,1,2,7),(7,2,3,6),(3,4,5,6)]
faces.extend(tuple(reversed(f)) for f in front)
faces.extend(tuple(i+8 for i in f) for f in front)
faces.extend((i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8))
wall=object_mesh('wall',vertices,faces)
v,t,m=prepare_mesh(bpy.context,[wall],Matrix.Identity(4),settings)
boxes=try_rectangular_wall(v,t,settings)
assert boxes is not None
assert np.isclose(sum(_volume(a,b) for a,b in boxes),m['volume'])
assert not any(np.all(np.array([1.5,0.1,1])>a.min(axis=0)) and np.all(np.array([1.5,0.1,1])<a.max(axis=0)) for a,b in boxes)
# Narrow door becomes a deliberately ignored seam.
v[:,0]=np.where(np.isclose(v[:,0],2),1.05,v[:,0])
boxes=try_rectangular_wall(v,t,settings)
assert boxes is not None and np.isclose(sum(_volume(a,b) for a,b in boxes),1.8)
# Rotation outside the proven axis-aligned scope must use the generic decomposition.
r=np.array(Matrix.Rotation(0.4,3,'Z'))
assert try_rectangular_wall(v@r.T,t,settings) is None
print('PREPROCESS_PASS transform units box doorway narrow_gap unsupported_rotation')
sheet=object_mesh('large_sheet',[(0,0,0),(10,0,0),(10,10,0),(0,10,0)],[(0,1,2,3)])
try:
    prepare_mesh(bpy.context,[sheet],Matrix.Identity(4),settings)
    raise AssertionError('large open sheet accepted')
except ValueError as error:
    assert str(error)=='open_mesh'
small=cube('debris',(0,0,0),(0.01,0.01,0.0001))
v,t,m=prepare_mesh(bpy.context,[obj,small],Matrix.Identity(4),settings)
assert m['filtered_components']==1
# Build a watertight tiled ground slab with a small raised central cell.
xs=[0,0.45,0.55,1]
ys=xs
verts=[]
quads=[]
lookup={}
def face(points):
    indices=[]
    for p in points:
        if p not in lookup:
            lookup[p]=len(verts)
            verts.append(p)
        indices.append(lookup[p])
    quads.append(indices)
# Voxel boundary cancellation keeps matching face topology at the base of the bump.
zlevels=[0,0.2,0.25]
cells={(i,j,0) for i in range(3) for j in range(3)}|{(1,1,1)}
for i,j,k in cells:
    low=np.array([xs[i],ys[j],zlevels[k]])
    high=np.array([xs[i+1],ys[j+1],zlevels[k+1]])
    bv,bt=_box(low,high)
    sides=[((0,0,-1),(0,3,2,1)),((0,0,1),(4,5,6,7)),((0,-1,0),(0,1,5,4)),((1,0,0),(1,2,6,5)),((0,1,0),(2,3,7,6)),((-1,0,0),(3,0,4,7))]
    for delta,ids in sides:
        if (i+delta[0],j+delta[1],k+delta[2]) not in cells:
            face([tuple(bv[n]) for n in ids])
ground=object_mesh('ground',verts,quads)
v,t,m=prepare_mesh(bpy.context,[ground],Matrix.Identity(4),{**settings,'ground':True})
assert np.isclose(v[:,2].max(),0.2),m
assert m['ground_vertices']==4
print('PREPROCESS_PASS open_sheet_rejection debris ground_inward_flatten')
from collision_preprocess import _fill_small_gaps, rectangular_wall_metrics
# Negative and nonuniform object transforms must preserve physical dimensions and volume.
obj.scale=(-2,3,0.5)
bpy.context.view_layer.update()
v,t,m=prepare_mesh(bpy.context,[obj],Matrix.Identity(4),settings)
assert np.allclose(m['dimensions_m'],[4,3,1.5]),m
assert np.isclose(m['volume'],18),m
# PCA must reject a detached oblique flake without classifying a symmetric solid as thin.
flake=cube('oblique_flake',(0,0,0),(2,2,0.0005))
flake.rotation_euler=(0.4,0.7,0.3)
bpy.context.view_layer.update()
v,t,m=prepare_mesh(bpy.context,[obj,flake],Matrix.Identity(4),settings)
assert m['filtered_components']==1,m
symmetric=cube('symmetric',(0,0,0),(2,2,2))
symmetric.rotation_euler=(0.7,0.3,0.9)
bpy.context.view_layer.update()
v,t,m=prepare_mesh(bpy.context,[symmetric],Matrix.Identity(4),{**settings,'min_thickness':1.9})
assert m['filtered_components']==0 and np.isclose(m['volume'],8),m
# An actual doorway is measured before and after the exact partition.
v,t,m=prepare_mesh(bpy.context,[wall],Matrix.Identity(4),settings)
assert m['opening_measurement']=='rectangular_only'
assert len(m['openings_before'])==len(m['openings_after'])==1,m
assert m['openings_before'][0]['width_m']==1 and m['openings_before'][0]['height_m']==2,m
v[:,0]=np.where(np.isclose(v[:,0],2),1.05,v[:,0])
m=rectangular_wall_metrics(v,t,settings)
assert np.isclose(m['openings_before'][0]['width_m'],0.05) and not m['openings_after'],m
# Keep a wide connected opening's narrow arm; close a separate genuinely small void.
mask=np.ones((5,5),dtype=bool)
mask[1:3,1:3]=False
mask[3,2]=False
coordinates=np.array([0,1,2,3,3.05,4])
assert np.array_equal(_fill_small_gaps(mask,coordinates,coordinates,0.1),mask)
mask[3,3:5]=False
assert not _fill_small_gaps(mask,coordinates,coordinates,0.1)[3,4]
mask=np.ones((5,5),dtype=bool)
mask[3,3]=False
assert _fill_small_gaps(mask,coordinates,coordinates,0.1).all()
print('PREPROCESS_PASS negative_scale oblique_flake symmetric_solid clearance_metrics large_opening_arm small_window')
# Touching closed pieces must retain separate topology, including after a non-welded join.
left=cube('touch_left',(0,0,0),(1,0.2,2))
right=cube('touch_right',(2,0,0),(3,0.2,2))
header=cube('touch_header',(0,0,2),(3,0.2,3))
v,t,m=prepare_mesh(bpy.context,[left,right,header],Matrix.Identity(4),settings)
assert np.isclose(m['volume'],1.4),m
assert len(try_rectangular_wall(v,t,settings))==3
bpy.ops.object.select_all(action='DESELECT')
for part in (left,right,header):
    part.select_set(True)
bpy.context.view_layer.objects.active=left
bpy.ops.object.join()
v,t,m=prepare_mesh(bpy.context,[left],Matrix.Identity(4),settings)
assert np.isclose(m['volume'],1.4),m
assert len(try_rectangular_wall(v,t,settings))==3
print('PREPROCESS_PASS touching_boxes touching_joined_boxes')
from collision_preprocess import evaluated_meshes
hidden=cube('hidden_modified',(0,0,0),(1,1,1))
hidden.modifiers.new('Subdiv','SUBSURF')
private=bpy.data.collections.new('private_canonical')
bpy.context.scene.collection.children.link(private)
private.objects.link(hidden)
for collection in list(hidden.users_collection):
    if collection != private:
        collection.objects.unlink(hidden)
bpy.context.view_layer.update()
v_visible,t_visible,m_visible=prepare_mesh(bpy.context,[hidden],Matrix.Identity(4),settings)
private.hide_viewport=True
hidden.hide_viewport=True
hidden.hide_set(True)
bpy.context.view_layer.update()
original_collections=set(bpy.data.collections)
original_links=list(hidden.users_collection)
original_name=hidden.name
v_hidden,t_hidden,m_hidden=prepare_mesh(bpy.context,[hidden],Matrix.Identity(4),settings)
assert len(v_hidden)==len(v_visible) and len(v_hidden)>len(hidden.data.vertices),(len(v_visible),len(v_hidden))
assert np.allclose(v_visible,v_hidden) and np.array_equal(t_visible,t_hidden)
assert hidden.hide_viewport and hidden.hide_get() and private.hide_viewport
assert list(hidden.users_collection)==original_links and hidden.name==original_name
assert set(bpy.data.collections)==original_collections
try:
    with evaluated_meshes(bpy.context,[hidden]) as graph:
        assert len(hidden.evaluated_get(graph).data.vertices)==len(v_visible)
        raise RuntimeError('injected_failure')
except RuntimeError as error:
    assert str(error)=='injected_failure'
assert hidden.hide_viewport and hidden.hide_get() and private.hide_viewport
assert list(hidden.users_collection)==original_links
assert set(bpy.data.collections)==original_collections
print('PREPROCESS_PASS hidden_collection_modifiers visibility_restored exception_cleanup')