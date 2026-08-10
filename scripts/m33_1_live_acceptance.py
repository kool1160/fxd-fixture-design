"""Opt-in exactly-one-request M33.1 OpenAI acceptance proof.

The script prints only bounded provenance.  It never prints credentials,
prompt content, unrestricted provider output, or source STEP bytes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxd_geometry import (  # noqa: E402
    ExecutionMode, OpenAiResponsesProvider, ProviderState, execute_design_mode,
)
from scripts.m33_1_self_check import synthetic_workflow  # noqa: E402


EXPECTED_REPOSITORY = "https://github.com/kool1160/fxd-fixture-design.git"
EXPECTED_BRANCH = "agent/m33-1-native-product-reconstruction"


def _git(*arguments: str) -> str:
    return subprocess.check_output(
        ("git", *arguments), cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
    ).strip()


def _refuse(reason: str) -> int:
    print(json.dumps({
        "schema": "fxd-m33-1-live-acceptance-v1",
        "status": "refused",
        "reason": reason,
    }, sort_keys=True))
    return 2


def main() -> int:
    if os.environ.get("FXD_M33_1_LIVE_ACCEPTANCE") != "1":
        return _refuse("explicit opt-in is required")
    try:
        remote = _git("remote", "get-url", "origin")
        branch = _git("branch", "--show-current")
        head = _git("rev-parse", "HEAD")
        dirty = _git("status", "--porcelain")
    except (OSError, subprocess.CalledProcessError):
        return _refuse("expected Git repository is unavailable")
    if remote.rstrip("/") != EXPECTED_REPOSITORY.rstrip("/"):
        return _refuse("repository identity does not match the M33.1 work order")
    if branch != EXPECTED_BRANCH:
        return _refuse("branch does not match the sole M33.1 implementation branch")
    if dirty:
        return _refuse("worktree must be clean so evidence binds to one exact head")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("FXD_OPENAI_MODEL", "").strip()
    if not api_key or not model:
        return _refuse("explicit OpenAI key and model configuration are required")

    source, document, workflow = synthetic_workflow()
    provider = OpenAiResponsesProvider(api_key, model)
    outcome = execute_design_mode(
        document, workflow, ExecutionMode.AI_DESIGN_LIVE,
        provider=provider, timeout_seconds=60.0,
    )
    evidence = outcome.provenance.to_dict()
    safe = {
        "schema": "fxd-m33-1-live-acceptance-v1",
        "repository": "kool1160/fxd-fixture-design",
        "branch": branch,
        "head": head,
        "source_sha256": document.source_sha256,
        "source_unchanged": document.source_bytes == source,
        "reconstruction_identity": evidence["reconstruction_identity"],
        "mode": evidence["mode"],
        "provider_identity": evidence["provider_identity"],
        "model_identity": evidence["model_identity"],
        "request_attempted": evidence["request_attempted"],
        "request_count": evidence["request_count"],
        "request_status": evidence["request_status"],
        "failure_category": evidence["failure_category"],
        "fallback_used": evidence["fallback_used"],
        "automatic_retries": evidence["automatic_retries"],
        "timeout_seconds": evidence["timeout_seconds"],
        "prompt_contract_version": evidence["prompt_contract_version"],
        "response_contract_version": evidence["response_contract_version"],
        "result_identity": evidence["result_identity"],
        "usage_status": evidence["usage_status"],
        "input_tokens": evidence["input_tokens"],
        "output_tokens": evidence["output_tokens"],
        "total_tokens": evidence["total_tokens"],
        "cost_usd": evidence["cost_usd"],
    }
    print(json.dumps(safe, sort_keys=True))
    if outcome.provider_state != ProviderState.SUCCESS:
        return 1
    if provider.request_count != 1 or evidence["request_count"] != 1:
        return 1
    if evidence["fallback_used"] or evidence["automatic_retries"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
