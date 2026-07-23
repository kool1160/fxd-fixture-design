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
    "revision_history_examples_v1.json",
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

    def _retoken(self, revision: dict[str, object]) -> None:
        revision["optimistic_concurrency_token"] = research.compute_concurrency_token(
            revision, revision["content_sha256"]
        )

    def _new_history_entry(
        self,
        revision_id: str,
        parent_revision_id: str,
        *,
        publication_state: str = "draft",
        current: bool = False,
    ) -> dict[str, object]:
        number = int(revision_id[1:])
        revision = {
            "revision_id": revision_id,
            "content_sha256": str(number % 10) * 64,
            "parent_revision_id": parent_revision_id,
            "author_identity": "FXD synthetic regression",
            "created_at": f"2026-07-23T{number:02d}:00:00Z",
            "change_reason": "Synthetic revision-history regression.",
            "source_revision": None,
            "optimistic_concurrency_token": "0" * 64,
            "publication_state": publication_state,
            "deprecation_state": "active",
            "restores_content_from_revision_id": None,
        }
        self._retoken(revision)
        return {
            "revision": revision,
            "change_kind": "update",
            "current_published_successor": current,
            "evidence_invalidated": False,
            "invalidation_reason": None,
        }

    def _assert_passes(self, mutate) -> None:
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
                research.validate_corpus()
            finally:
                research.DATA_DIR = original_data_dir

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
            if key
            not in {
                "sources",
                "complete_item_examples",
                "shop_standard_examples",
                "revision_histories",
                "project_pins",
            }
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
        self._assert_rejected(mutate, "root r1 cannot have parent")

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
        self._assert_rejected(mutate, "expected type.*array")

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

    def test_34_expiry_before_approval_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["rights_and_release"]["expiry_timestamp"] = "2025-01-01T00:00:00Z"
            self._resign(record)
        self._assert_rejected(mutate, "rights expiry must follow approval")

    def test_35_unknown_rights_basis_selected_for_release_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["privacy_classification"] = "selected_public_release"
            record["provenance"]["origin_classification"] = "selected_public_release"
            record["rights_and_release"]["rights_basis"] = "unknown_not_releasable"
            self._resign(record)
        self._assert_rejected(mutate, "not in")

    def test_36_https_cad_path_in_provenance_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["provenance"]["derivation_note"] = (
                "https://files.example.invalid/customer_asset/fixture.step"
            )
            self._resign(record)
        self._assert_rejected(mutate, "likely private payload reference")

    def test_37_https_employer_image_path_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["provenance"]["derivation_note"] = (
                "https://files.example.invalid/employer_fixture.png"
            )
            self._resign(record)
        self._assert_rejected(mutate, "likely private payload reference")

    def test_38_duplicate_coordinate_frame_identity_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["mounting_interfaces"][0]["frame"]["frame_id"] = (
                record["local_coordinate_system"]["frame_id"]
            )
            self._resign(record)
        self._assert_rejected(mutate, "duplicate coordinate-frame identity")

    def test_39_zero_diameter_hole_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["mounting_interfaces"][0]["interface_type"] = "hole_pattern"
            feature = record["mounting_interfaces"][0]["features"][0]
            feature["feature_type"] = "hole"
            feature["dimensions"] = {
                "diameter": 0,
                "length": None,
                "width": None,
                "height": None,
                "pitch": None,
                "units": "mm",
            }
            self._resign(record)
        self._assert_rejected(mutate, "exclusiveMinimum")

    def test_40_interface_type_feature_kind_mismatch_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["mounting_interfaces"][0]["interface_type"] = "hole_pattern"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 'hole'")

    def test_41_dangling_feature_replacement_class_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["mounting_interfaces"][0]["features"][0][
                "allowed_replacement_class"
            ] = "undeclared-replacement-class"
            self._resign(record)
        self._assert_rejected(mutate, "replacement class is not declared")

    def test_42_point_geometry_with_axis_payload_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            geometry = record["functional_interfaces"][0]["geometry"]
            geometry["kind"] = "point"
            geometry["normal"] = None
            geometry["axis"] = [1, 0, 0]
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*null")

    def test_43_functional_geometry_owner_unit_mismatch_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["functional_interfaces"][0]["geometry"]["units"] = "inch"
            self._resign(record)
        self._assert_rejected(mutate, "units differ from owning item")

    def test_44_contact_reference_to_robot_tcp_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["functional_interfaces"][0]["interface_type"] = "robot_tcp"
            self._resign(record)
        self._assert_rejected(mutate, "incompatible interface roles")

    def test_45_same_fixed_state_used_for_open_and_closed_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["open_closed_states"] = {
                "claimed": True,
                "open_state_id": "fixed",
                "closed_state_id": "fixed",
            }
            self._resign(record)
        self._assert_rejected(mutate, "open and closed states must be distinct")

    def test_46_provisional_envelope_bom_participation_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["authority_level"] = "provisional_review_envelope"
            record["category"] = "private_purchased_tooling"
            record["preview_representation"] = {
                "kind": "provisional_envelope",
                "authority": "provisional",
                "asset_identity": None,
                "visible_classification": "provisional_not_exact",
            }
            record["bom_participation"] = "permitted"
            record["feature_definition"] = None
            record["mounting_interfaces"] = []
            record["functional_interfaces"] = []
            record["contact_points"] = []
            record["material_manufacturing_intent"] = None
            for field in (
                "fixture_component_step",
                "fixture_assembly_step",
                "fixture_dxf",
                "manufacturing_release",
            ):
                record["export_participation"][field] = "excluded"
            for field in ("exact_collision", "exact_clearance", "manufacturing_release"):
                record["validation_participation"][field] = "excluded"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 'excluded'")

    def test_47_fixture_template_retaining_geometry_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["authority_level"] = "fixture_family_template"
            record["category"] = "fixture_family_template"
            record["bom_participation"] = "excluded"
            record["preview_representation"] = {
                "kind": "template_diagram",
                "authority": "informational",
                "asset_identity": None,
                "visible_classification": "template_not_completed_fixture",
            }
            record["engineering_details"].update({
                "configuration_parameters": ["synthetic"],
                "unsupported_conditions": ["synthetic"],
                "deterministic_validations_required": ["synthetic"],
                "required_human_review_questions": ["synthetic?"],
            })
            for field in record["export_participation"]:
                record["export_participation"][field] = "excluded"
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*null")

    def test_48_private_benchmark_retaining_exact_geometry_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["authority_level"] = "private_benchmark_reference"
            record["category"] = "private_benchmark_reference"
            record["bom_participation"] = "excluded"
            record["preview_representation"] = {
                "kind": "metadata_card",
                "authority": "informational",
                "asset_identity": None,
                "visible_classification": "knowledge_not_geometry",
            }
            for field in record["export_participation"]:
                record["export_participation"][field] = "excluded"
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*null")

    def test_49_shop_standard_retaining_geometry_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["authority_level"] = "shop_standard"
            record["category"] = "shop_standard_pack"
            record["bom_participation"] = "excluded"
            record["preview_representation"] = {
                "kind": "metadata_card",
                "authority": "informational",
                "asset_identity": None,
                "visible_classification": "knowledge_not_geometry",
            }
            record["engineering_details"].update({
                "scope": "shop",
                "precedence_level": 3,
                "conflict_behavior": "visible",
            })
            for field in record["export_participation"]:
                record["export_participation"][field] = "excluded"
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*null")

    def test_50_metadata_only_item_retaining_exact_source_geometry_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["authority_level"] = "metadata_only_commercial_component"
            record["category"] = "private_purchased_tooling"
            record["storage_policy"] = "metadata_only"
            record["edit_authority"] = "read_only"
            record["bom_participation"] = "excluded"
            record["preview_representation"] = {
                "kind": "metadata_card",
                "authority": "informational",
                "asset_identity": None,
                "visible_classification": "metadata_only_not_geometry",
            }
            record["source_file"] = {
                "identity": "hidden-exact-source",
                "sha256": "a" * 64,
                "source_classification": "supplier_authorized_exact",
                "licensing_usage_evidence": "Synthetic test evidence.",
            }
            for field in (
                "fixture_component_step",
                "fixture_assembly_step",
                "fixture_dxf",
                "manufacturing_release",
            ):
                record["export_participation"][field] = "excluded"
            for field in ("exact_collision", "exact_clearance", "manufacturing_release"):
                record["validation_participation"][field] = "excluded"
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*null")

    def test_51_noninitial_revision_without_parent_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_family_templates_v1.json"]["templates"][0]
            record["revision"]["revision_id"] = "r2"
            record["revision"]["parent_revision_id"] = None
            self._resign(record)
        self._assert_rejected(mutate, "non-initial revision requires a parent")

    def test_52_root_revision_restoring_future_revision_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_family_templates_v1.json"]["templates"][0]
            record["revision"]["restores_content_from_revision_id"] = "r2"
            self._resign(record)
        self._assert_rejected(mutate, "root r1 cannot have parent or rollback target")

    def test_53_clone_with_only_arbitrary_tag_rejected(self) -> None:
        def mutate(documents):
            records = documents["component_patterns_v1.json"]["records"]
            clone = deepcopy(records[0])
            clone["item_id"] = records[1]["item_id"]
            clone["name"] = records[1]["name"]
            clone["provenance"]["record_identity"] = clone["item_id"]
            clone["tags"].append("count-padding-token")
            self._resign(clone)
            records[1] = clone
        self._assert_rejected(mutate, "semantic duplicate records")

    def test_54_clone_with_only_provenance_note_suffix_rejected(self) -> None:
        def mutate(documents):
            records = documents["component_patterns_v1.json"]["records"]
            clone = deepcopy(records[0])
            clone["item_id"] = records[1]["item_id"]
            clone["name"] = records[1]["name"]
            clone["provenance"]["record_identity"] = clone["item_id"]
            clone["provenance"]["usage_note"] += " Count-padding suffix."
            self._resign(clone)
            records[1] = clone
        self._assert_rejected(mutate, "semantic duplicate records")

    def test_55_clone_with_only_dependency_label_rejected(self) -> None:
        def mutate(documents):
            records = documents["component_patterns_v1.json"]["records"]
            clone = deepcopy(records[0])
            clone["item_id"] = records[1]["item_id"]
            clone["name"] = records[1]["name"]
            clone["provenance"]["record_identity"] = clone["item_id"]
            clone["downstream_dependencies"].append("count-padding-dependency")
            self._resign(clone)
            records[1] = clone
        self._assert_rejected(mutate, "semantic duplicate records")

    def test_56_provisional_context_nonprovisional_envelope_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "process_context_patterns"
            ][0]
            record["keep_out_envelopes"][0]["provisional"] = False
            self._resign(record)
        self._assert_rejected(mutate, "expected constant True")

    def test_57_public_knowledge_retaining_exact_source_file_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "engineering_principles"
            ][0]
            record["source_file"] = {
                "identity": "hidden-exact-source",
                "sha256": "b" * 64,
                "source_classification": "supplier_authorized_exact",
                "licensing_usage_evidence": "Synthetic test evidence.",
            }
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*null")

    def test_58_release_decision_after_expiry_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            rights = record["rights_and_release"]
            rights["expiry_timestamp"] = "2026-07-24T00:00:00Z"
            rights["release_decision_timestamp"] = "2026-07-25T00:00:00Z"
            self._resign(record)
        self._assert_rejected(mutate, "release decision is not before rights expiry")

    def test_59_legitimate_canonical_public_source_url_passes(self) -> None:
        def mutate(documents):
            source = documents["fixture_library_reference_v1.json"]["sources"][0]
            source["canonical_url"] = (
                "https://www.carrlane.com/engineering-resources/"
                "fixture-design-principles?research-validation=1"
            )
        self._assert_passes(mutate)

    def test_60_unresolved_revision_parent_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            revision = history["revisions"][1]["revision"]
            revision["parent_revision_id"] = "r9"
            self._retoken(revision)
        self._assert_rejected(mutate, "parent revision does not resolve")

    def test_61_unresolved_restored_revision_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            revision = history["revisions"][2]["revision"]
            revision["restores_content_from_revision_id"] = "r9"
            self._retoken(revision)
        self._assert_rejected(mutate, "restored revision does not resolve")

    def test_62_revision_ancestry_cycle_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            r4 = self._new_history_entry("r4", "r5")
            r5 = self._new_history_entry("r5", "r4")
            history["revisions"].extend([r4, r5])
        self._assert_rejected(mutate, "revision ancestry contains a cycle")

    def test_63_rollback_target_not_ancestor_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            history["revisions"].append(self._new_history_entry("r4", "r1"))
            revision = history["revisions"][2]["revision"]
            revision["restores_content_from_revision_id"] = "r4"
            self._retoken(revision)
        self._assert_rejected(mutate, "rollback target is not an ancestor")

    def test_64_duplicate_published_successors_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            history["revisions"].append(
                self._new_history_entry(
                    "r4", "r2", publication_state="published_research", current=True
                )
            )
        self._assert_rejected(mutate, "duplicate published successors")

    def test_65_stale_publication_parent_token_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            history["publication_attempts"][1][
                "expected_parent_concurrency_token"
            ] = "0" * 64
        self._assert_rejected(mutate, "stale parent concurrency token")

    def test_66_project_pin_to_unresolved_revision_rejected(self) -> None:
        def mutate(documents):
            pin = documents["revision_history_examples_v1.json"]["project_pins"][1]
            pin["pinned_revision_id"] = "r9"
        self._assert_rejected(mutate, "pinned revision does not resolve")

    def test_67_project_automatic_adoption_rejected(self) -> None:
        def mutate(documents):
            pin = documents["revision_history_examples_v1.json"]["project_pins"][1]
            pin["automatic_adoption"] = True
        self._assert_rejected(mutate, "cannot silently adopt")

    def test_68_silent_project_migration_rejected(self) -> None:
        def mutate(documents):
            pin = documents["revision_history_examples_v1.json"]["project_pins"][0]
            pin["migration"]["silent_adoption"] = True
        self._assert_rejected(mutate, "silent project migration is prohibited")

    def test_69_rollback_without_evidence_invalidation_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            rollback = history["revisions"][2]
            rollback["evidence_invalidated"] = False
            rollback["invalidation_reason"] = None
        self._assert_rejected(mutate, "rollback must invalidate dependent evidence")

    def test_70_rollback_without_new_child_parent_rejected(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            revision = history["revisions"][2]["revision"]
            revision["parent_revision_id"] = None
            self._retoken(revision)
        self._assert_rejected(mutate, "exactly one parentless r1 root")

    def test_71_provisional_context_claiming_exact_access_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "process_context_patterns"
            ][0]
            record["access_authority"] = "exact"
            self._resign(record)
        self._assert_rejected(mutate, "not in")

    def test_72_provisional_context_claiming_exact_collision_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "process_context_patterns"
            ][0]
            record["collision_authority"] = "exact"
            self._resign(record)
        self._assert_rejected(mutate, "not in")

    def test_73_provisional_context_claiming_exact_envelope_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "process_context_patterns"
            ][0]
            record["envelope_authority"] = "exact"
            self._resign(record)
        self._assert_rejected(mutate, "not in")

    def test_74_exact_access_without_exact_source_evidence_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "process_context_patterns"
            ][0]
            record["geometry_authority"] = "exact_private_imported_cad"
            record["geometry_source_item_id"] = None
            record["access_authority"] = "exact"
            self._resign(record)
        self._assert_rejected(mutate, "expected type.*string")

    def test_75_open_and_closed_state_kinds_must_match_claims(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["movement_states"].append({
                "state_id": "moving-state",
                "state_kind": "moving",
                "description": "Synthetic incompatible state kind.",
            })
            record["open_closed_states"] = {
                "claimed": True,
                "open_state_id": "fixed",
                "closed_state_id": "moving-state",
            }
            self._resign(record)
        self._assert_rejected(mutate, "open-state reference does not have open state kind")

    def test_76_nonapplicable_feature_dimension_rejected(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "complete_item_examples"
            ][0]
            record["mounting_interfaces"][0]["features"][0]["dimensions"][
                "width"
            ] = 10
            self._resign(record)
        self._assert_rejected(mutate, "planar_face forbids dimension width")

    def test_77_authority_matrix_covers_exactly_all_eleven_authorities(self) -> None:
        self.assertEqual(research.AUTHORITY_LEVELS, set(research.AUTHORITY_RULES))

    def test_78_pending_selected_release_rights_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["privacy_classification"] = "selected_public_release"
            record["provenance"]["origin_classification"] = "selected_public_release"
            record["rights_and_release"]["release_decision_state"] = "pending_review"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 'approved'")

    def test_79_advisory_bom_hint_cannot_be_deliverable(self) -> None:
        def mutate(documents):
            record = documents["fixture_library_reference_v1.json"][
                "engineering_principles"
            ][0]
            record["advisory_bom_hint"] = {
                "classification": "generic_review_placeholder",
                "description": "Synthetic non-deliverable hint.",
                "deliverable_eligible": True,
            }
            self._resign(record)
        self._assert_rejected(mutate, "expected constant False")

    def test_80_denied_selected_release_rights_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["privacy_classification"] = "selected_public_release"
            record["provenance"]["origin_classification"] = "selected_public_release"
            record["rights_and_release"]["release_decision_state"] = "denied"
            self._resign(record)
        self._assert_rejected(mutate, "expected constant 'approved'")

    def test_81_selected_release_without_grantor_rejected(self) -> None:
        def mutate(documents):
            record = documents["synthetic_examples_v1.json"]["cases"][0]
            record["privacy_classification"] = "selected_public_release"
            record["provenance"]["origin_classification"] = "selected_public_release"
            rights = record["rights_and_release"]
            del rights["rights_holder_or_grantor_identity"]
            rights["rights_basis"] = "original_synthetic_work"
            rights["release_decision_state"] = "approved"
            rights["public_release_permission"] = True
            rights["released_metadata_fields"] = ["case_id"]
            self._resign(record)
        self._assert_rejected(
            mutate, "missing required property 'rights_holder_or_grantor_identity'"
        )

    def test_82_canonical_source_url_cannot_hide_private_cad_asset(self) -> None:
        def mutate(documents):
            source = documents["fixture_library_reference_v1.json"]["sources"][0]
            source["canonical_url"] = (
                "https://public.example/customer-cad/private-fixture.step"
            )
        self._assert_rejected(
            mutate, "canonical public source URL contains private or asset content"
        )

    def test_83_rollback_digest_must_match_restored_ancestor(self) -> None:
        def mutate(documents):
            history = documents["revision_history_examples_v1.json"]["histories"][0]
            revision = history["revisions"][2]["revision"]
            revision["content_sha256"] = "3" * 64
            self._retoken(revision)
        self._assert_rejected(
            mutate, "rollback content digest does not match the restored ancestor"
        )


if __name__ == "__main__":
    unittest.main()
