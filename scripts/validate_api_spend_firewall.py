"""Fail closed if the standing Codex contract can imply product API spending."""
from __future__ import annotations

from pathlib import Path


REQUIRED_PROMPT_TOKENS = (
    "## Current-main authority preflight",
    "Before trusting branch-local project state",
    "If current `main` cannot be inspected",
    "stale branch governance",
    "`CONTINUE` **never authorizes an OpenAI API request.**",
    "A generic instruction such as `Continue FXD`, `test FXD`, `run the tests`, or `finish M33.1` is not API-spend authorization.",
    "must not:",
    "OPENAI_API_KEY",
    "FXD_M33_1_LIVE_ACCEPTANCE",
    "scripts/m33_1_live_acceptance.py",
    "api.openai.com",
    "live OpenAI evidence only when separately and explicitly authorized",
    "stop `BLOCKED`",
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    prompt_path = root / ".github" / "codex" / "prompts" / "run-milestone.md"
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read standing Codex prompt: {exc}"]

    for token in REQUIRED_PROMPT_TOKENS:
        if token not in prompt:
            errors.append(f"standing Codex prompt lacks API-spend/current-main firewall token: {token!r}")

    evidence_section = prompt.split("## Evidence", 1)[-1]
    if "explicit opt-in live OpenAI evidence;" in evidence_section:
        errors.append("standing Codex prompt still authorizes live evidence by generic applicability")

    work_order = prompt.split("## Work order", 1)[-1]
    if "current `main` `CURRENT.md` is `HELD`" not in work_order:
        errors.append("standing Codex prompt does not fail closed on a current-main hold")
    if "product_implementation_held: true" not in work_order:
        errors.append("standing Codex prompt does not bind implementation to current-main hold state")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("FXD API spend firewall validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("FXD API spend firewall validated: stale branches, CONTINUE, and ordinary testing cannot authorize provider spend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
