import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, KernelCapabilities, KernelEdgeRecord,
                          KernelTriangleMesh, ManufacturingGeometry, ManufacturingSolid,
                          Vec3, build_review_geometry, generate_fixture_concepts, import_step)


class DisplayKernel:
    capabilities = KernelCapabilities("test", "1", True, True, True, True, True, True)

    def tessellate(self, shape, **_kwargs):
        return (KernelTriangleMesh("face:1", ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)), ((0, 1, 2),)),)

    def edge_records(self, shape):
        return (KernelEdgeRecord("edge:1", (0., 0., 0.), (1., 0., 0.)),)


class VisualContractTests(unittest.TestCase):
    def test_fixture_and_product_display_items_keep_traceability(self):
        product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        annotations = EngineeringAnnotations.for_product(
            product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=1)
        concept = generate_fixture_concepts(product, annotations).recommended
        solids = tuple(ManufacturingSolid(
            feature.identity, feature.kind, "laser_cut", "steel", 1.0, "nominal", 0.1, 0.0,
            None, (), object()) for feature in concept.fixture.features)
        manufacturing = ManufacturingGeometry(
            concept.identity, product.source_sha256, "mm",
            tuple(item.identity for item in concept.fixture.features), solids, object(),
            b"ISO-10303-21;\nEND-ISO-10303-21;", b"0\nSECTION\n0\nEOF\n")
        geometry = build_review_geometry(DisplayKernel(), product, object(), concept, manufacturing)
        self.assertEqual(geometry.items[0].identity, "product")
        self.assertEqual(len(geometry.items), len(concept.fixture.features) + 1)
        fixture = geometry.item(concept.fixture.features[0].identity)
        self.assertEqual(fixture.rule, concept.fixture.features[0].rule)
        self.assertTrue(fixture.meshes[0].face_reference.startswith(fixture.identity + "/"))
        self.assertTrue(fixture.edges[0].reference.startswith(fixture.identity + "/"))


if __name__ == "__main__":
    unittest.main()
