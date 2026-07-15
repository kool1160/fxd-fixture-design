import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fxd_geometry import EngineeringAnnotations, ValidationResult, Vec3, import_step
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

    def test_sequential_edits_replay_from_canonical_baseline_without_compounding(self):
        original = self.project.active.fixture.parameters.base_thickness
        first = self.project.edit_parameter("base_thickness", original + 2)
        second = first.edit_parameter("contact_clearance", 0.8)
        self.assertEqual(second.active.fixture.parameters.base_thickness, original + 2)
        self.assertEqual(second.active.fixture.parameters.contact_clearance, 0.8)
        self.assertEqual(len({item.revision_id for item in second.revisions}), len(second.revisions))

    def test_move_resize_replace_and_restore_are_restricted(self):
        moved = self.project.edit_feature("support-1", "move", (1, 2, 3), "access adjustment")
        original_support = next(x for x in self.project.active.fixture.features if x.identity == "support-1")
        moved_support = next(x for x in moved.active.fixture.features if x.identity == "support-1")
        self.assertNotEqual(moved_support.bounds, original_support.bounds)
        resized = moved.edit_feature("support-1", "resize", {"x": 25}, "contact area")
        support = next(x for x in resized.active.fixture.features if x.identity == "support-1")
        self.assertEqual(support.bounds.maximum.x - support.bounds.minimum.x, 25)
        replaced = resized.edit_feature("round-pin-1", "replace", "relieved_locator", "thermal float")
        locator = next(x for x in replaced.active.fixture.features if x.identity == "round-pin-1")
        self.assertEqual(locator.kind, "relieved_locator")
        self.assertEqual(locator.manufacturing.method, "laser_cut")
        self.assertEqual(locator.manufacturing.interface, "tab_and_slot")
        restored = replaced.restore(self.project.revision_id)
        self.assertEqual(restored.active.fixture.parameters, self.project.active.fixture.parameters)
        self.assertEqual(restored.edit_log, ())
        self.assertEqual(restored.revision_id, self.project.revision_id)
        self.assertEqual(len({item.revision_id for item in restored.revisions}), len(restored.revisions))
        with self.assertRaisesRegex(ProjectFormatError, "unsupported"):
            self.project.edit_parameter("arbitrary_geometry", 1)
        with self.assertRaisesRegex(ProjectFormatError, "unsupported feature edit"):
            self.project.edit_feature("support-1", "freeform", {})

    def test_fit_locator_and_clamp_parameters_change_engineering_contracts(self):
        edited = self.project.edit_parameter("fit", "slip_fit")
        edited = edited.edit_parameter("locator_type", "relieved_locator")
        edited = edited.edit_parameter("clamp_choice", "toggle_clamp")
        locator = next(x for x in edited.active.fixture.features if x.identity == "round-pin-1")
        self.assertEqual(locator.kind, "relieved_locator")
        self.assertEqual(locator.manufacturing.fit, "slip_fit")
        clamp_features = [x for x in edited.active.fixture.features
                          if x.kind == "clamp_mount" or x.identity.startswith("clamp")]
        for feature in clamp_features:
            self.assertEqual(feature.manufacturing.interface, "toggle_clamp")
            self.assertEqual(feature.parameters["clamp_choice"], "toggle_clamp")

    def test_revision_and_approval_are_bound_to_active_concept(self):
        if len(self.project.concepts) < 2:
            self.skipTest("fixture generator produced one concept")
        valid = ValidationResult(
            "fxd-validation-v1", self.project.active.identity,
            self.project.product.source_sha256, "mm", "valid", (), "valid-evidence")
        with patch("fxd_geometry.project.validate_fixture_concept", return_value=valid):
            approved = self.project.decide("approve_for_review", "reviewed")
            self.assertEqual(approved.approved_revision, approved.revision_id)
            switched = approved.with_concept(approved.concepts[1].identity)
        self.assertIsNone(switched.approved_revision)
        self.assertNotEqual(switched.revision_id, approved.revision_id)
        self.assertEqual(switched.revisions[-1].active_concept, switched.active_concept)

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
        self.assertEqual(restored.revisions[-1].active_concept, edited.active_concept)


if __name__ == "__main__":
    unittest.main()
