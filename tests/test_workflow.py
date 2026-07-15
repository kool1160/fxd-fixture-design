import unittest
from pathlib import Path

from fxd_geometry import (
    Aabb, EngineeringAnnotations, GeometryReference, ReviewZone, SequencePlan,
    VALIDATION_VERSION, ValidationResult, Vec3, WeldJoint, WorkflowEnvelope,
    WorkflowError, WorkflowStep, compare_workflow_variants, evaluate_weld_rules,
    evaluate_workflow, generate_fixture_primitives, import_step,
)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        ref = GeometryReference("BRACKET_A", "BRACKET_BODY")
        base = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        self.annotations = base.__class__(**{**base.__dict__, "weld_joints": (
            WeldJoint("weld-1", (ref,), "manual MIG", sequence=1, release_sequence=2),)})
        self.fixture = generate_fixture_primitives(self.product, self.annotations)
        self.empty = lambda name: SequencePlan(name)

    def validation(self, status="valid", digest="validation-digest"):
        return ValidationResult(
            VALIDATION_VERSION, "concept-1", self.product.source_sha256, "mm",
            status, (), digest,
        )

    def evaluate(self, *, validation=None, weld=None, tack=None, clamp=None, release=None,
                 loading=None, zones=(), envelopes=(), variant_identity="manual", process="manual"):
        return evaluate_workflow(
            self.product, self.fixture, self.annotations,
            evaluate_weld_rules(self.product, self.fixture, self.annotations),
            validation or self.validation(),
            weld or self.empty("weld"), tack or self.empty("tack"),
            clamp or self.empty("clamp"), release or self.empty("release"),
            loading or self.empty("loading"), zones, envelopes,
            variant_identity=variant_identity, process=process,
        )

    def test_sequences_are_editable_and_missing_steps_are_traceable(self):
        weld = self.empty("weld").with_step(WorkflowStep("w1", 1, "weld", weld_joint_identity="weld-1"))
        updated = weld.with_step(WorkflowStep("w1", 1, "tack", weld_joint_identity="weld-1"))
        self.assertEqual(updated.steps[0].action, "tack")
        report = self.evaluate(weld=weld)
        self.assertIn("missing_sequence_step", {item.code for item in report.warnings})
        loading_visual = next(item for item in report.visual_items if item.identity == "loading")
        self.assertIn("missing_loading_sequence", loading_visual.findings)

    def test_zones_and_shared_envelopes_produce_linked_findings(self):
        ref = self.annotations.weld_joints[0].references[0]
        zone = ReviewZone("spatter-1", "spatter", (ref,), self.fixture.features[0].bounds)
        envelope = WorkflowEnvelope("robot-approach", "cobot", self.fixture.features[0].bounds,
                                    references=(ref,), process_data_complete=True)
        report = self.evaluate(zones=(zone,), envelopes=(envelope,), process="cobot")
        self.assertTrue(report.blocked)
        envelope_visual = next(item for item in report.visual_items if item.identity == "robot-approach")
        self.assertIn("approach_envelope_conflict", envelope_visual.findings)
        finding = next(item for item in report.findings if item.code == "approach_envelope_conflict")
        self.assertEqual(finding.workflow_identity, "robot-approach")
        self.assertEqual(finding.geometry_identity, self.fixture.features[0].identity)

    def test_loading_and_unloading_conflicts_are_distinct_and_traceable(self):
        loading = SequencePlan("loading", (WorkflowStep("load-part", 1, "load component"),))
        load = WorkflowEnvelope("load-path", "load", self.fixture.features[0].bounds,
                                process_data_complete=True)
        unload = WorkflowEnvelope("unload-path", "unload", self.fixture.features[0].bounds,
                                  process_data_complete=True)
        report = self.evaluate(loading=loading, envelopes=(load, unload))
        codes = {item.code for item in report.findings}
        self.assertIn("blocked_loading_path", codes)
        self.assertIn("blocked_unload_path", codes)
        self.assertNotIn("missing_loading_envelope", codes)
        self.assertNotIn("missing_unload_sequence_evidence", codes)

    def test_variants_require_manual_and_automated_reports_and_preserve_validation(self):
        manual = self.evaluate(variant_identity="manual", process="manual")
        robot = self.evaluate(variant_identity="robot", process="robot")
        comparison = compare_workflow_variants((manual, robot))
        self.assertTrue(comparison.all_deterministic_gates_pass)

        invalid_robot = self.evaluate(validation=self.validation("invalid"),
                                      variant_identity="robot-invalid", process="robot")
        comparison = compare_workflow_variants((manual, invalid_robot))
        self.assertFalse(comparison.all_deterministic_gates_pass)

        with self.assertRaises(WorkflowError):
            compare_workflow_variants((manual,))
        with self.assertRaises(WorkflowError):
            compare_workflow_variants((manual, self.evaluate(variant_identity="manual-2", process="manual")))

    def test_validation_identity_and_evidence_fail_closed(self):
        mismatched = ValidationResult(
            VALIDATION_VERSION, "concept-1", "wrong-source", "mm", "valid", (), "digest")
        with self.assertRaises(WorkflowError):
            self.evaluate(validation=mismatched)
        with self.assertRaises(WorkflowError):
            self.evaluate(validation=self.validation(digest=""))


if __name__ == "__main__":
    unittest.main()
