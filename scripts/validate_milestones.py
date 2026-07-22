"""Offline validation for the authoritative FXD milestone registry."""

from __future__ import annotations

import argparse
import copy
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
CLOSED_SEQUENCE_STATUSES = {"Complete", "Superseded", "Cancelled"}
REOPENED_SEQUENCE_STATUSES = {"Planned", "Active", "Blocked", "Waiting", "Paused"}
REOPENING_HISTORY_FIELDS = (
    "implementation_prs",
    "merge_commits",
    "evidence_profiles",
    "evidence_results",
    "completion_evidence",
    "closeout_pr",
    "closeout_merge_commit",
    "state_finalization_pr",
    "decisions",
    "replacement_milestone",
    "legacy",
    "legacy_reconciliation",
    "historical_gaps",
)
FINALIZATION_REGISTRY_PATH = "docs/MILESTONE_STATE.json"
FINALIZATION_DERIVED_STATUS_PATHS = (
    "README.md",
    "BACKLOG.md",
    "docs/ROADMAP_QUEUE.md",
    "docs/STRATEGY_HANDOFF.md",
    "docs/LOCAL_ENGINEERING_WORKBENCH.md",
    "docs/project-records/README.md",
)
AUTHORITY_MARKER = "<!-- FXD-MILESTONE-STATE: docs/MILESTONE_STATE.json -->"
HISTORICAL_MARKER = "<!-- FXD-HISTORICAL-MILESTONE-SNAPSHOT -->"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+Milestone\s+(\d+)\b", re.IGNORECASE)
STATUS_PATTERN = re.compile(r"(?:\*\*Status:\*\*|\bStatus:)\s*([^\r\n]+)", re.IGNORECASE)
MILESTONE_STATUS_PATTERN = re.compile(
    r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:Milestone|M)\s*(\d+)\s*:\s*([^\r\n]+)",
    re.IGNORECASE,
)
CURRENT_PATTERN = re.compile(r"\bcurrent\s+(?:product\s+)?milestone\s*(?::|is)?\s*(?:Milestone|M)?\s*(\d+)\b", re.IGNORECASE)
CURRENT_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+Current\s+(?:product\s+)?milestone\b", re.IGNORECASE)
ANY_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+")
MILESTONE_REFERENCE_PATTERN = re.compile(r"\b(?:Milestone|M)\s*(\d+)\b", re.IGNORECASE)
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


def _retains_completed_state_evidence(milestone: dict[str, Any]) -> bool:
    """Recognize a non-Complete record that preserves its earlier completion history."""

    closeout_pr = milestone.get("closeout_pr")
    closeout_commit = milestone.get("closeout_merge_commit")
    merges = milestone.get("merge_commits")
    selected_profiles = milestone.get("evidence_profiles")
    evidence_results = milestone.get("evidence_results")
    decisions = milestone.get("decisions")
    return (
        _positive_int(milestone.get("state_finalization_pr"))
        and _positive_int(closeout_pr)
        and isinstance(closeout_commit, str)
        and bool(SHA_PATTERN.fullmatch(closeout_commit))
        and isinstance(merges, list)
        and closeout_commit in merges
        and isinstance(milestone.get("completion_evidence"), str)
        and bool(milestone.get("completion_evidence", "").strip())
        and isinstance(selected_profiles, list)
        and all(isinstance(profile, str) for profile in selected_profiles)
        and isinstance(evidence_results, dict)
        and set(selected_profiles).issubset(evidence_results)
        and isinstance(decisions, list)
        and any(
            "closeout" in decision.casefold()
            and f"#{closeout_pr}" in decision
            and closeout_commit in decision
            for decision in decisions
            if isinstance(decision, str)
        )
    )


def _sequence_projection(data: dict[str, Any]) -> dict[str, Any]:
    """Return only fields whose change alters the governed product sequence."""

    lane = data.get("product_lane") if isinstance(data.get("product_lane"), dict) else {}
    milestones = data.get("milestones") if isinstance(data.get("milestones"), list) else []
    return {
        "governance_effective_milestone": data.get("governance_effective_milestone"),
        "product_lane": {
            "paused": lane.get("paused"),
            "active_milestone": lane.get("active_milestone"),
            "pause_reason": lane.get("pause_reason"),
            "decision": lane.get("decision"),
        },
        "milestones": [
            {
                "number": milestone.get("number"),
                "sequence_position": milestone.get("sequence_position"),
                "predecessor": milestone.get("predecessor"),
                "sequence_status": milestone.get("status"),
                "replacement_milestone": milestone.get("replacement_milestone"),
            }
            for milestone in milestones
            if isinstance(milestone, dict)
        ],
    }


