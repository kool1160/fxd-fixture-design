import tempfile
import unittest
from pathlib import Path

from fxd_geometry import EngineeringAnnotations, Vec3, import_step
from fxd_geometry.project import FxdProject, ProjectFormatError


class ProjectPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("tests/fixtures/synthetic_assembly.step")
        product = import_step(self.source)
        annotations = EngineeringAnnotations.for_product(
            product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=12)
        self.project = FxdProject.from_product(product, annotations)

    def test_round_trip_preserves_source_identity_and_review_state(self):
        project = self.project.suppress("support-1").correct("datum", "BRACKET_BODY", "engineer review")
        project = project.decide("approve_for_review", "reviewed locally")
        with tempfile.TemporaryDirectory() as directory:
            path = project.save(Path(directory) / "fixture.fxd.json")
            restored = FxdProject.load(path)
        self.assertEqual(restored.product.source_sha256, self.project.product.source_sha256)
        self.assertEqual(restored.product.source_bytes, self.source.read_bytes())
        self.assertIn("support-1", restored.suppressed_features)
        self.assertEqual(restored.active.corrections[0].key, "datum")
        self.assertEqual(restored.decisions[-1].action, "approve_for_review")
        self.assertEqual(restored.annotations.build_orientation, Vec3(0, 0, 1))

    def test_bad_format_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ProjectFormatError):
                FxdProject.load(path)


if __name__ == "__main__":
    unittest.main()
