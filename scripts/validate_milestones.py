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
        merges = milestone.get("merge_commits")
        if not isinstance(merges, list) or any(not isinstance(commit, str) or not SHA_PATTERN.fullmatch(commit) for commit in merges):
            errors.append(f"milestone {number!r} merge_commits must contain lowercase 40-character SHAs")
        selected_profiles = milestone.get("evidence_profiles")
        if not isinstance(selected_profiles, list) or not selected_profiles:
            errors.append(f"milestone {number!r} must select at least one evidence profile")
        elif any(profile not in allowed_profiles for profile in selected_profiles):
            errors.append(f"milestone {number!r} selects an unknown evidence profile")

        decisions = milestone.get("decisions")
        if not isinstance(decisions, list) or any(not isinstance(decision, str) or not decision.strip() for decision in decisions):
            errors.append(f"milestone {number!r} decisions must be an array of nonempty strings")

        if status == "Active":
            if not _positive_int(issue):
                errors.append(f"Active milestone {number!r} requires an authoritative issue")
            if not isinstance(prs, list) or not prs:
                errors.append(f"Active milestone {number!r} requires an implementation PR")
        if status == "Complete":
            if not isinstance(merges, list) or not merges:
                errors.append(f"Complete milestone {number!r} requires merged evidence")
            evidence = milestone.get("completion_evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                errors.append(f"Complete milestone {number!r} requires completion_evidence")
            if milestone.get("legacy"):
                if milestone.get("legacy_reconciliation") is not True:
                    errors.append(f"legacy Complete milestone {number!r} requires explicit legacy_reconciliation")
                if not _nonempty_strings(milestone.get("historical_gaps")):
                    errors.append(f"legacy Complete milestone {number!r} requires historical_gaps")
            elif _positive_int(governance_start) and number >= governance_start:
                closeout_pr = milestone.get("closeout_pr")
                if not _positive_int(closeout_pr):
                    errors.append(f"post-governance Complete milestone {number!r} requires a separate closeout PR")
                elif isinstance(prs, list) and closeout_pr in prs:
                    errors.append(f"post-governance Complete milestone {number!r} closeout PR must be distinct from implementation PRs")
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
                elif current_heading in expected_status and raw_status in LEGAL_STATUSES and raw_status != expected_status[current_heading]:
                    errors.append(
                        f"{relative}:{line_number} conflicts for milestone {current_heading}: {raw_status} != {expected_status[current_heading]}"
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


def validate_git_history(data: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    for milestone in data.get("milestones", []):
        if not isinstance(milestone, dict):
            continue
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
    return errors


def validate_registry(path: Path, repo_root: Path, *, check_git_history: bool = True) -> dict[str, Any]:
    data = load_registry(path)
    errors = validate_registry_data(data)
    errors.extend(validate_derived_documents(data, repo_root))
    if check_git_history:
        errors.extend(validate_git_history(data, repo_root))
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
