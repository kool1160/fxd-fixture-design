import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, ManufacturingSpec, Vec3,
                          build_fabrication_package, generate_fixture_concepts,
                          generate_fixture_primitives, generate_manufacturing_geometry,
                          import_step, validate_fixture_concept)
from fxd_geometry.export import ExportError
from fxd_geometry.kernel import KernelCapabilities, KernelOperationError


class FakeKernel:
    """Contract test double; records the exact manufacturing operations."""

    capabilities = KernelCapabilities("test", "1", True, True, True, True, True, True)

    def __init__(self):
        self.slots = []
        self.holes = []
        self.cuts = []

    def make_box(self, minimum, maximum):
        return ("box", minimum, maximum)

    def make_cylinder(self, center, radius, height):
        return ("cylinder", center, radius, height)

    def cut(self, left, right):
        self.cuts.append(right)
        return ("cut", left, right)

    def make_slot(self, minimum, maximum):
        value = ("slot", minimum, maximum)
        self.slots.append(value)
        return value

    def make_hole(self, center, radius, height):
        value = ("hole", center, radius, height)
        self.holes.append(value)
        return value

    def compound(self, models):
        return ("compound", models)

    def topology_counts(self, model):
        return type("Counts", (), {"solids": 1})()

    def export_step(self, model):
        return b"ISO-10303-21;\nEND-ISO-10303-21;\n"


class ManufacturingGeometryTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=1)

    def test_features_have_explicit_public_fabrication_intent(self):
        concept = generate_fixture_primitives(self.product, self.annotations)
        self.assertTrue(all(feature.manufacturing for feature in concept.features))
        base = concept.features[0].manufacturing
        self.assertEqual(base, ManufacturingSpec("laser_cut", "mild_steel", 10.0,
                                                  "machined_datum", 0.5, 1.0,
                                                  "baseplate_slot", ("profile_cut", "deburr")))
        self.assertEqual(base.method, "laser_cut")
        self.assertEqual(next(f for f in concept.features if f.kind == "round_pin").manufacturing.method,
                         "machined")

    def test_kernel_and_dxf_share_the_same_cut_operation_plan(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        kernel = FakeKernel()
        geometry = generate_manufacturing_geometry(concept, kernel)
        expected = tuple(feature.identity for feature in concept.fixture.features)
        self.assertEqual(geometry.units, "mm")
        self.assertEqual(geometry.source_sha256, concept.fixture.source_sha256)
        self.assertEqual(geometry.feature_identities, expected)
        self.assertEqual(geometry.identities, expected)
        self.assertTrue(geometry.step_bytes.startswith(b"ISO-10303-21"))
        self.assertTrue(geometry.dxf_bytes.startswith(b"0\nSECTION"))

        # Every supported B-Rep cut type must have a corresponding DXF layer.
        self.assertGreaterEqual(len(kernel.slots), 4)
        self.assertEqual(len(kernel.holes), 1)
        self.assertEqual(len(kernel.cuts), len(kernel.slots) + len(kernel.holes))
        self.assertIn(b"baseplate_slot", geometry.dxf_bytes)
        self.assertIn(b"baseplate_pin_hole", geometry.dxf_bytes)
        self.assertIn(b"support_pad_relief", geometry.dxf_bytes)
        self.assertIn(b"CIRCLE", geometry.dxf_bytes)

        validation = validate_fixture_concept(self.product, concept)
        self.assertFalse(validation.blocked)
        package = build_fabrication_package(
            concept, manufacturing=geometry, validation=validation)
        self.assertIn('"geometry_source": "reviewed_real_kernel"', package.manifest)
        self.assertIn("supported prismatic/cylindrical DXF", package.manifest)
        self.assertIn("baseplate_slot", package.dxf)
        self.assertIn("baseplate_pin_hole", package.dxf)

    def test_export_rejects_wrong_source_missing_or_reordered_features(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        geometry = generate_manufacturing_geometry(concept, FakeKernel())
        with self.assertRaisesRegex(ExportError, "source assembly"):
            build_fabrication_package(concept, manufacturing=replace(geometry, source_sha256="wrong"))
        reversed_solids = tuple(reversed(geometry.solids))
        with self.assertRaisesRegex(KernelOperationError, "declared feature order"):
            replace(geometry, solids=reversed_solids)
        with self.assertRaisesRegex(KernelOperationError, "declared feature order"):
            replace(geometry, solids=geometry.solids[:-1])

    def test_malformed_step_or_dxf_cannot_be_labeled_reviewed_geometry(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        geometry = generate_manufacturing_geometry(concept, FakeKernel())
        with self.assertRaisesRegex(KernelOperationError, "STEP output is malformed"):
            replace(geometry, step_bytes=b"not step")
        with self.assertRaisesRegex(KernelOperationError, "DXF output is malformed"):
            replace(geometry, dxf_bytes=b"not dxf")


if __name__ == "__main__":
    unittest.main()
