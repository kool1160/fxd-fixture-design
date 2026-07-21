"""Deterministic M32 acceptance coverage using a legally shareable synthetic bracket."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from fxd_geometry import (
    AdjustmentState, BuildComponentRole, ConstructionMethod, FixtureBuildError, GeometryAuthority,
    FixtureBuildPlan, FixtureBuildRequirements, FixtureFamily, FixtureLifecycle,
    FixturePurpose, MultiStationRequirements, OcpKernel, Vec3, AnnotationRole, GeometryReference, author_fixture_build,
    build_fixture_build_package, generate_fixture_concepts,
    generate_multi_station_fixture_alternatives, generate_multi_station_fixture_build_plan,
    generate_multi_station_layout,
    load_step_for_workbench,
    product_from_workbench_document, InteractiveWorkflow, ProcessSetup, validate_fixture_build_plan,
    source_orientation, face_annotation,
)
from fxd_geometry.annotations import EngineeringAnnotations
from fxd_geometry.project import FxdProject
from fxd_geometry.ai_fixture_engineer import deterministic_baseline_proposal
from fxd_geometry.interactive_workflow import _engineering_annotations


class MultiStationFixtureTests(unittest.TestCase):
    """M32 stays source-immutable and deterministic without provider credentials."""

    @classmethod
    def setUpClass(cls):
        cls.kernel = OcpKernel()
        # Two plain, synthetic plates make a legally shareable angled bracket:
        # one horizontal member and one upright member.  No customer or vendor CAD
        # is used in this repository fixture.
        horizontal = cls.kernel.make_box((0, 0, 0), (120, 38, 5))
        upright = cls.kernel.make_box((0, 0, 5), (5, 38, 62))
        cls.source_bytes = cls.kernel.export_step(cls.kernel.compound((horizontal, upright)))
        cls.source_sha256 = sha256(cls.source_bytes).hexdigest()
        cls.directory = tempfile.TemporaryDirectory()
        cls.source = Path(cls.directory.name) / "synthetic_two_piece_angled_bracket.step"
        cls.source.write_bytes(cls.source_bytes)
        cls.product = product_from_workbench_document(load_step_for_workbench(cls.source))
        cls.annotations = EngineeringAnnotations.for_product(
            cls.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="synthetic MIG weld", production_quantity=100,
        )
        cls.concept = generate_fixture_concepts(cls.product, cls.annotations).recommended

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def build_requirements(self):
        return FixtureBuildRequirements(
            self.product.source_sha256, FixturePurpose.FULL_WELD,
            ConstructionMethod.LASER_CUT_FABRICATED, FixtureLifecycle.PERMANENT,
            None, "A", 100, "repeat production", "synthetic MIG weld",
            ("laser cutting", "fixture welding", "machining"), None, True, True,
            AdjustmentState.LOCKED,
            ("Synthetic public acceptance geometry; all dimensions remain editable review inputs.",),
            confirmed_weld_intent=True,
            confirmed_weld_evidence=(
                "joint_reference=synthetic-bracket-joint", "weld_side=operator",
                "weld_length_mm=38.0", "weld_process=synthetic MIG weld",
                "weld_sequence=1", "approach_direction=(0,1,0)",
                "torch_envelope_mm=25.0",
            ),
        )

    def station_requirements(self, *, count=5, maximum_length=3000.0):
        return MultiStationRequirements(
            FixtureFamily.LINEAR_MULTI_STATION_WELD, count, maximum_length, None,
            "Operator front (+Y)", "-X", "Operator front (+Y)", "manual",
            "Table mounting holes", 100, True,
        )

    def plan(self, *, count=5, maximum_length=3000.0):
        return generate_multi_station_fixture_build_plan(
            self.product, self.concept, self.build_requirements(),
            self.station_requirements(count=count, maximum_length=maximum_length),
        )

    def test_five_station_real_ocp_fixture_is_source_immutable_and_connected(self):
        before = self.source.read_bytes()
        plan = self.plan()
        layout = plan.multi_station_layout
        self.assertIsNotNone(layout)
        assert layout is not None
        self.assertEqual(len(layout.stations), 5)
        self.assertEqual([item.identity for item in layout.stations], [
            "m32-station-01", "m32-station-02", "m32-station-03", "m32-station-04", "m32-station-05",
        ])
        self.assertTrue(all(item.product_source_sha256 == self.source_sha256 for item in layout.stations))
        self.assertTrue(all(item.source_component_identities for item in layout.stations))
        self.assertEqual(validate_fixture_build_plan(self.product, plan).status, "valid")
        assembly = author_fixture_build(plan, self.product, self.kernel)
        self.assertFalse(assembly.provisional)
        self.assertEqual(assembly.review_labels, ())
        roles = [item.component.role for item in assembly.components]
        self.assertIn(BuildComponentRole.BASEPLATE, roles)
        self.assertIn(BuildComponentRole.DATUM_RAIL, roles)
        self.assertGreaterEqual(roles.count(BuildComponentRole.SUPPORT_PAD), 15)
        self.assertEqual(roles.count(BuildComponentRole.HARD_STOP), 5)
        self.assertEqual(roles.count(BuildComponentRole.CLAMP_BRACKET), 5)
        self.assertEqual(roles.count(BuildComponentRole.TOGGLE_CLAMP), 0)
        self.assertEqual(sum(item.role == BuildComponentRole.TOGGLE_CLAMP for item in plan.components), 5)
        self.assertEqual(sum(item.role == BuildComponentRole.CLAMP_OPEN_ENVELOPE for item in plan.components), 5)
        self.assertTrue(all(
            item.geometry_authority == GeometryAuthority.PURCHASED_COMPONENT
            for item in plan.components
            if item.role in {BuildComponentRole.TOGGLE_CLAMP, BuildComponentRole.CLAMP_OPEN_ENVELOPE}
        ))
        self.assertGreaterEqual(roles.count(BuildComponentRole.END_BRACE), 2)
        self.assertTrue(all(item.topology.solids >= 1 for item in assembly.components))
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(self.source_sha256, sha256(self.source.read_bytes()).hexdigest())

    def test_station_count_edit_and_bom_reconcile_deterministically(self):
        five = self.plan(count=5)
        self.assertEqual(five.to_dict(), self.plan(count=5).to_dict())
        three = self.plan(count=3)
        self.assertNotEqual(five.identity, three.identity)
        self.assertEqual(len(three.multi_station_layout.stations), 3)
        five_package = build_fixture_build_package(author_fixture_build(five, self.product, self.kernel), five)
        three_package = build_fixture_build_package(author_fixture_build(three, self.product, self.kernel), three)
        five_bom = json.loads(five_package["bom.json"])
        three_bom = json.loads(three_package["bom.json"])
        count_role = lambda bom, token: sum(token in item["description"] for item in bom)
        self.assertEqual(count_role(five_bom, "vendor-neutral toggle-clamp"), 0)
        self.assertEqual(count_role(three_bom, "vendor-neutral toggle-clamp"), 0)
        self.assertFalse(any(item["geometry_authority"] == "purchased_component_geometry" for item in five_bom))
        self.assertFalse(any("toggle" in name or "clamp-open" in name for name in five_package))
        self.assertFalse(any(item["classification"] == "purchased_tooling"
                             for item in json.loads(five_package["nest-classification.json"])))
        self.assertIn("adjustment-slot-map.json", five_package)
        self.assertIn("multi_station_layout", json.loads(five_package["manifest.json"]))

    def test_one_up_and_selected_count_alternatives_use_the_same_build_contract(self):
        alternatives = generate_multi_station_fixture_alternatives(
            self.product, self.concept, self.build_requirements(), self.station_requirements(count=5),
        )
        self.assertEqual([len(item.multi_station_layout.stations) for item in alternatives], [1, 5])
        self.assertTrue(all(validate_fixture_build_plan(self.product, item).valid for item in alternatives))

    def test_layout_limit_access_and_family_fail_closed(self):
        with self.assertRaisesRegex(FixtureBuildError, "smaller-layout proposal"):
            self.plan(count=8, maximum_length=650.0)
        with self.assertRaisesRegex(FixtureBuildError, "unsupported fixture family"):
            MultiStationRequirements(
                "unsupported_family", 1, 1000.0, None, "front", "-X", "front", "manual", "holes", 1,
            )
        plan = self.plan()
        layout = plan.multi_station_layout
        assert layout is not None
        trapped = replace(layout.stations[0], open_clamp_envelope_clear=False, trapped_part=True)
        invalid = replace(plan, multi_station_layout=replace(layout, stations=(trapped,) + layout.stations[1:]))
        validation = validate_fixture_build_plan(self.product, invalid)
        self.assertTrue(validation.blocked)
        self.assertTrue({"FXD-M32-CLP", "FXD-M32-ACC"} <= {item.rule_id for item in validation.findings})
        assembly = author_fixture_build(invalid, self.product, self.kernel)
        self.assertTrue(assembly.provisional)
        self.assertEqual(assembly.review_labels, ("PROVISIONAL", "NOT APPROVED", "INVALID BUILD PLAN"))
        broken_component = replace(plan.components[1], parent_component_identity="missing-parent")
        structural = replace(plan, components=(plan.components[0], broken_component) + plan.components[2:])
        structural_validation = validate_fixture_build_plan(self.product, structural)
        self.assertTrue(structural_validation.authoring_blocked)
        with self.assertRaises(FixtureBuildError):
            author_fixture_build(structural, self.product, self.kernel)
        stale = replace(plan, requirements=replace(plan.requirements, source_sha256="0" * 64))
        stale_validation = validate_fixture_build_plan(self.product, stale)
        self.assertTrue(stale_validation.authoring_blocked)
        with self.assertRaises(FixtureBuildError):
            author_fixture_build(stale, self.product, self.kernel)

    def test_station_access_is_explicit_and_unknown_evidence_fails_closed(self):
        raw_layout = generate_multi_station_layout(self.product, self.station_requirements(count=4))
        self.assertTrue(all(station.hand_access_clear is None and station.unload_path_clear is None
                            and station.trapped_part is None for station in raw_layout.stations))
        plan = self.plan(count=4)
        layout = plan.multi_station_layout
        assert layout is not None
        self.assertTrue(all(station.loading_envelope and station.unloading_envelope for station in layout.stations))
        self.assertTrue(all(station.access_evidence for station in layout.stations))
        unknown = replace(
            layout.stations[0], clamp_tip_reaches_surface=None,
            open_clamp_envelope_clear=None, hand_access_clear=None,
            unload_path_clear=None, trapped_part=None,
        )
        invalid = replace(plan, multi_station_layout=replace(
            layout, stations=(unknown,) + layout.stations[1:]
        ))
        findings = validate_fixture_build_plan(self.product, invalid).findings
        self.assertTrue(any("not evaluated" in item.message for item in findings))
        self.assertTrue(any(item.disposition == "review_blocker" for item in findings))

    def test_local_station_plates_and_end_clearance_are_axis_neutral(self):
        def assert_layout(product, concept, *, unload="-X", operator_side="Operator front (+Y)"):
            requirements = replace(self.build_requirements(), source_sha256=product.source_sha256)
            station_requirements = replace(
                self.station_requirements(count=4), unloading_direction=unload,
                operator_loading_side=operator_side,
            )
            plan = generate_multi_station_fixture_build_plan(
                product, concept, requirements, station_requirements,
            )
            layout = plan.multi_station_layout
            assert layout is not None
            plates = [item for item in plan.components if item.role == BuildComponentRole.STATION_PLATE]
            braces = [item for item in plan.components if item.role == BuildComponentRole.END_BRACE]
            self.assertEqual(len(plates), 4)
            self.assertEqual({item.parent_component_identity for item in plates}, {"m32-backbone"})
            self.assertTrue(all(
                not station.product_bounds.intersects(brace.bounds)
                for station in (layout.stations[0], layout.stations[-1])
                for brace in braces
            ))
            validation = validate_fixture_build_plan(product, plan)
            self.assertTrue(validation.valid, [item.message for item in validation.findings])
            return layout.primary_axis

        self.assertEqual(assert_layout(self.product, self.concept), "x")
        with tempfile.TemporaryDirectory() as directory:
            horizontal = self.kernel.make_box((0, 0, 0), (38, 120, 5))
            upright = self.kernel.make_box((0, 0, 5), (38, 5, 62))
            path = Path(directory) / "synthetic_y_primary.step"
            path.write_bytes(self.kernel.export_step(self.kernel.compound((horizontal, upright))))
            product = product_from_workbench_document(load_step_for_workbench(path))
            annotations = EngineeringAnnotations.for_product(
                product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
                process_type="synthetic MIG weld", production_quantity=100,
            )
            concept = generate_fixture_concepts(product, annotations).recommended
            conflicting = generate_multi_station_fixture_build_plan(
                product, concept, replace(self.build_requirements(), source_sha256=product.source_sha256),
                replace(self.station_requirements(count=4), unloading_direction="+X"),
            )
            conflicting_validation = validate_fixture_build_plan(product, conflicting)
            self.assertTrue(conflicting_validation.review_blocked)
            self.assertTrue(any("operator hand clearance is blocked" in item.message
                                for item in conflicting_validation.findings))
            self.assertEqual(assert_layout(
                product, concept, unload="+X", operator_side="Operator right (+X)"
            ), "y")

    def test_length_constrained_reduction_is_explicit_and_preserves_requested_intent(self):
        requested = self.station_requirements(count=5, maximum_length=1219.2)
        from fxd_geometry import propose_multi_station_fit
        fit = propose_multi_station_fit(self.product, requested)
        self.assertEqual(fit.requested_station_count, 5)
        self.assertEqual(fit.feasible_station_count, 4)
        self.assertTrue(fit.requires_explicit_acceptance)
        accepted = replace(requested, requested_station_count=4, requested_intent_station_count=5)
        plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept, self.build_requirements(), accepted,
        )
        layout = plan.multi_station_layout
        assert layout is not None
        self.assertEqual(len(layout.stations), 4)
        self.assertEqual(layout.requirements.requested_intent_station_count, 5)
        self.assertGreater(layout.requested_intent_required_length_mm, 1219.2)
        self.assertLessEqual(layout.required_fixture_length_mm, 1219.2)

    def test_missing_weld_intent_is_review_blocking_not_false_weld_access_validation(self):
        plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept,
            replace(self.build_requirements(), confirmed_weld_intent=False),
            self.station_requirements(count=4),
        )
        validation = validate_fixture_build_plan(self.product, plan)
        weld = next(item for item in validation.findings if item.rule_id == "FXD-WLD-001")
        self.assertEqual(weld.severity, "error")
        self.assertEqual(weld.disposition, "review_blocker")
        self.assertIn("unconfirmed candidate interfaces", weld.message)
        assembly = author_fixture_build(plan, self.product, self.kernel)
        self.assertTrue(assembly.provisional)
        with self.assertRaises(FixtureBuildError):
            build_fixture_build_package(assembly, plan)

    def test_confirmed_weld_contract_requires_complete_torch_evidence(self):
        incomplete_requirements = replace(
            self.build_requirements(), confirmed_weld_evidence=("weld_side=operator",)
        )
        plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept, incomplete_requirements,
            self.station_requirements(count=4),
        )
        validation = validate_fixture_build_plan(self.product, plan)
        self.assertTrue(any("Confirmed weld intent is incomplete" in item.message
                            for item in validation.findings))
        self.assertTrue(all(station.weld_access_clear is None
                            for station in plan.multi_station_layout.stations))
        complete = self.plan(count=4)
        self.assertTrue(all(station.weld_access_clear is True
                            for station in complete.multi_station_layout.stations))
        self.assertTrue(all(any("weld_access=clear" == value for value in station.access_evidence)
                            for station in complete.multi_station_layout.stations))

    def test_candidate_weld_face_is_unconfirmed_until_engineer_records_required_intent(self):
        document = load_step_for_workbench(self.source)
        component = self.product.components[0]
        body = component.bodies[0]
        reference = body.faces[0].identity
        candidate = face_annotation(
            document,
            GeometryReference(component.identity, body.identity, reference),
            AnnotationRole.WELD_JOINT,
        )
        setup = ProcessSetup(
            "M32 weld intent", fixture_type="Weld fixture", manufacturing_process="MIG welding", operation_mode="Manual",
            production_quantity=100, manufacturing_orientation=source_orientation(self.product.source_sha256, accepted=True),
            manufacturing_build_direction=Vec3(0, 0, 1), manufacturing_loading_direction=Vec3(1, 0, 0),
            manufacturing_unloading_direction=Vec3(-1, 0, 0),
        )
        unconfirmed = replace(candidate, evidence=candidate.evidence + (
            "weld_candidate_status=unconfirmed", "weld_side=Unknown", "weld_length_mm=0.000",
            "weld_process=MIG welding", "weld_sequence=0",
        ))
        annotations = _engineering_annotations(
            self.product, InteractiveWorkflow(self.product.source_sha256, setup, (unconfirmed,)),
        )
        self.assertEqual(annotations.weld_joints, ())
        confirmed = replace(candidate, evidence=candidate.evidence + (
            "weld_candidate_status=confirmed", "weld_side=Operator side", "weld_length_mm=42.000",
            "weld_process=MIG welding", "weld_sequence=1",
        ))
        annotations = _engineering_annotations(
            self.product, InteractiveWorkflow(self.product.source_sha256, setup, (confirmed,)),
        )
        self.assertEqual(len(annotations.weld_joints), 1)
        self.assertEqual(annotations.weld_joints[0].sequence, 1)

    def test_legacy_weld_face_is_not_confirmed_for_m32(self):
        document = load_step_for_workbench(self.source)
        component = self.product.components[0]
        body = component.bodies[0]
        candidate = face_annotation(
            document, GeometryReference(component.identity, body.identity, body.faces[0].identity),
            AnnotationRole.WELD_JOINT,
        )
        setup = ProcessSetup(
            "M32 legacy weld boundary", fixture_family=FixtureFamily.LINEAR_MULTI_STATION_WELD.value,
            fixture_type="Weld fixture", manufacturing_process="MIG welding", operation_mode="Manual",
            production_quantity=100, manufacturing_orientation=source_orientation(
                self.product.source_sha256, accepted=True,
            ), manufacturing_loading_direction=Vec3(1, 0, 0),
            manufacturing_unloading_direction=Vec3(-1, 0, 0),
        )
        annotations = _engineering_annotations(
            self.product, InteractiveWorkflow(self.product.source_sha256, setup, (candidate,)),
        )
        self.assertEqual(annotations.weld_joints, ())

    def test_persistence_preserves_station_identity_and_material_edit_revokes_build(self):
        plan = replace(self.plan(), authoring_state="provisional")
        workflow = InteractiveWorkflow(self.product.source_sha256, ProcessSetup("M32 persistence"))
        project = FxdProject.from_product(self.product, self.annotations, workflow=workflow).with_fixture_build(plan)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m32.fxd.json"
            project.save(path)
            restored = FxdProject.load(path)
        self.assertEqual(restored.fixture_build.to_dict(), plan.to_dict())
        self.assertEqual(restored.fixture_build.authoring_state, "provisional")
        changed = project.edit_parameter("clearance", 3.0, "M32 material geometry review edit")
        self.assertIsNone(changed.fixture_build)
        self.assertIsNone(changed.approved_revision)

    def test_fixture_proposal_does_not_clear_independent_fixture_build_evidence(self):
        plan = self.plan()
        workflow = InteractiveWorkflow(
            self.product.source_sha256,
            ProcessSetup("M32 proposal separation", manufacturing_orientation=source_orientation(
                self.product.source_sha256, accepted=True,
            ), manufacturing_loading_direction=Vec3(1, 0, 0),
               manufacturing_unloading_direction=Vec3(-1, 0, 0)),
        )
        project = FxdProject.from_product(self.product, self.annotations, workflow=workflow).with_fixture_build(plan)
        proposal = deterministic_baseline_proposal(project)
        updated = project.with_fixture_proposal(proposal)
        self.assertIsNotNone(updated.fixture_build)
        self.assertEqual(updated.fixture_build.to_dict(), plan.to_dict())
        self.assertEqual(updated.fixture_build_validation.evidence_digest,
                         validate_fixture_build_plan(self.product, plan).evidence_digest)
