import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, ManufacturingSpec, Vec3,
                          generate_fixture_concepts, generate_fixture_primitives,
                          generate_manufacturing_geometry, import_step)
from fxd_geometry.kernel import KernelCapabilities


class FakeKernel:
    """Contract test double; real OCP coverage remains in kernel tests."""

    capabilities = KernelCapabilities("test", "1", True, True, True, True, True, True)

    def make_box(self, minimum, maximum):
        return ("box", minimum, maximum)

    def make_cylinder(self, center, radius, height):
        return ("cylinder", center, radius, height)

    def compound(self, models):
        return ("compound", models)

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

    def test_kernel_boundary_authors_opaque_solids_and_step(self):
        concept = generate_fixture_concepts(self.product, self.annotations).recommended
        geometry = generate_manufacturing_geometry(concept, FakeKernel())
        self.assertEqual(geometry.units, "mm")
        self.assertEqual(len(geometry.solids), len(concept.fixture.features))
        self.assertIn("round-pin-1", geometry.identities)
        self.assertTrue(geometry.step_bytes.startswith(b"ISO-10303-21"))


if __name__ == "__main__":
    unittest.main()
