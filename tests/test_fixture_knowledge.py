"""Public fixture precedent remains deterministic, traceable, and offline."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fxd_geometry.fixture_knowledge import (
    FIXTURE_KNOWLEDGE_SCHEMA,
    FixtureKnowledgeError,
    PrecedentQuery,
    knowledge_record_counts,
    load_fixture_knowledge,
    retrieve_precedent,
)


class FixtureKnowledgeTests(unittest.TestCase):
    def query(self, **changes):
        values = {
            "fixture_family": "linear_multi_station_weld_fixture",
            "assembly_form": "sheet-metal and fabricated weldments",
            "material_form": "plate",
            "process": "MIG welding",
            "production_volume": "repeat production",
            "handling_mode": "manual",
            "build_orientation": "accepted manufacturing orientation",
            "construction_method": "laser_cut_fabricated",
            "station_count": 4,
            "datum_opportunities": ("accepted immutable source face",),
            "support_opportunities": ("lower product surface",),
            "locator_opportunities": ("side face", "end face"),
            "clamp_direction": "+Y",
            "load_unload_intent": ("load -Y", "unload +Y"),
            "weld_access": ("qualified review",),
            "changeover_needs": ("replaceable contacts",),
        }
        values.update(changes)
        return PrecedentQuery(**values)

    def test_public_library_schema_counts_and_provenance(self):
        library = load_fixture_knowledge()
        self.assertEqual(library.schema_version, FIXTURE_KNOWLEDGE_SCHEMA)
        self.assertEqual(knowledge_record_counts(library.records), {
            "component_application": 6,
            "engineering_principle": 8,
            "fixture_pattern": 6,
            "human_acceptance": 1,
            "human_rejection": 1,
        })
        self.assertTrue(all(record.source_ids for record in library.records))
        self.assertTrue(all(source.licensing_note for source in library.sources))

    def test_serialization_and_ranking_are_stable(self):
        first = load_fixture_knowledge()
        second = load_fixture_knowledge()
        self.assertEqual(first.to_json(), second.to_json())
        first_result = retrieve_precedent(first, self.query())
        second_result = retrieve_precedent(second, self.query())
        self.assertEqual(first_result, second_result)
        self.assertEqual(
            first_result.selected_record_identities[0],
            "pattern-001-compact-continuous-base",
        )
        self.assertIn(
            "human-rejected-001-generic-m32",
            tuple(item.record_identity for item in first_result.rejected_constraints),
        )
        self.assertTrue(first_result.selected[0].score_components)
        self.assertIn("fixture_family", first_result.selected[0].matching_fields)

    def test_retrieval_matches_family_process_material_handling_and_station_count(self):
        result = retrieve_precedent(load_fixture_knowledge(), self.query())
        compact = result.compact_context()
        selected = compact["selected"]
        self.assertTrue(any("process" in item["matching_fields"] for item in selected))
        self.assertTrue(any("handling_mode" in item["matching_fields"] for item in selected))
        self.assertTrue(any("station_count" in item["matching_fields"] for item in selected))
        self.assertFalse(any(
            item["record_type"] == "human_rejection" for item in selected
        ))

    def test_retrieval_tie_breaks_by_stable_identity_and_reports_conflicts(self):
        result = retrieve_precedent(
            load_fixture_knowledge(),
            self.query(handling_mode="robot", construction_method="welded_tube_frame"),
            limit=22,
        )
        equal_score_pairs = [
            (left, right)
            for left, right in zip(result.selected, result.selected[1:])
            if left.score == right.score
        ]
        self.assertTrue(all(
            left.record_identity < right.record_identity
            for left, right in equal_score_pairs
        ))
        self.assertTrue(any(
            item.conflicts for item in result.selected + result.non_applicable
        ))

    def test_retrieval_is_offline_and_does_not_require_source_urls(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
            result = retrieve_precedent(load_fixture_knowledge(), self.query())
        self.assertTrue(result.selected)

    def test_missing_source_and_invalid_cross_reference_are_rejected(self):
        root = Path(__file__).resolve().parents[1] / "data" / "fixture_knowledge"
        records = json.loads((root / "fixture_knowledge_v1.json").read_text(encoding="utf-8"))
        records["records"][0]["source_ids"] = ["missing-source"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.json"
            path.write_text(json.dumps(records), encoding="utf-8")
            with self.assertRaisesRegex(FixtureKnowledgeError, "unknown sources"):
                load_fixture_knowledge(path, root / "fixture_knowledge_sources_v1.json")
        records["records"][0]["source_ids"] = ["destaco-welding-clamping"]
        records["records"][0]["related_record_ids"] = ["missing-record"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.json"
            path.write_text(json.dumps(records), encoding="utf-8")
            with self.assertRaisesRegex(FixtureKnowledgeError, "unknown records"):
                load_fixture_knowledge(path, root / "fixture_knowledge_sources_v1.json")

    def test_invalid_record_type_and_schema_are_rejected(self):
        root = Path(__file__).resolve().parents[1] / "data" / "fixture_knowledge"
        source_path = root / "fixture_knowledge_sources_v1.json"
        records = json.loads((root / "fixture_knowledge_v1.json").read_text(encoding="utf-8"))
        records["records"][0]["record_type"] = "secret_shop_rule"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.json"
            path.write_text(json.dumps(records), encoding="utf-8")
            with self.assertRaisesRegex(FixtureKnowledgeError, "unsupported record_type"):
                load_fixture_knowledge(path, source_path)
        records["records"][0]["record_type"] = "component_application"
        records["records"][0]["schema_version"] = "unknown"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.json"
            path.write_text(json.dumps(records), encoding="utf-8")
            with self.assertRaisesRegex(FixtureKnowledgeError, "unsupported schema_version"):
                load_fixture_knowledge(path, source_path)

    def test_public_corpus_contains_no_binary_or_downloaded_assets(self):
        root = Path(__file__).resolve().parents[1] / "data" / "fixture_knowledge"
        self.assertEqual(
            sorted(path.suffix for path in root.iterdir()),
            [".json", ".json"],
        )
        encoded = "\n".join(path.read_text(encoding="utf-8") for path in root.iterdir())
        self.assertNotIn("data:image", encoded)
        self.assertNotIn("source_step_base64", encoded)
        self.assertNotIn(".step", encoded.lower())


if __name__ == "__main__":
    unittest.main()
