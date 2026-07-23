from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fxd_geometry import (
    AdjustmentState, BuildComponentRole, ClecoSpec, ClecoStrategy, ConstructionMethod,
    FixtureBuildComponent, FixtureBuildError, FixtureBuildPlan, FixtureBuildRequirements,
    FixtureLifecycle, FixturePurpose, GeometryAuthority, HoleProcess, HoleProcessSpec,
    NestClassification, OcpKernel, PokaYokeSpec, TabSlotJoint, Vec3, author_fixture_build,
    build_fixture_build_package, compare_fixture_build_plans, generate_fixture_build_plan,
    generate_fixture_concepts, import_step, validate_fixture_build_plan,
    write_fixture_build_package,
)
from fxd_geometry.annotations import EngineeringAnnotations
from fxd_geometry.project import FxdProject
from fxd_geometry.operations import export_project_package, project_export_block_reason


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"


class FabricationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FIXTURE.read_bytes()
        cls.product = import_step(FIXTURE)
        cls.annotations = EngineeringAnnotations.for_product(
            cls.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=20,
        )
        cls.concept = generate_fixture_concepts(cls.product, cls.annotations).recommended

    def requirements(self, *, purpose=FixturePurpose.TACK_LOCATION,
                     method=ConstructionMethod.TACK_LOCATION,
                     lifecycle=FixtureLifecycle.DISPOSABLE_RECUT):
        return FixtureBuildRequirements(
            self.product.source_sha256, purpose, method, lifecycle, "JOB-REV-A", "A",
            20, "repeat quarterly", "MIG", ("laser cutting", "fixture welding"),
            True if purpose == FixturePurpose.TACK_LOCATION else None,
            None if purpose == FixturePurpose.TACK_LOCATION else True,
            True, AdjustmentState.LOCKED,
            ("Representative dimensions remain editable proof geometry.",),
            cleco_strategy=ClecoStrategy.SEPARATE_FIXTURE_HOLES,
        )

    def plan(self, **kwargs):
        return generate_fixture_build_plan(self.product, self.concept, self.requirements(**kwargs))

    def codes(self, plan):
        return {item.rule_id for item in validate_fixture_build_plan(self.product, plan).findings}

    def test_fixture_purpose_categories_and_tack_location_workflow(self):
        self.assertEqual(len(FixturePurpose), 9)
        plan = self.plan()
        result = validate_fixture_build_plan(self.product, plan)
        self.assertFalse(result.blocked)
        self.assertEqual(plan.requirements.fixture_purpose, FixturePurpose.TACK_LOCATION)
        self.assertEqual(plan.tack_sequence[-2:], ("release", "unload"))
        self.assertIn("full-weld access was not evaluated", " ".join(item.message for item in result.findings))

    def test_contract_serialization_digest_and_project_persistence(self):
        plan = self.plan()
        restored = FixtureBuildPlan.from_dict(plan.to_dict())
        self.assertEqual(restored.to_dict(), plan.to_dict())
        self.assertEqual(restored.evidence_digest, plan.evidence_digest)
        project = FxdProject.from_product(self.product, self.annotations).with_fixture_build(plan)
        before = project.revision_id
        changed = replace(plan, requirements=replace(plan.requirements, fixture_revision="B"))
        self.assertNotEqual(project.with_fixture_build(changed).revision_id, before)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "m30.fxd.json"
            project.save(destination)
            loaded = FxdProject.load(destination)
            self.assertEqual(loaded.fixture_build.to_dict(), plan.to_dict())
            self.assertEqual(loaded.active_validation.evidence_digest, project.active_validation.evidence_digest)

    def test_round_diamond_and_four_pad_overconstraint_variants(self):
        plan = self.plan()
        self.assertEqual(len([item for item in plan.components if item.role == BuildComponentRole.ROUND_PIN]), 1)
        self.assertEqual(len([item for item in plan.components if item.role == BuildComponentRole.DIAMOND_PIN]), 1)
        pad = next(item for item in plan.components if item.role == BuildComponentRole.SUPPORT_PAD)
        extra = replace(pad, identity="m30-support-4", part_number="FXD-M30-099")
        bad = replace(plan, components=plan.components + (extra,))
        self.assertIn("FXD-DAT-001", self.codes(bad))
        second_round = replace(next(item for item in plan.components if item.role == BuildComponentRole.ROUND_PIN),
                               identity="m30-round-pin-2", part_number="FXD-M30-098")
        bad = replace(plan, components=plan.components + (second_round,))
        self.assertIn("FXD-PIN-001", self.codes(bad))

    def test_diamond_pin_is_relieved_and_step_export_preserves_the_clearance(self):
        kernel = OcpKernel()
        assembly = author_fixture_build(self.plan(), self.product, kernel)
        round_pin = next(item for item in assembly.components if item.component.role == BuildComponentRole.ROUND_PIN)
        diamond_pin = next(item for item in assembly.components if item.component.role == BuildComponentRole.DIAMOND_PIN)

        def spans(shape):
            vertices = [vertex for mesh in kernel.tessellate(shape) for vertex in mesh.vertices_mm]
            return tuple(max(vertex[index] for vertex in vertices) - min(vertex[index] for vertex in vertices)
                         for index in (0, 1, 2))

        round_spans = spans(round_pin.shape)
        diamond_spans = spans(diamond_pin.shape)
        self.assertGreater(diamond_pin.topology.faces, round_pin.topology.faces)
        self.assertLess(diamond_spans[0], round_spans[0])
        self.assertGreater(diamond_spans[1], diamond_spans[0])
        self.assertLess(abs(diamond_spans[1] - round_spans[1]), 0.2)
        self.assertIn("relief_axis=fixture_x", diamond_pin.component.evidence)
        self.assertIn("locating_axis=fixture_y", diamond_pin.component.evidence)

        exported_spans = spans(kernel.import_step(diamond_pin.step_bytes))
        self.assertLess(exported_spans[0], exported_spans[1])
        self.assertAlmostEqual(exported_spans[1], diamond_spans[1], places=4)

    def test_unload_and_clamp_reaction_fail_closed(self):
        plan = self.plan()
        unloaded = replace(plan, requirements=replace(plan.requirements, unload_clearance_evaluated=False))
        self.assertIn("FXD-DST-001", self.codes(unloaded))
        clamp = next(item for item in plan.components if item.role == BuildComponentRole.CLAMP_PLATE)
        no_reaction = replace(clamp, reaction_support_identity=None)
        bad = replace(plan, components=tuple(no_reaction if item.identity == clamp.identity else item for item in plan.components))
        self.assertIn("FXD-SUP-001", self.codes(bad))

    def test_locator_surface_and_tab_slot_checks(self):
        plan = self.plan()
        pin = next(item for item in plan.components if item.role == BuildComponentRole.ROUND_PIN)
        seam = replace(pin, contact_condition="weld_seam")
        bad = replace(plan, components=tuple(seam if item.identity == pin.identity else item for item in plan.components))
        self.assertIn("FXD-LOC-001", self.codes(bad))
        joint = plan.tab_slots[0]
        undersized = replace(joint, slot_width_mm=joint.tab_thickness_mm)
        bottoms = replace(plan, tab_slots=(undersized,))
        self.assertIn("FXD-TAB-001", self.codes(bottoms))

    def test_poka_yoke_and_extended_cleco_traceability(self):
        plan = self.plan()
        self.assertEqual(plan.poka_yokes[0].strategy, "asymmetric tab and keyed slot")
        self.assertTrue(plan.poka_yokes[0].prevents_reversal)
        reversible = replace(plan.poka_yokes[0], prevents_reversal=False)
        self.assertIn("FXD-PKY-001", self.codes(replace(plan, poka_yokes=(reversible,))))
        cleco = plan.clecos[0]
        restored = ClecoSpec.from_dict(cleco.to_dict())
        self.assertEqual(restored.installation_side, "fixture assembly side")
        self.assertEqual(restored.fixture_build_role, "temporary fixture assembly")
        self.assertTrue(restored.hole_remains)

    def test_tube_wall_geometry_and_service_items_require_maintenance_evidence(self):
        frame = self.plan(purpose=FixturePurpose.FULL_WELD, method=ConstructionMethod.WELDED_TUBE_FRAME,
                          lifecycle=FixtureLifecycle.PERMANENT)
        assembly = author_fixture_build(frame, self.product, OcpKernel())
        tube = next(item for item in assembly.components if item.component.role == BuildComponentRole.TUBE_FRAME)
        self.assertGreater(tube.topology.faces, 6)
        pad = next(item for item in frame.components if item.role == BuildComponentRole.SUPPORT_PAD)
        unserviceable = replace(pad, replaceable=False, maintenance_access=False)
        bad = replace(frame, components=tuple(unserviceable if item.identity == pad.identity else item
                                              for item in frame.components))
        self.assertIn("FXD-MNT-001", self.codes(bad))
        self.assertIn("FXD-PKY-001", self.codes(replace(frame, poka_yokes=())))

    def test_hole_process_and_cleco_product_approval_checks(self):
        plan = self.plan()
        base = next(item for item in plan.components if item.identity == "m30-baseplate")
        precision = HoleProcessSpec("precision-laser", Vec3(base.bounds.minimum.x + 30, base.bounds.minimum.y + 30, base.bounds.minimum.z),
                                    8.0, HoleProcess.LASER_CLEARANCE, precision_required=True)
        bad_base = replace(base, holes=base.holes + (precision,))
        bad = replace(plan, components=tuple(bad_base if item.identity == base.identity else item for item in plan.components))
        self.assertIn("FXD-HOL-001", self.codes(bad))
        cleco = plan.clecos[0]
        product_holes = replace(cleco, strategy=ClecoStrategy.PRODUCT_HOLES, product_hole_approved=False)
        bad = replace(plan, clecos=(product_holes,))
        self.assertIn("FXD-CLE-001", self.codes(bad))
        valid_product = replace(product_holes, product_hole_approved=True, post_use_process=HoleProcess.WELD_FILL_GRIND)
        checked = validate_fixture_build_plan(self.product, replace(plan, clecos=(valid_product,)))
        self.assertFalse(any(item.severity == "error" and item.rule_id == "FXD-CLE-001" for item in checked.findings))
        product_requirements = replace(
            plan.requirements, cleco_strategy=ClecoStrategy.PRODUCT_HOLES,
            product_hole_approved=False, product_hole_justification=None,
        )
        product_plan = generate_fixture_build_plan(self.product, self.concept, product_requirements)
        self.assertEqual(product_plan.clecos[0].strategy, ClecoStrategy.PRODUCT_HOLES)
        self.assertTrue(validate_fixture_build_plan(self.product, product_plan).blocked)
        approved_plan = generate_fixture_build_plan(self.product, self.concept, replace(
            product_requirements, product_hole_approved=True,
            product_hole_justification="Customer-approved plug-weld finishing process",
        ))
        self.assertFalse(validate_fixture_build_plan(self.product, approved_plan).blocked)
        compared = compare_fixture_build_plans((approved_plan, plan), self.product)
        self.assertEqual(compared[0].plan_identity, plan.identity)

    def test_lifecycle_nest_and_source_identity_are_gated(self):
        plan = self.plan()
        missing_job = replace(plan, requirements=replace(plan.requirements, job_revision=None))
        self.assertIn("FXD-COST-001", self.codes(missing_job))
        base = next(item for item in plan.components if item.identity == "m30-baseplate")
        mixed = replace(base, nest_classification=NestClassification.PRODUCT)
        self.assertIn("FXD-COST-001", self.codes(replace(plan, components=tuple(mixed if item.identity == base.identity else item for item in plan.components))))
        wrong = replace(plan, requirements=replace(plan.requirements, source_sha256="0" * 64))
        self.assertTrue(validate_fixture_build_plan(self.product, wrong).blocked)
        self.assertEqual(FIXTURE.read_bytes(), self.source)

    def test_construction_alternatives_do_not_prefer_invalid_plan(self):
        tack = self.plan()
        frame = self.plan(purpose=FixturePurpose.FULL_WELD, method=ConstructionMethod.WELDED_TUBE_FRAME,
                          lifecycle=FixtureLifecycle.PERMANENT)
        invalid = replace(tack, requirements=replace(tack.requirements, unload_clearance_evaluated=False))
        rows = compare_fixture_build_plans((invalid, frame, tack), self.product)
        self.assertEqual(rows[-1].plan_identity, invalid.identity)
        self.assertNotEqual(rows[0].status, "invalid")

    def test_real_ocp_brep_dxf_bom_and_export_gate(self):
        plan = self.plan()
        assembly = author_fixture_build(plan, self.product, OcpKernel())
        self.assertTrue(assembly.components)
        self.assertTrue(all(item.topology.solids >= 1 for item in assembly.components))
        self.assertTrue(any(item.dxf_bytes for item in assembly.components))
        package = build_fixture_build_package(assembly, plan, self.product)
        self.assertIn("bom.json", package)
        self.assertIn("nest-classification.json", package)
        self.assertIn("cleco-hole-map.json", package)
        self.assertIn("poka-yoke-map.json", package)
        self.assertTrue(any(name.startswith("step/") for name in package))
        with tempfile.TemporaryDirectory() as directory:
            paths = write_fixture_build_package(assembly, plan, self.product, directory)
            step_path = next(item for item in paths if item.suffix == ".step")
            reimported = OcpKernel().import_step(step_path)
            self.assertGreaterEqual(OcpKernel().topology_counts(reimported).solids, 1)
            dxf_path = next(item for item in paths if item.suffix == ".dxf")
            self.assertTrue(dxf_path.read_bytes().startswith(b"0\nSECTION"))
        provisional = replace(plan.requirements, adjustment_state=AdjustmentState.PROVISIONAL)
        with self.assertRaises(FixtureBuildError):
            build_fixture_build_package(assembly, replace(plan, requirements=provisional), self.product)
        self.assertEqual(FIXTURE.read_bytes(), self.source)

    def test_provisional_access_or_missing_poka_yoke_cannot_export_m30_package(self):
        frame = self.plan(
            purpose=FixturePurpose.FULL_WELD,
            method=ConstructionMethod.WELDED_TUBE_FRAME,
            lifecycle=FixtureLifecycle.PERMANENT,
        )
        missing_poka_yoke = replace(frame, poka_yokes=())
        for plan in (
                missing_poka_yoke,
                replace(frame, requirements=replace(frame.requirements, full_weld_access_available=None))):
            with self.subTest(plan=plan.identity):
                assembly = author_fixture_build(plan, self.product, OcpKernel())
                self.assertEqual(assembly.validation.status, "provisional")
                with self.assertRaisesRegex(FixtureBuildError, "validation result can be exported"):
                    build_fixture_build_package(assembly, plan, self.product)

    def test_provisional_geometry_is_never_authored_as_manufacturing(self):
        plan = self.plan()
        base = next(item for item in plan.components if item.identity == "m30-baseplate")
        proof = replace(base, geometry_authority=GeometryAuthority.PROVISIONAL_ENVELOPE)
        bad = replace(plan, components=tuple(proof if item.identity == base.identity else item for item in plan.components))
        self.assertTrue(validate_fixture_build_plan(self.product, bad).blocked)
        with self.assertRaises(FixtureBuildError):
            author_fixture_build(bad, self.product, OcpKernel())

    def test_project_export_gate_and_package_include_m30_outputs(self):
        plan = self.plan()
        project = SimpleNamespace(
            product=self.product, active=self.concept, active_validation=SimpleNamespace(
                blocked=False, status="provisional", evidence_digest="test", findings=(), version="test",
            ),
            suppressed_features=frozenset(), fixture_build=plan, workflow=None, revision_id="rev-m30-test",
        )
        self.assertIsNone(project_export_block_reason(project))
        provisional_evidence = self.plan(
            purpose=FixturePurpose.FULL_WELD,
            method=ConstructionMethod.WELDED_TUBE_FRAME,
            lifecycle=FixtureLifecycle.PERMANENT,
        )
        self.assertIn("status must be valid", project_export_block_reason(
            SimpleNamespace(**(project.__dict__ | {"fixture_build": provisional_evidence}))
        ))
        provisional = replace(plan, requirements=replace(plan.requirements, adjustment_state=AdjustmentState.PROVISIONAL))
        self.assertIn("status must be valid", project_export_block_reason(
            SimpleNamespace(**(project.__dict__ | {"fixture_build": provisional}))
        ))
        with tempfile.TemporaryDirectory() as directory:
            with patch("fxd_geometry.operations.build_fabrication_package", return_value=object()), \
                 patch("fxd_geometry.operations.write_fabrication_package", return_value=()):
                paths = export_project_package(project, directory, kernel=OcpKernel())
            names = {item.relative_to(directory).as_posix() for item in paths}
            self.assertIn("m30-manufacturing/bom.json", names)
            self.assertTrue(any(name.startswith("m30-manufacturing/step/") for name in names))


if __name__ == "__main__":
    unittest.main()
