"""Offline validation for the authoritative FXD milestone registry."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "fxd-milestone-state-v1"
LEGAL_STATUSES = {
    "Planned",
    "Active",
    "Blocked",
    "Waiting",
    "Paused",
    "Complete",
    "Superseded",
    "Cancelled",
}
BLOCKING_SEQUENCE_STATUSES = {"Blocked", "Waiting", "Paused"}
AUTHORITY_MARKER = "<!-- FXD-MILESTONE-STATE: docs/MILESTONE_STATE.json -->"
HISTORICAL_MARKER = "<!-- FXD-HISTORICAL-MILESTONE-SNAPSHOT -->"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+Milestone\s+(\d+)\b", re.IGNORECASE)
STATUS_PATTERN = re.compile(r"(?:\*\*Status:\*\*|\bStatus:)\s*([^\r\n]+)", re.IGNORECASE)
CURRENT_PATTERN = re.compile(r"\bcurrent\s+(?:product\s+)?milestone\s*(?::|is)?\s*(?:Milestone|M)?\s*(\d+)\b", re.IGNORECASE)
PROSE_STATUS_PATTERNS = (
    re.compile(
        r"\b(?:Milestone|M)\s*(\d+)\b\s+(?:is|remains|has status)\s+(?:the\s+sole\s+)?(Planned|Active|Blocked|Waiting|Paused|Complete|Superseded|Cancelled)\b",
        re.IGNORECASE,
    ),
)
ILLEGAL_STATUS_PATTERN = re.compile(
    r"\b(Pending|In progress|Mostly complete|Current\s*/\s*Pending|Implemented|Complete under review|Functionally complete)\b",
    re.IGNORECASE,
)
REQUIRED_MILESTONE_FIELDS = {
    "number",
    "title",
    "sequence_position",
    "predecessor",
    "status",
    "issue",
    "implementation_prs",
    "merge_commits",
    "evidence_profiles",
    "completion_evidence",
    "closeout_pr",
    "decisions",
    "replacement_milestone",
    "legacy",
    "historical_gaps",
}


class MilestoneValidationError(RuntimeError):
    """Raised when milestone governance validation fails."""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _sequence_projection(data: dict[str, Any]) -> dict[str, Any]:
    """Return only fields whose change alters the governed product sequence."""

    lane = data.get("product_lane") if isinstance(data.get("product_lane"), dict) else {}
    milestones = data.get("milestones") if isinstance(data.get("milestones"), list) else []
    return {
        "governance_effective_milestone": data.get("governance_effective_milestone"),
        "product_lane": {
            "paused": lane.get("paused"),
            "active_milestone": lane.get("active_milestone"),
        },
        "milestones": [
            {
                "number": milestone.get("number"),
                "sequence_position": milestone.get("sequence_position"),
                "predecessor": milestone.get("predecessor"),
                "terminal_sequence_status": (
                    milestone.get("status") if milestone.get("status") in {"Superseded", "Cancelled"} else None
                ),
                "replacement_milestone": milestone.get("replacement_milestone"),
            }
            for milestone in milestones
            if isinstance(milestone, dict)
        ],
    }


def validate_sequence_transition(current: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    """Require a one-step revision bump and decision when sequence fields change."""

    if _sequence_projection(current) == _sequence_projection(previous):
        return []
    current_revision = current.get("sequence_revision")
    previous_revision = previous.get("sequence_revision")
    errors: list[str] = []
    if not _positive_int(previous_revision) or current_revision != previous_revision + 1:
        errors.append("sequence changes require sequence_revision to increment exactly once from the prior registry")
    if not _nonempty_strings(current.get("sequence_decisions")):
        errors.append("sequence changes require nonempty sequence_decisions")
    return errors


def commit_message_matches_pr(message: str, pull_request: int) -> bool:
    """Recognize GitHub's merge and squash commit PR-number forms."""

    if not isinstance(message, str) or not _positive_int(pull_request):
        return False
    subject = next((line.strip() for line in message.splitlines() if line.strip()), "")
    return bool(
        re.search(
            rf"(?:\(\s*#{pull_request}\s*\)|\bmerge\s+pull\s+request\s+#{pull_request}\b)",
            subject,
            re.IGNORECASE,
        )
    )


