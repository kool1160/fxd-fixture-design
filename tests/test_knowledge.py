import json
import tempfile
import unittest
from pathlib import Path

from fxd_geometry import (CorrectionRecord, EngineeringAnnotations, FixtureCorrection,
                          KnowledgeError, KnowledgeStore, Vec3, generate_fixture_concepts,
                          import_step, private_knowledge_path)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=10)
        self.concept = generate_fixture_concepts(self.product, annotations).ranked[0]

    def test_record_is_attributable_copy_on_write_and_excludes_geometry(self):
        record = self._record()
        payload = record.to_dict()
        self.assertEqual(payload["source_digest"], self.product.source_sha256)
        self.assertEqual(payload["author"], "engineer-1")
        self.assertNotIn("bounds", json.dumps(payload))
        self.assertNotIn("references", json.dumps(payload))
        training = record.to_training_dict()
        self.assertNotIn("source_digest", training)
        self.assertNotIn("concept_identity", training)
        self.assertEqual(training["privacy"], "source_geometry_excluded")

    def test_decision_state_and_scope_are_gated(self):
        with self.assertRaises(KnowledgeError):
            self._record(decision="rejected")
        with self.assertRaises(KnowledgeError):
            self._record(scope="universal")
        accepted = self._record(decision="accepted", accepted_outcome="keep two supports")
        self.assertEqual(accepted.decision, "accepted")

    def test_store_has_duplicate_guard_and_separate_training_export(self):
        store = KnowledgeStore().add(self._record())
        with self.assertRaises(KnowledgeError):
            store.add(self._record())
        with tempfile.TemporaryDirectory() as directory:
            local_path = Path(directory) / "corrections.json"
            store.save(local_path)
            self.assertEqual(KnowledgeStore.load(local_path), store)
            path = Path(directory) / "training.json"
            store.save_training_view(path)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], "fxd-training-knowledge-v1")
            self.assertNotIn("source_digest", saved["records"][0])

    def test_private_store_location_is_explicitly_ignored(self):
        self.assertEqual(private_knowledge_path(), Path(".fxd/knowledge/corrections.json"))
        self.assertIn(".fxd/knowledge/", Path(".gitignore").read_text(encoding="utf-8"))

    def _record(self, **kwargs):
        return CorrectionRecord.from_concept(
            "record-1", "engineer-1", "2026-07-13T00:00:00Z", self.concept,
            FixtureCorrection("clamp_force", "review", "force data missing"), **kwargs)


if __name__ == "__main__":
    unittest.main()
