import tempfile
import unittest
from pathlib import Path

from fxd_geometry import EngineeringAnnotations, Vec3, import_step
from fxd_geometry.project import FxdProject, ProjectFormatError


class EditRegenerateTests(unittest.TestCase):
    def setUp(self):
        product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.project = FxdProject.from_product(
            product, EngineeringAnnotations.for_product(
                product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
                process_type="manual MIG", production_quantity=10))

    def test_supported_parameter_edit_creates_revision_and_regenerates(self):
        original = self.project.active.fixture.parameters.base_thickness
        edited = self.project.edit_parameter("base_thickness", original + 2, "datum plate change")
        self.assertNotEqual(edited.revision_id, self.project.revision_id)
        self.assertEqual(edited.active.fixture.parameters.base_thickness, original + 2)
        self.assertEqual(edited.product.source_bytes, self.project.product.source_bytes)
        self.assertIsNone(edited.approved_revision)
        self.assertEqual(edited.revisions[-1].evidence_digest, edited.active_validation.evidence_digest)

    def test_move_resize_replace_and_restore_are_restricted(self):
        moved = self.project.edit_feature("support-1", "move", (1, 2, 3), "access adjustment")
        self.assertNotEqual(moved.active.fixture.features[1].bounds,
                            self.project.active.fixture.features[1].bounds)
        resized = moved.edit_feature("support-1", "resize", {"x": 25}, "contact area")
        self.assertEqual(resized.active.fixture.features[1].bounds.maximum.x -
                         resized.active.fixture.features[1].bounds.minimum.x, 25)
        replaced = resized.edit_feature("round-pin-1", "replace", "relieved_locator", "thermal float")
        self.assertEqual(replaced.active.fixture.features[-2].kind, "relieved_locator")
        restored = replaced.restore(self.project.revision_id)
        self.assertEqual(restored.active.fixture.parameters, self.project.active.fixture.parameters)
        self.assertEqual(restored.edit_log, ())
        with self.assertRaisesRegex(ProjectFormatError, "unsupported"):
            self.project.edit_parameter("arbitrary_geometry", 1)
        with self.assertRaisesRegex(ProjectFormatError, "unsupported feature edit"):
            self.project.edit_feature("support-1", "freeform", {})

    def test_compare_and_project_round_trip_preserve_revision_evidence(self):
        edited = self.project.edit_parameter("contact_clearance", 0.8, "fit review")
        comparison = edited.compare(self.project.revision_id)
        self.assertEqual(comparison["other_validation"], self.project.active_validation.status)
        with tempfile.TemporaryDirectory() as directory:
            restored = FxdProject.load(edited.save(Path(directory) / "edited.fxd.json"))
        self.assertEqual(restored.revision_id, edited.revision_id)
        self.assertEqual(restored.edit_log, edited.edit_log)
        self.assertEqual(restored.active.fixture.parameters.contact_clearance, 0.8)
        self.assertEqual(restored.product.source_sha256, edited.product.source_sha256)


if __name__ == "__main__":
    unittest.main()
