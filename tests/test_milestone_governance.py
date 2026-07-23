from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.validate_milestones import (
    AUTHORITY_MARKER,
    MilestoneValidationError,
    commit_message_matches_pr,
    load_registry,
    validate_derived_documents,
    validate_git_history,
    validate_registry,
    validate_registry_data,
    validate_sequence_history,
    validate_sequence_transition,
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

    def build_post_governance_history(
        self,
        root: Path,
        *,
        implementation_subject_pr: int = 54,
        implementation_prs: list[int] | None = None,
        implementation_subjects: list[str] | None = None,
        evidence_at_closeout: bool = True,
        state_finalization_pr: int = 61,
        create_finalization_ref: bool = True,
        finalization_subject: str = "Finalize Milestone 32 governance state",
        simulate_squash_merge: bool = False,
        closeout_files: dict[str, str] | None = None,
        finalization_files: dict[str, str] | None = None,
    ) -> dict:
        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", *args],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )
            return result.stdout.strip()

        git("init", "--quiet")
        git("config", "user.name", "FXD Governance Test")
        git("config", "user.email", "governance-test@example.invalid")
        declared_prs = [54] if implementation_prs is None else implementation_prs
        subjects = (
            [f"Milestone 32 implementation (#{implementation_subject_pr})"]
            if implementation_subjects is None
            else implementation_subjects
        )
        implementation_commits: list[str] = []
        for index, subject in enumerate(subjects, start=1):
            relative = f"implementation-{index}.txt"
            (root / relative).write_text(f"reviewed implementation {index}\n", encoding="utf-8")
            git("add", relative)
            git("commit", "--quiet", "-m", subject)
            implementation_commits.append(git("rev-parse", "HEAD"))

        closeout_data = self.data()
        for legacy_milestone in closeout_data["milestones"]:
            if legacy_milestone["number"] < 32:
                legacy_milestone["merge_commits"] = [implementation_commits[0]]
        closeout = self.milestone(closeout_data, 32)
        evidence_results = {
            profile: [f"Reviewed evidence profile {profile}."]
            for profile in closeout["evidence_profiles"]
        }
        closeout.update(
            {
                "implementation_prs": declared_prs,
                "merge_commits": implementation_commits,
                "evidence_results": evidence_results if evidence_at_closeout else {},
                "completion_evidence": (
                    "All selected evidence profiles were reviewed in closeout PR #60."
                    if evidence_at_closeout
                    else None
                ),
                "closeout_pr": 60,
                "closeout_merge_commit": None,
                "decisions": [*closeout["decisions"], "Closeout evidence approved for finalization."],
            }
        )
        registry = root / "docs" / "MILESTONE_STATE.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps(closeout_data, indent=2) + "\n", encoding="utf-8")
        for relative, content in (closeout_files or {}).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        git("add", "docs/MILESTONE_STATE.json", *(closeout_files or {}).keys())
        git("commit", "--quiet", "-m", "Milestone 32 closeout evidence (#60)")
        closeout_commit = git("rev-parse", "HEAD")

        final_data = copy.deepcopy(closeout_data)
        final_milestone = self.milestone(final_data, 32)
        final_milestone.update(
            {
                "status": "Complete",
                "merge_commits": [*implementation_commits, closeout_commit],
                "evidence_results": evidence_results,
                "completion_evidence": "All selected evidence profiles were reviewed in closeout PR #60.",
                "closeout_merge_commit": closeout_commit,
                "state_finalization_pr": state_finalization_pr,
                "decisions": [
                    *closeout["decisions"],
                    f"Separate closeout PR #60 approved and merged as {closeout_commit}.",
                ],
            }
        )
        disposition = final_data["product_lane"]["after_milestone_32_closeout"]
        final_data["product_lane"].update(
            {
                "paused": disposition["paused"],
                "active_milestone": disposition["active_milestone"],
                "pause_reason": disposition["reason"],
                "decision": disposition["decision"],
            }
        )
        final_data["sequence_revision"] = closeout_data["sequence_revision"] + 1
        final_data["sequence_decisions"] = [
            "Issue #56 approved the post-Milestone-32 product-lane pause."
        ]
        registry.write_text(json.dumps(final_data, indent=2) + "\n", encoding="utf-8")
        for relative, content in (finalization_files or {}).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        git("add", "docs/MILESTONE_STATE.json", *(finalization_files or {}).keys())
        git("commit", "--quiet", "-m", finalization_subject)
        if create_finalization_ref:
            git("update-ref", f"refs/pull/{state_finalization_pr}/head", "HEAD")
        if simulate_squash_merge:
            git("checkout", "--quiet", "--detach", closeout_commit)
            registry.write_text(json.dumps(final_data, indent=2) + "\n", encoding="utf-8")
            git("add", "docs/MILESTONE_STATE.json")
            git("commit", "--quiet", "-m", f"Finalize Milestone 32 (#{state_finalization_pr})")
        return final_data

    def build_selector_repository(self, root: Path, data: dict | None = None) -> dict:
        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", *args],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )
            return result.stdout.strip()

        git("init", "--quiet")
        git("config", "user.name", "FXD Selector Test")
        git("config", "user.email", "selector-test@example.invalid")
        (root / "seed.txt").write_text("selector history seed\n", encoding="utf-8")
        git("add", "seed.txt")
        git("commit", "--quiet", "-m", "Selector history seed")
        seed = git("rev-parse", "HEAD")

        registry_data = self.data() if data is None else copy.deepcopy(data)
        registry_data["derived_documents"] = []
        registry_data["historical_snapshot_documents"] = []
        for milestone in registry_data["milestones"]:
            if milestone["number"] < 32:
                milestone["merge_commits"] = [seed]

        scripts = root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts" / "fxd-backlog.mjs", scripts / "fxd-backlog.mjs")
        shutil.copy2(ROOT / "scripts" / "validate_milestones.py", scripts / "validate_milestones.py")
        registry = root / "docs" / "MILESTONE_STATE.json"
        registry.parent.mkdir()
        registry.write_text(json.dumps(registry_data, indent=2) + "\n", encoding="utf-8")
        git("add", "scripts", "docs/MILESTONE_STATE.json")
        git("commit", "--quiet", "-m", "Add selector governance state")
        return registry_data

    def commit_registry(self, root: Path, data: dict, *, subject: str, pull_request: int | None = None) -> None:
        registry = root / "docs" / "MILESTONE_STATE.json"
        registry.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/MILESTONE_STATE.json"], cwd=root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", subject], cwd=root, check=True)
        if pull_request is not None:
            subprocess.run(
                ["git", "update-ref", f"refs/pull/{pull_request}/head", "HEAD"],
                cwd=root,
                check=True,
            )

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

    def test_registry_rejects_malformed_flags_references_and_duplicate_evidence(self) -> None:
        data = self.data()
        milestone = self.milestone(data, 32)
        milestone["legacy"] = "false"
        milestone["historical_gaps"] = [""]
        milestone["replacement_milestone"] = "33"
        milestone["closeout_merge_commit"] = "not-a-sha"
        milestone["implementation_prs"] = [54, 54]
        milestone["evidence_profiles"] = ["A", "A"]
        errors = validate_registry_data(data)
        for phrase in (
            "legacy must be true or false",
            "historical_gaps must be an array of nonempty strings",
            "replacement_milestone must be null or a positive integer",
            "closeout_merge_commit must be null or a lowercase 40-character SHA",
            "implementation_prs cannot contain duplicates",
            "evidence_profiles cannot contain duplicates",
        ):
            self.assertTrue(any(phrase in error for error in errors), (phrase, errors))

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

    def test_post_governance_milestone_cannot_claim_legacy_reconciliation(self) -> None:
        data = self.data()
        active = self.milestone(data, 32)
        active["legacy"] = True
        active["legacy_reconciliation"] = True
        active["historical_gaps"] = ["Fabricated bypass."]
        self.assert_error(data, "post-governance milestone 32 cannot be classified as legacy")

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

    def test_closeout_must_be_distinct_merged_and_decided(self) -> None:
        data = self.data()
        milestone = self.milestone(data, 32)
        milestone.update(
            {
                "status": "Complete",
                "merge_commits": ["ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc"],
                "completion_evidence": "Synthetic test evidence.",
                "closeout_pr": 54,
                "closeout_merge_commit": None,
                "decisions": ["Completion approved without the required record."],
            }
        )
        data["product_lane"].update(
            {"paused": True, "active_milestone": None, "pause_reason": "Test pause", "decision": "Test decision"}
        )
        errors = validate_registry_data(data)
        self.assertTrue(any("distinct from implementation PRs" in error for error in errors), errors)
        self.assertTrue(any("requires a closeout merge commit" in error for error in errors), errors)
        self.assertTrue(any("requires an explicit closeout decision" in error for error in errors), errors)

    def test_valid_post_governance_closeout_contract_is_accepted(self) -> None:
        data = self.data()
        milestone = self.milestone(data, 32)
        merge = "ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc"
        milestone.update(
            {
                "status": "Complete",
                "merge_commits": [merge],
                "completion_evidence": "Synthetic test evidence.",
                "evidence_results": {profile: [f"Profile {profile} accepted evidence."] for profile in "ABCDE"},
                "closeout_pr": 60,
                "closeout_merge_commit": merge,
                "state_finalization_pr": 61,
                "decisions": [f"Separate closeout PR #60 approved and merged as {merge}."],
            }
        )
        data["product_lane"].update(
            {"paused": True, "active_milestone": None, "pause_reason": "Test pause", "decision": "Test decision"}
        )
        closeout_errors = [error for error in validate_registry_data(data) if "closeout" in error]
        self.assertEqual([], closeout_errors)

    def test_closeout_evidence_pr_can_merge_before_its_sha_exists(self) -> None:
        data = self.data()
        active = self.milestone(data, 32)
        active["closeout_pr"] = 60
        active["closeout_merge_commit"] = None
        active["completion_evidence"] = "All selected evidence profiles were reviewed in closeout PR #60."
        active["evidence_results"] = {profile: [f"Profile {profile} accepted evidence."] for profile in "ABCDE"}
        errors = validate_registry_data(data)
        self.assertFalse(any("closeout" in error for error in errors), errors)

    def test_closeout_evidence_pr_requires_all_profile_results(self) -> None:
        data = self.data()
        active = self.milestone(data, 32)
        active["closeout_pr"] = 60
        active["completion_evidence"] = "Incomplete closeout evidence."
        active["evidence_results"] = {"A": ["Only deterministic evidence was recorded."]}
        self.assert_error(data, "closeout evidence PR requires results for every selected evidence profile")

    def test_complete_requires_results_for_every_selected_evidence_profile(self) -> None:
        data = self.data()
        milestone = self.milestone(data, 32)
        merge = "ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc"
        milestone.update(
            {
                "status": "Complete",
                "merge_commits": [merge],
                "completion_evidence": "Summary alone is insufficient.",
                "evidence_results": {"A": ["Deterministic suite passed."]},
                "closeout_pr": 60,
                "closeout_merge_commit": merge,
                "state_finalization_pr": 61,
                "decisions": [f"Separate closeout PR #60 approved and merged as {merge}."],
            }
        )
        data["product_lane"].update(
            {"paused": True, "active_milestone": None, "pause_reason": "Test pause", "decision": "Test decision"}
        )
        self.assert_error(data, "requires results for every selected evidence profile")

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

    def test_unrecognized_and_noncanonical_derived_statuses_are_rejected(self) -> None:
        data = self.data()
        data["derived_documents"] = ["ROADMAP.md"]
        data["historical_snapshot_documents"] = []
        for raw_status in ("Bogus", "active"):
            with self.subTest(raw_status=raw_status), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "ROADMAP.md").write_text(
                    f"{AUTHORITY_MARKER}\n## Milestone 32 - Test\n**Status:** {raw_status}\n",
                    encoding="utf-8",
                )
                errors = validate_derived_documents(data, root)
            self.assertTrue(any("unrecognized or noncanonical status" in error for error in errors), errors)

    def test_derived_milestone_colon_status_must_match_registry(self) -> None:
        data = self.data()
        self.milestone(data, 32)["status"] = "Complete"
        data["derived_documents"] = ["CURRENT.md"]
        data["historical_snapshot_documents"] = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CURRENT.md").write_text(
                f"{AUTHORITY_MARKER}\n- Milestone 32: Active under Issue #57\n",
                encoding="utf-8",
            )
            errors = validate_derived_documents(data, root)
        self.assertTrue(any("Active != Complete" in error for error in errors), errors)

    def test_current_milestone_heading_must_match_registry(self) -> None:
        data = self.data()
        self.milestone(data, 32)["status"] = "Complete"
        data["product_lane"].update(
            {
                "paused": True,
                "active_milestone": None,
                "pause_reason": "Approved test pause.",
                "decision": "Issue #56",
            }
        )
        data["derived_documents"] = ["CURRENT.md"]
        data["historical_snapshot_documents"] = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CURRENT.md").write_text(
                f"{AUTHORITY_MARKER}\n## Current milestone\n\nContext.\n\nMilestone 32 - stale projection.\n",
                encoding="utf-8",
            )
            errors = validate_derived_documents(data, root)
        self.assertTrue(any("registry product lane is formally paused" in error for error in errors), errors)

    def test_legal_current_derived_projections_are_accepted(self) -> None:
        data = self.data()
        data["derived_documents"] = ["CURRENT.md"]
        data["historical_snapshot_documents"] = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CURRENT.md").write_text(
                f"{AUTHORITY_MARKER}\n- Milestone 32: Active under Issue #57\n\n"
                "## Current milestone\n\nMilestone 32 - Multi-station weld fixture synthesis.\n",
                encoding="utf-8",
            )
            errors = validate_derived_documents(data, root)
        self.assertEqual([], errors)

    def test_historical_document_requires_snapshot_marker(self) -> None:
        data = self.data()
        data["derived_documents"] = ["HISTORY.md"]
        data["historical_snapshot_documents"] = ["HISTORY.md"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "HISTORY.md").write_text(AUTHORITY_MARKER, encoding="utf-8")
            errors = validate_derived_documents(data, root)
        self.assertTrue(any("not marked as a non-authoritative snapshot" in error for error in errors), errors)

    def test_historical_snapshot_statuses_remain_accepted(self) -> None:
        data = self.data()
        data["derived_documents"] = ["HISTORY.md"]
        data["historical_snapshot_documents"] = ["HISTORY.md"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "HISTORY.md").write_text(
                f"{AUTHORITY_MARKER}\n<!-- FXD-HISTORICAL-MILESTONE-SNAPSHOT -->\n"
                "## Current milestone\nMilestone 20: Pending\n",
                encoding="utf-8",
            )
            errors = validate_derived_documents(data, root)
        self.assertEqual([], errors)

    def test_recorded_merge_commit_must_exist_in_local_history(self) -> None:
        data = self.data()
        self.milestone(data, 20)["merge_commits"] = ["0" * 40]
        errors = validate_git_history(data, ROOT)
        self.assertTrue(any("absent from local Git history" in error for error in errors), errors)

    def test_closeout_commit_message_must_identify_declared_pr(self) -> None:
        merge = "5f90765b96140f0cb3103f3ac5e04a79f82ab604"
        data = {
            "governance_effective_milestone": 32,
            "milestones": [
                {
                    "number": 32,
                    "status": "Complete",
                    "merge_commits": [merge],
                    "closeout_pr": 60,
                    "closeout_merge_commit": merge,
                }
            ],
        }
        errors = validate_git_history(data, ROOT)
        self.assertTrue(any("not associated with closeout PR #60" in error for error in errors), errors)
        data["milestones"][0]["closeout_pr"] = 40
        self.assertFalse(any("not associated" in error for error in validate_git_history(data, ROOT)))

    def test_post_governance_history_binds_each_implementation_pr_and_reviewed_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertEqual([], errors)

    def test_valid_three_stage_completion_path_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            milestone = self.milestone(data, 32)
            self.assertEqual(61, milestone["state_finalization_pr"])
            self.assertEqual(milestone["closeout_merge_commit"], milestone["merge_commits"][-1])
            self.assertEqual([], validate_registry_data(data))
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertEqual([], errors)

    def test_direct_non_pr_completion_commit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root, create_finalization_ref=False)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("no matching local pull-head ref" in error for error in errors), errors)

    def test_fabricated_finalization_pr_commit_subject_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                create_finalization_ref=False,
                finalization_subject="Finalize Milestone 32 (#61)",
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("no matching local pull-head ref" in error for error in errors), errors)

    def test_state_finalization_pull_ref_registry_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            final_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip()
            closeout = subprocess.run(
                ["git", "rev-parse", "HEAD^"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip()
            subprocess.run(["git", "checkout", "--quiet", "--detach", closeout], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "--quiet", "--allow-empty", "-m", "Stale finalization candidate"],
                cwd=root,
                check=True,
            )
            stale = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip()
            subprocess.run(["git", "update-ref", "refs/pull/61/head", stale], cwd=root, check=True)
            subprocess.run(["git", "checkout", "--quiet", "--detach", final_head], cwd=root, check=True)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("no matching local pull-head ref" in error for error in errors), errors)

    def test_state_finalization_pull_ref_is_durable_after_squash_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root, simulate_squash_merge=True)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertEqual([], errors)

    def test_origin_pull_named_branch_cannot_authenticate_finalization_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            final_head = subprocess.run(
                ["git", "rev-parse", "refs/pull/61/head"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            subprocess.run(["git", "update-ref", "-d", "refs/pull/61/head"], cwd=root, check=True)
            subprocess.run(
                ["git", "update-ref", "refs/remotes/origin/pull/61/head", final_head],
                cwd=root,
                check=True,
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("exact dedicated pull-head ref" in error for error in errors), errors)

    def test_alternate_refs_cannot_authenticate_finalization_pr(self) -> None:
        for alternate_ref in (
            "refs/heads/pull/61/head",
            "refs/tags/pull-61-head",
            "refs/remotes/pull/61/head",
            "refs/vendor/pull/61/head",
        ):
            with self.subTest(alternate_ref=alternate_ref), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = self.build_post_governance_history(root, create_finalization_ref=False)
                subprocess.run(["git", "update-ref", alternate_ref, "HEAD"], cwd=root, check=True)
                errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
            self.assertTrue(any("exact dedicated pull-head ref" in error for error in errors), errors)

    def test_symbolic_pull_ref_cannot_authenticate_finalization_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root, create_finalization_ref=False)
            subprocess.run(
                ["git", "symbolic-ref", "refs/pull/61/head", "refs/heads/master"],
                cwd=root,
                check=True,
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("exact pull-head ref is symbolic" in error for error in errors), errors)

    def test_state_finalization_pull_head_rejects_product_code_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            product = root / "fxd_geometry" / "concealed.py"
            product.parent.mkdir()
            product.write_text("CONCEALED_PRODUCT_CHANGE = True\n", encoding="utf-8")
            subprocess.run(["git", "add", product.relative_to(root).as_posix()], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "--quiet", "-m", "Conceal product work in finalization"],
                cwd=root,
                check=True,
            )
            subprocess.run(["git", "update-ref", "refs/pull/61/head", "HEAD"], cwd=root, check=True)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("unauthorized finalization tree path fxd_geometry/concealed.py" in error for error in errors), errors)

    def test_state_finalization_pull_head_rejects_unrelated_document_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                closeout_files={"README.md": f"{AUTHORITY_MARKER}\n**Status:** Active\nStable prose.\n"},
            )
            readme = root / "README.md"
            readme.write_text(
                f"{AUTHORITY_MARKER}\n**Status:** Complete\nUnrelated finalization prose.\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "--quiet", "-m", "Conceal unrelated documentation"],
                cwd=root,
                check=True,
            )
            subprocess.run(["git", "update-ref", "refs/pull/61/head", "HEAD"], cwd=root, check=True)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("unrelated derived-document content" in error for error in errors), errors)

    def test_state_finalization_rejects_unbound_derived_status_edit(self) -> None:
        marker = f"{AUTHORITY_MARKER}\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                closeout_files={
                    "docs/ROADMAP_QUEUE.md": marker + "## Build metadata\n\n**Status:** Active\n",
                },
                finalization_files={
                    "docs/ROADMAP_QUEUE.md": marker + "## Build metadata\n\n**Status:** Complete\n",
                },
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("unbound status projection" in error for error in errors), errors)

    def test_state_finalization_pull_head_rejects_unauthorized_tree_operations(self) -> None:
        cases = {
            "new source file": (None, "new_module.py", "print('unauthorized')\n"),
            "workflow change": (None, ".github/workflows/hidden.yml", "name: hidden\n"),
            "dependency change": (None, "requirements-hidden.txt", "unsafe-dependency\n"),
        }
        for label, (_, relative, content) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = self.build_post_governance_history(root)
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                subprocess.run(["git", "add", relative], cwd=root, check=True)
                subprocess.run(["git", "commit", "--quiet", "-m", label], cwd=root, check=True)
                subprocess.run(["git", "update-ref", "refs/pull/61/head", "HEAD"], cwd=root, check=True)
                errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
            self.assertTrue(any(f"unauthorized finalization tree path {relative}" in error for error in errors), errors)

        for operation in ("delete", "rename"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = self.build_post_governance_history(
                    root,
                    closeout_files={"reviewed.txt": "reviewed closeout content\n"},
                )
                if operation == "delete":
                    (root / "reviewed.txt").unlink()
                    subprocess.run(["git", "add", "-u", "reviewed.txt"], cwd=root, check=True)
                else:
                    subprocess.run(["git", "mv", "reviewed.txt", "renamed.txt"], cwd=root, check=True)
                subprocess.run(["git", "commit", "--quiet", "-m", f"Unauthorized {operation}"], cwd=root, check=True)
                subprocess.run(["git", "update-ref", "refs/pull/61/head", "HEAD"], cwd=root, check=True)
                errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
            self.assertTrue(any("unauthorized finalization tree" in error for error in errors), errors)

    def test_state_finalization_pull_head_accepts_only_authorized_paths(self) -> None:
        marker = f"{AUTHORITY_MARKER}\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                closeout_files={
                    "docs/ROADMAP_QUEUE.md": marker + "## Milestone 32 - Test\n\n**Status:** Active\n",
                    "docs/project-records/README.md": (
                        marker + "## Current milestone\n\nMilestone 32 - Multi-station weld fixture synthesis.\n"
                    ),
                },
                finalization_files={
                    "docs/ROADMAP_QUEUE.md": marker + "## Milestone 32 - Test\n\n**Status:** Complete\n",
                    "docs/project-records/README.md": marker + "## Current milestone\n\nProduct lane is Paused.\n",
                },
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertEqual([], errors)

    def test_state_finalization_pull_head_rejects_binary_derived_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                closeout_files={"README.md": f"{AUTHORITY_MARKER}\n**Status:** Active\n"},
            )
            (root / "README.md").write_bytes(b"\x00binary finalization content\n")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "Binary derived rewrite"], cwd=root, check=True)
            subprocess.run(["git", "update-ref", "refs/pull/61/head", "HEAD"], cwd=root, check=True)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("cannot contain binary changes" in error for error in errors), errors)

    def test_state_finalization_pull_head_rejects_file_mode_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                closeout_files={"README.md": f"{AUTHORITY_MARKER}\n**Status:** Active\n"},
            )
            subprocess.run(["git", "update-index", "--chmod=+x", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "Change derived file mode"], cwd=root, check=True)
            subprocess.run(["git", "update-ref", "refs/pull/61/head", "HEAD"], cwd=root, check=True)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("unauthorized finalization tree mode change" in error for error in errors), errors)

    def test_completion_requires_distinct_state_finalization_pr(self) -> None:
        for reused_pr in (54, 60):
            with self.subTest(reused_pr=reused_pr), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = self.build_post_governance_history(root, state_finalization_pr=reused_pr)
                errors = [
                    *validate_registry_data(data),
                    *validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json"),
                ]
            self.assertTrue(any("state-finalization PR must be distinct" in error for error in errors), errors)

    def test_state_finalization_cannot_change_root_registry_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            data["governance_issue"] = 999
            self.commit_registry(root, data, subject="Tamper with governance root", pull_request=61)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("unauthorized registry change at governance_issue" in error for error in errors), errors)

    def test_state_finalization_cannot_change_maintenance_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            data["maintenance_lane"]["candidates"][0]["status"] = "Complete"
            self.commit_registry(root, data, subject="Tamper with maintenance lane", pull_request=61)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(
            any("maintenance_lane.candidates[0].status" in error for error in errors),
            errors,
        )

    def test_state_finalization_cannot_change_unrelated_milestone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root)
            self.milestone(data, 31)["title"] = "Unauthorized rewrite"
            self.commit_registry(root, data, subject="Tamper with Milestone 31", pull_request=61)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("milestones[30].title" in error for error in errors), errors)

    def test_unrelated_merge_commit_cannot_impersonate_implementation_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root, implementation_subject_pr=99)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(
            any("no recorded merge commit associated with implementation PR #54" in error for error in errors),
            errors,
        )

    def test_implementation_prs_require_distinct_merge_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                implementation_prs=[54, 55],
                implementation_subjects=["Combined implementations (#54) (#55)"],
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("one-to-one mapping to distinct recorded merge commits" in error for error in errors), errors)
        self.assertTrue(any("one-to-one to distinct merge evidence" in error for error in errors), errors)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(
                root,
                implementation_prs=[54, 55],
                implementation_subjects=[
                    "Milestone 32 implementation (#54)",
                    "Milestone 32 integration repair (#55)",
                ],
            )
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertEqual([], errors)

    def test_completion_evidence_must_exist_in_closeout_commit_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.build_post_governance_history(root, evidence_at_closeout=False)
            errors = validate_git_history(data, root, root / "docs" / "MILESTONE_STATE.json")
        self.assertTrue(any("closeout evidence PR requires results" in error for error in errors), errors)
        self.assertTrue(any("milestones[31].evidence_results" in error for error in errors), errors)

    def test_github_merge_and_squash_messages_associate_pr_number(self) -> None:
        self.assertTrue(commit_message_matches_pr("Close milestone (#60)", 60))
        self.assertTrue(commit_message_matches_pr("Merge pull request #60 from governance/closeout", 60))
        self.assertFalse(commit_message_matches_pr("Close milestone (#59)", 60))
        self.assertFalse(commit_message_matches_pr("Unrelated change (#99)\n\nMentions implementation PR (#60).", 60))

    def test_sequence_change_requires_revision_bump_and_decision(self) -> None:
        previous = self.data()
        current = copy.deepcopy(previous)
        current["milestones"].append(
            {
                "number": 33,
                "sequence_position": 33,
                "predecessor": 32,
                "status": "Planned",
                "replacement_milestone": None,
            }
        )
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("sequence_revision" in error for error in errors), errors)
        self.assertTrue(any("sequence_decisions" in error for error in errors), errors)

        current["sequence_revision"] = previous["sequence_revision"] + 1
        current["sequence_decisions"] = ["Issue #999 explicitly approved the sequence addition."]
        self.assertEqual([], validate_sequence_transition(current, previous))

    def test_reopening_complete_milestone_requires_sequence_revision_and_new_decision(self) -> None:
        previous = self.data()
        current = copy.deepcopy(previous)
        self.milestone(current, 20)["status"] = "Planned"

        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("sequence_revision" in error for error in errors), errors)

        current["sequence_revision"] = previous["sequence_revision"] + 1
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("newly added approving sequence decision" in error for error in errors), errors)

        previous["sequence_revision"] = 2
        previous["sequence_decisions"] = ["Issue #900 approved an earlier sequence change."]
        current = copy.deepcopy(current)
        current["sequence_revision"] = 3
        current["sequence_decisions"] = list(previous["sequence_decisions"])
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("newly added approving sequence decision" in error for error in errors), errors)

        current["sequence_decisions"] = [
            *previous["sequence_decisions"],
            "Issue #999 approved a generic sequence change.",
        ]
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("identifying the milestone and authority" in error for error in errors), errors)

    def test_approved_completed_milestone_reopening_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            previous = self.build_post_governance_history(root)
            current = copy.deepcopy(previous)
            self.milestone(current, 32)["status"] = "Planned"
            current["sequence_revision"] = previous["sequence_revision"] + 1
            current["sequence_decisions"] = [
                *previous["sequence_decisions"],
                "Issue #999 approved reopening Milestone 32 for governed planning.",
            ]
            registry = root / "docs" / "MILESTONE_STATE.json"
            registry.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
            subprocess.run(["git", "add", "docs/MILESTONE_STATE.json"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "--quiet", "-m", "Approve governed Milestone 32 reopening"],
                cwd=root,
                check=True,
            )
            self.assertEqual([], validate_sequence_transition(current, previous))
            self.assertEqual([], validate_registry_data(current))
            self.assertEqual([], validate_sequence_history(current, registry, root))

            invalid_predecessor = copy.deepcopy(current)
            self.milestone(invalid_predecessor, 32)["predecessor"] = 30
            errors = [
                *validate_sequence_transition(invalid_predecessor, previous),
                *validate_registry_data(invalid_predecessor),
            ]
            self.assertTrue(any("predecessor must be 31" in error for error in errors), errors)

    def test_active_milestone_cannot_predeclare_retained_finalization_evidence(self) -> None:
        previous = self.data()
        current = copy.deepcopy(previous)
        milestone = self.milestone(current, 32)
        milestone.update(
            {
                "state_finalization_pr": 61,
                "closeout_pr": 60,
                "closeout_merge_commit": "a" * 40,
                "merge_commits": ["a" * 40],
                "completion_evidence": "Fabricated retained evidence.",
                "evidence_results": {profile: ["Fabricated."] for profile in milestone["evidence_profiles"]},
                "decisions": [f"Closeout PR #60 merged as {'a' * 40}."],
            }
        )
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("only when reopening a previously closed" in error for error in errors), errors)

    def test_reopening_preserves_completion_and_closeout_history(self) -> None:
        previous = self.data()
        current = copy.deepcopy(previous)
        milestone = self.milestone(current, 20)
        milestone["status"] = "Planned"
        milestone["completion_evidence"] = None
        current["sequence_revision"] = previous["sequence_revision"] + 1
        current["sequence_decisions"] = [
            "Issue #999 approved reopening Milestone 20 for governed planning."
        ]
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("preserve prior completion and closeout history field completion_evidence" in error for error in errors), errors)

    def test_all_closed_dispositions_require_governance_when_reopened(self) -> None:
        for closed in ("Complete", "Superseded", "Cancelled"):
            for reopened in ("Planned", "Active", "Blocked", "Waiting", "Paused"):
                with self.subTest(closed=closed, reopened=reopened):
                    previous = self.data()
                    current = copy.deepcopy(previous)
                    self.milestone(previous, 20)["status"] = closed
                    self.milestone(current, 20)["status"] = reopened
                    errors = validate_sequence_transition(current, previous)
                    self.assertTrue(any("sequence_revision" in error for error in errors), errors)

    def test_paused_transition_requires_sequence_revision(self) -> None:
        previous = self.data()
        current = copy.deepcopy(previous)
        self.milestone(current, 32)["status"] = "Paused"
        current["product_lane"].update(
            {
                "paused": True,
                "active_milestone": None,
                "pause_reason": "Governed test pause.",
                "decision": "Issue #999 approved the test pause.",
            }
        )
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("sequence_revision" in error for error in errors), errors)

    def test_paused_lane_transition_requires_new_decision(self) -> None:
        previous = self.data()
        previous["sequence_revision"] = 2
        previous["sequence_decisions"] = ["Issue #900 approved an earlier sequence change."]
        current = copy.deepcopy(previous)
        self.milestone(current, 32)["status"] = "Paused"
        current["product_lane"].update(
            {
                "paused": True,
                "active_milestone": None,
                "pause_reason": "Governed test pause.",
                "decision": "Issue #999 approved the test pause.",
            }
        )
        current["sequence_revision"] = 3
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("newly added approving sequence decision" in error for error in errors), errors)

    def test_sequence_revision_rejects_reused_decision_list(self) -> None:
        previous = self.data()
        previous["sequence_revision"] = 2
        previous["sequence_decisions"] = ["Issue #900 approved an earlier sequence change."]
        current = copy.deepcopy(previous)
        current["product_lane"]["pause_reason"] = "Materially different governing reason."
        current["sequence_revision"] = 3
        current["sequence_decisions"] = list(previous["sequence_decisions"])
        errors = validate_sequence_transition(current, previous)
        self.assertTrue(any("newly added approving sequence decision" in error for error in errors), errors)

    def test_approved_product_lane_pause_with_new_decision_is_accepted(self) -> None:
        previous = self.data()
        current = copy.deepcopy(previous)
        self.milestone(current, 32)["status"] = "Complete"
        disposition = current["product_lane"]["after_milestone_32_closeout"]
        current["product_lane"].update(
            {
                "paused": disposition["paused"],
                "active_milestone": disposition["active_milestone"],
                "pause_reason": disposition["reason"],
                "decision": disposition["decision"],
            }
        )
        current["sequence_revision"] = previous["sequence_revision"] + 1
        current["sequence_decisions"] = [
            "Issue #56 approved the post-Milestone-32 product-lane pause."
        ]
        self.assertEqual([], validate_sequence_transition(current, previous))

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
        with tempfile.TemporaryDirectory() as temp:
            context = Path(temp) / "selection.md"
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select", "--context", str(context)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            selected_context = context.read_text(encoding="utf-8")
        self.assertEqual(0, selected.returncode, selected.stderr)
        self.assertIn("Selected Active Milestone 32", selected.stdout)
        self.assertIn("Issue #57", selected.stdout)
        self.assertIn("Authoritative issue: #57", selected_context)
        self.assertIn("Implementation PRs: #54", selected_context)

    def test_registry_selector_rejects_active_milestone_with_blocked_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.data()
            self.milestone(data, 31)["status"] = "Blocked"
            self.build_selector_repository(root, data)
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("Milestone governance validation failed", selected.stderr)
        self.assertNotIn("Selected Active Milestone", selected.stdout)

    def test_registry_selector_rejects_waiting_and_paused_predecessors(self) -> None:
        for status in ("Waiting", "Paused"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = self.data()
                self.milestone(data, 31)["status"] = status
                self.build_selector_repository(root, data)
                selected = subprocess.run(
                    ["node", "scripts/fxd-backlog.mjs", "select"],
                    cwd=root,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            self.assertNotEqual(0, selected.returncode)
            self.assertIn("Milestone governance validation failed", selected.stderr)

    def test_registry_selector_rejects_malformed_predecessor_and_sequence(self) -> None:
        mutations = (
            ("predecessor", lambda data: self.milestone(data, 32).__setitem__("predecessor", 30)),
            ("sequence", lambda data: self.milestone(data, 32).__setitem__("sequence_position", 33)),
            ("projection", lambda data: data["product_lane"].__setitem__("active_milestone", 31)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = self.data()
                mutate(data)
                self.build_selector_repository(root, data)
                selected = subprocess.run(
                    ["node", "scripts/fxd-backlog.mjs", "select"],
                    cwd=root,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            self.assertNotEqual(0, selected.returncode)
            self.assertIn("Milestone governance validation failed", selected.stderr)

    def test_registry_selector_returns_governed_no_selection_for_paused_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.data()
            self.milestone(data, 32)["status"] = "Planned"
            data["product_lane"].update(
                {
                    "paused": True,
                    "active_milestone": None,
                    "pause_reason": "Approved selector pause.",
                    "decision": "Issue #999 approved the selector pause.",
                }
            )
            self.build_selector_repository(root, data)
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("product lane is formally paused", selected.stderr)
        self.assertNotIn("Selected Active Milestone", selected.stdout)

    def test_registry_selector_does_not_consult_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_selector_repository(root)
            self.assertFalse((root / "BACKLOG.md").exists())
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
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

    def test_hosted_acceptance_fetches_history_and_runs_for_every_pr(self) -> None:
        workflow = json.loads((ROOT / ".github" / "workflows" / "kernel-acceptance.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["ocp-acceptance"]["steps"]
        checkout = next(step for step in steps if step["name"] == "Check out repository")
        self.assertEqual(0, checkout["with"]["fetch-depth"])
        pull_evidence = next(step for step in steps if step["name"] == "Fetch pull-request head evidence")
        self.assertIn("refs/pull/", pull_evidence["run"])
        self.assertNotIn("refs/remotes/", pull_evidence["run"])
        self.assertRegex(pull_evidence["run"], r"refs/pull/.+/head:refs/pull/.+/head")
        declared_evidence = next(
            step for step in steps if step["name"] == "Fetch declared state-finalization pull evidence"
        )
        self.assertIn("state_finalization_pr", declared_evidence["run"])
        self.assertIn("refs/pull/${pull_request}/head", declared_evidence["run"])
        self.assertNotIn("refs/remotes/", declared_evidence["run"])
        self.assertNotIn("paths", workflow["on"]["pull_request"])

    def test_foreman_validates_governance_before_selection(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        validation = workflow.index("name: Validate authoritative milestone governance")
        selection = workflow.index("name: Select milestone")
        self.assertLess(validation, selection)
        self.assertIn("python scripts/validate_milestones.py", workflow[validation:selection])

    def test_foreman_rejects_closed_authoritative_milestone_issue(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        issue_step = workflow[workflow.index("name: Load authoritative milestone issue") :]
        self.assertIn("--json number,state,body,url", issue_step)
        self.assertRegex(issue_step, r'issue_state=.*state')
        self.assertIn('"$issue_state" != "OPEN"', issue_step)
        self.assertIn("authoritative milestone issue is not OPEN", issue_step)
        self.assertIn("failed to fetch authoritative milestone issue", issue_step)

    def test_foreman_rejects_whitespace_only_authoritative_issue_body(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        issue_validation = workflow.index("name: Load authoritative milestone issue")
        body_append = workflow.index(">> .fxd/selected-milestone.md", issue_validation)
        validation_script = workflow[issue_validation:body_append]
        predicate = '[[ "$issue_body" =~ [^[:space:]] ]]'
        self.assertIn('if [[ ! "$issue_body" =~ [^[:space:]] ]]; then', validation_script)

        bash = shutil.which("bash")
        if bash is None:
            git = shutil.which("git")
            if git is not None:
                git_bash = Path(git).resolve().parent.parent / "bin" / "bash.exe"
                if git_bash.is_file():
                    bash = str(git_bash)
        self.assertIsNotNone(bash, "Git Bash is required to verify the Foreman shell predicate")

        for label, body in {
            "empty": "",
            "spaces": "   ",
            "tabs": "\t\t",
            "newlines": "\n\n",
            "mixed whitespace": " \t\n\t ",
        }.items():
            with self.subTest(label=label):
                result = subprocess.run(
                    [bash, "-c", f'issue_body="$1"; {predicate}', "bash", body],
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)

        meaningful = subprocess.run(
            [bash, "-c", f'issue_body="$1"; {predicate}', "bash", "Milestone 32 scope"],
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, meaningful.returncode)

    def test_foreman_loads_open_issue_before_codex_execution(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        issue_validation = workflow.index("name: Load authoritative milestone issue")
        body_append = workflow.index(">> .fxd/selected-milestone.md", issue_validation)
        codex = workflow.index("name: Run Codex milestone Foreman")
        self.assertLess(issue_validation, body_append)
        self.assertLess(body_append, codex)
        validation_script = workflow[issue_validation:body_append]
        self.assertIn("set -euo pipefail", validation_script)
        self.assertIn("issue_state", validation_script)
        self.assertIn("issue_number", validation_script)
        self.assertIn("GITHUB_REPOSITORY", validation_script)

    def test_foreman_issue_number_matches_registry_selection(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        issue_step = workflow[workflow.index("name: Load authoritative milestone issue") :]
        self.assertIn("steps.milestone.outputs.issue_number", issue_step)
        self.assertIn('"$issue_number" != "$selected_issue"', issue_step)
        self.assertIn("authoritative milestone issue number mismatch", issue_step)
        self.assertIn("kool1160/fxd-fixture-design", issue_step)
        self.assertNotIn("gh issue view 57", issue_step)

    def test_foreman_rejects_authoritative_issue_repository_mismatch(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        issue_step = workflow[workflow.index("name: Load authoritative milestone issue") :]
        repository_check = issue_step.index('"$GITHUB_REPOSITORY" != "$EXPECTED_REPOSITORY"')
        issue_fetch = issue_step.index("gh issue view")
        self.assertLess(repository_check, issue_fetch)
        self.assertIn("authoritative milestone issue repository mismatch", issue_step)
        self.assertIn('issue_url" != "https://github.com/$EXPECTED_REPOSITORY/issues/$selected_issue', issue_step)


if __name__ == "__main__":
    unittest.main()
