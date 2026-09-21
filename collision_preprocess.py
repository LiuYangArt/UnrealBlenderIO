"""Collision input normalization; distances and volumes are expressed in metres."""
import numpy as np
from contextlib import contextmanager


@contextmanager
def evaluated_meshes(context, objects):
    """Evaluate modifiers of hidden canonical sources, restoring visibility on exit."""
    import bpy
    sources = list(dict.fromkeys(objects))
    visibility = [(obj, obj.hide_viewport,
                   obj.hide_get(view_layer=context.view_layer) if obj.name in context.view_layer.objects else None)
                  for obj in sources]
    collection = bpy.data.collections.new('UBIO_EVALUATE_COLLISION')
    try:
        context.scene.collection.children.link(collection)
        for obj in sources:
            collection.objects.link(obj)
            obj.hide_viewport = False
        context.view_layer.update()
        for obj in sources:
            obj.hide_set(False, view_layer=context.view_layer)
        context.view_layer.update()
        yield context.evaluated_depsgraph_get()
    finally:
        for obj, hidden_viewport, hidden_layer in visibility:
            if hidden_layer is not None:
                obj.hide_set(hidden_layer, view_layer=context.view_layer)
            obj.hide_viewport = hidden_viewport
        bpy.data.collections.remove(collection)
        context.view_layer.update()


def _clean(vertices, triangles):
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int32).reshape(-1,3)
    components = list(_components(triangles))
    if len(components) <= 1:
        return _clean_component(vertices, triangles)
    # Preserve disconnected shells, including open eye/head surfaces touching at a vertex.
    groups = components
    cleaned_vertices, cleaned_triangles = [], []
    offset = 0
    for indices in groups:
        used, remap = np.unique(triangles[indices], return_inverse=True)
        cv, ct = _clean_component(vertices[used], remap.reshape(-1,3))
        cleaned_vertices.append(cv)
        cleaned_triangles.append(ct+offset)
        offset += len(cv)
    return np.concatenate(cleaned_vertices), np.concatenate(cleaned_triangles).astype(np.int32)


def _clean_component(vertices, triangles):
    import bmesh
    bm = bmesh.new()
    try:
        verts = [bm.verts.new(v) for v in vertices]
        seen = set()
        for face in triangles:
            key = tuple(sorted(int(i) for i in face))
            if len(set(key)) != 3 or key in seen:
                continue
            seen.add(key)
            bm.faces.new([verts[int(i)] for i in face])
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-8)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.verts.index_update()
        return (np.asarray([tuple(v.co) for v in bm.verts], dtype=np.float64),
                np.asarray([[v.index for v in f.verts] for f in bm.faces], dtype=np.int32).reshape(-1, 3))
    finally:
        bm.free()

