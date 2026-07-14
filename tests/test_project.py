import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fxd_geometry import (
    Assumption,
    CriticalCharacteristic,
    EngineeringAnnotations,
    GeometryReference,
    Vec3,
    WeldJoint,
    import_step,
)
from fxd_geometry.project import FxdProject, ProjectFormatError


class ProjectPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("tests/fixtures/synthetic_assembly.step")
        product = import_step(self.source)
        component = product.components[0]
        body = component.bodies[0]
        reference = GeometryReference(component.identity, body.identity)
        annotations = EngineeringAnnotations(
            product.source_sha256, product.source_name,
            Vec3(0, 0, 1), Vec3(1, 0, 0), "manual MIG", 12,
            critical_characteristics=(CriticalCharacteristic(
                "fixture datum", (reference,), 25.0, "mm", 0.2, "synthetic"),),
            permitted_locating_surfaces=(reference,),
            forbidden_contact_areas=(reference,),
            weld_joints=(WeldJoint(
                "weld-1", (reference,), "MIG", "synthetic joint", 1,
                Vec3(1, 0, 0), 1.5, "kJ/mm", Vec3(0, 1, 0), True, 1,
                ("verify heat input",)),),
            shop_constraints=("manual loading",),
            assumptions=(Assumption("shift", "single", "test evidence"),),
        )
        self.project = FxdProject.from_product(product, annotations)

    def test_round_trip_preserves_source_annotations_validation_and_review_state(self):
        project = self.project.suppress("support-1")
        project = project.correct("datum", "BRACKET_BODY", "engineer review")
        project = project.decide("reject", "unsafe synthetic concept")
        before = project.active_validation
        with tempfile.TemporaryDirectory() as directory:
            path = project.save(Path(directory) / "fixture.fxd.json")
            restored = FxdProject.load(path)
        self.assertEqual(restored.product.source_sha256, self.project.product.source_sha256)
        self.assertEqual(restored.product.source_bytes, self.source.read_bytes())
        self.assertEqual(restored.annotations, self.project.annotations)
        self.assertIn("support-1", restored.suppressed_features)
        self.assertEqual(restored.active.corrections[0].key, "datum")
        self.assertEqual(restored.decisions[-1].action, "reject")
        self.assertEqual(restored.active_validation.status, before.status)
        self.assertEqual(restored.active_validation.evidence_digest, before.evidence_digest)

    def test_invalid_validation_cannot_be_approved(self):
        self.assertTrue(self.project.active_validation.blocked)
        with self.assertRaisesRegex(ProjectFormatError, "cannot be approved"):
            self.project.decide("approve_for_review", "should fail")

    def test_unknown_layers_and_features_fail_closed(self):
        with self.assertRaisesRegex(ProjectFormatError, "unknown visual layer"):
            self.project.toggle_layer("magic")
        with self.assertRaisesRegex(ProjectFormatError, "unknown fixture feature"):
            self.project.suppress("not-a-real-feature")

    def test_tampered_validation_snapshot_fails_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.project.save(Path(directory) / "fixture.fxd.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            identity = self.project.active_concept
            payload["validations"][identity]["evidence_digest"] = "tampered"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ProjectFormatError, "validation changed"):
                FxdProject.load(path)

    def test_bad_format_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ProjectFormatError):
                FxdProject.load(path)


if __name__ == "__main__":
    unittest.main()
