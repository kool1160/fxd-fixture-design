import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (
    AnnotationRole, EngineeringAnnotations, GeometryReference, InteractiveWorkflow,
    KernelAssembly, KernelComponent, ManufacturingClassification, OcpKernel,
    ProcessSetup, ProductReconstruction,
    ProductReconstructionError, TopologyCounts, Vec3, face_annotation, load_step_for_workbench,
    product_from_workbench_document, reconstruct_product,
)
from fxd_geometry.project import FxdProject, ProjectFormatError


class _PreM33KernelFaceRepr:
    """Independent reproduction of the historical six-field dataclass repr."""

    def __init__(self, reference, face, surface_type):
        self.reference = reference
        self.face = face
        self.surface_type = surface_type

    def __repr__(self):
        return (
            f"KernelFace(reference={self.reference!r}, "
            f"area_mm2={self.face.area_mm2!r}, center_mm={self.face.center_mm!r}, "
            f"normal={self.face.normal!r}, surface_type={self.surface_type!r}, "
            f"is_planar={self.face.is_planar!r})"
        )


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

    def test_multi_solid_component_preserves_exact_body_face_ownership(self):
        source = self.kernel.export_step(self.kernel.compound((
            self.kernel.make_box((0, 0, 0), (40, 30, 4)),
            self.kernel.make_box((60, 0, 0), (100, 30, 4)),
        )))
        imported = load_step_for_workbench(source, source_name="multi-solid.step")
        combined = KernelComponent(
            "component:synthetic-multi-solid", "assembly:root", "multi-solid",
            (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
             0.0, 0.0, 1.0, 0.0),
            self.kernel.topology_counts(imported.shape), imported.bodies,
            imported.faces,
        )
        document = replace(imported, assembly=KernelAssembly(
            "assembly:root", imported.source_sha256, "mm", ("assembly:root",),
            (combined,),
        ))
        product = product_from_workbench_document(document)
        reconstruction = reconstruct_product(document, product)

        self.assertEqual(len(product.components), 1)
        self.assertEqual(len(product.components[0].bodies), 2)
        self.assertEqual(len(reconstruction.bodies), 2)
        self.assertTrue(all(
            item.topology == TopologyCounts(1, 1, 6, 12)
            for item in reconstruction.bodies
        ))
        owned = [set(item.face_identities) for item in reconstruction.bodies]
        self.assertTrue(all(len(item) == 6 for item in owned))
        self.assertFalse(owned[0] & owned[1])
        self.assertEqual(set.union(*owned), {item.identity for item in reconstruction.faces})
        self.assertEqual(
            reconstruction.components[0].manufacturing_classification,
            ManufacturingClassification.UNKNOWN,
        )
        self.assertTrue(reconstruction.blocked)

    def test_tube_and_formed_channel_remain_unknown(self):
        outer = self.kernel.make_box((0, 0, 0), (100, 40, 20))
        inner = self.kernel.make_box((-1, 3, 3), (101, 37, 17))
        tube = self.kernel.cut(outer, inner)
        channel = self.kernel.boolean(
            "fuse",
            self.kernel.boolean(
                "fuse",
                self.kernel.make_box((0, 0, 0), (100, 40, 3)),
                self.kernel.make_box((0, 0, 0), (100, 3, 20)),
            ),
            self.kernel.make_box((0, 37, 0), (100, 40, 20)),
        )
        for name, shape in (("tube", tube), ("formed-channel", channel)):
            with self.subTest(name=name):
                source = self.kernel.export_step(shape)
                document = load_step_for_workbench(source, source_name=f"{name}.step")
                reconstruction = reconstruct_product(
                    document, product_from_workbench_document(document),
                )
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
        component = product.components[0]
        body = component.bodies[0]
        face = body.faces[0]
        current_reference = GeometryReference(
            component.identity, body.identity, face.identity,
        )
        annotations = replace(EngineeringAnnotations.for_product(
            product, build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0), process_type="review", production_quantity=1,
        ), permitted_locating_surfaces=(current_reference,))
        geometry_annotation = face_annotation(
            document, current_reference, AnnotationRole.PRIMARY_DATUM,
            notes="Historical v5 exact-reference compatibility evidence.",
        )
        workflow = InteractiveWorkflow(
            product.source_sha256, ProcessSetup("reconstruction-persistence"),
            geometry_annotations=(geometry_annotation,),
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
            kernel_component = document.assembly.components[0]
            from OCP.GeomAbs import GeomAbs_Plane
            self.assertTrue(all(item.is_planar for item in kernel_component.faces))
            historical_faces = []
            historical_face_by_current = {}
            for kernel_face in kernel_component.faces:
                historical_face = "face:" + hashlib.sha256(repr((
                    kernel_face.area_mm2, kernel_face.center_mm,
                    kernel_face.normal, int(GeomAbs_Plane),
                )).encode()).hexdigest()[:24]
                historical_face_by_current[kernel_face.reference] = historical_face
                historical_faces.append(_PreM33KernelFaceRepr(
                    historical_face, kernel_face, "plane",
                ))
                self.assertEqual(kernel_face.legacy_reference, historical_face)
                self.assertNotEqual(kernel_face.reference, historical_face)
            legacy_payload = repr((
                (1,), kernel_component.name, kernel_component.transform,
                kernel_component.topology,
                tuple(sorted(historical_faces, key=lambda item: item.reference)),
            )).encode()
            legacy_component = (
                "component:" + hashlib.sha256(legacy_payload).hexdigest()[:24]
            )
            legacy_body = "body:" + hashlib.sha256(
                legacy_component.encode()
            ).hexdigest()[:20]
            self.assertEqual(kernel_component.legacy_reference, legacy_component)
            self.assertNotEqual(legacy_component, component.identity)
            self.assertNotEqual(legacy_body, body.identity)

            def use_historical_v5_identities(value):
                if isinstance(value, list):
                    return [use_historical_v5_identities(item) for item in value]
                if isinstance(value, dict):
                    migrated = {
                        key: use_historical_v5_identities(item)
                        for key, item in value.items()
                    }
                    if (migrated.get("component_identity") == component.identity
                            and any(key in migrated for key in (
                                "body_identity", "face_identity", "edge_identity",
                            ))):
                        migrated["component_identity"] = legacy_component
                        if migrated.get("body_identity") == body.identity:
                            migrated["body_identity"] = legacy_body
                        face_identity = migrated.get("face_identity")
                        if face_identity in historical_face_by_current:
                            migrated["face_identity"] = historical_face_by_current[
                                face_identity
                            ]
                    return migrated
                return value

            legacy = use_historical_v5_identities(legacy)
            legacy_path = Path(directory) / "legacy-v5.fxd.json"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            migrated = FxdProject.load(legacy_path)
            self.assertIsNone(migrated.product_reconstruction)
            self.assertIsNone(migrated.ai_execution)
            self.assertEqual(migrated.product.source_sha256, document.source_sha256)
            self.assertEqual(
                migrated.annotations.permitted_locating_surfaces,
                (current_reference,),
            )
            self.assertEqual(
                migrated.workflow.geometry_annotations[0].reference,
                current_reference,
            )
            self.assertEqual(
                migrated.product.components[0].bodies[0].identity,
                kernel_component.bodies[0].reference,
            )

            invalid = json.loads(json.dumps(legacy))
            invalid["annotations"]["permitted_locating_surfaces"][0][
                "component_identity"
            ] = "component:not-a-historical-alias"
            invalid_path = Path(directory) / "invalid-v5.fxd.json"
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ProjectFormatError, "unknown component reference"):
                FxdProject.load(invalid_path)

            invalid_face = json.loads(json.dumps(legacy))
            invalid_face["annotations"]["permitted_locating_surfaces"][0][
                "face_identity"
            ] = "face:not-a-historical-alias"
            invalid_face_path = Path(directory) / "invalid-face-v5.fxd.json"
            invalid_face_path.write_text(json.dumps(invalid_face), encoding="utf-8")
            with self.assertRaisesRegex(ProjectFormatError, "unknown face reference"):
                FxdProject.load(invalid_face_path)

        changed_workflow = replace(
            workflow,
            setup=replace(workflow.setup, manufacturing_process="TIG welding"),
        )
        with self.assertRaisesRegex(ProductReconstructionError, "workflow"):
            reconstruction.require_current_source(product, changed_workflow)
        changed = project.with_workflow(changed_workflow)
        self.assertIsNone(changed.product_reconstruction)
        with tempfile.TemporaryDirectory() as directory:
            restored = FxdProject.load(
                changed.save(Path(directory) / "changed-workflow.fxd.json")
            )
        self.assertIsNone(restored.product_reconstruction)

    def test_tampered_or_stale_reconstruction_fails_closed(self):
        _, document = self._document()
        product = product_from_workbench_document(document)
        reconstruction = reconstruct_product(document, product)
        tampered = reconstruction.to_dict()
        tampered["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ProductReconstructionError, "identity"):
            ProductReconstruction.from_dict(tampered)
        with self.assertRaisesRegex(ProductReconstructionError, "exact reconstruction face"):
            replace(
                reconstruction, reconstruction_identity="",
                bodies=(replace(
                    reconstruction.bodies[0],
                    face_identities=reconstruction.bodies[0].face_identities[:-1],
                ),),
            )
        other_source = self.kernel.export_step(
            self.kernel.make_box((0, 0, 0), (121, 80, 8))
        )
        other_document = load_step_for_workbench(other_source, source_name="changed.step")
        other_product = product_from_workbench_document(other_document)
        with self.assertRaisesRegex(ProductReconstructionError, "stale"):
            reconstruction.require_current_source(other_product)


if __name__ == "__main__":
    unittest.main()
