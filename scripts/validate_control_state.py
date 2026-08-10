"""Deterministically validate the post-Issue-66 FXD control plane."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "fxd-control-state-v1"
LEGAL_STATES = {
    "PLANNED",
    "ACTIVE",
    "AWAITING_REVIEW",
    "REPAIR",
    "BLOCKED",
    "HELD",
    "COMPLETE",
    "SUPERSEDED",
    "CANCELLED",
}
KEY_CURRENT_DOCUMENTS = (
    "AGENTS.md",
    "CURRENT.md",
    "README.md",
    "docs/PRODUCT_DIRECTION.md",
    "docs/OPERATOR_PROTOCOL.md",
    "docs/ENGINEERING_CONSTITUTION.md",
    "docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md",
    "docs/ARCHITECTURE.md",
    "docs/MILESTONE_CONTRACT.md",
    "docs/ENGINEERING_TEAM.md",
    "docs/FOREMAN_SETUP.md",
    "docs/decisions/0001-ai-driven-fixture-synthesis-reset.md",
)
RESET_AUTHORITY_DOCUMENTS = {
    "AGENTS.md",
    "CURRENT.md",
    "README.md",
    "docs/PRODUCT_DIRECTION.md",
    "docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md",
    "docs/ARCHITECTURE.md",
    "docs/MILESTONE_CONTRACT.md",
    "docs/FOREMAN_SETUP.md",
    "docs/decisions/0001-ai-driven-fixture-synthesis-reset.md",
}
FORBIDDEN_CURRENT_CLAIMS = (
    "M32 is the sole Active",
    "Milestone 32 as the sole Active",
    "Issue #56 authorizes Milestone 32 as the sole Active",
    "PR #54 is the active implementation",
)
FROZEN_MILESTONE_REGISTRY_PATH = "docs/MILESTONE_STATE.json"
ACCEPTED_RESET_MERGE = "592876fefde118b5325bbb5b4949eeb1490cdf6c"


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()  # nosec B324 - Git object identity requires SHA-1


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot load {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path} root must be an object")
        return {}
    return data


def validate(repo_root: Path) -> list[str]:
    errors: list[str] = []
    state_path = repo_root / "docs" / "CONTROL_STATE.json"
    data = _load_json(state_path, errors)
    if not data:
        return errors

    if data.get("schema_version") != SCHEMA:
        errors.append(f"unsupported control-state schema: {data.get('schema_version')!r}")
    if not _positive_int(data.get("revision")):
        errors.append("control-state revision must be a positive integer")
    elif data.get("revision") != 3:
        errors.append(f"exact-head review control-state revision must be 3, got {data.get('revision')!r}")
    if data.get("state") not in LEGAL_STATES:
        errors.append(f"illegal control state: {data.get('state')!r}")
    if data.get("authority_issue") != 66:
        errors.append("Issue #66 must remain the accepted reset authority")

    accepted_reset = data.get("accepted_governance_reset")
    if not isinstance(accepted_reset, dict):
        errors.append("accepted_governance_reset must be an object")
        accepted_reset = {}
    expected_reset = {"issue": 66, "pull_request": 67, "merge_commit": ACCEPTED_RESET_MERGE}
    for key, expected in expected_reset.items():
        if accepted_reset.get(key) != expected:
            errors.append(
                f"accepted_governance_reset.{key} must be {expected!r}, "
                f"got {accepted_reset.get(key)!r}"
            )

    gate = data.get("active_gate")
    if not isinstance(gate, dict):
        errors.append("active_gate must be an object")
        gate = {}
    expected_gate = {
        "lane": "governance_repair",
        "issue": 74,
        "pull_request": 72,
        "branch": "governance/issue66-post-merge-repair",
        "expected_pr_state": "open_ready",
    }
    for key, expected in expected_gate.items():
        if gate.get(key) != expected:
            errors.append(f"active_gate.{key} must be {expected!r}, got {gate.get(key)!r}")
    if data.get("state") != "AWAITING_REVIEW":
        errors.append("revision 3 must remain AWAITING_REVIEW until Issue #74 / PR #72 is accepted")
    if data.get("product_implementation_held") is not True:
        errors.append("product implementation must remain held during governance repair review")

    superseded = data.get("superseded")
    if not isinstance(superseded, list):
        errors.append("superseded must be an array")
        superseded = []
    milestone_32 = next(
        (item for item in superseded if isinstance(item, dict) and item.get("number") == 32),
        None,
    )
    if not isinstance(milestone_32, dict):
        errors.append("M32 superseded disposition is missing")
    else:
        expected = {
            "issue": 57,
            "pull_request": 54,
            "disposition": "closed_unmerged_preserve_for_salvage",
        }
        for key, value in expected.items():
            if milestone_32.get(key) != value:
                errors.append(f"M32 superseded {key} must be {value!r}")
    for issue in (59, 63):
        if not any(
            isinstance(item, dict)
            and item.get("issue") == issue
            and item.get("disposition") == "closed_superseded"
            for item in superseded
        ):
            errors.append(f"superseded governance Issue #{issue} is missing")

    planned = data.get("planned_product_milestone")
    if not isinstance(planned, dict):
        errors.append("planned_product_milestone must be an object")
        planned = {}
    if (planned.get("number"), planned.get("issue"), planned.get("status")) != (33, 68, "PLANNED"):
        errors.append("M33 must remain PLANNED on Issue #68 during governance repair review")
    first_gate = planned.get("first_gate")
    if not isinstance(first_gate, dict):
        errors.append("M33 first_gate must be an object")
    elif (
        first_gate.get("id"),
        first_gate.get("issue"),
        first_gate.get("status"),
    ) != ("M33.1", 69, "BLOCKED_BY_GOVERNANCE_REPAIR"):
        errors.append("M33.1 must remain blocked on Issue #69 until Issue #74 / PR #72 is accepted")

    if data.get("operator_protocol") != "docs/OPERATOR_PROTOCOL.md":
        errors.append("control state must point to docs/OPERATOR_PROTOCOL.md")
    if data.get("current_human_surface") != "CURRENT.md":
        errors.append("control state must point to CURRENT.md")

    legacy = data.get("legacy_milestone_registry")
    if not isinstance(legacy, dict):
        errors.append("legacy_milestone_registry must be an object")
        legacy = {}
    if legacy.get("path") != FROZEN_MILESTONE_REGISTRY_PATH:
        errors.append(
            "legacy milestone registry path must remain "
            f"{FROZEN_MILESTONE_REGISTRY_PATH!r}, got {legacy.get('path')!r}"
        )
    legacy_path = repo_root / FROZEN_MILESTONE_REGISTRY_PATH
    if legacy.get("authority") != "historical_only":
        errors.append("legacy milestone registry must be classified historical_only")
    try:
        raw_legacy = legacy_path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read preserved legacy registry: {exc}")
    else:
        actual_blob = _git_blob_sha(raw_legacy)
        if actual_blob != legacy.get("git_blob_sha"):
            errors.append(
                "legacy milestone registry changed during the reset: "
                f"expected {legacy.get('git_blob_sha')}, got {actual_blob}"
            )

    for relative in KEY_CURRENT_DOCUMENTS:
        path = repo_root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"cannot read current authority document {relative}: {exc}")
            continue
        if (
            relative in RESET_AUTHORITY_DOCUMENTS
            and "#66" not in text
            and "Issue #66" not in text
        ):
            errors.append(f"reset authority document {relative} does not identify Issue #66")
        for forbidden in FORBIDDEN_CURRENT_CLAIMS:
            if forbidden.casefold() in text.casefold():
                errors.append(f"current authority document {relative} retains forbidden claim: {forbidden}")

    current = (repo_root / "CURRENT.md").read_text(encoding="utf-8")
    for token in (
        "AWAITING_REVIEW — GOVERNANCE REPAIR",
        "PRODUCT IMPLEMENTATION HELD",
        "Issue:** #74",
        "Implementation PR:** #72",
        "ready for exact-head review",
        "PR #54 — closed unmerged",
        ACCEPTED_RESET_MERGE,
    ):
        if token not in current:
            errors.append(f"CURRENT.md is missing required review token {token!r}")

    workflow = (repo_root / ".github" / "workflows" / "fxd-foreman.yml").read_text(
        encoding="utf-8"
    )
    for token in ("RETIRED BY ISSUE #66", "contents: read", "exit 1"):
        if token not in workflow:
            errors.append(f"retired Foreman workflow is missing {token!r}")
    for forbidden in (
        "openai/codex-action",
        "contents: write",
        "pull-requests: write",
        "issues: write",
        "gh pr create",
        "git push",
    ):
        if forbidden in workflow:
            errors.append(f"retired Foreman workflow retains forbidden capability {forbidden!r}")

    selector = (repo_root / "scripts" / "fxd-backlog.mjs").read_text(encoding="utf-8")
    if "automatic milestone selection is retired by Issue #66" not in selector:
        errors.append("legacy selector does not fail closed under Review-Control")
    if "fs.existsSync(controlState) || fs.existsSync(operatorProtocol)" not in selector:
        errors.append("selector retirement must survive a missing operator protocol")

    next_action = data.get("next_valid_action")
    if not isinstance(next_action, str) or "PR #72" not in next_action or "M33.1" not in next_action:
        errors.append("next_valid_action must keep PR #72 review ahead of M33.1")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("FXD control-state validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("FXD control state validated: Issue #74 / PR #72 awaiting exact-head review; product implementation held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
