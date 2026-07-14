import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (
    EngineeringAnnotations,
    FixtureFinding,
    KernelCapabilities,
    KernelEdgeRecord,
    KernelTriangleMesh,
    ManufacturingGeometry,
    ManufacturingSolid,
    Vec3,
    build_review_geometry,
    generate_fixture_concepts,
    import_step,
)


class DisplayKernel:
    capabilities = KernelCapabilities("test", "1", True, True, True, True, True, True)

    def __init__(self):
        self.sections = []

    def tessellate(self, shape, **_kwargs):
        return (KernelTriangleMesh(
            "face:1", ((0., 0., -1.), (1., 0., 1.), (0., 1., 1.)), ((0, 1, 2),)),)

    def edge_records(self, shape):
        prefix = "section-edge" if isinstance(shape, tuple) and shape[0] == "section" else "edge"
        return (KernelEdgeRecord(prefix + ":1", (0., 0., 0.), (1., 0., 0.)),)

    def section(self, shape, plane_origin_mm, plane_normal):
        self.sections.append((shape, plane_origin_mm, plane_normal))
        return ("section", shape)


class VisualContractTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="MIG", production_quantity=1)
        self.concept = generate_fixture_concepts(self.product, annotations).recommended

    def manufacturing(self, concept):
        solids = tuple(ManufacturingSolid(
            feature.identity, feature.kind, "laser_cut", "steel", 1.0, "nominal", 0.1, 0.0,
            None, (), object()) for feature in concept.fixture.features)
        return ManufacturingGeometry(
            concept.identity, self.product.source_sha256, "mm",
            tuple(item.identity for item in concept.fixture.features), solids, object(),
            b"ISO-10303-21;\nEND-ISO-10303-21;", b"0\nSECTION\n0\nEOF\n")

    def test_fixture_and_product_items_keep_traceability_and_sections(self):
        kernel = DisplayKernel()
        geometry = build_review_geometry(
            kernel, self.product, object(), self.concept, self.manufacturing(self.concept))
        self.assertEqual(geometry.concept_identity, self.concept.identity)
        self.assertEqual(geometry.items[0].identity, "product")
        self.assertTrue(geometry.items[0].source_references)
        self.assertEqual(len(geometry.items), len(self.concept.fixture.features) + 1)
        fixture = geometry.item(self.concept.fixture.features[0].identity)
        self.assertEqual(fixture.rule, self.concept.fixture.features[0].rule)
        self.assertTrue(fixture.meshes[0].face_reference.startswith(fixture.identity + "/"))
        self.assertTrue(fixture.edges[0].reference.startswith(fixture.identity + "/edge/"))
        self.assertTrue(fixture.section_edges[0].reference.startswith(fixture.identity + "/section/"))
        self.assertEqual(len(kernel.sections), len(geometry.items))

    def test_feature_findings_are_not_broadcast_to_every_visual_item(self):
        first, second = self.concept.fixture.features[:2]
        findings = (
            FixtureFinding("obvious_collision", "error", first.identity, "first only"),
            FixtureFinding("concept_requires_engineering_review", "warning", None, "global"),
        )
        fixture = replace(self.concept.fixture, findings=findings)
        concept = replace(self.concept, fixture=fixture)
        geometry = build_review_geometry(
            DisplayKernel(), self.product, object(), concept, self.manufacturing(concept))
        first_item = geometry.item(first.identity)
        second_item = geometry.item(second.identity)
        self.assertTrue(first_item.has_collision)
        self.assertFalse(second_item.has_collision)
        self.assertIn("concept_requires_engineering_review", first_item.findings)
        self.assertIn("concept_requires_engineering_review", second_item.findings)
        self.assertNotIn("obvious_collision", second_item.findings)

    def test_manufacturing_source_mismatch_fails_closed(self):
        manufacturing = replace(self.manufacturing(self.concept), source_sha256="wrong")
        with self.assertRaisesRegex(ValueError, "immutable product source"):
            build_review_geometry(DisplayKernel(), self.product, object(), self.concept, manufacturing)


if __name__ == "__main__":
    unittest.main()
