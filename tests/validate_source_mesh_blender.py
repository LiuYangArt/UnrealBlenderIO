"""Validate source/collision separation with real UE FBXs in a fresh Blender process."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from io_scene_fbx import parse_fbx

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/nanite-source"
sys.path.insert(0, str(ROOT.parent))
from UnrealBlenderIO import UnrealBlenderIO as ubio
from UnrealBlenderIO import i18n
from UnrealBlenderIO.util import Const, load_static_mesh_session

manifest = json.loads((OUT / "ue_export.json").read_text(encoding="utf-8"))
result = {"blender": bpy.app.version_string, "checks": [], "roundtrip_files": []}


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for blocks in (bpy.data.collections, bpy.data.meshes, bpy.data.materials):
        for block in list(blocks):
            if block.users == 0 or blocks == bpy.data.collections:
                blocks.remove(block)


def geometry_rows(path):
    root, _ = parse_fbx.parse(str(path))
    objects = next(element for element in root.elems if element.id == b"Objects")
    rows = []
    for geom in objects.elems:
        if geom.id != b"Geometry" or geom.props[2] != b"Mesh":
            continue
        children = {element.id: element for element in geom.elems}
        vertices = children[b"Vertices"].props[0]
        indices = children[b"PolygonVertexIndex"].props[0]
        name = geom.props[1].decode("utf-8").split("\0", 1)[0]
        rows.append({"name": name, "vertices": len(vertices) // 3, "triangles": sum(i < 0 for i in indices),
                     "collision": name.upper().startswith(("UCX_", "UBX_", "USP_", "UCP_")),
                     "geometry_hash": hashlib.sha256(vertices.tobytes() + indices.tobytes()).hexdigest()})
    return rows


def check_import(session_path, collision=True):
    session, roots = ubio.import_static_mesh_session(str(session_path), import_collision=collision)
    sources = [obj for obj in bpy.data.objects if obj.type == "MESH" and not obj.get(Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME)]
    collisions = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.get(Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME)]
    assert sources, session_path
    assert all(len(obj.data.polygons) != 313 for obj in sources), "Fallback leaked into source objects"
    assert not any(len(mesh.vertices) == 149 for mesh in bpy.data.meshes), "Discarded fallback mesh datablock leaked"
    for obj in collisions:
        assert bpy.data.objects.get(obj[Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME]) in sources
    if not collision:
        assert not collisions
    return session, roots, sources, collisions


for label, record in manifest["static_sessions"].items():
    clear_scene()
    path = Path(record["session"])
    session, roots, sources, collisions = check_import(path)
    assert len(sources) == 1
    assert len(sources[0].data.vertices) == record["source_vertices"]
    assert len(sources[0].data.polygons) == record["source_triangles"]
    raw_collision = [row for row in geometry_rows(session["paths"]["collision_fbx"]) if row["collision"]]
    assert len(collisions) == len(raw_collision)
    assert sorted(len(obj.data.polygons) for obj in collisions) == sorted(row["triangles"] for row in raw_collision)
    assert not any(row["collision"] for row in geometry_rows(session["paths"]["source_fbx"]))
    sources[0].data.vertices[0].co.x += 0.01
    if collisions:
        collisions[0].data.vertices[0].co.x += 0.002
    edited = ubio.export_static_mesh_session_to_fbx(bpy.context, str(path), session)
    rows = geometry_rows(edited)
    assert sum(row["triangles"] for row in rows if not row["collision"]) == record["source_triangles"]
    assert sum(row["triangles"] for row in rows if row["collision"]) == sum(row["triangles"] for row in raw_collision)
    result["roundtrip_files"].append({"label": label, "path": edited, "triangles": record["source_triangles"], "collision_triangles": sum(row["triangles"] for row in raw_collision)})
    result["checks"].append({"case": "static_" + label, "vertices": len(sources[0].data.vertices), "triangles": len(sources[0].data.polygons), "collision_objects": len(collisions)})
    _, _, _, skipped = check_import(path, collision=False)
    assert not skipped

for label, session_path in manifest["bp_sessions"].items():
    clear_scene()
    path = Path(session_path)
    session, roots, sources, collisions = check_import(path)
    canonical = [obj for obj in sources if obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) == Const.BP_STATIC_MESH_ROLE_CANONICAL_OBJECT]
    instances = [obj for obj in sources if obj.get(Const.BP_STATIC_MESH_PROP_COLLECTION_ROLE) == Const.BP_STATIC_MESH_ROLE_COMPONENT_OBJECT]
    assert len(canonical) == len(session["assets"])
    assert len(instances) == len(session["components"])
    for obj in instances:
        original = bpy.data.objects[obj[Const.BP_STATIC_MESH_PROP_CANONICAL_OBJECT_NAME]]
        assert obj.data == original.data, "Shared asset instances lost linked data"
    if label == "shared_mixed":
        shared = [obj for obj in instances if obj.data.name == next(o.data.name for o in canonical if len(o.data.vertices) == 2413)]
        assert len(shared) == 2 and shared[0].parent != shared[1].parent
        mirrored = next(obj for obj in shared if obj.parent.scale.x < 0)
        assert tuple(round(v, 2) for v in mirrored.parent.scale) == (-1.5, 0.75, 1.0)
        related = [obj for obj in collisions if obj.get(Const.STATIC_MESH_PROP_COLLISION_TARGET_NAME) == mirrored.name]
        assert related and related[0].parent == mirrored.parent
    paths = ubio.export_static_mesh_session_to_fbx(bpy.context, str(path), session)
    for asset, edited in zip(session["assets"], paths):
        exported = geometry_rows(edited)
        expected = geometry_rows(asset["source_fbx"])
        assert sum(row["triangles"] for row in exported if not row["collision"]) == sum(row["triangles"] for row in expected)
        original_collision = [row for row in geometry_rows(asset["collision_fbx"]) if row["collision"]]
        assert sum(row["triangles"] for row in exported if row["collision"]) == sum(row["triangles"] for row in original_collision)
    result["checks"].append({"case": "bp_" + label, "canonical_meshes": len(canonical), "instances": len(instances), "collision_objects": len(collisions), "outgoing_files": len(paths)})
    _, _, _, skipped = check_import(path, collision=False)
    assert not skipped

# Invalid sessions must fail before clearing an existing imported scene.
for kind, original_path, old_version in [("static", manifest["static_sessions"]["wall"]["session"], "1.0"), ("bp", manifest["bp_sessions"]["wall"], "2.2")]:
    clear_scene()
    check_import(Path(original_path))
    before = set(bpy.data.objects)
    data = json.loads(Path(original_path).read_text(encoding="utf-8"))
    data["schema_version"] = old_version
    test_path = OUT / (kind + "_old_session.json")
    test_path.write_text(json.dumps(data), encoding="utf-8")
    try:
        ubio.import_static_mesh_session(str(test_path))
    except ValueError as exc:
        assert str(exc) == "unsupported_session_version"
    else:
        raise AssertionError("Old fallback-capable session was accepted")
    assert set(bpy.data.objects) == before
    data = json.loads(Path(original_path).read_text(encoding="utf-8"))
    target = data["paths"] if kind == "static" else data["assets"][0]
    target["collision_fbx"] = str(OUT / "missing_collision.fbx")
    test_path = OUT / (kind + "_missing_collision.json")
    test_path.write_text(json.dumps(data), encoding="utf-8")
    try:
        ubio.import_static_mesh_session(str(test_path))
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing collision file was silently ignored")
    assert set(bpy.data.objects) == before
    check_import(test_path, collision=False)
    result["checks"].append({"case": kind + "_reject_old_and_missing", "scene_preserved": True, "skip_collision_allows_missing_file": True})

i18n.load_translations(force=True)
translated = {}
for language in ("en_US", "zh_HANS"):
    bpy.context.preferences.view.language = language
    translated[language] = i18n.tr("report.static_mesh.unsupported_session_version")
assert translated["en_US"] != translated["zh_HANS"]
result["localized_errors"] = translated
result["passed"] = True
(OUT / "blender_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("SOURCE_MESH_BLENDER_PASS " + json.dumps(result, ensure_ascii=False))