def _edge_counts(triangles):
    edges = np.sort(np.concatenate((triangles[:, :2], triangles[:, 1:], triangles[:, ::2])), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return int(np.count_nonzero(counts == 1)), int(np.count_nonzero(counts > 2))



def _cap_boundaries(bm):
    """Fill coplanar boundary rings together so nested window rings stay hollow."""
    import bmesh
    remaining = {edge for edge in bm.edges if edge.is_boundary}
    planar_groups, nonplanar = [], []
    while remaining:
        seed = remaining.pop()
        edges, pending = [seed], list(seed.verts)
        while pending:
            vertex = pending.pop()
            for edge in vertex.link_edges:
                if edge in remaining:
                    remaining.remove(edge)
                    edges.append(edge)
                    pending.extend(edge.verts)
        points = np.asarray([tuple(v.co) for v in {v for edge in edges for v in edge.verts}])
        center = points.mean(axis=0)
        _, _, axes = np.linalg.svd(points - center, full_matrices=True)
        normal = axes[-1]
        tolerance = max(float(np.ptp(points, axis=0).max()) * 1e-6, 1e-7)
        if np.max(np.abs((points - center) @ normal)) > tolerance:
            nonplanar.append(edges)
            continue
        for group_normal, group_center, group_tolerance, group_edges in planar_groups:
            if (abs(float(normal @ group_normal)) > 1 - 1e-6 and
                    np.max(np.abs((points - group_center) @ group_normal)) <= max(tolerance, group_tolerance)):
                group_edges.extend(edges)
                break
        else:
            planar_groups.append((normal, center, tolerance, edges))
    before = len(bm.faces)
    for normal, _, _, edges in planar_groups:
        bmesh.ops.triangle_fill(bm, edges=edges, normal=tuple(normal), use_beauty=True)
    for edges in nonplanar:
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    return len(bm.faces) - before


def repair_open_mesh(vertices, triangles):
    """Cap open boundaries on disposable BMeshes, without editing scene geometry."""
    import bmesh
    repaired_vertices, repaired_triangles = [], []
    offset = 0
    boundary_before, non_manifold_before = _edge_counts(triangles)
    diagnostics = dict(boundary_edges_before=boundary_before,
                       non_manifold_edges_before=non_manifold_before,
                       repair_faces_added=0)
    for indices in _components(triangles):
        used, remap = np.unique(triangles[indices], return_inverse=True)
        cv, ct = vertices[used], remap.reshape(-1, 3).astype(np.int32)
        # Capping a sheet cannot create thickness; preserve it for the input check.
        if not _closed(ct) and np.linalg.matrix_rank(cv - cv.mean(axis=0), tol=1e-8) == 3:
            bm = bmesh.new()
            try:
                verts = [bm.verts.new(point) for point in cv]
                for face in ct:
                    bm.faces.new([verts[int(i)] for i in face])
                boundary = [edge for edge in bm.edges if edge.is_boundary]
                if boundary:
                    diagnostics['repair_faces_added'] += _cap_boundaries(bm)
                    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
                    bmesh.ops.triangulate(bm, faces=list(bm.faces))
                    bm.verts.index_update()
                    cv = np.asarray([tuple(v.co) for v in bm.verts], dtype=np.float64)
                    ct = np.asarray([[v.index for v in face.verts] for face in bm.faces], dtype=np.int32)
            finally:
                bm.free()
        repaired_vertices.append(cv)
        repaired_triangles.append(ct + offset)
        offset += len(cv)
    v, t = np.concatenate(repaired_vertices), np.concatenate(repaired_triangles)
    boundary_after, non_manifold_after = _edge_counts(t)
    diagnostics.update(boundary_edges_after=boundary_after, non_manifold_edges_after=non_manifold_after)
    return v, t, diagnostics


def _components(triangles):
    by_vertex = {}
    for i, face in enumerate(triangles):
        for v in face:
            by_vertex.setdefault(int(v), []).append(i)
    remaining = set(range(len(triangles)))
    while remaining:
        stack = [remaining.pop()]
        result = []
        while stack:
            f = stack.pop()
            result.append(f)
            for v in triangles[f]:
                for other in by_vertex.pop(int(v), ()):
                    if other in remaining:
                        remaining.remove(other)
                        stack.append(other)
        yield result


def _closed(triangles):
    edges = {}
    for a, b, c in triangles:
        for u, v in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((int(u), int(v))))
            edges[key] = edges.get(key, 0) + 1
    return bool(edges) and all(count == 2 for count in edges.values())


def _volume(vertices, triangles):
    points = vertices - vertices.mean(axis=0)
    a, b, c = points[triangles].transpose(1, 0, 2)
    return abs(float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum())) / 6


