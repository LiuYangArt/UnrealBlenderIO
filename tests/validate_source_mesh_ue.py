"""Run inside the open UE editor; exports only, never saves source assets."""
import importlib.util
import json
import sys
from pathlib import Path

import unreal

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/nanite-source"
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("ubio_source_validation", ROOT / "UnrealAsset/Python/UnrealBlenderIO.py")
ubio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ubio)
ubio.BP_STATIC_MESH_SESSION_DIR = str(OUT / "bp")
result = {"engine": unreal.SystemLibrary.get_engine_version(), "static_sessions": {}, "bp_sessions": {}}
result["dirty_before"] = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
result["selection_before"] = [a.get_path_name() for a in ubio.actor_subsys.get_selected_level_actors()]
assets = {
    "wall": "/Game/FDBattleEnvContent/Levels/Pool/Meshes/Whitebox/BLD/SM_BLD01WallE.SM_BLD01WallE",
    "beam": "/Game/FDBattleEnvContent/Meshes/Beams/Kits/SM_BeamKitFrameA.SM_BeamKitFrameA",
    "decal": "/Game/FDBattleEnvContent/Meshes/Beams/Kits/SM_BeamKitFrameA_Decal.SM_BeamKitFrameA_Decal",
}
for label, asset_path in assets.items():
    mesh = unreal.load_asset(asset_path)
    assert mesh is not None, asset_path
    folder = OUT / "static" / label
    folder.mkdir(parents=True, exist_ok=True)
    session = ubio.build_static_mesh_session_data(None, mesh, "source_validation_" + label, str(folder), "content_browser_asset")
    ubio.export_static_mesh_asset_to_fbx(mesh, session["paths"]["source_fbx"])
    ubio.export_static_mesh_collision_to_fbx(mesh, session["paths"]["collision_fbx"])
    session_file = folder / "session.json"
    ubio.save_static_mesh_session(str(session_file), session)
    description = mesh.get_static_mesh_description(0)
    result["static_sessions"][label] = {"session": str(session_file), "source_vertices": description.get_vertex_count(), "source_triangles": description.get_triangle_count(), "render_triangles": mesh.get_num_triangles(0)}

# Use the real Blueprint class as the session owner and explicit component fixtures,
# so validation does not require changing the user's current level or selection.
bp = unreal.load_asset("/Game/FDBattleEnvContent/Levels/Pool/Prefab/BP_BLD01WallE_SM")
owner = unreal.get_default_object(bp.generated_class())
for label, component_assets in {"wall": ["wall"], "shared_mixed": ["wall", "wall", "beam", "decal"]}.items():
    components = []
    for index, asset_label in enumerate(component_assets):
        transform = ubio.get_default_bp_static_mesh_transform_dict()
        transform["location"].update(x=index * 350.0, y=index * -25.0, z=index * 10.0)
        transform["rotation"]["z"] = index * 30.0
        transform["scale"].update(x=-1.5 if index == 1 else 1.0, y=0.75 if index == 1 else 1.0)
        components.append({"component_name": f"Mesh{index}", "asset_path": assets[asset_label],
                           "static_mesh": unreal.load_asset(assets[asset_label]), "parent_component_key": None,
                           "actor_local_transform": transform, "relative_transform": transform,
                           "world_transform": transform, "attach_chain": ["Root", f"Mesh{index}"], "visible": True})
    folder = OUT / "bp" / label
    folder.mkdir(parents=True, exist_ok=True)
    session, export_log = ubio.build_bp_static_mesh_session_data(owner, components, "source_bp_" + label, str(folder))
    for asset in session["assets"]:
        mesh = unreal.load_asset(asset["asset_path"])
        ubio.export_static_mesh_asset_to_fbx(mesh, asset["source_fbx"])
        ubio.export_static_mesh_collision_to_fbx(mesh, asset["collision_fbx"])
    session_file = folder / "session.json"
    ubio.save_static_mesh_session(str(session_file), session)
    ubio.write_bp_static_mesh_log(str(folder), "export_ue.json", export_log)
    result["bp_sessions"][label] = str(session_file)

empty = unreal.new_object(unreal.StaticMesh)
try:
    ubio.export_static_mesh_asset_to_fbx(empty, str(OUT / "must_not_export.fbx"))
except RuntimeError as exc:
    assert "static_mesh_source_data_unavailable" in str(exc), exc
    result["missing_source_rejected"] = True
else:
    raise AssertionError("Mesh without source data was exported")
assert not (OUT / "must_not_export.fbx").exists()

result["dirty_after"] = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
result["selection_after"] = [a.get_path_name() for a in ubio.actor_subsys.get_selected_level_actors()]
assert result["dirty_before"] == result["dirty_after"]
assert result["selection_before"] == result["selection_after"]
result["passed"] = True
(OUT / "ue_export.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("SOURCE_MESH_UE_PASS " + json.dumps(result))
