"""Deterministic M32 acceptance coverage using a legally shareable synthetic bracket."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from fxd_geometry import (
    AdjustmentState, BuildComponentRole, ConstructionMethod, FixtureBuildError,
    FixtureBuildPlan, FixtureBuildRequirements, FixtureFamily, FixtureLifecycle,
    FixturePurpose, MultiStationRequirements, OcpKernel, Vec3, author_fixture_build,
    build_fixture_build_package, generate_fixture_concepts,
    generate_multi_station_fixture_alternatives, generate_multi_station_fixture_build_plan,
    load_step_for_workbench,
    product_from_workbench_document, InteractiveWorkflow, ProcessSetup, validate_fixture_build_plan,
)
from fxd_geometry.annotations import EngineeringAnnotations
from fxd_geometry.project import FxdProject


class MultiStationFixtureTests(unittest.TestCase):
    """M32 stays source-immutable and deterministic without provider credentials."""

    @classmethod
    def setUpClass(cls):
        cls.kernel = OcpKernel()
        # Two plain, synthetic plates make a legally shareable angled bracket:
        # one horizontal member and one upright member.  No customer or vendor CAD
        # is used in this repository fixture.
        horizontal = cls.kernel.make_box((0, 0, 0), (90, 38, 5))
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
        roles = [item.component.role for item in assembly.components]
        self.assertIn(BuildComponentRole.BASEPLATE, roles)
        self.assertIn(BuildComponentRole.DATUM_RAIL, roles)
        self.assertGreaterEqual(roles.count(BuildComponentRole.SUPPORT_PAD), 15)
        self.assertEqual(roles.count(BuildComponentRole.HARD_STOP), 5)
        self.assertEqual(roles.count(BuildComponentRole.CLAMP_BRACKET), 5)
        self.assertEqual(roles.count(BuildComponentRole.TOGGLE_CLAMP), 5)
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
        self.assertEqual(count_role(five_bom, "vendor-neutral toggle-clamp"), 5)
        self.assertEqual(count_role(three_bom, "vendor-neutral toggle-clamp"), 3)
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
        with self.assertRaises(FixtureBuildError):
            author_fixture_build(invalid, self.product, self.kernel)

    def test_persistence_preserves_station_identity_and_material_edit_revokes_build(self):
        plan = self.plan()
        workflow = InteractiveWorkflow(self.product.source_sha256, ProcessSetup("M32 persistence"))
        project = FxdProject.from_product(self.product, self.annotations, workflow=workflow).with_fixture_build(plan)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m32.fxd.json"
            project.save(path)
            restored = FxdProject.load(path)
        self.assertEqual(restored.fixture_build.to_dict(), plan.to_dict())
        changed = project.edit_parameter("clearance", 3.0, "M32 material geometry review edit")
        self.assertIsNone(changed.fixture_build)
        self.assertIsNone(changed.approved_revision)
