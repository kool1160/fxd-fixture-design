import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fxd_geometry import (
    ComponentGeometryError,
    HoleSpec,
    ManufacturingFinding,
    OcpKernel,
    Vec3,
    build_manufacturing_export_package,
    generate_fixture_concepts,
    generate_manufacturing_assembly,
    generate_manufacturing_assembly_for_product,
    import_step,
    validate_fixture_concept,
    validate_manufacturing_assembly,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"


class ManufacturingComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.product = import_step(FIXTURE)
        cls.annotations = cls.product.annotations_for_product if hasattr(cls.product, "annotations_for_product") else None
        from fxd_geometry import EngineeringAnnotations
        cls.annotations = EngineeringAnnotations.for_product(
            cls.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=1,
        )
        cls.concept = generate_fixture_concepts(cls.product, cls.annotations).recommended

    def make_assembly(self):
        return generate_manufacturing_assembly(self.product, self.concept, OcpKernel())

    def test_real_plate_brep_and_thickness(self):
        assembly = self.make_assembly()
        base = next(item for item in assembly.components if item.identity == "mfg-baseplate")
        self.assertGreaterEqual(OcpKernel().topology_counts(base.shape).solids, 1)
        self.assertEqual(base.thickness_mm, 10.0)
        self.assertEqual(len(base.holes), 4)
        self.assertEqual(len(base.tab_slots), 1)

    def test_deterministic_step_dxf_and_reimport(self):
        first = self.make_assembly()
        second = self.make_assembly()
        left = next(item for item in first.exports if item.component_identity == "mfg-baseplate")
        right = next(item for item in second.exports if item.component_identity == "mfg-baseplate")
        self.assertEqual(left.step_bytes, right.step_bytes)
        self.assertEqual(left.dxf_bytes, right.dxf_bytes)
        self.assertTrue(left.dxf_bytes.startswith(b"0\nSECTION"))
        imported = OcpKernel().import_step(left.step_bytes)
        self.assertGreaterEqual(OcpKernel().topology_counts(imported).solids, 1)

    def test_invalid_identity_and_component_relationships_fail_closed(self):
        assembly = self.make_assembly()
        bad_source = replace(assembly, source_sha256="bad")
        self.assertIn("source_identity_mismatch", {item.code for item in validate_manufacturing_assembly(self.product, bad_source)})
        orphan = replace(assembly, components=(replace(assembly.components[0], parent_component_identity="missing"),) + assembly.components[1:])
        self.assertIn("orphaned_component", {item.code for item in validate_manufacturing_assembly(self.product, orphan)})
        duplicate = replace(assembly, components=(assembly.components[0], replace(assembly.components[1], identity=assembly.components[0].identity)))
        self.assertIn("duplicate_component_identity", {item.code for item in validate_manufacturing_assembly(self.product, duplicate)})

    def test_hole_edge_distance_and_overlap_are_blocking(self):
        assembly = self.make_assembly()
        base = next(item for item in assembly.components if item.identity == "mfg-baseplate")
        bad_holes = (
            HoleSpec("bad-edge", "clearance", Vec3(1, 1, 0), 3, 12, "clearance", 0),
            HoleSpec("overlap", "clearance", Vec3(1.5, 1, 0), 3, 12, "clearance", 1),
        )
        changed = replace(assembly, components=tuple(replace(item, holes=bad_holes) if item is base else item for item in assembly.components))
        codes = {item.code for item in validate_manufacturing_assembly(self.product, changed)}
        self.assertIn("hole_edge_distance", codes)
        self.assertIn("overlapping_holes", codes)

    def test_missing_thickness_and_invalid_contract_fail_closed(self):
        assembly = self.make_assembly()
        base = next(item for item in assembly.components if item.identity == "mfg-baseplate")
        changed = replace(assembly, components=tuple(replace(item, thickness_mm=None) if item is base else item for item in assembly.components))
        self.assertIn("missing_thickness", {item.code for item in validate_manufacturing_assembly(self.product, changed)})
        with self.assertRaises(ComponentGeometryError):
            replace(base, material="")

    def test_validation_integration_and_export_gate(self):
        assembly = self.make_assembly()
        invalid_assembly = replace(assembly, source_sha256="bad")
        validation = validate_fixture_concept(self.product, self.concept, manufacturing_assembly=invalid_assembly)
        self.assertTrue(any(item.subsystem == "manufacturing" for item in validation.findings))
        review_gate = SimpleNamespace(blocked=False, status="provisional", evidence_digest="test")
        package = build_manufacturing_export_package(assembly, review_gate)
        self.assertIn("manifest.json", package)
        self.assertIn('"review_status": "ENGINEERING_REVIEW_REQUIRED"', package["manifest.json"])
        blocked = replace(assembly, findings=(ManufacturingFinding("bad", "mfg_test", "error", "blocked"),))
        with self.assertRaises(ComponentGeometryError):
            build_manufacturing_export_package(blocked, validation)

    def test_source_bytes_remain_unchanged_and_project_roundtrip_stays_compatible(self):
        source = FIXTURE.read_bytes()
        self.make_assembly()
        self.assertEqual(source, FIXTURE.read_bytes())

    def test_product_compatibility_entry_point_preserves_kernel_collision_findings(self):
        source = FIXTURE.read_bytes()
        assembly = self.make_assembly()
        first, second = assembly.components[:2]
        overlapping = replace(
            assembly,
            components=(
                replace(first, parent_component_identity=None, interface=None),
                replace(second, shape=first.shape, bounds=first.bounds,
                        parent_component_identity=None, interface=None),
            ) + assembly.components[2:],
        )
        kernel = OcpKernel()
        kernel_findings = validate_manufacturing_assembly(self.product, overlapping, kernel=kernel)
        self.assertIn("component_collision", {item.code for item in kernel_findings})
        blocked = replace(overlapping, findings=kernel_findings)

        with patch("fxd_geometry.component_geometry.generate_manufacturing_assembly", return_value=blocked):
            retained = generate_manufacturing_assembly_for_product(self.product, self.concept, kernel)

        self.assertIn("component_collision", {item.code for item in retained.findings})
        self.assertTrue(retained.blocked)
        with self.assertRaises(ComponentGeometryError):
            build_manufacturing_export_package(retained, SimpleNamespace(blocked=False))
        self.assertEqual(source, FIXTURE.read_bytes())


if __name__ == "__main__":
    unittest.main()
