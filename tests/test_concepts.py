import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, FixtureCorrection, FixtureFinding,
                          GeometryReference, Vec3, generate_fixture_concepts, import_step)


class CompleteConceptTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=10)

    def test_generates_ranked_alternatives_with_explainable_scores(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        self.assertEqual(len(result.concepts), 3)
        self.assertTrue(all(item.score.breakdown and item.score.rationale for item in result.concepts))
        self.assertTrue(all(any(f.kind == "clamp_mount" for f in item.fixture.features) for item in result.concepts))
        self.assertTrue(all(item.engineering_status == "provisional" for item in result.concepts))
        self.assertIs(result.recommended, result.ranked[0])

    def test_constraint_warnings_are_deterministic_and_visible(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        findings = {finding.code for finding in result.ranked[0].fixture.findings}
        self.assertIn("underconstrained", findings)
        self.assertIn("rotation_validation_unavailable", findings)
        self.assertEqual(result.ranked[0].constraints.rotational_status,
                         "requires_geometry_kernel_contact_validation")

    def test_invalid_concept_cannot_outrank_or_be_recommended_over_eligible_concept(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        highest_score = max(result.concepts, key=lambda item: item.score.total)
        invalid_fixture = replace(
            highest_score.fixture,
            findings=highest_score.fixture.findings + (
                FixtureFinding("forbidden_contact", "error", "loading-stop",
                               "deterministic forbidden contact"),
            ),
        )
        invalid = replace(highest_score, identity="concept-invalid-high-score", fixture=invalid_fixture)
        eligible = min(result.concepts, key=lambda item: item.score.total)
        mixed = replace(result, concepts=(invalid, eligible))
        self.assertEqual(invalid.engineering_status, "invalid")
        self.assertEqual(eligible.engineering_status, "provisional")
        self.assertIs(mixed.ranked[0], eligible)
        self.assertIs(mixed.recommended, eligible)

    def test_all_invalid_concepts_have_no_recommendation(self):
        annotations = replace(
            self.annotations,
            forbidden_contact_areas=(GeometryReference("BRACKET_A", "BRACKET_BODY"),),
        )
        result = generate_fixture_concepts(self.product, annotations)
        self.assertTrue(all(item.engineering_status == "invalid" for item in result.concepts))
        self.assertIsNone(result.recommended)

    def test_correction_is_copy_on_write_and_source_is_unchanged(self):
        result = generate_fixture_concepts(self.product, self.annotations)
        concept = result.ranked[0]
        edited = concept.with_correction(FixtureCorrection("clamp_force", "review", "force data missing"))
        self.assertEqual(concept.corrections, ())
        self.assertEqual(edited.corrections[0].key, "clamp_force")
        self.assertEqual(self.product.source_bytes, Path("tests/fixtures/synthetic_assembly.step").read_bytes())


if __name__ == "__main__":
    unittest.main()
