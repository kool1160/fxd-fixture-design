import json
import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fxd_geometry import (
    ComponentGeometryError,
    DrawingDimension,
    DrawingPackageError,
    EngineeringAnnotations,
    OcpKernel,
    ValidationResult,
    Vec3,
    build_manufacturing_export_package,
    generate_drawing_package,
    generate_fixture_concepts,
    generate_manufacturing_assembly,
    import_step,
    validate_fixture_concept,
    validate_drawing_package,
    write_drawing_package,
)
from fxd_geometry.project import FxdProject


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"


class DrawingPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_bytes = FIXTURE.read_bytes()
        cls.product = import_step(FIXTURE)
        cls.annotations = EngineeringAnnotations.for_product(
            cls.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=1,
        )
        cls.concept = generate_fixture_concepts(cls.product, cls.annotations).recommended
        cls.assembly = generate_manufacturing_assembly(cls.product, cls.concept, OcpKernel())
        cls.validation = ValidationResult(
            "fxd-validation-v1", cls.concept.identity, cls.product.source_sha256,
            "mm", "provisional", (), "authoritative-review-digest",
        )

    def make_package(self):
        return generate_drawing_package(self.assembly, self.validation, revision="A")

    def test_required_and_fabricated_sheets_are_generated(self):
        package = self.make_package()
        identities = {item.identity for item in package.sheets}
        self.assertIn("fixture-assembly", identities)
        self.assertIn("exploded-assembly", identities)
        self.assertTrue(any(item.identity.startswith("component-") for item in package.sheets))
        self.assertTrue(any(item.identity.startswith("detail-") for item in package.sheets))
        self.assertEqual(tuple(item.sheet_number for item in package.sheets),
                         tuple(range(1, len(package.sheets) + 1)))

    def test_pdf_is_deterministic_and_contains_review_evidence(self):
        first = self.make_package()
        second = self.make_package()
        self.assertEqual(first.pdf_bytes, second.pdf_bytes)
        self.assertEqual(first.pdf_digest, second.pdf_digest)
        self.assertTrue(first.pdf_bytes.startswith(b"%PDF-1.4"))
        self.assertEqual(first.page_count, first.pdf_bytes.count(b"/Type /Page "))
        self.assertIn(b"ENGINEERING REVIEW REQUIRED", first.pdf_bytes)
        self.assertIn(b"NOT RELEASED FOR PRODUCTION", first.pdf_bytes)
        self.assertIn(b"FXD-M23-", first.pdf_bytes)

    def test_bom_hole_table_and_export_links_reconcile(self):
        package = self.make_package()
        component_ids = {item.identity for item in self.assembly.components}
        self.assertEqual({item.component_identity for item in package.bom}, component_ids)
        exports = {item.component_identity: item for item in self.assembly.exports}
        for item in package.bom:
            self.assertEqual(item.step_filename, exports[item.component_identity].step_filename)
            self.assertEqual(item.dxf_filename, exports[item.component_identity].dxf_filename)
        base_sheet = next(item for item in package.sheets if item.identity == "component-mfg-baseplate")
        self.assertEqual(len(base_sheet.hole_table), 4)
        self.assertTrue(any(item.kind == "plate-thickness" for item in base_sheet.dimensions))

    def assert_bom_mutation_blocked(self, mutated):
        findings = validate_drawing_package(self.assembly, mutated, self.validation)
        self.assertTrue(any(item.severity == "error" for item in findings))
        with self.assertRaises(ComponentGeometryError):
            build_manufacturing_export_package(self.assembly, self.validation, mutated)

    def test_bom_authoritative_fields_are_reconciled(self):
        package = self.make_package()
        first, second = package.bom[:2]
        mutations = (
            replace(first, part_number="WRONG-PART"),
            replace(first, revision="Z"),
            replace(first, quantity=first.quantity + 1),
            replace(first, material="wrong-material"),
            replace(first, process="wrong-process"),
            replace(first, step_filename="wrong.step"),
            replace(first, dxf_filename="wrong.dxf"),
        )
        for mutation in mutations:
            with self.subTest(field=mutation):
                self.assert_bom_mutation_blocked(replace(package, bom=(mutation,) + package.bom[1:]))
        self.assert_bom_mutation_blocked(replace(package, bom=(replace(second, item_number=first.item_number),) + package.bom[1:]))
        self.assert_bom_mutation_blocked(replace(package, bom=package.bom[:-1]))
        self.assert_bom_mutation_blocked(replace(package, bom=(replace(first, component_identity="orphan"),) + package.bom[1:]))

    def test_pdf_boundary_and_page_evidence_are_reconciled(self):
        package = self.make_package()

        def tamper(payload):
            return replace(package, pdf_bytes=payload, pdf_digest=hashlib.sha256(payload).hexdigest())

        missing_review = package.pdf_bytes.replace(b"ENGINEERING REVIEW REQUIRED", b"REVIEW ONLY")
        missing_release = package.pdf_bytes.replace(b"NOT RELEASED FOR PRODUCTION", b"RELEASE TEXT")
        bad_page = package.pdf_bytes.replace(b"/Type /Page ", b"/Type /Pge ", 1)
        missing_title = package.pdf_bytes.replace(b"FIXTURE ASSEMBLY", b"MISSING TITLE", 1)
        for label, payload in (("review", missing_review), ("release", missing_release),
                               ("page-count", bad_page), ("required-title", missing_title)):
            with self.subTest(reason=label):
                mutated = tamper(payload)
                findings = validate_drawing_package(self.assembly, mutated, self.validation)
                self.assertTrue(any(item.severity == "error" for item in findings))
                with self.assertRaises(ComponentGeometryError):
                    build_manufacturing_export_package(self.assembly, self.validation, mutated)

    def test_standalone_writer_revalidates_tampered_package(self):
        package = self.make_package()
        payload = package.pdf_bytes.replace(b"ENGINEERING REVIEW REQUIRED", b"REMOVED")
        tampered = replace(package, pdf_bytes=payload, pdf_digest=hashlib.sha256(payload).hexdigest(), findings=())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DrawingPackageError):
                write_drawing_package(tampered, directory, assembly=self.assembly, validation=self.validation)

    def test_package_integrates_with_manufacturing_export(self):
        package = self.make_package()
        files = build_manufacturing_export_package(self.assembly, self.validation, package)
        self.assertIn("fixture-drawings.pdf", files)
        self.assertIn("drawing-manifest.json", files)
        manifest = json.loads(files["drawing-manifest.json"])
        self.assertEqual(manifest["pdf_digest"], package.pdf_digest)
        self.assertIn("drawing-bom.json", files)
        self.assertEqual(validate_drawing_package(self.assembly, package, self.validation), ())
        validation_with_drawings = validate_fixture_concept(
            self.product, self.concept, drawing_package=package)
        self.assertFalse(any(item.subsystem == "drawings" and item.severity == "error"
                             for item in validation_with_drawings.findings))

    def test_blocked_evidence_fails_closed(self):
        with self.assertRaises(DrawingPackageError):
            generate_drawing_package(replace(self.assembly, findings=(
                replace(self.assembly.findings[0], severity="error") if self.assembly.findings else
                SimpleNamespace(severity="error"),
            )), self.validation)
        with self.assertRaises(DrawingPackageError):
            generate_drawing_package(self.assembly, replace(self.validation, status="invalid"))
        package = self.make_package()
        with self.assertRaises(ComponentGeometryError):
            build_manufacturing_export_package(self.assembly, self.validation,
                                                replace(package, source_sha256="wrong"))

    def test_contract_rejects_unsupported_tolerance_and_missing_title_data(self):
        with self.assertRaises(DrawingPackageError):
            DrawingDimension("d", "component", "hole", 4.0, ("geometry",), tolerance_mm=-0.1)

    def test_project_round_trip_preserves_regenerable_drawing_intent(self):
        package = self.make_package()
        project = FxdProject.from_product(self.product, self.annotations)
        project = replace(project, drawing_intent=package.intent_dict())
        with tempfile.TemporaryDirectory() as directory:
            path = project.save(Path(directory) / "project.fxd.json")
            restored = FxdProject.load(path)
        self.assertEqual(restored.drawing_intent, package.intent_dict())

    def test_write_package_and_source_are_stable(self):
        package = self.make_package()
        with tempfile.TemporaryDirectory() as directory:
            paths = write_drawing_package(package, directory,
                                          assembly=self.assembly, validation=self.validation)
            self.assertEqual([item.name for item in paths],
                             ["drawing-bom.json", "drawing-manifest.json", "fixture-drawings.pdf"])
            self.assertTrue((Path(directory) / "fixture-drawings.pdf").read_bytes().startswith(b"%PDF-1.4"))
        self.assertEqual(self.source_bytes, FIXTURE.read_bytes())


if __name__ == "__main__":
    unittest.main()
