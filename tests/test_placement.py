import json
from dataclasses import replace
from pathlib import Path
import unittest

from fxd_geometry import (
    DatumCandidate, EngineeringAnnotations, GeometryReference, PlacementError,
    PlacementRole, Vec3, generate_fixture_concepts, generate_placement_plan,
    import_step, rank_datum_candidates, validate_fixture_concept, validate_placement_plan,
)
from fxd_geometry.project import FxdProject


class PlacementEngineTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=10,
        )
        self.reference = GeometryReference("BRACKET_A", "BRACKET_BODY")
        self.candidates = tuple(
            DatumCandidate(
                f"datum-{index}", self.reference, position, Vec3(0, 0, 1),
                100.0 - index, 0.9, 0.9, 0.8, 0.1,
                ("caller supplied surface normal",), ("proof-layer face evidence",), 0.9,
            )
            for index, position in enumerate((Vec3(0, 0, 0), Vec3(20, 0, 0),
                                               Vec3(0, 20, 0), Vec3(30, 20, 0)), 1)
        )

    def test_valid_roles_are_generated_and_solver_is_authoritative(self):
        plan = generate_placement_plan(self.product, self.annotations, self.candidates)
        self.assertTrue(plan.valid)
        self.assertEqual({item.role for item in plan.placements}, {
            PlacementRole.PRIMARY_DATUM, PlacementRole.SECONDARY_DATUM,
            PlacementRole.TERTIARY_DATUM, PlacementRole.ROUND_PIN,
            PlacementRole.DIAMOND_PIN, PlacementRole.STOP, PlacementRole.SUPPORT,
            PlacementRole.CLAMP,
        })
        self.assertEqual(plan.locating_strategy and len(plan.locating_strategy.contacts), 6)

    def test_candidate_ranking_uses_explicit_evidence_and_fails_closed(self):
        scores = rank_datum_candidates(self.product, self.candidates, self.annotations)
        self.assertEqual(scores[0].candidate_identity, "datum-1")
        invalid = replace(self.candidates[0], reference=GeometryReference("missing"))
        invalid_scores = rank_datum_candidates(self.product, (invalid,), self.annotations)
        self.assertFalse(invalid_scores[0].eligible)
        self.assertIn("invalid", " ".join(invalid_scores[0].reasons))

    def test_source_identity_and_deterministic_json_digest(self):
        first = generate_placement_plan(self.product, self.annotations, self.candidates)
        second = generate_placement_plan(self.product, self.annotations, tuple(reversed(self.candidates)))
        self.assertEqual(first.source_sha256, self.product.source_sha256)
        self.assertEqual(first.evidence_digest, second.evidence_digest)
        json.dumps(first.to_dict(), sort_keys=True)
        restored = type(first).from_dict(first.to_dict())
        self.assertEqual(restored.to_dict(), first.to_dict())

    def test_project_round_trip_preserves_optional_placement(self):
        plan = generate_placement_plan(self.product, self.annotations, self.candidates)
        project = FxdProject.from_product(self.product, self.annotations, placement=plan)
        with __import__("tempfile").TemporaryDirectory() as directory:
            path = project.save(Path(directory) / "placement.fxd.json")
            restored = FxdProject.load(path)
        self.assertIsNotNone(restored.placement)
        self.assertEqual(restored.placement.evidence_digest, plan.evidence_digest)

    def test_duplicate_constraint_direction_fails_closed(self):
        plan = generate_placement_plan(self.product, self.annotations, self.candidates)
        stop = next(item for item in plan.placements if item.identity == "loading-stop")
        duplicate = replace(stop, identity="duplicate-stop")
        checked = replace(plan, placements=plan.placements + (duplicate,))
        findings = validate_placement_plan(self.product, checked)
        self.assertTrue(any(item.rule == "placement_duplicate_constraint_direction" for item in findings))

    def test_alternative_is_retained_for_review(self):
        plan = generate_placement_plan(self.product, self.annotations, self.candidates)
        self.assertEqual(len(plan.alternatives), 1)
        self.assertTrue(plan.alternatives[0].identity)

    def test_clamp_capacity_gate_and_standard_tooling(self):
        plan = generate_placement_plan(self.product, self.annotations, self.candidates)
        clamp = next(item for item in plan.placements if item.role == PlacementRole.CLAMP)
        self.assertEqual(clamp.tooling_identity, "generic-toggle-clamp")
        weak = replace(clamp, force_n=1.0)
        checked = replace(plan, placements=tuple(weak if item.identity == clamp.identity else item for item in plan.placements))
        findings = validate_placement_plan(self.product, checked)
        self.assertTrue(any(item.rule == "placement_clamp_capacity_insufficient" for item in findings))

    def test_missing_candidates_are_blocking_not_inferred(self):
        plan = generate_placement_plan(self.product, self.annotations, ())
        self.assertTrue(plan.blocked)
        self.assertTrue(any(item.rule == "placement_missing_datum_evidence" for item in plan.findings))

    def test_concept_validation_includes_placement_findings(self):
        plan = generate_placement_plan(self.product, self.annotations, ())
        concept = generate_fixture_concepts(self.product, self.annotations, placement=plan).concepts[0]
        result = validate_fixture_concept(self.product, concept)
        self.assertTrue(any(item.subsystem == "placement" for item in result.findings))

    def test_malformed_candidate_is_rejected(self):
        with self.assertRaises(PlacementError):
            DatumCandidate("bad", self.reference, Vec3(0, 0, 0), Vec3(0, 0, 0), 10, .5, .5, .5, .5)


if __name__ == "__main__":
    unittest.main()
