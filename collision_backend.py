"""Single bundled convex-decomposition backend, with a fixed UE hull budget."""
import numpy as np

MAX_HULL_VERTICES = 64


def decompose(vertices, triangles, settings):
    import coacd
    coacd.set_log_level('warn')
    parts = coacd.run_coacd(
        coacd.Mesh(vertices, triangles),
        threshold=settings['error'], real_metric=True,
        max_convex_hull=settings['max_hulls'], preprocess_mode='auto',
        preprocess_resolution=30,
        resolution=500,
        mcts_nodes=10, mcts_iterations=20, mcts_max_depth=2,
        merge=True, decimate=True, max_ch_vertex=MAX_HULL_VERTICES,
        extrude=False, seed=0,
    )
    if not parts:
        raise ValueError('invalid_hull')
    if len(parts) > settings['max_hulls']:
        raise ValueError('hull_budget')
    return [(np.asarray(v, dtype=np.float64), np.asarray(f, dtype=np.int32)) for v, f in parts]
