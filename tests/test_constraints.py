import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, GeometryReference, LocatorContact,
                          LocatingStrategy, Vec3, analyze_locating_strategy,
                          generate_fixture_concepts, import_step)


class ConstraintSolverTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.ref = GeometryReference("BRACKET_A", "BRACKET_BODY")

    def test_valid_explicit_three_two_one_strategy_is_full_rank(self):
        contacts = (
            LocatorContact("rest-a", "rest", self.ref, Vec3(0, 0, 0), Vec3(0, 0, 1)),
            LocatorContact("rest-b", "rest", self.ref, Vec3(20, 0, 0), Vec3(0, 0, 1)),
            LocatorContact("rest-c", "rest", self.ref, Vec3(0, 20, 0), Vec3(0, 0, 1)),
            LocatorContact("stop-a", "stop", self.ref, Vec3(0, 0, 0), Vec3(1, 0, 0)),
            LocatorContact("stop-b", "stop", self.ref, Vec3(0, 20, 0), Vec3(1, 0, 0)),
            LocatorContact("side", "diamond_pin", self.ref, Vec3(0, 0, 0), Vec3(0, 1, 0)),
        )
        result = analyze_locating_strategy(self.product, LocatingStrategy(
            contacts, tolerance_mm=0.1, repeatability_mm=0.05,
            datum_assumptions=("primary plane is the three rest contacts",)))
        self.assertEqual(result.rank, 6)
        self.assertTrue(result.strategy_valid)
        self.assertEqual(result.uncontrolled_dofs, ())

    def test_redundant_and_underconstrained_cases_are_deterministic(self):
        contact = LocatorContact("rest-a", "rest", self.ref, Vec3(0, 0, 0), Vec3(0, 0, 1))
        duplicate = LocatorContact("rest-b", "rest", self.ref, Vec3(0, 0, 0), Vec3(0, 0, 1))
        result = analyze_locating_strategy(self.product, LocatingStrategy((contact, duplicate)))
        codes = {item.code for item in result.findings}
        self.assertIn("underconstrained", codes)
        self.assertIn("redundant_constraint", codes)
        self.assertFalse(result.strategy_valid)

    def test_invalid_explicit_strategy_cannot_be_recommended(self):
        annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        strategy = LocatingStrategy((LocatorContact(
            "only-rest", "rest", self.ref, Vec3(0, 0, 0), Vec3(0, 0, 1)),))
        result = generate_fixture_concepts(self.product, annotations, locating_strategy=strategy)
        self.assertIsNone(result.recommended)
        self.assertTrue(all(item.engineering_status == "invalid" for item in result.concepts))


if __name__ == "__main__":
    unittest.main()
