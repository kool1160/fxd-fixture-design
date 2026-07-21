from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.validate_milestones import (
    AUTHORITY_MARKER,
    MilestoneValidationError,
    load_registry,
    validate_derived_documents,
    validate_git_history,
    validate_registry,
    validate_registry_data,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "MILESTONE_STATE.json"


class MilestoneGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(REGISTRY)

    def data(self) -> dict:
        return copy.deepcopy(self.registry)

    def milestone(self, data: dict, number: int) -> dict:
        return next(item for item in data["milestones"] if item["number"] == number)

    def assert_error(self, data: dict, phrase: str) -> None:
        errors = validate_registry_data(data)
        self.assertTrue(any(phrase in error for error in errors), errors)

    def test_registry_data_is_valid(self) -> None:
        self.assertEqual([], validate_registry_data(self.data()))

    def test_malformed_registry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(MilestoneValidationError) as caught:
                load_registry(path)
        self.assertIn("malformed milestone registry", str(caught.exception))

    def test_unknown_schema_and_status_are_rejected(self) -> None:
        data = self.data()
        data["schema_version"] = "unknown"
        self.milestone(data, 20)["status"] = "Pending"
        errors = validate_registry_data(data)
        self.assertTrue(any("unknown milestone schema" in error for error in errors), errors)
        self.assertTrue(any("unknown status 'Pending'" in error for error in errors), errors)

    def test_multiple_active_milestones_are_rejected(self) -> None:
        data = self.data()
        self.milestone(data, 20)["status"] = "Active"
        self.milestone(data, 20)["issue"] = 56
        self.assert_error(data, "exactly one Active milestone")

    def test_zero_active_without_formal_pause_is_rejected(self) -> None:
        data = self.data()
        self.milestone(data, 32)["status"] = "Planned"
        self.assert_error(data, "requires exactly one Active milestone")

    def test_active_projection_mismatch_is_rejected(self) -> None:
        data = self.data()
        data["product_lane"]["active_milestone"] = 20
        self.assert_error(data, "does not match the sole Active milestone")

    def test_active_milestone_requires_issue_and_implementation_pr(self) -> None:
        data = self.data()
        active = self.milestone(data, 32)
        active["issue"] = None
        active["implementation_prs"] = []
        errors = validate_registry_data(data)
        self.assertTrue(any("requires an authoritative issue" in error for error in errors), errors)
        self.assertTrue(any("requires an implementation PR" in error for error in errors), errors)

    def test_invalid_predecessor_is_rejected(self) -> None:
        data = self.data()
        self.milestone(data, 32)["predecessor"] = 30
        self.assert_error(data, "predecessor must be 31")

    def test_duplicate_number_and_sequence_position_are_rejected(self) -> None:
        data = self.data()
        active = self.milestone(data, 32)
        active["number"] = 31
        active["sequence_position"] = 31
        errors = validate_registry_data(data)
        self.assertTrue(any("duplicate milestone numbers" in error for error in errors), errors)
        self.assertTrue(any("duplicate milestone sequence positions" in error for error in errors), errors)

    def test_active_cannot_skip_blocked_predecessor(self) -> None:
        data = self.data()
        self.milestone(data, 31)["status"] = "Blocked"
        errors = validate_registry_data(data)
        self.assertTrue(any("predecessor is not Complete or Superseded" in error for error in errors), errors)
        self.assertTrue(any("skips Blocked milestone 31" in error for error in errors), errors)

    def test_complete_milestone_requires_merge_evidence(self) -> None:
        data = self.data()
        self.milestone(data, 20)["merge_commits"] = []
        self.assert_error(data, "Complete milestone 20 requires merged evidence")

    def test_legacy_complete_requires_explicit_reconciliation(self) -> None:
        data = self.data()
        self.milestone(data, 20)["legacy_reconciliation"] = False
        self.assert_error(data, "legacy Complete milestone 20 requires explicit legacy_reconciliation")

    def test_post_governance_complete_requires_closeout_pr(self) -> None:
        data = self.data()
        active = self.milestone(data, 32)
        active["status"] = "Complete"
        active["merge_commits"] = ["ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc"]
        active["completion_evidence"] = "Synthetic test evidence."
        data["product_lane"].update(
            {"paused": True, "active_milestone": None, "pause_reason": "Test pause", "decision": "Test decision"}
        )
        self.assert_error(data, "post-governance Complete milestone 32 requires a separate closeout PR")

    def test_superseded_milestone_requires_decision_and_replacement(self) -> None:
        data = self.data()
        milestone = self.milestone(data, 20)
        milestone["status"] = "Superseded"
        milestone["decisions"] = []
        milestone["replacement_milestone"] = None
        errors = validate_registry_data(data)
        self.assertTrue(any("requires a decision record" in error for error in errors), errors)
        self.assertTrue(any("requires a replacement milestone" in error for error in errors), errors)

    def test_stale_m20_derived_status_is_rejected(self) -> None:
        data = self.data()
        data["derived_documents"] = ["BACKLOG.md"]
        data["historical_snapshot_documents"] = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "BACKLOG.md").write_text(
                f"{AUTHORITY_MARKER}\n## Milestone 20 — Test\n**Status:** Pending\n",
                encoding="utf-8",
            )
            errors = validate_derived_documents(data, root)
        self.assertTrue(any("non-authoritative status 'Pending'" in error for error in errors), errors)

    def test_legal_but_conflicting_derived_status_is_rejected(self) -> None:
        data = self.data()
        data["derived_documents"] = ["ROADMAP.md"]
        data["historical_snapshot_documents"] = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "ROADMAP.md").write_text(
                f"{AUTHORITY_MARKER}\n## Milestone 31 — Test\n**Status:** Active\n",
                encoding="utf-8",
            )
            errors = validate_derived_documents(data, root)
        self.assertTrue(any("Active != Complete" in error for error in errors), errors)

    def test_historical_document_requires_snapshot_marker(self) -> None:
        data = self.data()
        data["derived_documents"] = ["HISTORY.md"]
        data["historical_snapshot_documents"] = ["HISTORY.md"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "HISTORY.md").write_text(AUTHORITY_MARKER, encoding="utf-8")
            errors = validate_derived_documents(data, root)
        self.assertTrue(any("not marked as a non-authoritative snapshot" in error for error in errors), errors)

    def test_recorded_merge_commit_must_exist_in_local_history(self) -> None:
        data = self.data()
        self.milestone(data, 20)["merge_commits"] = ["0" * 40]
        errors = validate_git_history(data, ROOT)
        self.assertTrue(any("absent from local Git history" in error for error in errors), errors)

    def test_full_repository_registry_validation_passes(self) -> None:
        validated = validate_registry(REGISTRY, ROOT)
        self.assertEqual(32, validated["product_lane"]["active_milestone"])
        self.assertEqual(32, len(validated["milestones"]))

    def test_registry_contains_no_milestone_33(self) -> None:
        self.assertEqual(32, max(item["number"] for item in self.registry["milestones"]))

    def test_post_m32_disposition_is_formal_pause(self) -> None:
        disposition = self.registry["product_lane"]["after_milestone_32_closeout"]
        self.assertTrue(disposition["paused"])
        self.assertIsNone(disposition["active_milestone"])
        self.assertTrue(disposition["decision"])

    def test_pr55_is_blocked_maintenance_under_issue_58(self) -> None:
        candidate = self.registry["maintenance_lane"]["candidates"][0]
        self.assertEqual(55, candidate["pull_request"])
        self.assertEqual(58, candidate["issue"])
        self.assertEqual("Blocked", candidate["status"])
        self.assertIsNone(candidate["product_milestone"])

    def test_registry_selector_selects_only_active_m32(self) -> None:
        selected = subprocess.run(
            ["node", "scripts/fxd-backlog.mjs", "select"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, selected.returncode, selected.stderr)
        self.assertIn("Selected Active Milestone 32", selected.stdout)

    def test_registry_selector_cannot_silently_choose_m20(self) -> None:
        selected = subprocess.run(
            ["node", "scripts/fxd-backlog.mjs", "select", "--number", "20"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("Milestone 20 is not Active", selected.stderr)


if __name__ == "__main__":
    unittest.main()
