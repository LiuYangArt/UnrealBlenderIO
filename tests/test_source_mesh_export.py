import ast
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


class SourceMeshExportTests(unittest.TestCase):
    def setUp(self):
        self.output = tempfile.TemporaryDirectory()
        self.addCleanup(self.output.cleanup)
        self.tasks = []

        def export(task):
            self.tasks.append(task)
            Path(task.filename).write_bytes(b"test fbx")
            return True

        self.api = SimpleNamespace(
            FbxExportOption=SimpleNamespace,
            AssetExportTask=lambda: SimpleNamespace(errors=[]),
            StaticMeshExporterFBX=lambda: SimpleNamespace(run_asset_export_task=export),
            GeometryScript_AssetUtils=SimpleNamespace(get_num_static_mesh_lods_of_type=Mock(return_value=0)),
            GeometryScriptLODType=SimpleNamespace(HI_RES_SOURCE_MODEL="HI_RES"),
        )
        names = {"export_static_mesh_asset_to_fbx", "export_static_mesh_collision_to_fbx", "_export_static_mesh_fbx"}
        tree = ast.parse((ROOT / "UnrealAsset/Python/UnrealBlenderIO.py").read_text(encoding="utf-8"))
        functions = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
        self.namespace = {"unreal": self.api, "os": os, "ensure_directory": lambda path: os.makedirs(path, exist_ok=True),
                          "log_static_mesh_info": Mock(), "log_static_mesh_error": Mock()}
        exec(compile(functions, "UnrealBlenderIO.py", "exec"), self.namespace)
        self.mesh = Mock()
        self.mesh.get_path_name.return_value = "/Game/Test.Test"
        self.mesh.get_editor_property.return_value = SimpleNamespace(enabled=True)
        self.mesh.get_static_mesh_description.return_value = SimpleNamespace(get_triangle_count=lambda: 4712, get_vertex_count=lambda: 2413)

    def path(self, name):
        return os.path.join(self.output.name, name)

    def test_source_and_collision_never_share_export_options(self):
        self.namespace["export_static_mesh_asset_to_fbx"](self.mesh, self.path("source.fbx"))
        self.namespace["export_static_mesh_collision_to_fbx"](self.mesh, self.path("collision.fbx"))
        source, collision = self.tasks
        self.assertTrue(source.options.export_source_mesh)
        self.assertFalse(source.options.collision)
        self.assertFalse(source.options.level_of_detail)
        self.assertFalse(collision.options.export_source_mesh)
        self.assertTrue(collision.options.collision)
        self.assertFalse(collision.options.level_of_detail)

    def test_valid_nanite_hires_does_not_require_source_lod0(self):
        self.api.GeometryScript_AssetUtils.get_num_static_mesh_lods_of_type.return_value = 1
        self.mesh.get_static_mesh_description.side_effect = AssertionError("HiRes should take precedence")
        self.namespace["export_static_mesh_asset_to_fbx"](self.mesh, self.path("hires.fbx"))
        self.assertTrue(self.tasks[0].options.export_source_mesh)
        self.assertTrue(any("NANITE_HI_RES" in str(call) for call in self.namespace["log_static_mesh_info"].call_args_list))

    def test_no_source_fails_before_any_export(self):
        self.mesh.get_static_mesh_description.return_value = None
        with self.assertRaisesRegex(RuntimeError, "static_mesh_source_data_unavailable"):
            self.namespace["export_static_mesh_asset_to_fbx"](self.mesh, self.path("source.fbx"))
        self.assertFalse(self.tasks)
        self.assertFalse(Path(self.path("source.fbx")).exists())

    def test_disabled_nanite_ignores_hires(self):
        self.mesh.get_editor_property.return_value = SimpleNamespace(enabled=False)
        self.namespace["export_static_mesh_asset_to_fbx"](self.mesh, self.path("source.fbx"))
        self.api.GeometryScript_AssetUtils.get_num_static_mesh_lods_of_type.assert_not_called()
        self.mesh.get_static_mesh_description.assert_called_once_with(0)

    def test_missing_nanite_inspection_support_fails_closed(self):
        del self.api.GeometryScript_AssetUtils
        with self.assertRaisesRegex(RuntimeError, "geometry_script_required"):
            self.namespace["export_static_mesh_asset_to_fbx"](self.mesh, self.path("source.fbx"))
        self.assertFalse(self.tasks)


if __name__ == "__main__":
    unittest.main()