import math
import unittest
from pathlib import Path

from fxd_geometry import (Aabb, AccessAnalysisError, AccessEnvelope, EngineeringAnnotations,
                          GeometryReference, Vec3, WeldAccessRequest, evaluate_access,
                          WeldJoint, generate_fixture_primitives, import_step)


class AccessAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.joint_ref = GeometryReference("BRACKET_A", "BRACKET_BODY")
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        self.annotations = self.annotations.__class__(**{
            **self.annotations.__dict__, "weld_joints": (WeldJoint("weld-1", (self.joint_ref,), "manual MIG"),)
        })
        self.fixture = generate_fixture_primitives(self.product, self.annotations)

    def test_blocked_manual_and_robot_envelopes_are_reported_separately(self):
        requests = (
            WeldAccessRequest("manual-weld", "weld-1", AccessEnvelope(
                "manual-envelope", "manual", Aabb(Vec3(-1, -1, -1), Vec3(60, 60, 60)))),
            WeldAccessRequest("robot-weld", "weld-1", AccessEnvelope(
                "robot-envelope", "robot", Aabb(Vec3(40, 40, 40), Vec3(50, 50, 50)),
                direction=Vec3(0, 0, -1), reach=100, process_data_complete=True)),
        )
        result = evaluate_access(self.product, self.fixture, self.annotations, requests)
        self.assertTrue(result.blocked)
        self.assertEqual({item.code for item in result.findings if item.severity == "error"},
                         {"blocked_weld_approach"})
        self.assertTrue(any(item.request_identity == "manual-weld" for item in result.warnings))

    def test_clear_unload_path_and_missing_data_remain_explicit(self):
        result = evaluate_access(
            self.product, self.fixture, self.annotations,
            envelopes=(AccessEnvelope("unload", "unload", Aabb(Vec3(200, 200, 200), Vec3(210, 210, 210)),
                                      process_data_complete=True),))
        self.assertFalse(result.blocked)
        self.assertNotIn("blocked_unload_path", {item.code for item in result.findings})
        self.assertIn("missing_weld_access_intent", {item.code for item in result.findings})

    def test_unknown_joint_is_rejected(self):
        request = WeldAccessRequest("bad", "missing", AccessEnvelope(
            "manual", "manual", Aabb(Vec3(0, 0, 0), Vec3(1, 1, 1))))
        with self.assertRaisesRegex(AccessAnalysisError, "unknown weld joint"):
            evaluate_access(self.product, self.fixture, self.annotations, (request,))

    def test_target_must_exist_and_belong_to_selected_weld_joint(self):
        unknown_face = GeometryReference("BRACKET_A", "BRACKET_BODY", face_identity="MISSING_FACE")
        request = WeldAccessRequest("bad-face", "weld-1", AccessEnvelope(
            "manual-face", "manual", Aabb(Vec3(0, 0, 0), Vec3(1, 1, 1))),
            target_reference=unknown_face)
        with self.assertRaisesRegex(AccessAnalysisError, "unknown access face"):
            evaluate_access(self.product, self.fixture, self.annotations, (request,))

        unrelated = GeometryReference("BRACKET_B", "BRACKET_BODY")
        request = WeldAccessRequest("wrong-target", "weld-1", AccessEnvelope(
            "manual-target", "manual", Aabb(Vec3(0, 0, 0), Vec3(1, 1, 1))),
            target_reference=unrelated)
        with self.assertRaisesRegex(AccessAnalysisError, "does not belong to weld joint"):
            evaluate_access(self.product, self.fixture, self.annotations, (request,))

    def test_direction_must_be_finite(self):
        with self.assertRaisesRegex(AccessAnalysisError, "direction must be finite"):
            AccessEnvelope("bad-direction", "robot", Aabb(Vec3(0, 0, 0), Vec3(1, 1, 1)),
                           direction=Vec3(math.nan, 0, 1))


if __name__ == "__main__":
    unittest.main()