def prepare_mesh(context, objects, frame, settings):
    """Collect evaluated geometry in the chosen asset frame; reject unsafe input."""
    vertices, triangles = [], []
    scale = float(context.scene.unit_settings.scale_length)
    inverse = frame.inverted()
    with evaluated_meshes(context, objects) as graph:
        for obj in objects:
            if obj.type != 'MESH':
                continue
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles()
                transform = inverse @ obj.matrix_world
                offset = len(vertices)
                vertices.extend(tuple((transform @ v.co) * scale) for v in mesh.vertices)
                triangles.extend(tuple(offset + i for i in t.vertices) for t in mesh.loop_triangles)
            finally:
                evaluated.to_mesh_clear()
    if not triangles:
        raise ValueError('empty_mesh')
    v, t = _clean(vertices, triangles)
    if not len(t) or not np.isfinite(v).all():
        raise ValueError('degenerate_mesh')
    boundary_edges, non_manifold_edges = _edge_counts(t)
    if boundary_edges or non_manifold_edges:
        v, t, repair = repair_open_mesh(v, t)
        print('[UBIO Collision] repair: ' + str(repair), flush=True)
    else:
        repair = dict(boundary_edges_before=0, non_manifold_edges_before=0, repair_faces_added=0, boundary_edges_after=0, non_manifold_edges_after=0)
    metrics = {'input_vertices': len(vertices), 'input_triangles': len(triangles),
               'filtered_components': 0, 'ground_vertices': 0, 'non_manifold_components': 0,
               'input_bounds_min_m': v.min(axis=0).tolist(),
               'input_bounds_max_m': v.max(axis=0).tolist()}
    metrics.update(repair)
    keep = []
    for indices in _components(t):
        faces = t[indices]
        points = v[np.unique(faces)]
        extents = np.ptp(points, axis=0)
        # PCA catches detached flakes that are not aligned with the asset axes.
        centered = points - points.mean(axis=0)
        _, _, axes = np.linalg.svd(centered, full_matrices=False)
        thickness = float(np.ptp(centered @ axes.T, axis=0).min())
        closed = _closed(faces)
        volume = _volume(v, faces) if closed else float(np.prod(extents))
        if not closed and thickness <= 1e-8:
            # A planar sheet has no solid thickness to preserve.
            p = v[faces]
            area = np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1).sum()/2
            small_area = max(settings.get('feature_size', 0)**2,
                             settings.get('min_volume', 0)/max(settings.get('min_thickness', 0), 1e-6))
            if area > small_area or small_area <= 0:
                raise ValueError('open_mesh')
        if thickness < settings.get('min_thickness', 0) or volume < settings.get('min_volume', 0):
            metrics['filtered_components'] += 1
            continue
        if not closed:
            # CoACD preprocesses volumetric non-manifold input before decomposition.
            metrics['non_manifold_components'] += 1
        if volume <= 1e-15:
            raise ValueError('degenerate_mesh')
        keep.extend(indices)
    if not keep:
        raise ValueError('empty_after_filter')
    t = t[keep]
    used, remap = np.unique(t, return_inverse=True)
    v, t = v[used], remap.reshape(-1, 3).astype(np.int32)
    feature = settings.get('feature_size', 0)
    if settings.get('ground') and feature > 0:
        # Only compress protrusions above a proven dominant horizontal support plane.
        p = v[t]
        cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        horizontal = (np.abs(cross[:, :2]).max(axis=1) < 1e-9) & (cross[:, 2] > 1e-10)
        levels = {}
        for face, normal in zip(p[horizontal], cross[horizontal]):
            z = round(float(face[:, 2].mean()), 7)
            levels[z] = levels.get(z, 0) + float(normal[2]) / 2
        if levels:
            level = max(levels, key=levels.get)
            above = v[:, 2] > level + 1e-7
            if (above.any() and v[:, 2].max() - level <= feature and
                    levels[level] >= sum(levels.values()) * 0.75):
                candidate = v.copy()
                candidate[above, 2] = level
                cv, ct = _clean(candidate, t)
                if _closed(ct) and _volume(cv, ct) > 1e-15:
                    metrics['ground_vertices'] = int(above.sum())
                    v, t = cv, ct
    metrics.update(vertices=len(v), triangles=len(t), volume=_volume(v, t),
                   bounds_min_m=v.min(axis=0).tolist(), bounds_max_m=v.max(axis=0).tolist(),
                   dimensions_m=np.ptp(v, axis=0).tolist())
    metrics.update(rectangular_wall_metrics(v, t, settings))
    return v, t, metrics