def implementation_pr_merge_mapping(
    implementation_prs: list[int],
    commit_messages: dict[str, str],
    *,
    allowed_commits: list[str] | set[str] | None = None,
) -> tuple[dict[int, str] | None, list[int]]:
    """Map every implementation PR to a distinct PR-number-bearing commit."""

    allowed = set(commit_messages) if allowed_commits is None else set(allowed_commits)
    candidates = {
        pull_request: [
            commit
            for commit, message in commit_messages.items()
            if commit in allowed and commit_message_matches_pr(message, pull_request)
        ]
        for pull_request in implementation_prs
        if _positive_int(pull_request)
    }
    missing = [pull_request for pull_request, commits in candidates.items() if not commits]
    if missing:
        return None, missing

    commit_to_pr: dict[str, int] = {}

    def assign(pull_request: int, visited: set[str]) -> bool:
        for commit in candidates[pull_request]:
            if commit in visited:
                continue
            visited.add(commit)
            owner = commit_to_pr.get(commit)
            if owner is None or assign(owner, visited):
                commit_to_pr[commit] = pull_request
                return True
        return False

    for pull_request in sorted(candidates, key=lambda item: (len(candidates[item]), item)):
        if not assign(pull_request, set()):
            return None, []
    return {pull_request: commit for commit, pull_request in commit_to_pr.items()}, []


