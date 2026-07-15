import json
import tempfile
import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, ExportError, OperationsError, ProjectRecovery,
                          StructuredLog, Vec3, export_project_package, import_step,
                          load_preferences, save_preferences)
from fxd_geometry.project import FxdProject


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        self.project = FxdProject.from_product(self.product, self.annotations)

    def test_project_v2_save_and_v1_load_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.project.save(Path(directory) / "fixture.fxd.json")
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(FxdProject.load(path).product.source_sha256, self.product.source_sha256)
            payload["format"] = "fxd-neutral-project-v1"
            legacy = Path(directory) / "legacy.fxd.json"
            legacy.write_text(json.dumps(payload))
            self.assertEqual(FxdProject.load(legacy).revision_id, self.project.revision_id)

    def test_autosave_recovery_logs_and_preferences_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            project_path = Path(directory) / "fixture.fxd.json"
            recovery = ProjectRecovery(project_path)
            recovery.autosave(self.project)
            self.assertTrue(recovery.available())
            self.assertEqual(recovery.recover().product.source_sha256, self.product.source_sha256)
            event = StructuredLog(Path(directory) / "diagnostics.jsonl").record("project_saved", revision=self.project.revision_id)
            self.assertEqual(event.event, "project_saved")
            preferences = Path(directory) / "preferences.json"
            save_preferences(preferences, {"theme": "light"})
            self.assertEqual(load_preferences(preferences)["theme"], "light")
            with self.assertRaises(OperationsError):
                save_preferences(preferences, {"engineering_rule": "bad"})

    def test_application_export_uses_review_gate_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ExportError):
                export_project_package(self.project, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
