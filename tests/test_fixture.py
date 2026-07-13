import unittest
from pathlib import Path

from fxd_geometry import (EngineeringAnnotations, FixtureGenerationError, FixtureParameters,
                          GeometryReference, Vec3, generate_fixture_primitives, import_step)


class FixturePrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=1)

    def test_primitives_are_traceable_parameterized_and_explicit(self):
        concept = generate_fixture_primitives(self.product, self.annotations)
        self.assertEqual(concept.units, "mm")
        self.assertEqual(concept.source_sha256, self.product.source_sha256)
        self.assertEqual([feature.identity for feature in concept.features],
                         ["baseplate", "support-1", "support-2", "support-3", "loading-stop", "round-pin-1", "relieved-locator-1"])
        self.assertEqual(concept.features[1].source_references[0].component_identity, "BRACKET_A")
        self.assertTrue(all(feature.rule and feature.parameters for feature in concept.features))
        self.assertTrue(any(item.code == "concept_requires_engineering_review" for item in concept.findings))

    def test_forbidden_source_and_invalid_parameters_are_not_silently_accepted(self):
        with self.assertRaises(FixtureGenerationError):
            FixtureParameters(base_thickness=0)
        bad = EngineeringAnnotations(**{**self.annotations.__dict__,
            "permitted_locating_surfaces": (GeometryReference("missing"),)})
        with self.assertRaisesRegex(ValueError, "unknown component"):
            generate_fixture_primitives(self.product, bad)

    def test_unload_margin_and_forbidden_contacts_are_reported(self):
        annotations = EngineeringAnnotations(**{**self.annotations.__dict__,
            "forbidden_contact_areas": (GeometryReference("BRACKET_A", "BRACKET_BODY"),)})
        concept = generate_fixture_primitives(self.product, annotations, FixtureParameters(base_margin=0.1))
        codes = {item.code for item in concept.findings}
        self.assertIn("trapped_part", codes)
        self.assertIn("forbidden_contact", codes)


if __name__ == "__main__":
    unittest.main()