def load_registry(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MilestoneValidationError([f"cannot read registry {path}: {exc}"]) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MilestoneValidationError([f"malformed milestone registry: {exc.msg} at line {exc.lineno}"]) from exc
    if not isinstance(data, dict):
        raise MilestoneValidationError(["milestone registry root must be an object"])
    return data


def validate_registry_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unknown milestone schema: {data.get('schema_version')!r}")

    revision = data.get("sequence_revision")
    if not _positive_int(revision):
        errors.append("sequence_revision must be a positive integer")
    elif revision > 1 and not _nonempty_strings(data.get("sequence_decisions")):
        errors.append("sequence_revision changes require nonempty sequence_decisions")

    governance_start = data.get("governance_effective_milestone")
    if not _positive_int(data.get("governance_issue")):
        errors.append("governance_issue must be a positive integer")
    if not _positive_int(governance_start):
        errors.append("governance_effective_milestone must be a positive integer")

    profiles = data.get("evidence_profiles")
    if not isinstance(profiles, dict) or set(profiles) != set("ABCDEF"):
        errors.append("evidence_profiles must define exactly A through F")
        allowed_profiles: set[str] = set()
    else:
        allowed_profiles = set(profiles)

    milestones = data.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        errors.append("milestones must be a nonempty array")
        return errors

    numbers: list[int] = []
    positions: list[int] = []
    by_number: dict[int, dict[str, Any]] = {}
    for index, milestone in enumerate(milestones):
        label = f"milestones[{index}]"
        if not isinstance(milestone, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = REQUIRED_MILESTONE_FIELDS - set(milestone)
        if missing:
            errors.append(f"{label} missing fields: {', '.join(sorted(missing))}")

        number = milestone.get("number")
        position = milestone.get("sequence_position")
        if not _positive_int(number):
            errors.append(f"{label}.number must be a positive integer")
        else:
            numbers.append(number)
            by_number[number] = milestone
        if not _positive_int(position):
            errors.append(f"{label}.sequence_position must be a positive integer")
        else:
            positions.append(position)

        status = milestone.get("status")
        if status not in LEGAL_STATUSES:
            errors.append(f"milestone {number!r} has unknown status {status!r}")
        title = milestone.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"milestone {number!r} title must be nonempty")

        issue = milestone.get("issue")
        if issue is not None and not _positive_int(issue):
            errors.append(f"milestone {number!r} issue must be null or a positive integer")
        prs = milestone.get("implementation_prs")
        if not isinstance(prs, list) or any(not _positive_int(pr) for pr in prs):
            errors.append(f"milestone {number!r} implementation_prs must contain positive integers")
        elif len(prs) != len(set(prs)):
            errors.append(f"milestone {number!r} implementation_prs cannot contain duplicates")
        merges = milestone.get("merge_commits")
        if not isinstance(merges, list) or any(not isinstance(commit, str) or not SHA_PATTERN.fullmatch(commit) for commit in merges):
            errors.append(f"milestone {number!r} merge_commits must contain lowercase 40-character SHAs")
        elif len(merges) != len(set(merges)):
            errors.append(f"milestone {number!r} merge_commits cannot contain duplicates")
        selected_profiles = milestone.get("evidence_profiles")
        if not isinstance(selected_profiles, list) or not selected_profiles:
            errors.append(f"milestone {number!r} must select at least one evidence profile")
        elif any(profile not in allowed_profiles for profile in selected_profiles):
            errors.append(f"milestone {number!r} selects an unknown evidence profile")
        elif len(selected_profiles) != len(set(selected_profiles)):
            errors.append(f"milestone {number!r} evidence_profiles cannot contain duplicates")

        legacy = milestone.get("legacy")
        if not isinstance(legacy, bool):
            errors.append(f"milestone {number!r} legacy must be true or false")
        legacy_reconciliation = milestone.get("legacy_reconciliation")
        if legacy_reconciliation is not None and not isinstance(legacy_reconciliation, bool):
            errors.append(f"milestone {number!r} legacy_reconciliation must be true, false, or omitted")
        historical_gaps = milestone.get("historical_gaps")
        if not isinstance(historical_gaps, list) or any(
            not isinstance(gap, str) or not gap.strip() for gap in historical_gaps
        ):
            errors.append(f"milestone {number!r} historical_gaps must be an array of nonempty strings")
        replacement = milestone.get("replacement_milestone")
        if replacement is not None and not _positive_int(replacement):
            errors.append(f"milestone {number!r} replacement_milestone must be null or a positive integer")
        closeout_pr_value = milestone.get("closeout_pr")
        if closeout_pr_value is not None and not _positive_int(closeout_pr_value):
            errors.append(f"milestone {number!r} closeout_pr must be null or a positive integer")
        closeout_commit_value = milestone.get("closeout_merge_commit")
        if closeout_commit_value is not None and (
            not isinstance(closeout_commit_value, str) or not SHA_PATTERN.fullmatch(closeout_commit_value)
        ):
            errors.append(f"milestone {number!r} closeout_merge_commit must be null or a lowercase 40-character SHA")

        post_governance = _positive_int(governance_start) and _positive_int(number) and number >= governance_start
        evidence_results = milestone.get("evidence_results")
        if post_governance:
            if "closeout_merge_commit" not in milestone:
                errors.append(f"post-governance milestone {number!r} requires a closeout_merge_commit field")
            if milestone.get("legacy") is not False:
                errors.append(f"post-governance milestone {number!r} cannot be classified as legacy")
            if not isinstance(evidence_results, dict):
                errors.append(f"post-governance milestone {number!r} requires an evidence_results object")
            else:
                unknown_results = set(evidence_results) - set(selected_profiles or [])
                if unknown_results:
                    errors.append(
                        f"post-governance milestone {number!r} has results for unselected evidence profiles: "
                        f"{', '.join(sorted(unknown_results))}"
                    )
                for profile, entries in evidence_results.items():
                    if not _nonempty_strings(entries):
                        errors.append(
                            f"post-governance milestone {number!r} evidence profile {profile!r} "
                            "requires reviewable nonempty evidence entries"
                        )

        decisions = milestone.get("decisions")
        if not isinstance(decisions, list) or any(not isinstance(decision, str) or not decision.strip() for decision in decisions):
            errors.append(f"milestone {number!r} decisions must be an array of nonempty strings")

        if status == "Active":
            if not _positive_int(issue):
                errors.append(f"Active milestone {number!r} requires an authoritative issue")
            if not isinstance(prs, list) or not prs:
                errors.append(f"Active milestone {number!r} requires an implementation PR")
        if post_governance and milestone.get("closeout_pr") is not None:
            closeout_pr = milestone.get("closeout_pr")
            if not _positive_int(closeout_pr):
                errors.append(f"post-governance milestone {number!r} closeout PR must be null or a positive integer")
            elif isinstance(prs, list) and closeout_pr in prs:
                errors.append(f"post-governance milestone {number!r} closeout PR must be distinct from implementation PRs")
            if isinstance(evidence_results, dict):
                missing_closeout_results = set(selected_profiles or []) - set(evidence_results)
                if missing_closeout_results:
                    errors.append(
                        f"post-governance milestone {number!r} closeout evidence PR requires results for every selected "
                        f"evidence profile: {', '.join(sorted(missing_closeout_results))}"
                    )
            evidence = milestone.get("completion_evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                errors.append(f"post-governance milestone {number!r} closeout evidence PR requires completion_evidence")
        if status == "Complete":
            if not isinstance(merges, list) or not merges:
                errors.append(f"Complete milestone {number!r} requires merged evidence")
            evidence = milestone.get("completion_evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                errors.append(f"Complete milestone {number!r} requires completion_evidence")
            if post_governance and isinstance(evidence_results, dict):
                missing_results = set(selected_profiles or []) - set(evidence_results)
                if missing_results:
                    errors.append(
                        f"post-governance Complete milestone {number!r} requires results for every selected evidence profile: "
                        f"{', '.join(sorted(missing_results))}"
                    )
            if milestone.get("legacy"):
                if milestone.get("legacy_reconciliation") is not True:
                    errors.append(f"legacy Complete milestone {number!r} requires explicit legacy_reconciliation")
                if not _nonempty_strings(milestone.get("historical_gaps")):
                    errors.append(f"legacy Complete milestone {number!r} requires historical_gaps")
            elif post_governance:
                closeout_pr = milestone.get("closeout_pr")
                if not _positive_int(closeout_pr):
                    errors.append(f"post-governance Complete milestone {number!r} requires a separate closeout PR")
                closeout_commit = milestone.get("closeout_merge_commit")
                if not isinstance(closeout_commit, str) or not SHA_PATTERN.fullmatch(closeout_commit):
                    errors.append(f"post-governance Complete milestone {number!r} requires a closeout merge commit")
                elif not isinstance(merges, list) or closeout_commit not in merges:
                    errors.append(f"post-governance Complete milestone {number!r} closeout merge commit must be recorded in merge_commits")
                closeout_decision_fragments = (
                    "closeout",
                    f"#{closeout_pr}" if _positive_int(closeout_pr) else "#<missing>",
                    closeout_commit if isinstance(closeout_commit, str) else "<missing-commit>",
                )
                if not isinstance(decisions, list) or not any(
                    all(fragment.casefold() in decision.casefold() for fragment in closeout_decision_fragments)
                    for decision in decisions
                ):
                    errors.append(
                        f"post-governance Complete milestone {number!r} requires an explicit closeout decision linking its PR and merge commit"
                    )
        if status in {"Superseded", "Cancelled"}:
            if not _nonempty_strings(decisions):
                errors.append(f"{status} milestone {number!r} requires a decision record")
            if status == "Superseded" and not _positive_int(milestone.get("replacement_milestone")):
                errors.append(f"Superseded milestone {number!r} requires a replacement milestone")

    if len(numbers) != len(set(numbers)):
        errors.append("duplicate milestone numbers are prohibited")
    if len(positions) != len(set(positions)):
        errors.append("duplicate milestone sequence positions are prohibited")
    if numbers and sorted(numbers) != list(range(1, max(numbers) + 1)):
        errors.append("milestone numbers must be consecutive from 1")
    if positions and sorted(positions) != list(range(1, len(positions) + 1)):
        errors.append("sequence positions must be consecutive from 1")

    ordered = sorted(
        (milestone for milestone in milestones if isinstance(milestone, dict) and _positive_int(milestone.get("sequence_position"))),
        key=lambda item: item["sequence_position"],
    )
    for index, milestone in enumerate(ordered):
        number = milestone.get("number")
        expected_predecessor = None if index == 0 else ordered[index - 1].get("number")
        predecessor = milestone.get("predecessor")
        if predecessor != expected_predecessor:
            errors.append(f"milestone {number!r} predecessor must be {expected_predecessor!r}, got {predecessor!r}")
        if predecessor is not None and predecessor not in by_number:
            errors.append(f"milestone {number!r} references unknown predecessor {predecessor!r}")

    active = [milestone for milestone in milestones if isinstance(milestone, dict) and milestone.get("status") == "Active"]
    lane = data.get("product_lane")
    if not isinstance(lane, dict):
        errors.append("product_lane must be an object")
        lane = {}
    paused = lane.get("paused")
    projected_active = lane.get("active_milestone")
    if paused is True:
        if active:
            errors.append("a formally paused product lane must have zero Active milestones")
        if projected_active is not None:
            errors.append("a formally paused product lane must project active_milestone as null")
        if not isinstance(lane.get("pause_reason"), str) or not lane.get("pause_reason", "").strip():
            errors.append("a formally paused product lane requires pause_reason")
        if not isinstance(lane.get("decision"), str) or not lane.get("decision", "").strip():
            errors.append("a formally paused product lane requires a decision")
    elif paused is False:
        if len(active) != 1:
            errors.append(f"an unpaused product lane requires exactly one Active milestone, found {len(active)}")
        elif projected_active != active[0].get("number"):
            errors.append("product_lane.active_milestone does not match the sole Active milestone")
    else:
        errors.append("product_lane.paused must be true or false")

    post_closeout = lane.get("after_milestone_32_closeout")
    if not isinstance(post_closeout, dict):
        errors.append("product_lane must record the approved post-Milestone-32 closeout disposition")
    else:
        if post_closeout.get("paused") is not True or post_closeout.get("active_milestone") is not None:
            errors.append("post-Milestone-32 closeout disposition must formally pause with zero Active milestones")
        if not isinstance(post_closeout.get("reason"), str) or not post_closeout.get("reason", "").strip():
            errors.append("post-Milestone-32 closeout disposition requires a reason")
        if not isinstance(post_closeout.get("decision"), str) or not post_closeout.get("decision", "").strip():
            errors.append("post-Milestone-32 closeout disposition requires a decision")

    maintenance = data.get("maintenance_lane")
    candidates = maintenance.get("candidates") if isinstance(maintenance, dict) else None
    if not isinstance(candidates, list):
        errors.append("maintenance_lane.candidates must be an array")
    else:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                errors.append("maintenance candidates must be objects")
                continue
            if not _positive_int(candidate.get("pull_request")) or not _positive_int(candidate.get("issue")):
                errors.append("maintenance candidates require a pull request and maintenance issue")
            if candidate.get("product_milestone") is not None:
                errors.append("maintenance candidates cannot own product milestone status")
            if candidate.get("status") not in LEGAL_STATUSES:
                errors.append("maintenance candidates require a legal status")
            if not _nonempty_strings(candidate.get("blocking_findings")) and candidate.get("status") == "Blocked":
                errors.append("Blocked maintenance candidates require blocking_findings")

    for milestone in ordered:
        number = milestone.get("number")
        if milestone.get("status") == "Active" and milestone.get("predecessor") is not None:
            predecessor = by_number.get(milestone["predecessor"])
            if predecessor and predecessor.get("status") not in {"Complete", "Superseded"}:
                errors.append(f"Active milestone {number!r} predecessor is not Complete or Superseded")
        if milestone.get("status") in {"Active", "Complete"}:
            for earlier in ordered:
                if earlier.get("sequence_position", 0) >= milestone.get("sequence_position", 0):
                    break
                if earlier.get("status") in BLOCKING_SEQUENCE_STATUSES:
                    errors.append(
                        f"milestone {number!r} skips {earlier.get('status')} milestone {earlier.get('number')!r}"
                    )

    for milestone in milestones:
        if not isinstance(milestone, dict) or milestone.get("status") != "Superseded":
            continue
        replacement = milestone.get("replacement_milestone")
        if _positive_int(replacement) and replacement not in by_number:
            errors.append(f"Superseded milestone {milestone.get('number')!r} references unknown replacement {replacement!r}")

    return errors


def validate_derived_documents(data: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    documents = data.get("derived_documents")
    snapshots = data.get("historical_snapshot_documents")
    if not isinstance(documents, list) or any(not isinstance(path, str) or not path for path in documents):
        return ["derived_documents must be an array of repository-relative paths"]
    if not isinstance(snapshots, list) or any(not isinstance(path, str) or not path for path in snapshots):
        return ["historical_snapshot_documents must be an array of repository-relative paths"]
    snapshot_set = set(snapshots)
    unknown_snapshots = snapshot_set - set(documents)
    if unknown_snapshots:
        errors.append(f"historical snapshots are not designated derived documents: {', '.join(sorted(unknown_snapshots))}")

    expected_status = {
        milestone["number"]: milestone["status"]
        for milestone in data.get("milestones", [])
        if isinstance(milestone, dict) and _positive_int(milestone.get("number"))
    }
    active_number = data.get("product_lane", {}).get("active_milestone")

    for relative in documents:
        path = repo_root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"cannot read designated derived document {relative}: {exc}")
            continue
        if AUTHORITY_MARKER not in text:
            errors.append(f"derived document {relative} does not point to docs/MILESTONE_STATE.json")
        if relative in snapshot_set:
            if HISTORICAL_MARKER not in text:
                errors.append(f"historical document {relative} is not marked as a non-authoritative snapshot")
            continue

        current_heading: int | None = None
        for line_number, line in enumerate(text.splitlines(), start=1):
            heading = HEADING_PATTERN.match(line)
            if heading:
                current_heading = int(heading.group(1))
            status_match = STATUS_PATTERN.search(line)
            if status_match:
                raw_status = status_match.group(1).strip().strip("*` .")
                illegal = ILLEGAL_STATUS_PATTERN.search(raw_status)
                if illegal:
                    errors.append(f"{relative}:{line_number} uses non-authoritative status {illegal.group(1)!r}")
                else:
                    canonical_status = next(
                        (status for status in LEGAL_STATUSES if status.casefold() == raw_status.casefold()),
                        None,
                    )
                    if canonical_status is None or canonical_status != raw_status:
                        errors.append(f"{relative}:{line_number} uses unrecognized or noncanonical status {raw_status!r}")
                    elif current_heading in expected_status and canonical_status != expected_status[current_heading]:
                        errors.append(
                            f"{relative}:{line_number} conflicts for milestone {current_heading}: "
                            f"{canonical_status} != {expected_status[current_heading]}"
                        )
            current_match = CURRENT_PATTERN.search(line)
            if current_match and int(current_match.group(1)) != active_number:
                errors.append(f"{relative}:{line_number} names milestone {current_match.group(1)} as current; registry selects {active_number}")
            for pattern in PROSE_STATUS_PATTERNS:
                prose = pattern.search(line)
                if not prose:
                    continue
                number, status = int(prose.group(1)), prose.group(2).title()
                if number in expected_status and status != expected_status[number]:
                    errors.append(f"{relative}:{line_number} conflicts for milestone {number}: {status} != {expected_status[number]}")
    return errors


def validate_git_history(
    data: dict[str, Any],
    repo_root: Path,
    registry: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    registry = registry or repo_root / "docs" / "MILESTONE_STATE.json"
    try:
        registry_relative = registry.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return ["milestone registry must be inside the repository for Git-history validation"]
    for milestone in data.get("milestones", []):
        if not isinstance(milestone, dict):
            continue
        commit_messages: dict[str, str] = {}
        for commit in milestone.get("merge_commits", []):
            if not isinstance(commit, str) or not SHA_PATTERN.fullmatch(commit):
                continue
            exists = subprocess.run(
                ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                cwd=repo_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if exists.returncode != 0:
                errors.append(f"milestone {milestone.get('number')!r} merge commit {commit} is absent from local Git history")
                continue
            ancestor = subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                cwd=repo_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if ancestor.returncode != 0:
                errors.append(f"milestone {milestone.get('number')!r} merge commit {commit} is not in current HEAD history")
                continue
            message = subprocess.run(
                ["git", "show", "-s", "--format=%B", commit],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )
            if message.returncode == 0:
                commit_messages[commit] = message.stdout
        number = milestone.get("number")
        governance_start = data.get("governance_effective_milestone")
        if (
            milestone.get("status") == "Complete"
            and _positive_int(number)
            and _positive_int(governance_start)
            and number >= governance_start
        ):
            implementation_prs = milestone.get("implementation_prs")
            closeout_commit = milestone.get("closeout_merge_commit")
            if isinstance(implementation_prs, list):
                implementation_commits = set(commit_messages)
                if isinstance(closeout_commit, str):
                    implementation_commits.discard(closeout_commit)
                implementation_mapping, missing_prs = implementation_pr_merge_mapping(
                    implementation_prs,
                    commit_messages,
                    allowed_commits=implementation_commits,
                )
                for implementation_pr in missing_prs:
                    errors.append(
                        f"post-governance milestone {number!r} has no recorded merge commit associated "
                        f"with implementation PR #{implementation_pr} by its Git commit subject"
                    )
                if implementation_mapping is None and not missing_prs:
                    errors.append(
                        f"post-governance milestone {number!r} implementation PRs do not have a one-to-one "
                        "mapping to distinct recorded merge commits"
                    )
            closeout_pr = milestone.get("closeout_pr")
            if isinstance(closeout_commit, str) and SHA_PATTERN.fullmatch(closeout_commit) and _positive_int(closeout_pr):
                closeout_message = commit_messages.get(closeout_commit, "")
                if not commit_message_matches_pr(closeout_message, closeout_pr):
                    errors.append(
                        f"post-governance milestone {number!r} closeout merge commit is not associated "
                        f"with closeout PR #{closeout_pr} by its Git commit subject"
                    )
                registry_blob = subprocess.run(
                    ["git", "show", f"{closeout_commit}:{registry_relative}"],
                    cwd=repo_root,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if registry_blob.returncode != 0:
                    errors.append(
                        f"post-governance milestone {number!r} closeout merge commit does not contain "
                        f"{registry_relative}"
                    )
                    continue
                try:
                    closeout_data = json.loads(registry_blob.stdout)
                except json.JSONDecodeError:
                    errors.append(
                        f"post-governance milestone {number!r} closeout merge commit contains a malformed registry"
                    )
                    continue
                if not isinstance(closeout_data, dict):
                    errors.append(
                        f"post-governance milestone {number!r} closeout merge commit registry must be an object"
                    )
                    continue
                closeout_errors = validate_registry_data(closeout_data)
                errors.extend(
                    f"post-governance milestone {number!r} closeout merge commit registry: {error}"
                    for error in closeout_errors
                )
                closeout_milestone = next(
                    (
                        item
                        for item in closeout_data.get("milestones", [])
                        if isinstance(item, dict) and item.get("number") == number
                    ),
                    None,
                )
                if closeout_milestone is None:
                    errors.append(
                        f"post-governance milestone {number!r} is absent from the closeout merge commit registry"
                    )
                    continue
                closeout_lane = closeout_data.get("product_lane")
                if (
                    closeout_milestone.get("status") != "Active"
                    or not isinstance(closeout_lane, dict)
                    or closeout_lane.get("paused") is not False
                    or closeout_lane.get("active_milestone") != number
                ):
                    errors.append(
                        f"post-governance milestone {number!r} must remain the sole Active milestone "
                        "in the closeout merge commit registry"
                    )
                finalization_fields = {"status", "merge_commits", "closeout_merge_commit", "decisions"}
                reviewed_fields = (set(closeout_milestone) | set(milestone)) - finalization_fields
                for field in sorted(reviewed_fields):
                    if closeout_milestone.get(field) != milestone.get(field):
                        errors.append(
                            f"post-governance milestone {number!r} field {field!r} differs from "
                            "the reviewed closeout merge commit registry"
                        )
                if closeout_milestone.get("closeout_merge_commit") is not None:
                    errors.append(
                        f"post-governance milestone {number!r} closeout merge commit registry must not "
                        "predeclare its future closeout merge SHA"
                    )
                reviewed_merges = closeout_milestone.get("merge_commits")
                if isinstance(implementation_prs, list) and isinstance(reviewed_merges, list):
                    reviewed_mapping, missing_reviewed_prs = implementation_pr_merge_mapping(
                        implementation_prs,
                        commit_messages,
                        allowed_commits=reviewed_merges,
                    )
                    for implementation_pr in missing_reviewed_prs:
                        errors.append(
                            f"post-governance milestone {number!r} closeout merge commit registry "
                            f"does not record implementation PR #{implementation_pr} merge evidence"
                        )
                    if reviewed_mapping is None and not missing_reviewed_prs:
                        errors.append(
                            f"post-governance milestone {number!r} closeout merge commit registry does not "
                            "map implementation PRs one-to-one to distinct merge evidence"
                        )
                final_merges = milestone.get("merge_commits")
                if isinstance(reviewed_merges, list) and isinstance(final_merges, list):
                    if set(final_merges) != {*reviewed_merges, closeout_commit}:
                        errors.append(
                            f"post-governance milestone {number!r} state finalization may add only the "
                            "closeout merge commit to the reviewed merge evidence"
                        )
                reviewed_decisions = closeout_milestone.get("decisions")
                final_decisions = milestone.get("decisions")
                if isinstance(reviewed_decisions, list) and isinstance(final_decisions, list):
                    missing_reviewed_decisions = set(reviewed_decisions) - set(final_decisions)
                    if missing_reviewed_decisions:
                        errors.append(
                            f"post-governance milestone {number!r} state finalization removed a reviewed "
                            "closeout decision"
                        )
                    added_decisions = set(final_decisions) - set(reviewed_decisions)
                    required_fragments = ("closeout", f"#{closeout_pr}", closeout_commit)
                    if any(
                        not all(fragment.casefold() in decision.casefold() for fragment in required_fragments)
                        for decision in added_decisions
                    ):
                        errors.append(
                            f"post-governance milestone {number!r} state finalization may add only a "
                            "closeout PR and merge-commit linkage decision"
                        )
    return errors


def validate_sequence_history(data: dict[str, Any], registry: Path, repo_root: Path) -> list[str]:
    """Validate the branch-wide registry transition against its merge base."""

    try:
        relative = registry.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return ["milestone registry must be inside the repository for sequence-history validation"]
    head_blob = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if head_blob.returncode == 0:
        try:
            head_data = json.loads(head_blob.stdout)
        except json.JSONDecodeError:
            return ["milestone registry at HEAD is malformed"]
        if head_data != data:
            return validate_sequence_transition(data, head_data)

    merge_base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    previous_spec: str | None = None
    if merge_base.returncode == 0 and merge_base.stdout.strip():
        base = merge_base.stdout.strip()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        if base != head:
            previous_spec = f"{base}:{relative}"
    if previous_spec is None:
        latest = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", relative],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if latest.returncode != 0 or not latest.stdout.strip():
            return []
        previous_spec = f"{latest.stdout.strip()}^:{relative}"
    previous = subprocess.run(
        ["git", "show", previous_spec],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if previous.returncode != 0:
        return []
    try:
        previous_data = json.loads(previous.stdout)
    except json.JSONDecodeError:
        return [f"prior milestone registry at {previous_spec} is malformed"]
    return validate_sequence_transition(data, previous_data)


def validate_registry(path: Path, repo_root: Path, *, check_git_history: bool = True) -> dict[str, Any]:
    data = load_registry(path)
    errors = validate_registry_data(data)
    errors.extend(validate_derived_documents(data, repo_root))
    if check_git_history:
        errors.extend(validate_git_history(data, repo_root, path))
        errors.extend(validate_sequence_history(data, path, repo_root))
    if errors:
        raise MilestoneValidationError(errors)
    return data


def main(argv: list[str] | None = None) -> int:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--skip-git-history", action="store_true", help="test-only: skip local Git ancestry checks")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    registry = (args.registry or repo_root / "docs" / "MILESTONE_STATE.json").resolve()
    try:
        data = validate_registry(registry, repo_root, check_git_history=not args.skip_git_history)
    except MilestoneValidationError as exc:
        print("Milestone governance validation failed:", file=sys.stderr)
        for error in exc.errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    active = data["product_lane"]["active_milestone"]
    lane = "paused" if data["product_lane"]["paused"] else f"Active milestone {active}"
    print(f"Validated {len(data['milestones'])} FXD milestones; product lane: {lane}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
