import json
import tempfile
import unittest
from pathlib import Path
from fxd_geometry import (EngineeringAnnotations, Vec3, VisualProject,
    generate_fixture_concepts, import_step, load_project, save_project,
    scene_payload, validate_fixture_concept)

class VisualApplicationTests(unittest.TestCase):
    def setUp(self):
        product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        annotations = EngineeringAnnotations.for_product(product, build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0), process_type="manual MIG", production_quantity=1)
        concept = generate_fixture_concepts(product, annotations).recommended
        self.project = VisualProject(product, concept, validate_fixture_concept(product, concept))

    def test_scene_is_traceable_and_status_is_prominent(self):
        scene = scene_payload(self.project)
        self.assertEqual(scene["schema"], "fxd-visual-scene-v1")
        self.assertEqual(scene["status"], "invalid")
        self.assertTrue(all(item.get("source_reference") for item in scene["items"]))

    def test_edits_are_separate_from_source_and_visible(self):
        edited = self.project.edit_feature("baseplate", state="suppressed")
        self.assertEqual(edited.product.source_bytes, self.project.product.source_bytes)
        self.assertNotIn("baseplate", {item["identity"] for item in scene_payload(edited)["items"]})
        self.assertIn("baseplate", {item["identity"] for item in scene_payload(self.project)["items"]})

    def test_project_round_trip_reloads_source_and_overrides(self):
        edited = self.project.edit_feature("baseplate", state="suppressed")
        with tempfile.TemporaryDirectory() as directory:
            path = save_project(edited, Path(directory) / "review.fxd.json")
            self.assertEqual(json.loads(path.read_text())["schema"], "fxd-project-v1")
            def rebuild(raw, name):
                product = import_step(raw.decode("utf-8"), source_name=name)
                annotations = EngineeringAnnotations.for_product(product, build_orientation=Vec3(0, 0, 1),
                    loading_direction=Vec3(1, 0, 0), process_type="manual MIG", production_quantity=1)
                concept = generate_fixture_concepts(product, annotations).recommended
                return product, concept, validate_fixture_concept(product, concept)
            reloaded = load_project(path, rebuild)
            self.assertEqual(reloaded.product.source_sha256, self.project.product.source_sha256)
            self.assertEqual(reloaded.overrides[0].state, "suppressed")

    def test_blocked_concept_cannot_be_approved(self):
        with self.assertRaisesRegex(ValueError, "cannot be approved"):
            self.project.approve()
