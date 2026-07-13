import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, FixtureCorrection, Vec3,
                          generate_fixture_concepts, import_step)


class CompleteConceptTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=10)

    def test_generates_ranked_alternatives_with_explainable_scores(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        self.assertEqual([item.identity for item in result.ranked],
                         [item.identity for item in sorted(result.concepts,
                                                           key=lambda item: (-item.score.total, item.identity))])
        self.assertEqual(len(result.concepts), 3)
        self.assertTrue(all(item.score.breakdown and item.score.rationale for item in result.concepts))
        self.assertTrue(all(any(f.kind == "clamp_mount" for f in item.fixture.features) for item in result.concepts))

    def test_constraint_warnings_are_deterministic_and_visible(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        findings = {finding.code for finding in result.ranked[0].fixture.findings}
        self.assertIn("underconstrained", findings)
        self.assertIn("rotation_validation_unavailable", findings)
        self.assertEqual(result.ranked[0].constraints.rotational_status,
                         "requires_geometry_kernel_contact_validation")

    def test_correction_is_copy_on_write_and_source_is_unchanged(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        concept = result.ranked[0]
        edited = concept.with_correction(FixtureCorrection("clamp_force", "review", "force data missing"))
        self.assertEqual(concept.corrections, ())
        self.assertEqual(edited.corrections[0].key, "clamp_force")
        self.assertEqual(self.product.source_bytes, Path("tests/fixtures/synthetic_assembly.step").read_bytes())


if __name__ == "__main__":
    unittest.main()
