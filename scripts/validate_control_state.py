"""Validate authoritative FXD control state and fail closed on drift/cost routing."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "fxd-control-state-v1"
RESET_MERGE = "592876fefde118b5325bbb5b4949eeb1490cdf6c"
LEGACY_BLOB = "f667797f1ea59e508ebd46b97cc89061f56b1c1a"
HELD_PR = 79
HELD_BRANCH = "agent/m33-1-native-product-reconstruction"

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
    "Issue #66 is the active governance authority",
    "Implementation PR:** #67",
    "Do not begin product runtime implementation until PR #67 is accepted",
    "M33 must remain PLANNED",
    "M33.1 must remain blocked",
)


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()  # nosec B324


def mapping(data: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _active_workflow_text(text: str) -> str:
    """Ignore comments while preserving every executable/configuration line."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )


def _validate_workflow_cost_boundary(root: Path, errors: list[str]) -> None:
    """Reject any active GitHub workflow route capable of paid OpenAI development."""
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        errors.append(".github/workflows is missing")
        return

    for path in sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml"))):
        active = _active_workflow_text(path.read_text(encoding="utf-8"))
        normalized = active.casefold()
        relative = path.relative_to(root)

        # Case-insensitive and secret-name-independent. These cover the Codex
        # action, conventional or alternate OPENAI_API_KEY forwarding, direct
        # OpenAI HTTP calls, and SDK/provider use paired with any GitHub secret.
        if "codex-action" in normalized:
            errors.append(f"paid development Codex action is forbidden in {relative}")
        if "openai_api_key" in normalized:
            errors.append(f"OpenAI API key forwarding is forbidden in {relative}")
        if "api.openai.com" in normalized:
            errors.append(f"direct OpenAI API endpoint use is forbidden in {relative}")
        if "openai" in normalized and "secrets." in normalized:
            errors.append(f"OpenAI workflow use paired with a GitHub secret is forbidden in {relative}")

    retired = workflows / "m33-1-codex-continue.yml"
    if not retired.exists():
        errors.append("retired M33.1 paid dispatcher control surface is missing")
    else:
        text = retired.read_text(encoding="utf-8")
        for token in (
            "RETIRED — M33.1 paid Codex dispatcher",
            "contents: read",
            "Use ChatGPT Codex Remote",
            "exit 1",
        ):
            if token not in text:
                errors.append(f"retired paid dispatcher is missing {token!r}")
        active = _active_workflow_text(text).casefold()
        for forbidden in ("push:", "codex-action", "openai_api_key", "api.openai.com"):
            if forbidden in active:
                errors.append(f"retired paid dispatcher retains active route {forbidden!r}")


