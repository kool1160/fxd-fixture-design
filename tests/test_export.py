import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (AccessAnalysis, AccessFinding, ExportError,
                          EngineeringAnnotations, Vec3,
                          build_fabrication_package, generate_fixture_concepts,
                          import_step, validate_fixture_concept, write_fabrication_package)
from fxd_geometry.fixture import FixtureFinding


class FabricationExportTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0), process_type="MIG", production_quantity=1)

    def test_package_is_deterministic_and_reconciles_artifacts(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        first = build_fabrication_package(concept, "A")
        second = build_fabrication_package(concept, "A")
        self.assertEqual(first.files(), second.files())
        manifest = json.loads(first.manifest)
        bom = json.loads(first.bom)
        self.assertEqual(manifest["units"], "mm")
        self.assertFalse(manifest["production_approval"])
        self.assertIn("ENGINEERING_REVIEW_REQUIRED", first.step)
        self.assertIn("$INSUNITS", first.dxf)
        self.assertEqual(sum(item["quantity"] for item in bom["items"]), 9)

    def test_invalid_concept_is_not_exportable(self):
        concepts = generate_fixture_concepts(self.product, self.annotations)
        source = concepts.concepts[0]
        invalid = replace(source, fixture=replace(
            source.fixture,
            findings=source.fixture.findings + (FixtureFinding("blocked", "error", None, "blocked"),),
        ))
        with self.assertRaises(ExportError):
            build_fabrication_package(invalid)

    def test_blocked_access_is_not_exportable(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        access = AccessAnalysis("mm", (
            AccessFinding("blocked_unload_path", "error", "unload", "loading-stop",
                          "Unload envelope intersects the loading stop."),
        ))
        with self.assertRaisesRegex(ExportError, "blocked"):
            build_fabrication_package(concept, access=access)

    def test_invalid_validation_result_is_not_exportable(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        validation = validate_fixture_concept(self.product, concept)
        self.assertTrue(validation.blocked)
        with self.assertRaisesRegex(ExportError, "validation"):
            build_fabrication_package(concept, validation=validation)

    def test_write_has_expected_review_package(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        package = build_fabrication_package(concept, "B")
        with tempfile.TemporaryDirectory() as directory:
            paths = write_fabrication_package(package, directory)
            self.assertEqual([path.name for path in paths], list(package.files()))
            self.assertIn("engineering_review_required", (Path(directory) / "validation.json").read_text())


if __name__ == "__main__":
    unittest.main()
