import unittest
from pathlib import Path

from fxd_geometry import (
    Aabb, EngineeringAnnotations, GeometryReference, ReviewZone, SequencePlan,
    Vec3, WeldJoint, WorkflowEnvelope, WorkflowError, WorkflowStep,
    compare_workflow_variants, evaluate_weld_rules, evaluate_workflow,
    generate_fixture_primitives, import_step,
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

    def test_sequences_are_editable_and_missing_steps_are_traceable(self):
        weld = self.empty("weld").with_step(WorkflowStep("w1", 1, "weld", weld_joint_identity="weld-1"))
        updated = weld.with_step(WorkflowStep("w1", 1, "tack", weld_joint_identity="weld-1"))
        self.assertEqual(updated.steps[0].action, "tack")
        report = evaluate_workflow(
            self.product, self.fixture, self.annotations,
            evaluate_weld_rules(self.product, self.fixture, self.annotations),
            weld, self.empty("tack"), self.empty("clamp"), self.empty("release"))
        self.assertIn("missing_sequence_step", {item.code for item in report.warnings})

    def test_zones_and_shared_envelopes_produce_linked_findings(self):
        ref = self.annotations.weld_joints[0].references[0]
        zone = ReviewZone("spatter-1", "spatter", (ref,), self.fixture.features[0].bounds)
        envelope = WorkflowEnvelope("robot-approach", "cobot", self.fixture.features[0].bounds,
                                    references=(ref,), process_data_complete=True)
        report = evaluate_workflow(
            self.product, self.fixture, self.annotations,
            evaluate_weld_rules(self.product, self.fixture, self.annotations),
            self.empty("weld"), self.empty("tack"), self.empty("clamp"), self.empty("release"),
            (zone,), (envelope,))
        self.assertTrue(report.blocked)
        self.assertEqual(report.visual_items[0].identity, "spatter-1")
        self.assertIn("approach_envelope_conflict", {item.code for item in report.findings})

    def test_variants_cannot_hide_blocked_report(self):
        report = evaluate_workflow(
            self.product, self.fixture, self.annotations,
            evaluate_weld_rules(self.product, self.fixture, self.annotations),
            self.empty("weld"), self.empty("tack"), self.empty("clamp"), self.empty("release"),
            envelopes=(WorkflowEnvelope("blocked-unload", "unload", self.fixture.features[0].bounds),),
            variant_identity="manual")
        comparison = compare_workflow_variants((report,))
        self.assertFalse(comparison.all_deterministic_gates_pass)
        with self.assertRaises(WorkflowError):
            compare_workflow_variants((report, report))


if __name__ == "__main__":
    unittest.main()
