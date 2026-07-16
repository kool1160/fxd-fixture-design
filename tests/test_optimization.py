import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile

from fxd_geometry import (
    CostAssumptions, CostRateTable, OcpKernel, OptimizationError,
    analyze_fixture_cost, build_manufacturing_export_package,
    generate_fixture_concepts, generate_manufacturing_assembly, import_step,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"


class OptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fxd_geometry import EngineeringAnnotations, Vec3
        cls.product = import_step(FIXTURE)
        annotations = EngineeringAnnotations.for_product(
            cls.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=40,
        )
        cls.annotations = annotations
        cls.concept = generate_fixture_concepts(cls.product, annotations).recommended
        cls.assembly = generate_manufacturing_assembly(cls.product, cls.concept, OcpKernel())
        cls.validation = SimpleNamespace(blocked=False, source_sha256=cls.product.source_sha256,
                                          concept_identity=cls.concept.identity, evidence_digest="validation-evidence")

    def analyze(self, *, validation=None, **kwargs):
        return analyze_fixture_cost(self.assembly, validation=validation or self.validation, **kwargs)

    def test_deterministic_total_breakdown_and_json(self):
        first, second = self.analyze(), self.analyze()
        self.assertTrue(first.valid, first.findings)
        self.assertEqual(first.evidence_digest, second.evidence_digest)
        self.assertEqual(first.to_dict(), second.to_dict())
        summary = first.summary
        assert summary is not None
        expected = sum((summary.engineering_cost, summary.programming_cost, summary.fixture_build_cost,
                        summary.commissioning_cost, summary.maintenance_allowance, summary.replacement_allowance))
        self.assertEqual(summary.total_estimated_cost, expected)
        self.assertEqual(summary.currency, "USD")

    def test_material_and_process_costs_are_traceable(self):
        result = self.analyze()
        assert result.summary is not None
        material = next(item.material for item in result.summary.component_costs if item.material)
        assert material is not None
        self.assertGreater(material.mass_kg, 0)
        self.assertIn("volume_mm3", material.evidence.formula)
        self.assertTrue(all(item.evidence.rule_id == "m25_process_time"
                             for component in result.summary.component_costs for item in component.processes))

    def test_volume_scenarios_and_recommendations_are_deterministic(self):
        result = self.analyze(production_quantity=1000)
        self.assertEqual(tuple(item.identity for item in result.scenarios),
                         ("prototype", "low-volume", "medium-volume", "high-volume"))
        self.assertEqual(len(result.recommendations), 4)
        self.assertGreater(result.scenarios[-1].fixture_count, 1)
        self.assertIn("engineering", result.recommendations[0].explanation)

    def test_rate_units_currency_and_upstream_gates_fail_closed(self):
        with self.assertRaises(OptimizationError):
            CostAssumptions(currency="")
        with self.assertRaises(OptimizationError):
            CostRateTable(material_cost_per_kg={"mild_steel": -1})
        blocked = replace(self.assembly, findings=())
        result = analyze_fixture_cost(blocked, validation=self.validation)
        self.assertFalse(result.blocked)
        invalid_validation = SimpleNamespace(blocked=True, source_sha256=self.product.source_sha256,
                                             concept_identity=self.concept.identity)
        self.assertTrue(self.analyze(validation=invalid_validation).blocked)

    def test_identity_mismatch_and_project_intent_evidence(self):
        invalid = SimpleNamespace(blocked=False, source_sha256="wrong", concept_identity=self.concept.identity)
        result = analyze_fixture_cost(self.assembly, validation=invalid)
        self.assertIn("source_identity_mismatch", {item.code for item in result.findings})
        self.assertIn("notice", result.to_dict())

    def test_export_contains_cost_review_files_and_rejects_tampering(self):
        result = self.analyze()
        files = build_manufacturing_export_package(self.assembly, self.validation, optimization=result)
        self.assertIn("fixture-cost-summary.json", files)
        self.assertIn("volume-scenarios.json", files)
        tampered = replace(result, rate_table=CostRateTable(process_cost_per_hour={"laser_cut": 999.0}))
        with self.assertRaises(Exception):
            build_manufacturing_export_package(self.assembly, self.validation, optimization=tampered)

    def test_project_persistence_preserves_optimization_intent_and_revision_identity(self):
        from dataclasses import replace
        from fxd_geometry.project import FxdProject
        project = FxdProject.from_product(self.product, self.annotations)
        intent = self.analyze().to_dict()
        saved = replace(project, optimization_intent=intent)
        self.assertNotEqual(project.revision_id, saved.revision_id)
        with tempfile.TemporaryDirectory() as directory:
            restored = FxdProject.load(saved.save(Path(directory) / "project.fxd.json"))
        self.assertEqual(restored.optimization_intent, intent)


if __name__ == "__main__":
    unittest.main()
