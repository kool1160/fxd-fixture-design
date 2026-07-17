import importlib.util
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from fxd_geometry import (EngineeringAnnotations, ExportError, OperationsError, ProjectRecovery,
                          StructuredLog, Vec3, export_project_package, import_step,
                          load_preferences, save_preferences)
from fxd_geometry.project import FxdProject


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        self.project = FxdProject.from_product(self.product, self.annotations)

    def test_project_v3_save_and_true_v1_load_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.project.save(Path(directory) / "fixture.fxd.json")
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schema_version"], 3)
            self.assertEqual(FxdProject.load(path).product.source_sha256, self.product.source_sha256)
            payload["format"] = "fxd-neutral-project-v1"
            payload.pop("schema_version")
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

    def test_suppressed_or_corrected_project_cannot_reach_export_generation(self):
        clean_validation = SimpleNamespace(
            blocked=False, status="provisional", evidence_digest="evidence"
        )
        with patch.object(
            FxdProject, "active_validation", new_callable=PropertyMock,
            return_value=clean_validation,
        ):
            suppressed = replace(
                self.project, suppressed_features=frozenset({"support-1"})
            )
            corrected = self.project.correct("clamp_force", "review", "engineering correction")
            for project, message in (
                (suppressed, "suppressed fixture features"),
                (corrected, "active fixture corrections"),
            ):
                with self.subTest(message=message), tempfile.TemporaryDirectory() as directory, \
                        patch("fxd_geometry.operations.build_fabrication_package") as build:
                    with self.assertRaisesRegex(ExportError, message):
                        export_project_package(project, directory)
                    build.assert_not_called()
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_clean_validated_project_reaches_export_generation(self):
        clean_validation = SimpleNamespace(blocked=False)
        package = SimpleNamespace()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            FxdProject, "active_validation", new_callable=PropertyMock,
            return_value=clean_validation,
        ), patch(
            "fxd_geometry.operations.build_fabrication_package", return_value=package
        ) as build, patch(
            "fxd_geometry.operations.write_fabrication_package", return_value=()
        ) as write:
            self.assertEqual(export_project_package(self.project, directory), ())
        build.assert_called_once()
        write.assert_called_once_with(package, directory)

    def test_large_legally_shareable_assembly_has_a_measured_budget(self):
        performance = _load_script("fxd_performance_budget", ROOT / "scripts" / "performance_budget.py")
        result = performance.measure()
        self.assertGreaterEqual(result["components"], performance.INSTANCE_COUNT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["fixture"], "generated legally shareable large_synthetic_assembly.step")

    def test_release_manifest_only_hashes_explicit_reviewed_artifacts(self):
        manifest_script = _load_script("fxd_release_manifest", ROOT / "scripts" / "release-manifest.py")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temp_root = Path(directory)
            artifact = temp_root / "fxd-app.zip"
            artifact.write_bytes(b"reviewed-build")
            private = temp_root / ".fxd" / "customer.step"
            private.parent.mkdir()
            private.write_bytes(b"private")
            output = temp_root / "manifest.json"
            relative_artifact = artifact.relative_to(ROOT).as_posix()
            manifest = manifest_script.build_manifest("0.1.0", output, [relative_artifact], root=ROOT)
            self.assertEqual(list(manifest["files"]), [relative_artifact])
            self.assertFalse(manifest["production_approval"])
            with self.assertRaises(ValueError):
                manifest_script.build_manifest(
                    "0.1.0", output, [private.relative_to(ROOT).as_posix()], root=ROOT)


if __name__ == "__main__":
    unittest.main()
