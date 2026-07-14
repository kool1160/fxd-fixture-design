import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, FixtureFinding, Vec3,
                          generate_fixture_concepts, import_step,
                          validate_fixture_concept)


class ValidationPipelineTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0), process_type="manual MIG",
            production_quantity=10)
        self.concept = generate_fixture_concepts(self.product, self.annotations).recommended

    def test_pipeline_is_versioned_deterministic_and_separates_subsystems(self):
        first = validate_fixture_concept(self.product, self.concept)
        second = validate_fixture_concept(self.product, self.concept)
        self.assertEqual(first, second)
        self.assertEqual(first.version, "fxd-validation-v1")
        self.assertEqual(first.status, "invalid")
        self.assertTrue(any(item.code == "fixture_product_collision" for item in first.findings))
        self.assertTrue({item.subsystem for item in first.findings} >=
                        {"access", "weld", "clamp", "manufacturing"})
        self.assertTrue(first.evidence_digest)

    def test_known_concept_error_is_invalid_and_export_gate_can_use_result(self):
        invalid = replace(self.concept, fixture=replace(
            self.concept.fixture,
            findings=self.concept.fixture.findings +
            (FixtureFinding("unsafe_fixture", "error", None, "synthetic unsafe case"),)))
        result = validate_fixture_concept(self.product, invalid)
        self.assertTrue(result.blocked)
        self.assertTrue(any(item.code == "unsafe_fixture" for item in result.findings))

    def test_repeatability_gap_is_an_error(self):
        from fxd_geometry import LocatingStrategy
        strategy = LocatingStrategy((), tolerance_mm=0.1, repeatability_mm=0.2)
        concept = generate_fixture_concepts(self.product, self.annotations,
                                             locating_strategy=strategy).concepts[0]
        result = validate_fixture_concept(self.product, concept)
        self.assertTrue(any(item.code == "repeatability_exceeds_tolerance" and
                            item.severity == "error" for item in result.findings))


if __name__ == "__main__":
    unittest.main()