def _validate_retained_finalization_transition(current: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    """Allow finalization evidence on non-Complete work only as preserved reopening history."""

    previous_milestones = {
        milestone.get("number"): milestone
        for milestone in previous.get("milestones", [])
        if isinstance(milestone, dict) and _positive_int(milestone.get("number"))
    }
    errors: list[str] = []
    for milestone in current.get("milestones", []):
        if not isinstance(milestone, dict) or milestone.get("status") == "Complete":
            continue
        finalization_pr = milestone.get("state_finalization_pr")
        if finalization_pr is None:
            continue
        prior = previous_milestones.get(milestone.get("number"))
        if not isinstance(prior, dict) or (
            prior.get("status") not in CLOSED_SEQUENCE_STATUSES
            and prior.get("state_finalization_pr") != finalization_pr
        ):
            errors.append(
                f"non-Complete milestone {milestone.get('number')!r} may retain state-finalization PR evidence "
                "only when reopening a previously closed registry record"
            )
    return errors


def validate_sequence_transition(current: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    """Require one new revision and newly approving decisions for a sequence change."""

    retention_errors = _validate_retained_finalization_transition(current, previous)
    if _sequence_projection(current) == _sequence_projection(previous):
        return retention_errors
    current_revision = current.get("sequence_revision")
    previous_revision = previous.get("sequence_revision")
    errors: list[str] = list(retention_errors)
    if not _positive_int(previous_revision) or current_revision != previous_revision + 1:
        errors.append("sequence changes require sequence_revision to increment exactly once from the prior registry")
    previous_decisions = previous.get("sequence_decisions", [])
    current_decisions = current.get("sequence_decisions")
    additions: list[str] = []
    if not isinstance(previous_decisions, list) or any(
        not isinstance(decision, str) or not decision.strip() for decision in previous_decisions
    ):
        errors.append("the prior registry has invalid sequence_decisions")
        previous_decisions = []
    if not _nonempty_strings(current_decisions):
        errors.append("sequence changes require nonempty sequence_decisions")
    else:
        additions = current_decisions[len(previous_decisions) :]
        if current_decisions[: len(previous_decisions)] != previous_decisions:
            errors.append("sequence changes must preserve prior sequence_decisions in their existing order")
        if len(current_decisions) != len(set(current_decisions)):
            errors.append("sequence changes cannot reorder, duplicate, or reuse sequence_decisions")
        if not additions or not any(
            re.search(r"\b(?:approved|approves|authorized|authorizes)\b", decision, re.IGNORECASE)
            and re.search(r"#\d+\b", decision)
            for decision in additions
        ):
            errors.append("sequence changes require at least one newly added approving sequence decision")

    previous_milestones = {
        milestone.get("number"): milestone
        for milestone in previous.get("milestones", [])
        if isinstance(milestone, dict) and _positive_int(milestone.get("number"))
    }
    for milestone in current.get("milestones", []):
        if not isinstance(milestone, dict) or not _positive_int(milestone.get("number")):
            continue
        number = milestone["number"]
        prior = previous_milestones.get(number)
        if not isinstance(prior, dict):
            continue
        if prior.get("status") not in CLOSED_SEQUENCE_STATUSES or milestone.get("status") not in REOPENED_SEQUENCE_STATUSES:
            continue
        decision_pattern = re.compile(rf"\b(?:Milestone\s*{number}|M{number})\b", re.IGNORECASE)
        if not any(
            decision_pattern.search(decision)
            and re.search(r"\b(?:reopen(?:ed|ing|s)?|reactivat(?:e|ed|es|ing))\b", decision, re.IGNORECASE)
            and re.search(r"\b(?:approved|approves|authorized|authorizes)\b", decision, re.IGNORECASE)
            and re.search(r"#\d+\b", decision)
            for decision in additions
        ):
            errors.append(
                f"reopening milestone {number} from {prior.get('status')} to {milestone.get('status')} requires "
                "a newly added approving sequence decision identifying the milestone and authority"
            )
        for field in REOPENING_HISTORY_FIELDS:
            if milestone.get(field) != prior.get(field):
                errors.append(
                    f"reopening milestone {number} must preserve prior completion and closeout history field {field}"
                )
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


def _milestone_by_number(data: dict[str, Any], number: int) -> dict[str, Any] | None:
    return next(
        (
            milestone
            for milestone in data.get("milestones", [])
            if isinstance(milestone, dict) and milestone.get("number") == number
        ),
        None,
    )


def _structured_differences(expected: Any, actual: Any, path: str = "") -> list[tuple[str, Any, Any]]:
    """Return deterministic JSON-value differences with reviewable field paths."""

    if type(expected) is not type(actual):
        return [(path or "<root>", expected, actual)]
    if isinstance(expected, dict):
        differences: list[tuple[str, Any, Any]] = []
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}" if path else key
            if key not in expected:
                differences.append((child, "<absent>", actual[key]))
            elif key not in actual:
                differences.append((child, expected[key], "<absent>"))
            else:
                differences.extend(_structured_differences(expected[key], actual[key], child))
        return differences
    if isinstance(expected, list):
        differences = []
        common = min(len(expected), len(actual))
        for index in range(common):
            differences.extend(_structured_differences(expected[index], actual[index], f"{path}[{index}]"))
        for index in range(common, max(len(expected), len(actual))):
            expected_value = expected[index] if index < len(expected) else "<absent>"
            actual_value = actual[index] if index < len(actual) else "<absent>"
            differences.append((f"{path}[{index}]", expected_value, actual_value))
        return differences
    return [] if expected == actual else [(path or "<root>", expected, actual)]


def validate_state_finalization_delta(
    current: dict[str, Any],
    closeout: dict[str, Any],
    milestone_number: int,
) -> list[str]:
    """Allow only the contract-authorized third-stage registry transition."""

    prefix = f"post-governance milestone {milestone_number!r} state-finalization"
    errors: list[str] = []
    reviewed_milestone = _milestone_by_number(closeout, milestone_number)
    final_milestone = _milestone_by_number(current, milestone_number)
    if reviewed_milestone is None or final_milestone is None:
        return [f"{prefix} requires the milestone in both closeout and final registries"]

    finalization_pr = final_milestone.get("state_finalization_pr")
    closeout_pr = final_milestone.get("closeout_pr")
    implementation_prs = final_milestone.get("implementation_prs")
    if reviewed_milestone.get("state_finalization_pr") is not None:
        errors.append(f"{prefix} closeout snapshot must not predeclare a state-finalization PR")
    if not _positive_int(finalization_pr):
        errors.append(f"{prefix} requires a distinct state-finalization PR")
    elif finalization_pr == closeout_pr or (
        isinstance(implementation_prs, list) and finalization_pr in implementation_prs
    ):
        errors.append(
            f"{prefix} PR #{finalization_pr} must be distinct from every implementation and closeout PR"
        )

    closeout_commit = final_milestone.get("closeout_merge_commit")
    reviewed_merges = reviewed_milestone.get("merge_commits")
    final_merges = final_milestone.get("merge_commits")
    if not isinstance(reviewed_merges, list) or not isinstance(final_merges, list) or final_merges != [
        *reviewed_merges,
        closeout_commit,
    ]:
        errors.append(f"{prefix} may append only the closeout merge commit to reviewed merge evidence")

    reviewed_decisions = reviewed_milestone.get("decisions")
    final_decisions = final_milestone.get("decisions")
    linkage_decision: str | None = None
    if not isinstance(reviewed_decisions, list) or not isinstance(final_decisions, list):
        errors.append(f"{prefix} requires preserved milestone decisions")
    elif final_decisions[: len(reviewed_decisions)] != reviewed_decisions or len(final_decisions) != len(
        reviewed_decisions
    ) + 1:
        errors.append(f"{prefix} may add exactly one closeout PR/SHA linkage decision")
    else:
        linkage_decision = final_decisions[-1]
        fragments = ("closeout", f"#{closeout_pr}", str(closeout_commit))
        if not isinstance(linkage_decision, str) or not all(
            fragment.casefold() in linkage_decision.casefold() for fragment in fragments
        ):
            errors.append(f"{prefix} linkage decision must identify the closeout PR and merge commit")

    errors.extend(f"{prefix}: {error}" for error in validate_sequence_transition(current, closeout))

    expected = copy.deepcopy(closeout)
    expected["sequence_revision"] = current.get("sequence_revision")
    expected["sequence_decisions"] = current.get("sequence_decisions")

    reviewed_lane = closeout.get("product_lane")
    if not isinstance(reviewed_lane, dict):
        errors.append(f"{prefix} closeout snapshot has no valid product lane")
    else:
        disposition = reviewed_lane.get("after_milestone_32_closeout") if milestone_number == 32 else None
        if not isinstance(disposition, dict):
            errors.append(f"{prefix} has no pre-approved post-closeout product-lane disposition")
        else:
            expected_lane = copy.deepcopy(reviewed_lane)
            expected_lane.update(
                {
                    "paused": disposition.get("paused"),
                    "active_milestone": disposition.get("active_milestone"),
                    "pause_reason": disposition.get("reason"),
                    "decision": disposition.get("decision"),
                }
            )
            expected["product_lane"] = expected_lane

    expected_milestone = _milestone_by_number(expected, milestone_number)
    if expected_milestone is not None:
        expected_milestone.update(
            {
                "status": "Complete",
                "merge_commits": final_merges,
                "closeout_merge_commit": closeout_commit,
                "state_finalization_pr": finalization_pr,
                "decisions": final_decisions,
            }
        )

    for path, expected_value, actual_value in _structured_differences(expected, current):
        errors.append(
            f"{prefix} PR #{finalization_pr} contains unauthorized registry change at {path}: "
            f"expected {expected_value!r}, got {actual_value!r}"
        )
    return errors


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
            if "state_finalization_pr" not in milestone:
                errors.append(f"post-governance milestone {number!r} requires a state_finalization_pr field")
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

        state_finalization_pr = milestone.get("state_finalization_pr")
        if state_finalization_pr is not None and not _positive_int(state_finalization_pr):
            errors.append(f"milestone {number!r} state_finalization_pr must be null or a positive integer")
        if (
            post_governance
            and status != "Complete"
            and state_finalization_pr is not None
            and not _retains_completed_state_evidence(milestone)
        ):
            errors.append(
                f"post-governance milestone {number!r} cannot predeclare a future state-finalization PR or "
                "discard the completed record that PR previously finalized"
            )

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
                if not _positive_int(state_finalization_pr):
                    errors.append(
                        f"post-governance Complete milestone {number!r} requires a distinct state-finalization PR"
                    )
                elif state_finalization_pr == closeout_pr or (
                    isinstance(prs, list) and state_finalization_pr in prs
                ):
                    errors.append(
                        f"post-governance Complete milestone {number!r} state-finalization PR must be distinct "
                        "from implementation and closeout PRs"
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


def _validate_status_claim(
    *,
    relative: str,
    line_number: int,
    milestone_number: int | None,
    raw_claim: str,
    expected_status: dict[int, str],
) -> list[str]:
    """Validate one current-status claim while permitting explanatory prose after it."""

    raw = raw_claim.strip().strip("*` .")
    illegal = ILLEGAL_STATUS_PATTERN.search(raw)
    if illegal:
        return [f"{relative}:{line_number} uses non-authoritative status {illegal.group(1)!r}"]
    status_match = re.match(
        r"(Planned|Active|Blocked|Waiting|Paused|Complete|Superseded|Cancelled)\b",
        raw,
        re.IGNORECASE,
    )
    claimed = status_match.group(1) if status_match else next(iter(raw.split()), raw)
    canonical = next((status for status in LEGAL_STATUSES if status.casefold() == claimed.casefold()), None)
    if canonical is None or canonical != claimed:
        return [f"{relative}:{line_number} uses unrecognized or noncanonical status {claimed!r}"]
    if milestone_number in expected_status and canonical != expected_status[milestone_number]:
        return [
            f"{relative}:{line_number} conflicts for milestone {milestone_number}: "
            f"{canonical} != {expected_status[milestone_number]}"
        ]
    return []


def _validate_current_milestone_claim(
    *, relative: str, line_number: int, claimed: int, active_number: Any, paused: Any
) -> list[str]:
    if paused is True:
        return [
            f"{relative}:{line_number} names milestone {claimed} as current; registry product lane is formally paused"
        ]
    if claimed != active_number:
        return [f"{relative}:{line_number} names milestone {claimed} as current; registry selects {active_number}"]
    return []


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
    lane = data.get("product_lane") if isinstance(data.get("product_lane"), dict) else {}
    active_number = lane.get("active_milestone")
    lane_paused = lane.get("paused")

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
        current_section_level: int | None = None
        for line_number, line in enumerate(text.splitlines(), start=1):
            any_heading = ANY_HEADING_PATTERN.match(line)
            current_section = CURRENT_HEADING_PATTERN.match(line)
            if current_section:
                current_section_level = len(current_section.group(1))
            elif any_heading and current_section_level is not None and len(any_heading.group(1)) <= current_section_level:
                current_section_level = None
            heading = HEADING_PATTERN.match(line)
            if heading:
                current_heading = int(heading.group(1))
            status_match = STATUS_PATTERN.search(line)
            if status_match:
                errors.extend(
                    _validate_status_claim(
                        relative=relative,
                        line_number=line_number,
                        milestone_number=current_heading,
                        raw_claim=status_match.group(1),
                        expected_status=expected_status,
                    )
                )
            milestone_status = MILESTONE_STATUS_PATTERN.match(line)
            if milestone_status:
                errors.extend(
                    _validate_status_claim(
                        relative=relative,
                        line_number=line_number,
                        milestone_number=int(milestone_status.group(1)),
                        raw_claim=milestone_status.group(2),
                        expected_status=expected_status,
                    )
                )
            current_match = CURRENT_PATTERN.search(line)
            if current_match:
                errors.extend(
                    _validate_current_milestone_claim(
                        relative=relative,
                        line_number=line_number,
                        claimed=int(current_match.group(1)),
                        active_number=active_number,
                        paused=lane_paused,
                    )
                )
            elif current_section_level is not None and not current_section:
                section_milestone = MILESTONE_REFERENCE_PATTERN.search(line)
                if section_milestone:
                    errors.extend(
                        _validate_current_milestone_claim(
                            relative=relative,
                            line_number=line_number,
                            claimed=int(section_milestone.group(1)),
                            active_number=active_number,
                            paused=lane_paused,
                        )
                    )
                    current_section_level = None
            for pattern in PROSE_STATUS_PATTERNS:
                prose = pattern.search(line)
                if not prose:
                    continue
                number, status = int(prose.group(1)), prose.group(2).title()
                if number in expected_status and status != expected_status[number]:
                    errors.append(f"{relative}:{line_number} conflicts for milestone {number}: {status} != {expected_status[number]}")
    return errors


def _registry_at_revision(repo_root: Path, revision: str, registry_relative: str) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{registry_relative}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _git_blob(repo_root: Path, revision: str, relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _git_tree_mode(repo_root: Path, revision: str, relative: str) -> str | None:
    result = subprocess.run(
        ["git", "ls-tree", "-z", revision, "--", relative],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    metadata = result.stdout.split(b"\t", 1)[0].decode("ascii", errors="replace")
    return metadata.split(" ", 1)[0] if " " in metadata else None


def _finalization_projection_signature(line: str) -> tuple[str, str, str] | None:
    """Return a stable signature only for an exact current-status projection line."""

    statuses = "|".join(sorted(LEGAL_STATUSES, key=len, reverse=True))
    patterns = (
        (
            "status",
            re.compile(
                rf"^(\s*(?:[-*+]\s+)?(?:\*\*)?Status:(?:\*\*)?\s*)({statuses})(\b.*)$"
            ),
        ),
        (
            "milestone-status",
            re.compile(
                rf"^(\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:Milestone|M)\s*\d+\s*:\s*)"
                rf"({statuses})(\b.*)$"
            ),
        ),
        (
            "milestone-prose",
            re.compile(
                rf"^(.*\b(?:Milestone|M)\s*\d+\b\s+(?:is|remains|has status)\s+"
                rf"(?:the\s+sole\s+)?)(?:({statuses}))(\b.*)$",
                re.IGNORECASE,
            ),
        ),
    )
    for category, pattern in patterns:
        match = pattern.fullmatch(line)
        if match:
            return category, match.group(1), match.group(3)

    lane = re.fullmatch(
        r"\s*(?:[-*+]\s+)?(?:Current (?:product )?milestone|Product lane)\s*(?::|is)\s*"
        r"(?:Milestone\s*\d+|M\s*\d+|Paused|None)\s*[.;]?\s*",
        line,
        re.IGNORECASE,
    )
    current_section_milestone = re.fullmatch(
        r"\s*(?:Milestone|M)\s*\d+\s*(?:-|—|:)\s*[^\r\n]+",
        line,
        re.IGNORECASE,
    )
    return ("lane-projection", "", "") if lane or current_section_milestone else None


def _line_is_in_current_milestone_section(lines: list[str], index: int) -> bool:
    for previous in range(index - 1, -1, -1):
        if not lines[previous].strip():
            continue
        return CURRENT_HEADING_PATTERN.fullmatch(lines[previous]) is not None
    return False


def _validate_derived_finalization_content(
    repo_root: Path,
    closeout_commit: str,
    finalization_commit: str,
    relative: str,
) -> list[str]:
    """Allow only in-place edits of exact current-status projection lines."""

    before_blob = _git_blob(repo_root, closeout_commit, relative)
    after_blob = _git_blob(repo_root, finalization_commit, relative)
    if before_blob is None or after_blob is None:
        return [f"state-finalization derived document {relative} must exist before and after finalization"]
    if b"\x00" in before_blob or b"\x00" in after_blob:
        return [f"state-finalization derived document {relative} cannot contain binary changes"]
    try:
        before = before_blob.decode("utf-8").splitlines()
        after = after_blob.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return [f"state-finalization derived document {relative} must remain UTF-8 text"]
    if len(before) != len(after):
        return [
            f"state-finalization derived document {relative} may reconcile status in place but cannot add or remove lines"
        ]

    errors: list[str] = []
    for line_number, (reviewed_line, final_line) in enumerate(zip(before, after), start=1):
        if reviewed_line == final_line:
            continue
        reviewed_signature = _finalization_projection_signature(reviewed_line)
        final_signature = _finalization_projection_signature(final_line)
        signatures_match = reviewed_signature is not None and reviewed_signature == final_signature
        if signatures_match and reviewed_signature[0] == "lane-projection":
            inline_projection = bool(
                re.match(r"\s*(?:[-*+]\s+)?(?:Current (?:product )?milestone|Product lane)\b", reviewed_line, re.IGNORECASE)
                and re.match(r"\s*(?:[-*+]\s+)?(?:Current (?:product )?milestone|Product lane)\b", final_line, re.IGNORECASE)
            )
            signatures_match = inline_projection or (
                _line_is_in_current_milestone_section(before, line_number - 1)
                and _line_is_in_current_milestone_section(after, line_number - 1)
            )
        if not signatures_match:
            errors.append(
                f"state-finalization derived document {relative}:{line_number} contains unrelated "
                "derived-document content; only the existing current-status projection token may change"
            )
    return errors


def _validate_state_finalization_tree_delta(
    *,
    repo_root: Path,
    closeout_commit: str,
    finalization_commit: str,
    registry_relative: str,
) -> list[str]:
    """Reject every finalization pull-head tree delta outside the narrow contract allowlist."""

    allowed_registry = registry_relative == FINALIZATION_REGISTRY_PATH
    allowed_paths = {
        registry_relative,
        *(FINALIZATION_DERIVED_STATUS_PATHS if allowed_registry else ()),
    }
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            closeout_commit,
            finalization_commit,
            "--",
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ["state-finalization pull-head tree could not be compared with the reviewed closeout tree"]
    parts = result.stdout.split(b"\x00")
    if parts and parts[-1] == b"":
        parts.pop()
    if len(parts) % 2:
        return ["state-finalization pull-head tree produced malformed path evidence"]

    errors: list[str] = []
    for index in range(0, len(parts), 2):
        try:
            status = parts[index].decode("ascii")
            relative = parts[index + 1].decode("utf-8")
        except UnicodeDecodeError:
            errors.append("state-finalization pull-head tree contains a non-UTF-8 path")
            continue
        if relative not in allowed_paths:
            errors.append(
                f"unauthorized finalization tree path {relative} has operation {status}; expected governance stage "
                f"permits only {registry_relative} and exact current-status reconciliation paths"
            )
            continue
        if status != "M":
            errors.append(
                f"unauthorized finalization tree operation {status} at {relative}; additions, deletions, and renames "
                "are prohibited during state finalization"
            )
            continue
        reviewed_mode = _git_tree_mode(repo_root, closeout_commit, relative)
        final_mode = _git_tree_mode(repo_root, finalization_commit, relative)
        if reviewed_mode != "100644" or final_mode != reviewed_mode:
            errors.append(
                f"unauthorized finalization tree mode change at {relative}: "
                f"expected regular file mode 100644, got {reviewed_mode!r} -> {final_mode!r}"
            )
            continue
        if relative != registry_relative:
            errors.extend(
                _validate_derived_finalization_content(
                    repo_root,
                    closeout_commit,
                    finalization_commit,
                    relative,
                )
            )
    return errors


def _state_finalization_registry_evidence(
    *,
    current: dict[str, Any],
    repo_root: Path,
    registry_relative: str,
    state_finalization_pr: int,
    closeout_commit: str,
    reserved_commits: set[str],
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    """Find the exact declared GitHub pull-head ref that carried finalization."""

    if _registry_at_revision(repo_root, "HEAD", registry_relative) != current:
        return None, None, []
    if not _is_ancestor(repo_root, closeout_commit, "HEAD"):
        return None, None, []

    pull_ref = f"refs/pull/{state_finalization_pr}/head"
    symbolic = subprocess.run(
        ["git", "symbolic-ref", "-q", pull_ref],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if symbolic.returncode == 0:
        return None, None, [f"state-finalization PR #{state_finalization_pr} exact pull-head ref is symbolic"]
    target = subprocess.run(
        ["git", "show-ref", "--verify", "--hash", pull_ref],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    commit = target.stdout.strip()
    if target.returncode != 0 or not commit:
        return None, None, []
    object_type = subprocess.run(
        ["git", "cat-file", "-t", commit],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if object_type.returncode != 0 or object_type.stdout.strip() != "commit":
        return None, None, [f"state-finalization PR #{state_finalization_pr} exact pull-head ref must target a commit"]
    if commit in reserved_commits or not _is_ancestor(repo_root, closeout_commit, commit):
        return None, None, []
    pull_data = _registry_at_revision(repo_root, commit, registry_relative)
    if pull_data != current:
        return None, None, []
    tree_errors = _validate_state_finalization_tree_delta(
        repo_root=repo_root,
        closeout_commit=closeout_commit,
        finalization_commit=commit,
        registry_relative=registry_relative,
    )
    return pull_data, f"{pull_ref} at {commit}", tree_errors


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
                state_finalization_pr = milestone.get("state_finalization_pr")
                if _positive_int(state_finalization_pr):
                    finalization_data, evidence, tree_errors = _state_finalization_registry_evidence(
                        current=data,
                        repo_root=repo_root,
                        registry_relative=registry_relative,
                        state_finalization_pr=state_finalization_pr,
                        closeout_commit=closeout_commit,
                        reserved_commits=set(milestone.get("merge_commits", [])),
                    )
                    if finalization_data is None:
                        errors.extend(tree_errors)
                        errors.append(
                            f"post-governance milestone {number!r} expected state-finalization PR "
                            f"#{state_finalization_pr} evidence, but no matching local pull-head ref exists; "
                            "the exact dedicated pull-head ref "
                            f"refs/pull/{state_finalization_pr}/head must carry the finalization registry in current "
                            "HEAD history"
                        )
                    else:
                        errors.extend(
                            f"post-governance milestone {number!r} state-finalization PR #{state_finalization_pr}: "
                            f"{error}"
                            for error in tree_errors
                        )
                        errors.extend(validate_state_finalization_delta(finalization_data, closeout_data, number))
                        if evidence is None:
                            errors.append(
                                f"post-governance milestone {number!r} state-finalization PR evidence is missing"
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