def _validate_hold_projections(root: Path, errors: list[str]) -> None:
    """Require every current operator projection to agree with the held PR state."""
    required = {
        "README.md": (
            "HELD — COST CONTROL",
            "draft PR #79",
            "ChatGPT Codex Remote",
            "paid GitHub Codex dispatcher is retired",
        ),
        "docs/FOREMAN_SETUP.md": (
            "HELD — COST CONTROL",
            "**Implementation PR:** #79",
            "ChatGPT Codex Remote",
            "no Profile E/product-runtime paid request is authorized while held",
        ),
        "docs/MILESTONE_CONTRACT.md": (
            "**Implementation PR:** #79",
            "**Status:** HELD — COST CONTROL",
            "## Development/API cost boundary",
            "While held: no Codex implementation/repair pass",
        ),
    }
    forbidden = {
        "README.md": ("implementation PR does not exist",),
        "docs/FOREMAN_SETUP.md": ("there is no implementation PR",),
        "docs/MILESTONE_CONTRACT.md": ("- **Status:** ACTIVE\n\nProve:",),
    }
    for relative, tokens in required.items():
        text = (root / relative).read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                errors.append(f"{relative} does not project held PR #79 state: missing {token!r}")
        for token in forbidden.get(relative, ()):
            if token.casefold() in text.casefold():
                errors.append(f"{relative} retains contradictory pre-hold claim {token!r}")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads((root / "docs/CONTROL_STATE.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load docs/CONTROL_STATE.json: {exc}"]

    required_root = {
        "schema_version": SCHEMA,
        "revision": 3,
        "authority_issue": 70,
        "state": "HELD",
        "product_implementation_held": True,
        "operator_protocol": "docs/OPERATOR_PROTOCOL.md",
        "current_human_surface": "CURRENT.md",
    }
    for key, expected in required_root.items():
        if data.get(key) != expected:
            errors.append(f"{key} must be {expected!r}, got {data.get(key)!r}")

    hold = mapping(data, "hold", errors)
    if hold.get("authority") != "owner" or hold.get("reason") != "cost_control":
        errors.append("hold must be owner-authorized cost_control")
    resume = hold.get("resume_condition")
    if not isinstance(resume, str) or "Explicit owner instruction" not in resume:
        errors.append("hold.resume_condition must require explicit owner instruction")

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
        "lane": "product",
        "milestone": 33,
        "id": "M33.1",
        "issue": 69,
        "pull_request": HELD_PR,
        "branch": HELD_BRANCH,
        "expected_pr_state": "open_draft_held_cost_control",
    }
    for key, expected in expected_gate.items():
        if gate.get(key) != expected:
            errors.append(f"active_gate.{key} must be {expected!r}, got {gate.get(key)!r}")
    objective = gate.get("objective")
    if not isinstance(objective, str) or "reconstruction" not in objective.casefold():
        errors.append("active_gate.objective must name product reconstruction")
    if not isinstance(objective, str) or "live openai" not in objective.casefold():
        errors.append("active_gate.objective must name explicit live OpenAI mode")

    execution = mapping(data, "development_execution", errors)
    expected_execution = {
        "implementation_surface": "chatgpt_codex_remote",
        "repository_api_key_for_development": False,
        "github_paid_codex_dispatchers_allowed": False,
        "product_runtime_api_requires_explicit_review_control_authorization": True,
    }
    for key, expected in expected_execution.items():
        if execution.get(key) != expected:
            errors.append(f"development_execution.{key} must be {expected!r}")

    milestone = mapping(data, "product_milestone", errors)
    if (milestone.get("number"), milestone.get("issue"), milestone.get("status")) != (33, 68, "ACTIVE"):
        errors.append("product_milestone must remain active M33 / Issue #68")
    child = milestone.get("active_gate")
    if not isinstance(child, dict) or (
        child.get("id"), child.get("issue"), child.get("status")
    ) != ("M33.1", 69, "HELD"):
        errors.append("product_milestone.active_gate must hold only M33.1 / Issue #69")

    budgets = mapping(data, "budgets", errors)
    expected_budgets = {
        "development_api_requests": 0,
        "repository_paid_codex_dispatchers": 0,
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
        actual_blob = blob_sha((root / "docs/MILESTONE_STATE.json").read_bytes())
    except OSError as exc:
        errors.append(f"cannot read legacy milestone registry: {exc}")
    else:
        if legacy.get("git_blob_sha") != LEGACY_BLOB or actual_blob != LEGACY_BLOB:
            errors.append("legacy milestone registry changed from the frozen pre-reset blob")

    current = (root / "CURRENT.md").read_text(encoding="utf-8")
    for token in (
        "HELD — COST CONTROL — M33.1 / ISSUE #69 / PR #79",
        "Implementation PR:** #79",
        "ChatGPT Codex Remote",
        "Development API requests:** 0",
        "Paid GitHub Codex dispatchers:** forbidden",
        "Profile E request remains unspent",
        "**HOLD**",
        "Live requests per acceptance run:** 1",
        "Automatic provider retries:** 0",
        "Repair requests in M33.1:** 0",
        "Maximum request timeout:** 60 seconds",
        "PR #54 — closed unmerged",
    ):
        if token not in current:
            errors.append(f"CURRENT.md is missing {token!r}")
    for token in ("Implementation PR:** none yet", "**CONTINUE**"):
        if token in current:
            errors.append(f"CURRENT.md retains unsafe active token {token!r}")

    next_action = data.get("next_valid_action")
    if not isinstance(next_action, str) or not next_action.startswith("HOLD."):
        errors.append("next_valid_action must be HOLD")
    if isinstance(next_action, str) and "Profile E" not in next_action:
        errors.append("next_valid_action must hold Profile E")

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

    _validate_hold_projections(root, errors)

    foreman = (root / ".github/workflows/fxd-foreman.yml").read_text(encoding="utf-8")
    for token in ("RETIRED BY ISSUE #66", "contents: read", "exit 1"):
        if token not in foreman:
            errors.append(f"retired Foreman is missing {token!r}")
    for forbidden in (
        "openai/codex-action", "contents: write", "pull-requests: write",
        "issues: write", "gh pr create", "git push",
    ):
        if forbidden in foreman:
            errors.append(f"retired Foreman retains {forbidden!r}")

    _validate_workflow_cost_boundary(root, errors)

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
    print("FXD control state validated: M33.1 / Issue #69 / PR #79 HELD for cost control; paid development API routes forbidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
