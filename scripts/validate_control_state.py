"""Validate the authoritative FXD control state and fail closed on drift."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "fxd-control-state-v1"
RESET_MERGE = "592876fefde118b5325bbb5b4949eeb1490cdf6c"
LEGACY_BLOB = "f667797f1ea59e508ebd46b97cc89061f56b1c1a"
CURRENT_DOCS = (
    "AGENTS.md", "CURRENT.md", "README.md", "docs/PRODUCT_DIRECTION.md",
    "docs/OPERATOR_PROTOCOL.md", "docs/ENGINEERING_CONSTITUTION.md",
    "docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md", "docs/ARCHITECTURE.md",
    "docs/MILESTONE_CONTRACT.md", "docs/ENGINEERING_TEAM.md",
    "docs/FOREMAN_SETUP.md", "docs/decisions/0001-ai-driven-fixture-synthesis-reset.md",
)
ACTIVE_PROJECTION_DOCS = {
    "AGENTS.md", "CURRENT.md", "README.md", "docs/MILESTONE_CONTRACT.md",
    "docs/FOREMAN_SETUP.md", "docs/decisions/0001-ai-driven-fixture-synthesis-reset.md",
}
STALE_RESET_CLAIMS = (
    "AWAITING_REVIEW — GOVERNANCE RESET",
    "PRODUCT IMPLEMENTATION HELD",
    "Issue #66 is the active governance authority",
    "Implementation PR:** #67",
    "Do not begin product runtime implementation until PR #67 is accepted",
    "M33 must remain PLANNED",
    "M33.1 must remain blocked",
)


def canonical_worktree_blob(root: Path, relative: str) -> str:
    """Hash the logical Git content so Windows checkout EOLs cannot forge drift."""
    return subprocess.check_output(
        ("git", "hash-object", f"--path={relative}", relative),
        cwd=root, text=True, stderr=subprocess.DEVNULL,
    ).strip()


def mapping(data: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads((root / "docs/CONTROL_STATE.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load docs/CONTROL_STATE.json: {exc}"]

    required_root = {
        "schema_version": SCHEMA,
        "revision": 2,
        "authority_issue": 70,
        "state": "ACTIVE",
        "product_implementation_held": False,
        "operator_protocol": "docs/OPERATOR_PROTOCOL.md",
        "current_human_surface": "CURRENT.md",
    }
    for key, expected in required_root.items():
        if data.get(key) != expected:
            errors.append(f"{key} must be {expected!r}, got {data.get(key)!r}")

    reset = mapping(data, "accepted_reset", errors)
    for key, expected in {
        "issue": 66,
        "pull_request": 67,
        "merge_commit": RESET_MERGE,
        "decision": "docs/decisions/0001-ai-driven-fixture-synthesis-reset.md",
    }.items():
        if reset.get(key) != expected:
            errors.append(f"accepted_reset.{key} must be {expected!r}")

    activation = mapping(data, "activation", errors)
    if activation.get("issue") != 70:
        errors.append("activation.issue must be 70")

    gate = mapping(data, "active_gate", errors)
    expected_gate = {
        "lane": "product", "milestone": 33, "id": "M33.1", "issue": 69,
        "pull_request": None, "branch": None,
        "expected_pr_state": "none_until_codex_continue",
    }
    for key, expected in expected_gate.items():
        if gate.get(key) != expected:
            errors.append(f"active_gate.{key} must be {expected!r}, got {gate.get(key)!r}")
    objective = gate.get("objective")
    if not isinstance(objective, str) or "reconstruction" not in objective.casefold():
        errors.append("active_gate.objective must name product reconstruction")
    if not isinstance(objective, str) or "live openai" not in objective.casefold():
        errors.append("active_gate.objective must name explicit live OpenAI mode")

    milestone = mapping(data, "product_milestone", errors)
    if (milestone.get("number"), milestone.get("issue"), milestone.get("status")) != (33, 68, "ACTIVE"):
        errors.append("product_milestone must activate M33 / Issue #68")
    child = milestone.get("active_gate")
    if not isinstance(child, dict) or (child.get("id"), child.get("issue"), child.get("status")) != (
        "M33.1", 69, "ACTIVE"
    ):
        errors.append("product_milestone.active_gate must activate only M33.1 / Issue #69")

    budgets = mapping(data, "budgets", errors)
    expected_budgets = {
        "live_requests_per_acceptance_run": 1,
        "automatic_provider_retries": 0,
        "repair_requests": 0,
        "request_timeout_seconds_max": 60,
        "model_policy": "explicitly configured high-capability OpenAI model; no default guess",
    }
    for key, expected in expected_budgets.items():
        if budgets.get(key) != expected:
            errors.append(f"budgets.{key} must be {expected!r}, got {budgets.get(key)!r}")

    superseded = data.get("superseded")
    if not isinstance(superseded, list):
        errors.append("superseded must be an array")
        superseded = []
    if not any(
        isinstance(item, dict)
        and item.get("number") == 32
        and item.get("issue") == 57
        and item.get("pull_request") == 54
        and item.get("disposition") == "closed_unmerged_preserve_for_salvage"
        for item in superseded
    ):
        errors.append("superseded M32 / Issue #57 / PR #54 disposition is missing")
    for issue in (59, 63):
        if not any(
            isinstance(item, dict)
            and item.get("issue") == issue
            and item.get("disposition") == "closed_superseded"
            for item in superseded
        ):
            errors.append(f"superseded governance Issue #{issue} is missing")

    legacy = mapping(data, "legacy_milestone_registry", errors)
    if legacy.get("path") != "docs/MILESTONE_STATE.json" or legacy.get("authority") != "historical_only":
        errors.append("legacy milestone registry must remain historical-only at docs/MILESTONE_STATE.json")
    try:
        actual_blob = canonical_worktree_blob(root, "docs/MILESTONE_STATE.json")
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"cannot read legacy milestone registry: {exc}")
    else:
        if legacy.get("git_blob_sha") != LEGACY_BLOB or actual_blob != LEGACY_BLOB:
            errors.append("legacy milestone registry changed from the frozen pre-reset blob")

    current = (root / "CURRENT.md").read_text(encoding="utf-8")
    for token in (
        "ACTIVE — M33.1 / ISSUE #69", "M33:** AI-Driven Fixture Synthesis Proof",
        "Issue:** #69", "Implementation PR:** none yet", "## IN SCOPE",
        "## OUT OF SCOPE", "## Budgets", "## Required evidence", "**CONTINUE**",
        "PR #54 — closed unmerged", "Live requests per acceptance run:** 1",
        "Automatic provider retries:** 0", "Repair requests in M33.1:** 0",
        "Maximum request timeout:** 60 seconds",
    ):
        if token not in current:
            errors.append(f"CURRENT.md is missing {token!r}")
    for token in ("PRODUCT IMPLEMENTATION HELD", "Implementation PR:** #67"):
        if token in current:
            errors.append(f"CURRENT.md retains superseded reset token {token!r}")

    next_action = data.get("next_valid_action")
    if not isinstance(next_action, str) or "CONTINUE" not in next_action or "Issue #69" not in next_action:
        errors.append("next_valid_action must issue CONTINUE for Issue #69")
    if not isinstance(next_action, str) or "AWAITING_REVIEW" not in next_action:
        errors.append("next_valid_action must require Codex to stop AWAITING_REVIEW")

    for relative in CURRENT_DOCS:
        try:
            text = (root / relative).read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"cannot read {relative}: {exc}")
            continue
        if relative in ACTIVE_PROJECTION_DOCS and "#66" not in text and "Issue #66" not in text:
            errors.append(f"{relative} does not preserve Issue #66 reset authority")
        for forbidden in ("M32 is the sole Active", "PR #54 is the active implementation"):
            if forbidden.casefold() in text.casefold():
                errors.append(f"{relative} retains forbidden current claim: {forbidden}")
        if relative in ACTIVE_PROJECTION_DOCS:
            for stale in STALE_RESET_CLAIMS:
                if stale.casefold() in text.casefold():
                    errors.append(f"{relative} retains stale activation claim: {stale}")

    workflow = (root / ".github/workflows/fxd-foreman.yml").read_text(encoding="utf-8")
    for token in ("RETIRED BY ISSUE #66", "contents: read", "exit 1"):
        if token not in workflow:
            errors.append(f"retired Foreman is missing {token!r}")
    for forbidden in (
        "openai/codex-action", "contents: write", "pull-requests: write",
        "issues: write", "gh pr create", "git push",
    ):
        if forbidden in workflow:
            errors.append(f"retired Foreman retains {forbidden!r}")

    selector = (root / "scripts/fxd-backlog.mjs").read_text(encoding="utf-8")
    if "automatic milestone selection is retired by Issue #66" not in selector:
        errors.append("legacy selector does not fail closed")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("FXD control-state validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("FXD control state validated: M33.1 / Issue #69 ACTIVE under Issue #70.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
