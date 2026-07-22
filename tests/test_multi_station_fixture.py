"""Deterministic M32 acceptance coverage using a legally shareable synthetic bracket."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from fxd_geometry import (
    Aabb, AdjustmentState, BuildComponentRole, ConfirmedWeldIntent, ConstructionMethod, FixtureBuildError, GeometryAuthority,
    FixtureBuildPlan, FixtureBuildRequirements, FixtureFamily, FixtureLifecycle,
    FixturePurpose, MultiStationRequirements, OcpKernel, Vec3, AnnotationRole, GeometryReference, author_fixture_build,
    build_fixture_build_package, generate_fixture_concepts,
    generate_multi_station_fixture_alternatives, generate_multi_station_fixture_build_plan,
    generate_multi_station_layout,
    load_step_for_workbench,
    product_from_workbench_document, InteractiveWorkflow, ProcessSetup, validate_fixture_build_plan,
    ReferencePlane, reference_plane_orientation, source_orientation, face_annotation,
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

    def build_requirements(self, product=None, *, welds=None):
        product = product or self.product
        body = product.components[0].bodies[0]
        orientation = source_orientation(product.source_sha256, accepted=True)
        confirmed = tuple(welds) if welds is not None else (ConfirmedWeldIntent(
            "synthetic-bracket-joint",
            (GeometryReference(product.components[0].identity, body.identity, body.faces[0].identity),),
            "operator", 38.0, "synthetic MIG weld", 1,
            Vec3(60.0, 0.0, 12.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 1.0, 0.0),
            Vec3(12.0, 12.0, 30.0), orientation.identity,
            ("Synthetic engineer-confirmed torch evidence.",),
        ),)
        return FixtureBuildRequirements(
            product.source_sha256, FixturePurpose.FULL_WELD,
            ConstructionMethod.LASER_CUT_FABRICATED, FixtureLifecycle.PERMANENT,
            None, "A", 100, "repeat production", "synthetic MIG weld",
            ("laser cutting", "fixture welding", "machining"), None, True, True,
            AdjustmentState.LOCKED,
            ("Synthetic public acceptance geometry; all dimensions remain editable review inputs.",),
            confirmed_weld_intent=True,
            confirmed_weld_joint_count=len(confirmed),
            confirmed_welds=confirmed,
        )

    def station_requirements(self, *, count=5, maximum_length=3000.0, product=None,
                             loading_source=Vec3(0.0, -1.0, 0.0),
                             unloading_source=Vec3(-1.0, 0.0, 0.0),
                             operator_source=Vec3(0.0, 1.0, 0.0),
                             clamp_source=Vec3(0.0, 1.0, 0.0),
                             up_source=Vec3(0.0, 0.0, 1.0)):
        product = product or self.product
        orientation = source_orientation(product.source_sha256, accepted=True)
        return MultiStationRequirements(
            FixtureFamily.LINEAR_MULTI_STATION_WELD, count, maximum_length, None,
            "Operator front (+Y)", "-X", "Operator front (+Y)", "manual",
            "Table mounting holes", 100, True,
            loading_direction_source=loading_source,
            unloading_direction_source=unloading_source,
            operator_loading_direction_source=operator_source,
            clamp_operating_direction_source=clamp_source,
            manufacturing_up_direction_source=up_source,
            source_to_manufacturing=orientation.source_to_manufacturing,
            manufacturing_to_source=orientation.manufacturing_to_source,
            manufacturing_orientation_identity=orientation.identity,
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

    def test_dxf_profiles_use_the_plate_plane_or_fail_closed(self):
        plan = self.plan()
        assembly = author_fixture_build(plan, self.product, self.kernel)
        authored_by_role = {item.component.role: item for item in assembly.components}

        base_dxf = authored_by_role[BuildComponentRole.BASEPLATE].dxf_bytes.decode("ascii")
        rail = authored_by_role[BuildComponentRole.DATUM_RAIL]
        rail_dxf = rail.dxf_bytes.decode("ascii")
        self.assertIn("FXD_PROFILE_PLANE=XY", base_dxf)
        self.assertIn("FXD_PROFILE_PLANE=XZ", rail_dxf)
        self.assertIn(f"20\n{format(rail.component.bounds.maximum.z, '.9g')}\n", rail_dxf)

        for item in assembly.components:
            if item.component.role in {
                    BuildComponentRole.LOCATOR_PLATE,
                    BuildComponentRole.HARD_STOP,
                    BuildComponentRole.CLAMP_BRACKET}:
                self.assertIsNone(
                    item.dxf_bytes,
                    f"{item.component.identity} must not export an ambiguous plate-plane DXF",
                )

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
            unload_source = {"-X": Vec3(-1, 0, 0), "+X": Vec3(1, 0, 0)}[unload]
            operator_source = (Vec3(1, 0, 0) if "+X" in operator_side else Vec3(0, 1, 0))
            base_requirements = self.build_requirements(product)
            requirements = self.build_requirements(product, welds=(replace(
                base_requirements.confirmed_welds[0],
                approach_direction_manufacturing=operator_source,
                approach_direction_source=operator_source,
            ),))
            station_requirements = replace(
                self.station_requirements(
                    count=4, product=product,
                    loading_source=Vec3(-operator_source.x, -operator_source.y, -operator_source.z),
                    unloading_source=unload_source, operator_source=operator_source,
                    clamp_source=operator_source,
                ), unloading_direction=unload,
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
                product, concept, self.build_requirements(product),
                replace(self.station_requirements(
                    count=4, product=product, unloading_source=Vec3(1, 0, 0),
                ), unloading_direction="+X"),
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
            self.build_requirements(), confirmed_welds=(), confirmed_weld_joint_count=1,
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
        provisional = author_fixture_build(plan, self.product, self.kernel)
        self.assertTrue(provisional.provisional)
        with self.assertRaises(FixtureBuildError):
            build_fixture_build_package(provisional, plan)
        complete = self.plan(count=4)
        self.assertTrue(all(station.weld_access_clear is True
                            for station in complete.multi_station_layout.stations))
        self.assertTrue(all(any("weld_access=clear" == value for value in station.access_evidence)
                            for station in complete.multi_station_layout.stations))

    def test_non_identity_orientation_persists_source_frame_process_and_torch_directions(self):
        orientation = reference_plane_orientation(
            self.product.source_sha256, ReferencePlane.TOP,
            rotation_degrees=90.0, accepted=True,
        )
        manufacturing_load = Vec3(0.0, -1.0, 0.0)
        manufacturing_unload = Vec3(-1.0, 0.0, 0.0)
        manufacturing_operator = Vec3(0.0, 1.0, 0.0)
        manufacturing_torch = Vec3(0.0, 1.0, 0.0)
        base_weld = self.build_requirements().confirmed_welds[0]
        weld = replace(
            base_weld,
            approach_direction_manufacturing=manufacturing_torch,
            approach_direction_source=orientation.manufacturing_vector_to_source(manufacturing_torch),
            manufacturing_orientation_identity=orientation.identity,
        )
        requirements = self.build_requirements(welds=(weld,))
        station_requirements = replace(
            self.station_requirements(count=4),
            loading_direction_source=orientation.manufacturing_vector_to_source(manufacturing_load),
            unloading_direction_source=orientation.manufacturing_vector_to_source(manufacturing_unload),
            operator_loading_direction_source=orientation.manufacturing_vector_to_source(manufacturing_operator),
            clamp_operating_direction_source=orientation.manufacturing_vector_to_source(manufacturing_operator),
            manufacturing_up_direction_source=orientation.manufacturing_z_source,
            source_to_manufacturing=orientation.source_to_manufacturing,
            manufacturing_to_source=orientation.manufacturing_to_source,
            manufacturing_orientation_identity=orientation.identity,
        )
        plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept, requirements, station_requirements,
        )
        station = plan.multi_station_layout.stations[0]
        self.assertEqual(station.loading_direction_source,
                         orientation.manufacturing_vector_to_source(manufacturing_load))
        self.assertEqual(station.unloading_direction_source,
                         orientation.manufacturing_vector_to_source(manufacturing_unload))
        self.assertEqual(station.operator_direction_source,
                         orientation.manufacturing_vector_to_source(manufacturing_operator))
        self.assertEqual(station.weld_access_results[0].approach_direction_source,
                         orientation.manufacturing_vector_to_source(manufacturing_torch))
        validation = validate_fixture_build_plan(self.product, plan)
        self.assertTrue(all(station.hand_access_clear is not None
                            and station.unload_path_clear is not None
                            for station in plan.multi_station_layout.stations))
        self.assertEqual(validation.review_blocked,
                         any(station.trapped_part or not station.hand_access_clear
                             or not station.unload_path_clear
                             or station.weld_access_clear is not True
                             for station in plan.multi_station_layout.stations))

        flipped = reference_plane_orientation(
            self.product.source_sha256, ReferencePlane.TOP,
            flip_normal=True, rotation_degrees=180.0, accepted=True,
        )
        flipped_operator = flipped.manufacturing_vector_to_source(Vec3(0.0, 1.0, 0.0))
        flipped_requirements = replace(
            station_requirements,
            loading_direction_source=flipped.manufacturing_vector_to_source(Vec3(0.0, -1.0, 0.0)),
            unloading_direction_source=flipped.manufacturing_vector_to_source(Vec3(0.0, 1.0, 0.0)),
            operator_loading_direction_source=flipped_operator,
            clamp_operating_direction_source=flipped_operator,
            manufacturing_up_direction_source=flipped.manufacturing_z_source,
            source_to_manufacturing=flipped.source_to_manufacturing,
            manufacturing_to_source=flipped.manufacturing_to_source,
            manufacturing_orientation_identity=flipped.identity,
        )
        flipped_weld = replace(
            weld,
            approach_direction_manufacturing=Vec3(0.0, 1.0, 0.0),
            approach_direction_source=flipped_operator,
            manufacturing_orientation_identity=flipped.identity,
        )
        flipped_plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept, self.build_requirements(welds=(flipped_weld,)),
            flipped_requirements,
        )
        self.assertEqual(flipped_plan.multi_station_layout.stations[0].operator_direction_source,
                         flipped_operator)

    def test_source_z_and_oblique_orientations_apply_full_station_transform(self):
        for plane, rotation in ((ReferencePlane.FRONT, 0.0), (ReferencePlane.TOP, 37.0)):
            with self.subTest(plane=plane.value, rotation=rotation):
                orientation = reference_plane_orientation(
                    self.product.source_sha256, plane,
                    rotation_degrees=rotation, accepted=True,
                )
                operator = orientation.manufacturing_vector_to_source(Vec3(0.0, 1.0, 0.0))
                up = orientation.manufacturing_z_source
                weld = replace(
                    self.build_requirements().confirmed_welds[0],
                    approach_direction_manufacturing=Vec3(0.0, 1.0, 0.0),
                    approach_direction_source=operator,
                    manufacturing_orientation_identity=orientation.identity,
                )
                station_requirements = replace(
                    self.station_requirements(count=4),
                    loading_direction_source=orientation.manufacturing_vector_to_source(Vec3(0.0, -1.0, 0.0)),
                    unloading_direction_source=operator,
                    operator_loading_direction_source=operator,
                    clamp_operating_direction_source=operator,
                    manufacturing_up_direction_source=up,
                    source_to_manufacturing=orientation.source_to_manufacturing,
                    manufacturing_to_source=orientation.manufacturing_to_source,
                    manufacturing_orientation_identity=orientation.identity,
                )
                plan = generate_multi_station_fixture_build_plan(
                    self.product, self.concept, self.build_requirements(welds=(weld,)),
                    station_requirements,
                )
                station = plan.multi_station_layout.stations[0]
                self.assertEqual(station.operator_direction_source, operator)
                self.assertEqual(plan.multi_station_layout.requirements.clamp_operating_direction_source,
                                 operator)
                self.assertEqual(len(station.source_to_station_manufacturing), 16)
                self.assertNotEqual(station.source_to_station_manufacturing[:12],
                                    (1.0, 0.0, 0.0, station.translation_mm.x,
                                     0.0, 1.0, 0.0, station.translation_mm.y,
                                     0.0, 0.0, 1.0, station.translation_mm.z))
                opened = next(item for item in plan.components
                              if item.identity == f"{station.identity}-clamp-open-envelope")
                product_center = Vec3(
                    (station.product_bounds.minimum.x + station.product_bounds.maximum.x) * 0.5,
                    (station.product_bounds.minimum.y + station.product_bounds.maximum.y) * 0.5,
                    (station.product_bounds.minimum.z + station.product_bounds.maximum.z) * 0.5,
                )
                opened_center = Vec3(
                    (opened.bounds.minimum.x + opened.bounds.maximum.x) * 0.5,
                    (opened.bounds.minimum.y + opened.bounds.maximum.y) * 0.5,
                    (opened.bounds.minimum.z + opened.bounds.maximum.z) * 0.5,
                )
                displacement = Vec3(opened_center.x - product_center.x,
                                    opened_center.y - product_center.y,
                                    opened_center.z - product_center.z)
                self.assertGreater(displacement.y, 0.0)

    def test_confirmed_torch_approach_and_envelope_change_deterministic_access(self):
        clear_weld = self.build_requirements().confirmed_welds[0]
        clear = self.plan(count=4)
        self.assertTrue(all(station.weld_access_clear is True
                            for station in clear.multi_station_layout.stations))

        blocked_weld = replace(
            clear_weld,
            approach_direction_manufacturing=Vec3(0.0, -1.0, 0.0),
            approach_direction_source=Vec3(0.0, -1.0, 0.0),
        )
        blocked = generate_multi_station_fixture_build_plan(
            self.product, self.concept, self.build_requirements(welds=(blocked_weld,)),
            self.station_requirements(count=4),
        )
        self.assertTrue(any(station.weld_access_clear is False
                            for station in blocked.multi_station_layout.stations))

        oversized_weld = replace(clear_weld, torch_envelope_mm=Vec3(500.0, 500.0, 30.0))
        oversized = generate_multi_station_fixture_build_plan(
            self.product, self.concept, self.build_requirements(welds=(oversized_weld,)),
            self.station_requirements(count=4),
        )
        self.assertTrue(any(station.weld_access_clear is False
                            for station in oversized.multi_station_layout.stations))
        self.assertNotEqual(
            clear.multi_station_layout.stations[0].weld_access_results[0].torch_envelope,
            oversized.multi_station_layout.stations[0].weld_access_results[0].torch_envelope,
        )

    def test_every_confirmed_weld_is_evaluated_and_one_blocked_joint_blocks_build(self):
        clear_weld = self.build_requirements().confirmed_welds[0]
        blocked_weld = replace(
            clear_weld, identity="blocked-second-joint", sequence=2,
            joint_position_source_mm=Vec3(60.0, 0.0, 12.0),
            approach_direction_manufacturing=Vec3(0.0, -1.0, 0.0),
            approach_direction_source=Vec3(0.0, -1.0, 0.0),
        )
        requirements = self.build_requirements(welds=(clear_weld, blocked_weld))
        plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept, requirements, self.station_requirements(count=4),
        )
        for station in plan.multi_station_layout.stations:
            self.assertEqual([item.joint_identity for item in station.weld_access_results],
                             [clear_weld.identity, blocked_weld.identity])
        validation = validate_fixture_build_plan(self.product, plan)
        self.assertTrue(validation.review_blocked)
        self.assertTrue(any(blocked_weld.identity in item.message for item in validation.findings))
        self.assertFalse(any(clear_weld.identity in item.message for item in validation.findings))

    def test_validation_rejects_missing_duplicate_or_inconsistent_joint_results(self):
        first = self.build_requirements().confirmed_welds[0]
        second = replace(first, identity="second-clear-joint", sequence=2)
        plan = generate_multi_station_fixture_build_plan(
            self.product, self.concept, self.build_requirements(welds=(first, second)),
            self.station_requirements(count=4),
        )
        layout = plan.multi_station_layout
        station = layout.stations[0]
        self.assertEqual(len(station.weld_access_results), 2)

        variants = (
            replace(station, weld_access_results=station.weld_access_results[:1], weld_access_clear=True),
            replace(station, weld_access_results=(station.weld_access_results[0],) * 2,
                    weld_access_clear=True),
            replace(station, weld_access_clear=not all(item.clear for item in station.weld_access_results)),
        )
        expected_messages = (
            "do not cover every confirmed joint exactly once",
            "do not cover every confirmed joint exactly once",
            "aggregate disagrees with its per-joint results",
        )
        for variant, expected in zip(variants, expected_messages):
            with self.subTest(expected=expected):
                tampered_layout = replace(layout, stations=(variant,) + layout.stations[1:])
                validation = validate_fixture_build_plan(
                    self.product, replace(plan, multi_station_layout=tampered_layout),
                )
                self.assertTrue(validation.review_blocked)
                self.assertTrue(any(expected in item.message for item in validation.findings))

    def test_validation_rejects_station_spacing_larger_than_recorded_pitch(self):
        plan = self.plan(count=4)
        layout = plan.multi_station_layout
        station = layout.stations[1]
        delta = Vec3(10.0, 0.0, 0.0) if layout.primary_axis == "x" else Vec3(0.0, 10.0, 0.0)
        transform = list(station.source_to_station_manufacturing)
        transform[3 if layout.primary_axis == "x" else 7] += 10.0
        moved = replace(
            station,
            translation_mm=Vec3(station.translation_mm.x + delta.x,
                                station.translation_mm.y + delta.y,
                                station.translation_mm.z),
            product_bounds=Aabb(
                Vec3(station.product_bounds.minimum.x + delta.x,
                     station.product_bounds.minimum.y + delta.y,
                     station.product_bounds.minimum.z),
                Vec3(station.product_bounds.maximum.x + delta.x,
                     station.product_bounds.maximum.y + delta.y,
                     station.product_bounds.maximum.z),
            ),
            source_to_station_manufacturing=tuple(transform),
        )
        validation = validate_fixture_build_plan(
            self.product,
            replace(plan, multi_station_layout=replace(
                layout, stations=(layout.stations[0], moved) + layout.stations[2:],
            )),
        )
        self.assertTrue(any("not stable equal-pitch placements" in item.message
                            for item in validation.findings))

    def test_manufacturing_transform_integrity_fails_authoring_closed(self):
        plan = self.plan(count=4)
        layout = plan.multi_station_layout
        station = layout.stations[0]
        tampered_matrix = list(station.source_to_station_manufacturing)
        tampered_matrix[3] += 1.0
        tampered_station = replace(
            station, source_to_station_manufacturing=tuple(tampered_matrix),
        )
        validation = validate_fixture_build_plan(
            self.product,
            replace(plan, multi_station_layout=replace(
                layout, stations=(tampered_station,) + layout.stations[1:],
            )),
        )
        transform_findings = tuple(
            finding for finding in validation.findings
            if "transform does not match" in finding.message
        )
        self.assertEqual(len(transform_findings), 1)
        self.assertEqual(transform_findings[0].disposition, "authoring_blocker")

        bad_inverse = list(layout.requirements.manufacturing_to_source)
        bad_inverse[3] += 1.0
        with self.assertRaisesRegex(FixtureBuildError, "not mutual inverses"):
            generate_multi_station_fixture_build_plan(
                self.product, self.concept, self.build_requirements(),
                replace(layout.requirements, manufacturing_to_source=tuple(bad_inverse)),
            )

    def test_validation_rejects_access_evidence_stale_for_current_geometry(self):
        plan = self.plan(count=4)
        shim = next(item for item in plan.components if item.role == BuildComponentRole.SHIM_PACK)
        changed_shim = replace(shim, bounds=Aabb(
            shim.bounds.minimum,
            Vec3(shim.bounds.maximum.x + 1.0, shim.bounds.maximum.y, shim.bounds.maximum.z),
        ))
        changed_components = tuple(
            changed_shim if item.identity == shim.identity else item
            for item in plan.components
        )
        validation = validate_fixture_build_plan(
            self.product, replace(plan, components=changed_components),
        )
        stale = tuple(item for item in validation.findings
                      if "access evidence is missing or stale" in item.message)
        self.assertEqual(len(stale), len(plan.multi_station_layout.stations))
        self.assertTrue(validation.review_blocked)

        station = plan.multi_station_layout.stations[0]
        missing_digest_layout = replace(
            plan.multi_station_layout,
            stations=(replace(station, access_evidence_digest=""),)
            + plan.multi_station_layout.stations[1:],
        )
        missing_validation = validate_fixture_build_plan(
            self.product, replace(plan, multi_station_layout=missing_digest_layout),
        )
        self.assertTrue(any("access evidence is missing or stale" in item.message
                            for item in missing_validation.findings))

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
        self.assertIsNone(annotations.weld_joints[0].direction)

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
        self.assertEqual(restored.fixture_build.requirements.confirmed_welds,
                         plan.requirements.confirmed_welds)
        self.assertEqual(restored.fixture_build.multi_station_layout.stations[0].weld_access_results,
                         plan.multi_station_layout.stations[0].weld_access_results)
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
