import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (
    EngineeringAnnotations, FixtureParameters, StructuralParameters, StructuralStrategy,
    Vec3, compare_structural_concepts, generate_fixture_concepts,
    generate_fixture_primitives, generate_structural_assembly, import_step,
    select_structural_strategy, validate_fixture_concept, validate_structural_assembly,
)
from fxd_geometry.fixture import FixtureFeature
from fxd_geometry.project import FxdProject
from fxd_geometry.aabb import Aabb


class StructuralConceptTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)
        self.fixture = generate_fixture_primitives(self.product, self.annotations)

    def test_baseplate_and_welded_frame_strategy_selection(self):
        strategy, _, _ = select_structural_strategy(self.product, self.annotations)
        self.assertEqual(strategy, StructuralStrategy.BASEPLATE)
        strategy, _, _ = select_structural_strategy(
            self.product, self.annotations,
            StructuralParameters(strategy_override=StructuralStrategy.WELDED_FRAME))
        self.assertEqual(strategy, StructuralStrategy.WELDED_FRAME)

    def test_complete_structure_is_connected_and_traceable(self):
        assembly = generate_structural_assembly(self.product, self.annotations, self.fixture)
        self.assertTrue(assembly.valid)
        self.assertTrue(assembly.load_paths)
        self.assertTrue(any(item.kind == "base_support" for item in assembly.members))
        self.assertTrue(any(item.kind == "riser" for item in assembly.members))
        self.assertTrue(all(item.source_references or item.kind in {"baseplate", "welded_frame_base", "frame_rail", "base_support"}
                            for item in assembly.members))
        self.assertTrue(all(item.rule and item.assumptions for item in assembly.members))

    def test_welded_frame_contains_structural_members(self):
        assembly = generate_structural_assembly(
            self.product, self.annotations, self.fixture,
            StructuralParameters(strategy_override=StructuralStrategy.WELDED_FRAME))
        self.assertEqual(assembly.strategy, StructuralStrategy.WELDED_FRAME)
        self.assertEqual(len([item for item in assembly.members if item.kind == "frame_rail"]), 4)
        self.assertTrue(assembly.valid)

    def test_disconnected_member_fails_closed(self):
        assembly = generate_structural_assembly(self.product, self.annotations, self.fixture)
        member = next(item for item in assembly.members if item.kind == "support")
        disconnected = replace(member, bounds=Aabb.from_values(10000, 10000, 10000, 10010, 10010, 10010))
        changed = replace(assembly, members=tuple(disconnected if item.identity == member.identity else item
                                                    for item in assembly.members))
        findings = validate_structural_assembly(changed)
        self.assertIn("disconnected_structural_member", {item.code for item in findings})

    def test_unsupported_feature_fails_before_structural_generation(self):
        unsupported = FixtureFeature(
            "unsupported", "free_form", Aabb.from_values(0, 0, 0, 1, 1, 1), (),
            "unsupported_rule", {}, assumptions=("unsupported test feature",))
        with self.assertRaisesRegex(ValueError, "unsupported fixture feature kind"):
            generate_structural_assembly(self.product, self.annotations,
                                         replace(self.fixture, features=self.fixture.features + (unsupported,)))

    def test_sizing_and_load_path_assumptions_are_explicit(self):
        assembly = generate_structural_assembly(self.product, self.annotations, self.fixture)
        self.assertIn(("base_support_count", 4), assembly.sizing_assumptions)
        self.assertTrue(all(path.assumptions and path.evidence for path in assembly.load_paths))
        self.assertTrue(any("force adequacy" in assumption for path in assembly.load_paths
                            for assumption in path.assumptions))

    def test_source_identity_is_preserved(self):
        assembly = generate_structural_assembly(self.product, self.annotations, self.fixture)
        self.assertEqual(assembly.source_sha256, self.product.source_sha256)
        self.assertEqual(self.product.source_bytes, Path("tests/fixtures/synthetic_assembly.step").read_bytes())

    def test_validation_rejects_foreign_structural_evidence(self):
        concept = generate_fixture_concepts(self.product, self.annotations).concepts[0]
        forged_structure = replace(concept.structure, source_sha256="foreign-source")
        result = validate_fixture_concept(self.product, replace(concept, structure=forged_structure))
        self.assertEqual(result.status, "invalid")
        self.assertIn("structural_identity_mismatch", {item.code for item in result.findings})

    def test_alternate_structures_are_comparable_without_overriding_status(self):
        concepts = generate_fixture_concepts(self.product, self.annotations).concepts
        comparison = compare_structural_concepts(concepts)
        self.assertEqual({item.concept_identity for item in comparison},
                         {item.identity for item in concepts})
        self.assertTrue(all(item.rationale for item in comparison))
        self.assertTrue(all(item.status in {"valid", "provisional", "invalid"} for item in comparison))

    def test_project_round_trip_regenerates_structure(self):
        project = FxdProject.from_product(self.product, self.annotations)
        with tempfile.TemporaryDirectory() as directory:
            path = project.save(Path(directory) / "fixture.fxd.json")
            restored = FxdProject.load(path)
        self.assertEqual(restored.active.structure, project.active.structure)
        self.assertEqual(restored.product.source_sha256, project.product.source_sha256)


if __name__ == "__main__":
    unittest.main()