def _box(low, high):
    vertices = np.array([[low[0], low[1], low[2]], [high[0], low[1], low[2]],
                         [high[0], high[1], low[2]], [low[0], high[1], low[2]],
                         [low[0], low[1], high[2]], [high[0], low[1], high[2]],
                         [high[0], high[1], high[2]], [low[0], high[1], high[2]]], dtype=np.float64)
    faces = np.array([(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
                      (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)], dtype=np.int32)
    return vertices, faces


def _rectangular_wall_grid(vertices, triangles):
    """Prove an orthogonal constant-depth solid before sampling grid occupancy."""
    v, t = np.asarray(vertices), np.asarray(triangles)
    if not len(t):
        return None
    extent = np.ptp(v, axis=0)
    depth = int(np.argmin(extent))
    axes = [i for i in range(3) if i != depth]
    if extent[depth] <= 1e-8:
        return None
    coords = [np.unique(np.round(v[:, a], 7)) for a in range(3)]
    if len(coords[depth]) != 2:
        return None
    normals = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    sizes = np.linalg.norm(normals, axis=1)
    if np.any(sizes < 1e-12):
        return None
    if np.any((np.abs(normals) > sizes[:, None] * 1e-6).sum(axis=1) != 1):
        return None
    x, y = (coords[a] for a in axes)
    if (len(x)-1)*(len(y)-1) > 4096:
        return None
    front = t[np.all(np.abs(v[t, depth] - coords[depth][0]) < 1e-7, axis=1)]
    back = t[np.all(np.abs(v[t, depth] - coords[depth][-1]) < 1e-7, axis=1)]
    if not len(front) or not len(back):
        return None
    def occupancy(faces):
        result = np.zeros((len(x)-1, len(y)-1), dtype=bool)
        tri = v[faces][:, :, axes]
        for i in range(len(x)-1):
            for j in range(len(y)-1):
                point = np.array([(x[i]+x[i+1])/2, (y[j]+y[j+1])/2])
                edge = np.roll(tri, -1, axis=1)-tri
                delta = point-tri
                signs = edge[:, :, 0]*delta[:, :, 1]-edge[:, :, 1]*delta[:, :, 0]
                result[i,j] = np.any(np.all(signs >= -1e-10, axis=1) | np.all(signs <= 1e-10, axis=1))
        return result
    occupied = occupancy(front)
    if not np.array_equal(occupied, occupancy(back)):
        return None
    expected_volume = float(((np.diff(x)[:,None]*np.diff(y)[None,:])*occupied).sum()*extent[depth])
    # Reject overlapping disconnected shells, missing side surfaces and false projections.
    if not _closed(t) or not np.isclose(_volume(v,t), expected_volume, rtol=1e-5, atol=1e-10):
        return None
    return v, axes, x, y, occupied


def _empty_regions(occupied):
    remaining = set(map(tuple, np.argwhere(~occupied)))
    while remaining:
        seed = remaining.pop()
        pending, cells = [seed], [seed]
        while pending:
            i, j = pending.pop()
            for point in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
                if point in remaining:
                    remaining.remove(point)
                    pending.append(point)
                    cells.append(point)
        yield cells


def _fill_small_gaps(occupied, x, y, feature):
    result = occupied.copy()
    if feature <= 0:
        return result
    for cells in _empty_regions(occupied):
        indices = np.array(cells)
        low, high = indices.min(axis=0), indices.max(axis=0)+1
        widths = [x[high[0]]-x[low[0]], y[high[1]]-y[low[1]]]
        # Protect a large connected opening even when it has a narrow neck or arm.
        for axis in (0,1):
            if widths[axis] > feature:
                continue
            grid = occupied if axis == 0 else occupied.T
            transposed = indices if axis == 0 else indices[:,::-1]
            bounded = True
            for col in np.unique(transposed[:,1]):
                rows = transposed[transposed[:,1] == col,0]
                first, last = int(rows.min()), int(rows.max())
                if first == 0 or last+1 == grid.shape[0] or not grid[first-1,col] or not grid[last+1,col]:
                    bounded = False
                    break
            if bounded:
                result[indices[:,0],indices[:,1]] = True
                break
    return result


def rectangular_wall_metrics(vertices, triangles, settings):
    """Report only proved rectangular clearances, measured in asset X/Y and Z."""
    grid = _rectangular_wall_grid(vertices, triangles)
    result = {'opening_measurement': 'unsupported', 'openings_before': [], 'openings_after': []}
    if grid is None:
        return result
    _, axes, x, y, occupied = grid
    if axes[1] != 2:
        return result
    result['opening_measurement'] = 'rectangular_only'
    def openings(mask):
        measured = []
        for cells in _empty_regions(mask):
            indices = np.array(cells)
            low, high = indices.min(axis=0), indices.max(axis=0)+1
            if len(cells) != int(np.prod(high-low)):
                continue
            # Doorways may touch the bottom; unbounded outer silhouette is not a window.
            if low[0] == 0 or high[0] == mask.shape[0] or high[1] == mask.shape[1]:
                continue
            measured.append({'width_m': float(x[high[0]]-x[low[0]]),
                             'height_m': float(y[high[1]]-y[low[1]]),
                             'bottom_m': float(y[low[1]]),
                             'horizontal_min_m': float(x[low[0]]),
                             'horizontal_axis': axes[0]})
        return measured
    result['openings_before'] = openings(occupied)
    result['openings_after'] = openings(_fill_small_gaps(occupied,x,y,settings.get('feature_size',0)))
    return result


def try_rectangular_wall(vertices, triangles, settings):
    """Exact boxes for proven orthogonal constant-depth solids, otherwise None."""
    grid = _rectangular_wall_grid(vertices, triangles)
    if grid is None:
        return None
    v, axes, x, y, original = grid
    occupied = _fill_small_gaps(original,x,y,float(settings.get('feature_size',0)))
    boxes = []
    remaining = occupied.copy()
    for i in range(remaining.shape[0]):
        for j in range(remaining.shape[1]):
            if not remaining[i,j]:
                continue
            end_x = i+1
            while end_x < remaining.shape[0] and remaining[end_x,j]:
                end_x += 1
            end_y = j+1
            while end_y < remaining.shape[1] and remaining[i:end_x,end_y].all():
                end_y += 1
            remaining[i:end_x,j:end_y] = False
            low, high = v.min(axis=0).copy(), v.max(axis=0).copy()
            low[axes], high[axes] = [x[i],y[j]], [x[end_x],y[end_y]]
            boxes.append(_box(low,high))
    return boxes or None