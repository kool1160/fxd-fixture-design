"""Adversarial regression tests for the non-runtime fixture-library research."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import validate_fixture_library_research as research


DATA_FILES = (
    "fixture_library_reference_v1.json",
    "fixture_family_templates_v1.json",
    "component_patterns_v1.json",
    "failure_modes_v1.json",
    "synthetic_examples_v1.json",
)


class FixtureLibraryResearchTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.documents = {
            filename: research.load_json(research.DATA_DIR / filename)
            for filename in DATA_FILES
        }

    def _resign(self, record: dict[str, object]) -> None:
        research.refresh_revision_evidence(record)

    def _assert_rejected(self, mutate, expected: str) -> None:
        documents = deepcopy(self.documents)
        mutate(documents)
        with TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            for filename, document in documents.items():
                (temporary_path / filename).write_text(
                    json.dumps(document, indent=2) + "\n", encoding="utf-8"
                )
            original_data_dir = research.DATA_DIR
            research.DATA_DIR = temporary_path
            try:
                with self.assertRaisesRegex(research.ResearchValidationError, expected):
                    research.validate_corpus()
            finally:
                research.DATA_DIR = original_data_dir

    def test_00_valid_reference_corpus_passes(self) -> None:
        counts = research.validate_corpus()
        self.assertEqual(83, sum(
            value
            for key, value in counts.items()
            if key not in {"sources", "complete_item_examples", "shop_standard_examples"}
        ))

    def test_01_duplicate_common_item_identity_rejected(self) -> None:
        def mutate(documents):
            records = documents["fixture_library_reference_v1.json"]["engineering_principles"]
            records[1]["item_id"] = records[0]["item_id"]
        self._assert_rejected(mutate, "duplicate identity")

    def test_02_missing_source_reference_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["engineering_principles"][0]
            record["source_ids"] = ["source-that-does-not-exist"]
            self._resign(record)
        self._assert_rejected(mutate, "unresolved source identities")

    def test_03_illegal_authority_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["engineering_principles"][0]
            record["authority_level"] = "unbounded_exact_authority"
            self._resign(record)
        self._assert_rejected(mutate, "not in")

    def test_04_missing_required_units_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["engineering_principles"][0]
            del record["units"]
            self._resign(record)
        self._assert_rejected(mutate, "missing required property 'units'")

    def test_05_template_without_human_questions_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_family_templates_v1.json"]["templates"][0]
            record["required_human_review_questions"] = []
            self._resign(record)
        self._assert_rejected(mutate, "array has too few items")

    def test_06_duplicate_source_identity_rejected(self) -> None:
        def mutate(documents):
            records = documents["fixture_library_reference_v1.json"]["sources"]
            records[1]["source_id"] = records[0]["source_id"]
        self._assert_rejected(mutate, "duplicate identity")

    def test_07_duplicate_fixture_template_identity_rejected(self) -> None:
        def mutate(documents):
            records = documents["fixture_family_templates_v1.json"]["templates"]
            records[1]["template_id"] = records[0]["template_id"]
        self._assert_rejected(mutate, "duplicate identity")

    def test_08_duplicate_process_context_identity_rejected(self) -> None:
        def mutate(documents):
            records = documents["fixture_library_reference_v1.json"]["process_context_patterns"]
            records[1]["asset_id"] = records[0]["asset_id"]
        self._assert_rejected(mutate, "duplicate identity")

    def test_09_duplicate_benchmark_identity_rejected(self) -> None:
        def mutate(documents):
            records = documents["synthetic_examples_v1.json"]["cases"]
            records[1]["case_id"] = records[0]["case_id"]
        self._assert_rejected(mutate, "duplicate identity")

    def test_10_dangling_benchmark_context_reference_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["process_context_asset_ids"] = ["missing-context-asset"]
            self._resign(record)
        self._assert_rejected(mutate, "unresolved process-context identities")

    def test_11_malformed_revision_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_family_templates_v1.json"]["templates"][0]
            record["revision"]["revision_id"] = "not-a-revision"
        self._assert_rejected(mutate, "does not match")

    def test_12_cloned_filler_cannot_inflate_count_rejected(self) -> None:
        def mutate(documents):
            records = documents["component_patterns_v1.json"]["records"]
            template = deepcopy(records[0])
            for index in range(1, 20):
                identity = records[index]["item_id"]
                name = records[index]["name"]
                records[index] = deepcopy(template)
                records[index]["item_id"] = identity
                records[index]["name"] = name
                records[index]["provenance"]["record_identity"] = identity
                self._resign(records[index])
        self._assert_rejected(mutate, "semantic duplicate records")

    def test_13_invalid_scope_precedence_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["shop_standard_examples"][0]
            record["precedence_level"] = 6
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 3")

    def test_14_production_maximum_below_minimum_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_family_templates_v1.json"]["templates"][0]
            record["production_volume_range"]["minimum"] = 10
            record["production_volume_range"]["maximum"] = 2
            self._resign(record)
        self._assert_rejected(mutate, "production minimum exceeds maximum")

    def test_15_provisional_context_collision_authority_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["process_context_patterns"][0]
            record["movement_states"][0]["authoritative_for_collision"] = True
            self._resign(record)
        self._assert_rejected(mutate, "expected constant False")

    def test_16_invalid_calendar_date_rejected(self) -> None:
        def mutate(documents):
            documents["fixture_library_reference_v1.json"]["sources"][0][
                "date_accessed"
            ] = "2026-02-30"
        self._assert_rejected(mutate, "invalid calendar date")

    def test_17_provisional_exact_preview_and_step_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["authority_level"] = "provisional_review_envelope"
            record["preview_representation"]["authority"] = "exact"
            record["preview_representation"]["kind"] = "exact_tessellation"
            record["export_participation"]["fixture_component_step"] = "permitted"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant")

    def test_18_supplier_exact_without_evidence_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["authority_level"] = "supplier_authorized_exact_cad"
            record["category"] = "private_purchased_tooling"
            record["supplier_or_author"] = None
            record["model_or_internal_number"] = None
            record["source_file"] = None
            self._resign(record)
        self._assert_rejected(mutate, "expected type")

    def test_19_private_path_and_cad_filename_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["provenance"]["derivation_note"] = (
                "Imported from C:\\\\Users\\\\Chris\\\\Private\\\\customer_fixture.step"
            )
            self._resign(record)
        self._assert_rejected(mutate, "likely private payload reference")

    def test_20_zero_mounting_frame_axis_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["mounting_interfaces"][0]["frame"]["axes"]["x"] = [0, 0, 0]
            self._resign(record)
        self._assert_rejected(mutate, "zero-length direction")

    def test_21_zero_functional_direction_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["functional_interfaces"][0]["direction"] = [0, 0, 0]
            self._resign(record)
        self._assert_rejected(mutate, "zero-length direction")

    def test_22_non_orthogonal_frame_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["local_coordinate_system"]["axes"]["y"] = [1, 0, 0]
            self._resign(record)
        self._assert_rejected(mutate, "axes are not orthogonal")

    def test_23_contradictory_output_participation_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["engineering_principles"][0]
            record["export_participation"]["fixture_assembly_step"] = "permitted"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 'excluded'")

    def test_24_missing_movement_state_reference_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["functional_interfaces"][0]["movement_state"] = "missing-state"
            self._resign(record)
        self._assert_rejected(mutate, "movement-state reference does not resolve")

    def test_25_process_context_fixture_bom_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["process_context_patterns"][0]
            record["output_participation"]["fixture_bom"] = "permitted"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 'excluded'")

    def test_26_invalid_revision_ancestry_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_family_templates_v1.json"]["templates"][0]
            record["revision"]["parent_revision_id"] = record["revision"]["revision_id"]
            self._resign(record)
        self._assert_rejected(mutate, "invalid ancestry")

    def test_27_selected_release_without_explicit_permission_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["privacy_classification"] = "selected_public_release"
            record["provenance"]["origin_classification"] = "selected_public_release"
            record["rights_and_release"]["public_release_permission"] = False
            self._resign(record)
        self._assert_rejected(mutate, "expected constant True")

    def test_28_revoked_public_rights_still_permitting_export_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            rights = record["rights_and_release"]
            rights["revocation_state"] = "revoked"
            rights["revocation_timestamp"] = "2026-07-23T01:00:00Z"
            rights["revocation_reason"] = "Synthetic revocation regression."
            self._resign(record)
        self._assert_rejected(mutate, "revoked rights still permit release")

    def test_29_separate_equipment_without_delivery_authorization_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["process_context_patterns"][0]
            record["deliverable_scope"] = "separate_equipment_deliverable"
            record["geometry_authority"] = "exact_private_imported_cad"
            self._resign(record)
        self._assert_rejected(mutate, "expected type")

    def test_30_exact_process_context_without_source_item_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["process_context_patterns"][0]
            record["geometry_authority"] = "exact_private_imported_cad"
            record["geometry_source_item_id"] = None
            self._resign(record)
        self._assert_rejected(mutate, "expected type")

    def test_31_functional_geometry_kind_value_mismatch_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["functional_interfaces"][0]["geometry"]["kind"] = "axis"
            self._resign(record)
        self._assert_rejected(mutate, "axis geometry requires axis")

    def test_32_incomplete_open_closed_state_claim_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"]["complete_item_examples"][0]
            record["open_closed_states"] = {
                "claimed": True,
                "open_state_id": "fixed",
                "closed_state_id": None,
            }
            self._resign(record)
        self._assert_rejected(mutate, "claimed open/closed states incomplete")

    def test_33_station_count_maximum_below_minimum_rejected(self) -> None:
        def mutate(documents):
            records = documents["fixture_family_templates_v1.json"]["templates"]
            record = next(
                item for item in records if item["station_count_range"] is not None
            )
            record["station_count_range"] = {"minimum": 8, "maximum": 2}
            self._resign(record)
        self._assert_rejected(mutate, "station minimum exceeds maximum")


if __name__ == "__main__":
    unittest.main()
