import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (
    AnnotationRole, EngineeringAnnotations, GeometryReference, InteractiveWorkflow,
    ManufacturingClassification, OcpKernel, ProcessSetup, ProductReconstruction,
    ProductReconstructionError, Vec3, face_annotation, load_step_for_workbench,
    product_from_workbench_document, reconstruct_product,
)
from fxd_geometry.project import FxdProject


class M33ProductReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = OcpKernel()

    def _document(self, dimensions=(120.0, 80.0, 8.0)):
        source = self.kernel.export_step(self.kernel.make_box((0, 0, 0), dimensions))
        return source, load_step_for_workbench(source, source_name="synthetic-m33-plate.step")

    def test_reconstruction_is_deterministic_source_bound_and_exact(self):
        source, document = self._document()
        product = product_from_workbench_document(document)
        first = reconstruct_product(document, product)
        second = reconstruct_product(document, product)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.reconstruction_identity, first.expected_identity())
        self.assertEqual(first.source_sha256, document.source_sha256)
        self.assertEqual(document.source_bytes, source)
        self.assertEqual(len(first.components), 1)
        self.assertEqual(len(first.bodies), 1)
        self.assertEqual(len(first.faces), 6)
        self.assertEqual(len(first.planes), 6)
        self.assertTrue(first.datum_contact_candidates)
        self.assertEqual(
            first.components[0].manufacturing_classification,
            ManufacturingClassification.PLATE_SHEET,
        )
        self.assertFalse(first.blocked)
        first.require_current_source(product)

    def test_cylindrical_evidence_records_axis_without_guessing_hole_meaning(self):
        source = self.kernel.export_step(
            self.kernel.make_cylinder((0, 0, 0), 5.0, 40.0)
        )
        document = load_step_for_workbench(source, source_name="synthetic-cylinder.step")
        product = product_from_workbench_document(document)
        reconstruction = reconstruct_product(document, product)

        self.assertEqual(len(reconstruction.axes), 1)
        self.assertEqual(len(reconstruction.hole_evidence), 1)
        hole = reconstruction.hole_evidence[0]
        self.assertFalse(hole.confirmed)
        self.assertEqual(hole.interpretation, "cylindrical_feature_candidate")
        self.assertIn("internal hole", hole.ambiguity[0])
        self.assertEqual(
            reconstruction.components[0].manufacturing_classification,
            ManufacturingClassification.UNKNOWN,
        )
        self.assertTrue(reconstruction.blocked)

    def test_explicit_classification_override_is_traceable(self):
        source = self.kernel.export_step(self.kernel.make_box((0, 0, 0), (20, 20, 20)))
        document = load_step_for_workbench(source, source_name="ambiguous-block.step")
        product = product_from_workbench_document(document)
        unresolved = reconstruct_product(document, product)
        self.assertTrue(unresolved.blocked)

        resolved = reconstruct_product(
            document, product,
            classification_overrides={
                product.components[0].identity: ManufacturingClassification.MACHINED,
            },
        )
        self.assertFalse(resolved.blocked)
        self.assertEqual(
            resolved.components[0].classification_provenance,
            ("engineer_explicit_classification",),
        )

    def test_confirmed_weld_intent_is_distinct_from_candidates(self):
        _, document = self._document()
        product = product_from_workbench_document(document)
        component = product.components[0]
        face = document.assembly.components[0].faces[0]
        reference = GeometryReference(
            component.identity, component.bodies[0].identity, face.reference,
        )
        annotation = face_annotation(
            document, reference, AnnotationRole.WELD_JOINT,
            notes="Synthetic engineer-confirmed weld intent.",
        )
        workflow = InteractiveWorkflow(
            document.source_sha256,
            ProcessSetup("synthetic", manufacturing_process="MIG welding"),
            geometry_annotations=(annotation,),
        )
        reconstruction = reconstruct_product(document, product, workflow)
        self.assertEqual(reconstruction.weld_candidates, ())
        self.assertEqual(len(reconstruction.confirmed_weld_intent), 1)
        self.assertTrue(reconstruction.confirmed_weld_intent[0].engineer_confirmed)
        self.assertFalse(any(
            item.category == "weld_intent" for item in reconstruction.unresolved_questions
        ))

    def test_project_v6_persists_reconstruction_and_v5_migrates_without_it(self):
        _, document = self._document()
        product = product_from_workbench_document(document)
        annotations = EngineeringAnnotations.for_product(
            product, build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0), process_type="review", production_quantity=1,
        )
        workflow = InteractiveWorkflow(
            product.source_sha256, ProcessSetup("reconstruction-persistence"),
        )
        reconstruction = reconstruct_product(document, product, workflow)
        project = FxdProject.from_product(
            product, annotations, workflow=workflow,
        ).with_product_reconstruction(reconstruction)

        with tempfile.TemporaryDirectory() as directory:
            path = project.save(Path(directory) / "m33.fxd.json")
            restored = FxdProject.load(path)
            self.assertEqual(
                restored.product_reconstruction.to_dict(), reconstruction.to_dict()
            )
            legacy = project.to_dict()
            legacy["format"] = "fxd-neutral-project-v5"
            legacy["schema_version"] = 5
            legacy.pop("product_reconstruction")
            legacy.pop("ai_execution")
            legacy_path = Path(directory) / "legacy-v5.fxd.json"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            migrated = FxdProject.load(legacy_path)
            self.assertIsNone(migrated.product_reconstruction)
            self.assertIsNone(migrated.ai_execution)

    def test_tampered_or_stale_reconstruction_fails_closed(self):
        _, document = self._document()
        product = product_from_workbench_document(document)
        reconstruction = reconstruct_product(document, product)
        tampered = reconstruction.to_dict()
        tampered["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ProductReconstructionError, "identity"):
            ProductReconstruction.from_dict(tampered)
        other_source = self.kernel.export_step(
            self.kernel.make_box((0, 0, 0), (121, 80, 8))
        )
        other_document = load_step_for_workbench(other_source, source_name="changed.step")
        other_product = product_from_workbench_document(other_document)
        with self.assertRaisesRegex(ProductReconstructionError, "stale"):
            reconstruction.require_current_source(other_product)


if __name__ == "__main__":
    unittest.main()
