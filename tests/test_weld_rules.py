import math
import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, GeometryReference, Vec3, WeldJoint,
                          WeldRuleConfig, evaluate_weld_rules, generate_fixture_primitives,
                          import_step)


class WeldRuleTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        ref = GeometryReference("BRACKET_A", "BRACKET_BODY")
        base = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        self.annotations = EngineeringAnnotations(**{
            **base.__dict__, "weld_joints": (WeldJoint(
                "weld-1", (ref,), "manual MIG", sequence=1, direction=Vec3(1, 0, 0),
                heat_input=12, heat_input_units="J/mm", distortion_direction=Vec3(0, 0, 1),
                release_sequence=2),)})
        self.fixture = generate_fixture_primitives(self.product, self.annotations)

    def test_explicit_heat_and_clamp_conflict_are_traceable_warnings(self):
        result = evaluate_weld_rules(
            self.product, self.fixture, self.annotations,
            WeldRuleConfig(max_heat_input=10, heat_input_units="J/mm",
                           clamp_force_directions=(("support-1", Vec3(0, 0, 10)),)))
        codes = {item.code for item in result.warnings}
        self.assertIn("heat_input_exceeds_config", codes)
        self.assertIn("clamp_reinforces_distortion", codes)
        self.assertTrue(all(item.rule and item.confidence > 0 for item in result.findings))

    def test_opposing_force_is_distinct_from_perpendicular_force(self):
        opposing = evaluate_weld_rules(
            self.product, self.fixture, self.annotations,
            WeldRuleConfig(clamp_force_directions=(("support-1", Vec3(0, 0, -2)),)))
        self.assertTrue(any(item.identity.startswith("clamp-weld-1")
                            for item in opposing.recommendations))
        self.assertNotIn("clamp_perpendicular_to_distortion",
                         {item.code for item in opposing.findings})

        perpendicular = evaluate_weld_rules(
            self.product, self.fixture, self.annotations,
            WeldRuleConfig(clamp_force_directions=(("support-1", Vec3(1, 0, 0)),)))
        self.assertIn("clamp_perpendicular_to_distortion",
                      {item.code for item in perpendicular.warnings})
        self.assertFalse(any(item.identity.startswith("clamp-weld-1")
                             for item in perpendicular.recommendations))

    def test_invalid_force_directions_fail_before_analysis(self):
        for direction in (Vec3(0, 0, 0), Vec3(math.inf, 0, 0)):
            with self.subTest(direction=direction):
                with self.assertRaisesRegex(ValueError, "clamp force directions"):
                    WeldRuleConfig(clamp_force_directions=(("support-1", direction),))

    def test_missing_sequence_and_process_data_remain_explicit(self):
        ref = GeometryReference("BRACKET_A", "BRACKET_BODY")
        joint = WeldJoint("incomplete", (ref,))
        annotations = EngineeringAnnotations(**{**self.annotations.__dict__, "weld_joints": (joint,)})
        result = evaluate_weld_rules(self.product, self.fixture, annotations)
        self.assertTrue({"missing_process", "missing_tack_sequence", "missing_release_sequence",
                         "missing_weld_direction"}.issubset({item.code for item in result.warnings}))
        self.assertTrue(result.findings)

    def test_config_threshold_requires_units(self):
        with self.assertRaisesRegex(ValueError, "heat_input_units"):
            WeldRuleConfig(max_heat_input=10)


if __name__ == "__main__":
    unittest.main()
