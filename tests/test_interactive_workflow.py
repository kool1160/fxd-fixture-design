from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from fxd_geometry import (
    AnnotationRole, CustomerToolingRecord, GeometryReference, InteractiveWorkflow,
    InteractiveWorkflowError, OcpKernel, OperationTiming, ProcessSetup, Vec3,
    analyze_engineering_workflow, compare_concepts, face_annotation,
    load_step_for_workbench, product_from_workbench_document,
    reference_plane_orientation, source_orientation, ReferencePlane,
    tooling_record_from_file,
)
from fxd_geometry.project import FxdProject


class InteractiveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.kernel = OcpKernel()
        cls.source = Path(cls.directory.name) / "workflow-source.step"
        shape = cls.kernel.make_box((0, 0, 0), (120, 80, 24))
        cls.source.write_bytes(cls.kernel.export_step(shape))
        cls.original = cls.source.read_bytes()
        cls.document = load_step_for_workbench(cls.source)
        cls.product = product_from_workbench_document(cls.document)
        cls.component = cls.document.assembly.components[0]
        cls.body = cls.product.components[0].bodies[0]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setup(self):
        return ProcessSetup(
            "M28 workflow", "Weld fixture", "MIG welding", "Manual", 100,
            "Medium", Vec3(0, 0, 1), Vec3(1, 0, 0), Vec3(-1, 0, 0),
            "Top and operator-side hand access", "No robot in this revision",
            ("laser cutting", "welding"), "Mild-steel fabricated assembly",
            "Baseplate", 0.1, 2.0, ("vendor-neutral standard clamps",),
            manufacturing_orientation=source_orientation(self.document.source_sha256, accepted=True),
            manufacturing_build_direction=Vec3(0, 0, 1),
            manufacturing_loading_direction=Vec3(1, 0, 0),
            manufacturing_unloading_direction=Vec3(-1, 0, 0),
        )

    def workflow(self):
        roles = (
            AnnotationRole.PRIMARY_DATUM,
            AnnotationRole.SECONDARY_DATUM,
            AnnotationRole.TERTIARY_DATUM,
        )
        annotations = tuple(face_annotation(
            self.document,
            GeometryReference(self.component.reference, self.body.identity, face.reference),
            role,
        ) for face, role in zip(self.component.faces[:3], roles))
        return InteractiveWorkflow(self.document.source_sha256, self.setup(), annotations)

    def test_process_intent_round_trip_preserves_explicit_unknowns(self):
        setup = replace(self.setup(), automation_assumptions=None)
        restored = ProcessSetup.from_dict(setup.to_dict())
        self.assertEqual(restored, setup)
        self.assertIsNone(restored.automation_assumptions)

    def test_legacy_workflow_without_manufacturing_orientation_remains_readable(self):
        payload = self.workflow().to_dict()
        payload["schema_version"] = "fxd-interactive-workflow-v1"
        for key in (
            "manufacturing_orientation", "manufacturing_build_direction",
            "manufacturing_loading_direction", "manufacturing_unloading_direction",
        ):
            payload["setup"].pop(key)
        restored = InteractiveWorkflow.from_dict(payload)
        self.assertEqual(restored.schema_version, "fxd-interactive-workflow-v1")
        self.assertIsNone(restored.setup.manufacturing_orientation)
        with self.assertRaisesRegex(InteractiveWorkflowError, "accepted manufacturing orientation"):
            analyze_engineering_workflow(self.document, restored)

    def test_real_ocp_product_preserves_source_and_stable_face_references(self):
        first = product_from_workbench_document(self.document)
        second = product_from_workbench_document(self.document)
        self.assertEqual(first, second)
        self.assertEqual(first.source_bytes, self.original)
        self.assertEqual(first.source_sha256, sha256(self.original).hexdigest())
        self.assertTrue(first.components[0].bodies[0].faces)

    def test_annotation_is_separate_from_source_cad_and_exact(self):
        workflow = self.workflow()
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertTrue(all(item.exact_reference for item in workflow.geometry_annotations))
        self.assertTrue(all(item.evidence for item in workflow.geometry_annotations))

    def test_annotation_without_face_identity_fails_closed(self):
        with self.assertRaises(InteractiveWorkflowError):
            face_annotation(
                self.document,
                GeometryReference(self.component.reference, self.body.identity),
                AnnotationRole.PRIMARY_DATUM,
            )

    def test_analysis_composes_existing_placement_concept_and_validation_engines(self):
        project = analyze_engineering_workflow(self.document, self.workflow())
        self.assertIsNotNone(project.placement)
        self.assertEqual(len(project.concepts), 3)
        self.assertTrue(project.active_validation.findings)
        self.assertTrue(project.workflow.analysis_completed)
        self.assertEqual(
            {item.operation for item in project.workflow.timings},
            {"normalize_real_ocp_evidence", "placement_analysis", "concept_generation",
             "validation", "total_analysis"},
        )

    def test_analysis_requires_an_accepted_manufacturing_orientation(self):
        setup = replace(
            self.setup(), manufacturing_orientation=source_orientation(self.document.source_sha256),
        )
        with self.assertRaisesRegex(InteractiveWorkflowError, "accepted manufacturing orientation"):
            analyze_engineering_workflow(
                self.document, InteractiveWorkflow(self.document.source_sha256, setup)
            )

    def test_analysis_uses_accepted_manufacturing_axes_at_the_engine_boundary(self):
        orientation = reference_plane_orientation(
            self.document.source_sha256, ReferencePlane.RIGHT, accepted=True,
        )
        setup = replace(
            self.setup(), manufacturing_orientation=orientation,
            manufacturing_build_direction=Vec3(0, 0, 1),
            manufacturing_loading_direction=Vec3(1, 0, 0),
            manufacturing_unloading_direction=Vec3(-1, 0, 0),
        )
        project = analyze_engineering_workflow(
            self.document, InteractiveWorkflow(self.document.source_sha256, setup)
        )
        self.assertEqual(
            project.annotations.build_orientation,
            orientation.manufacturing_vector_to_source(Vec3(0, 0, 1)),
        )
        self.assertEqual(
            project.annotations.loading_direction,
            orientation.manufacturing_vector_to_source(Vec3(1, 0, 0)),
        )
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_missing_datum_evidence_is_blocking_not_placeholder_geometry(self):
        project = analyze_engineering_workflow(
            self.document, InteractiveWorkflow(self.document.source_sha256, self.setup())
        )
        self.assertTrue(project.placement.blocked)
        self.assertTrue(any(item.rule == "placement_missing_datum_evidence"
                            for item in project.placement.findings))
        self.assertTrue(all(feature.rule and feature.source_references
                            for concept in project.concepts
                            for feature in concept.fixture.features))

    def test_concept_comparison_never_recommends_invalid_concept(self):
        project = analyze_engineering_workflow(self.document, self.workflow())
        rows = compare_concepts(project)
        self.assertEqual(len(rows), 3)
        self.assertFalse(any(row.recommended and row.validation_status == "invalid" for row in rows))
        self.assertTrue(all("not a quote" in row.cost_evidence for row in rows))
        self.assertTrue(all(row.unloading_evidence for row in rows))
        self.assertTrue(all(row.operator_access_evidence for row in rows))
        self.assertTrue(all(row.weld_access_evidence for row in rows))
        self.assertTrue(all(row.automation_access_evidence for row in rows))
        self.assertTrue(all(row.manufacturability_evidence for row in rows))
        self.assertTrue(all(row.maintainability_evidence for row in rows))
        self.assertTrue(all(
            row.fabricated_component_count + row.purchased_tooling_count
            == row.fixture_feature_count for row in rows
        ))

    def test_supported_edit_creates_revision_and_revalidates(self):
        project = analyze_engineering_workflow(self.document, self.workflow())
        before = project.revision_id
        edited = project.edit_parameter("base_thickness", 18.0, "Increase review thickness")
        self.assertNotEqual(edited.revision_id, before)
        self.assertIsNone(edited.approved_revision)
        self.assertEqual(edited.active.fixture.parameters.base_thickness, 18.0)
        self.assertTrue(edited.active_validation.evidence_digest)

    def test_project_round_trip_preserves_complete_workflow_and_source(self):
        project = analyze_engineering_workflow(self.document, self.workflow())
        workflow = replace(project.workflow, concepts_generated=True, active_stage="Concepts")
        project = project.with_workflow(workflow)
        destination = Path(self.directory.name) / "workflow.fxd.json"
        project.save(destination)
        restored = FxdProject.load(destination)
        self.assertEqual(restored.workflow.to_dict(), workflow.to_dict())
        self.assertEqual(
            restored.workflow.setup.manufacturing_orientation,
            workflow.setup.manufacturing_orientation,
        )
        self.assertEqual(restored.product.source_bytes, self.original)
        self.assertEqual(restored.revision_id, project.revision_id)

    def test_unverified_customer_tooling_is_visibly_distinct(self):
        record = tooling_record_from_file(
            self.source, identity="customer-clamp", kind="clamp", verified=False,
        )
        self.assertFalse(record.verified)
        self.assertEqual(record.source_sha256, sha256(self.original).hexdigest())
        workflow = self.workflow().with_tooling(record)
        restored = InteractiveWorkflow.from_dict(workflow.to_dict())
        self.assertFalse(restored.customer_tooling[0].verified)

    def test_verified_tooling_requires_traceable_metadata(self):
        with self.assertRaises(InteractiveWorkflowError):
            CustomerToolingRecord("tool", "clamp", verified=True)

    def test_verified_customer_tooling_preserves_supplied_private_metadata(self):
        record = tooling_record_from_file(
            self.source, identity="private-clamp-01", kind="clamp",
            manufacturer="FXD test tooling", part_number="TC-01", revision="B",
            mounting_direction=Vec3(0, 0, 1), working_direction=Vec3(0, 0, -1),
            stroke_mm=32.0, reach_mm=85.0, force_n=1200.0, verified=True,
        )
        restored = CustomerToolingRecord.from_dict(record.to_dict())
        self.assertEqual(restored, record)
        self.assertTrue(restored.verified)
        self.assertEqual(restored.part_number, "TC-01")
        self.assertEqual(restored.working_direction, Vec3(0, 0, -1))

    def test_workflow_json_is_deterministic_and_contains_no_supplier_download_action(self):
        payload = self.workflow().to_dict()
        first = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        second = json.dumps(InteractiveWorkflow.from_dict(payload).to_dict(),
                            sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)
        self.assertNotIn("download", first.lower())

    def test_observational_timings_do_not_change_revision_identity(self):
        project = analyze_engineering_workflow(self.document, self.workflow())
        changed_timing = replace(
            project.workflow,
            timings=(OperationTiming("total_analysis", 99999.0),),
        )
        self.assertEqual(
            replace(project, workflow=changed_timing).revision_id,
            project.revision_id,
        )

    def test_annotation_order_is_canonical_in_serialization(self):
        workflow = self.workflow()
        reversed_workflow = replace(
            workflow, geometry_annotations=tuple(reversed(workflow.geometry_annotations))
        )
        self.assertEqual(workflow.to_dict(), reversed_workflow.to_dict())


if __name__ == "__main__":
    unittest.main()
