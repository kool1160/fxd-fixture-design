from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.validate_control_state import validate


ROOT = Path(__file__).resolve().parents[1]


class GovernanceResetTests(unittest.TestCase):
    def test_authoritative_control_state_validates(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_m33_1_is_the_only_active_gate(self) -> None:
        state = json.loads((ROOT / "docs" / "CONTROL_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(2, state["revision"])
        self.assertEqual(70, state["authority_issue"])
        self.assertEqual("ACTIVE", state["state"])
        self.assertFalse(state["product_implementation_held"])
        self.assertEqual(
            {
                "lane": "product",
                "milestone": 33,
                "id": "M33.1",
                "issue": 69,
                "pull_request": None,
                "branch": None,
                "expected_pr_state": "none_until_codex_continue",
                "objective": state["active_gate"]["objective"],
            },
            state["active_gate"],
        )
        self.assertEqual("ACTIVE", state["product_milestone"]["status"])
        self.assertEqual("ACTIVE", state["product_milestone"]["active_gate"]["status"])
        self.assertIn("CONTINUE", state["next_valid_action"])
        self.assertIn("Issue #69", state["next_valid_action"])
        self.assertIn("AWAITING_REVIEW", state["next_valid_action"])

    def test_m33_1_provider_budgets_are_hard_ceiling(self) -> None:
        state = json.loads((ROOT / "docs" / "CONTROL_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "live_requests_per_acceptance_run": 1,
                "automatic_provider_retries": 0,
                "repair_requests": 0,
                "request_timeout_seconds_max": 60,
                "model_policy": "explicitly configured high-capability OpenAI model; no default guess",
            },
            state["budgets"],
        )

    def test_reset_merge_and_superseded_m32_remain_durable(self) -> None:
        state = json.loads((ROOT / "docs" / "CONTROL_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(66, state["accepted_reset"]["issue"])
        self.assertEqual(67, state["accepted_reset"]["pull_request"])
        self.assertEqual(
            "592876fefde118b5325bbb5b4949eeb1490cdf6c",
            state["accepted_reset"]["merge_commit"],
        )
        m32 = next(item for item in state["superseded"] if item.get("number") == 32)
        self.assertEqual(57, m32["issue"])
        self.assertEqual(54, m32["pull_request"])
        self.assertEqual("closed_unmerged_preserve_for_salvage", m32["disposition"])

    def test_current_state_keeps_scope_and_budgets_in_front_of_agents(self) -> None:
        current = (ROOT / "CURRENT.md").read_text(encoding="utf-8")
        for token in (
            "ACTIVE — M33.1 / ISSUE #69",
            "M33:** AI-Driven Fixture Synthesis Proof",
            "Issue:** #69",
            "Implementation PR:** none yet",
            "## IN SCOPE",
            "## OUT OF SCOPE",
            "## Budgets",
            "Live requests per acceptance run:** 1",
            "Automatic provider retries:** 0",
            "Repair requests in M33.1:** 0",
            "Maximum request timeout:** 60 seconds",
            "## Required evidence",
            "**CONTINUE**",
            "PR #54 — closed unmerged",
        ):
            self.assertIn(token, current)
        self.assertNotIn("PRODUCT IMPLEMENTATION HELD", current)
        self.assertNotIn("Implementation PR:** #67", current)

    def test_autonomous_foreman_workflow_is_retired_and_read_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("RETIRED BY ISSUE #66", workflow)
        self.assertIn("Use docs/OPERATOR_PROTOCOL.md", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("exit 1", workflow)
        for forbidden in (
            "openai/codex-action",
            "contents: write",
            "pull-requests: write",
            "issues: write",
            "gh pr create",
            "git push",
        ):
            self.assertNotIn(forbidden, workflow)

    def test_real_repository_selector_fails_closed_under_review_control(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = Path(temp) / "selected.md"
            result = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select", "--context", str(context)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertFalse(context.exists())
        self.assertNotEqual(0, result.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", result.stderr)

    def test_control_state_keeps_selector_retired_without_operator_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            docs = root / "docs"
            scripts.mkdir()
            docs.mkdir()
            shutil.copy2(ROOT / "scripts" / "fxd-backlog.mjs", scripts / "fxd-backlog.mjs")
            # Isolate selector authority; historical-registry semantics are covered
            # by the real legacy validator suite.
            (scripts / "validate_legacy_milestones.py").write_text(
                "raise SystemExit(0)\n", encoding="utf-8"
            )
            (docs / "CONTROL_STATE.json").write_text("{}\n", encoding="utf-8")
            (docs / "MILESTONE_STATE.json").write_text(
                json.dumps(
                    {
                        "product_lane": {"paused": False, "active_milestone": 32},
                        "milestones": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertFalse((docs / "OPERATOR_PROTOCOL.md").exists())
            result = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", result.stderr)
        self.assertNotIn("Selected", result.stdout)

    def test_control_state_validator_pins_exact_historical_registry_path(self) -> None:
        validator = (ROOT / "scripts" / "validate_control_state.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'legacy.get("path") != "docs/MILESTONE_STATE.json"',
            validator,
        )
        self.assertIn(
            '(root / "docs/MILESTONE_STATE.json").read_bytes()',
            validator,
        )

    def test_historical_validation_never_prints_m32_as_current_authority(self) -> None:
        result = subprocess.run(
            ["node", "scripts/fxd-backlog.mjs", "validate"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("immutable legacy FXD milestone records", result.stdout)
        self.assertIn("historical FXD milestone records", result.stdout)
        self.assertIn("frozen historical projection only", result.stdout)
        self.assertNotIn("Active milestone 32", result.stdout)
        self.assertNotIn("Active Milestone 32", result.stdout)

    def test_operator_protocol_separates_builder_and_review_control(self) -> None:
        protocol = (ROOT / "docs" / "OPERATOR_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("Review-Control decides and reviews", protocol)
        self.assertIn("Codex implements one bounded gate", protocol)
        self.assertIn("AWAITING_REVIEW", protocol)
        self.assertIn("Claude / Anthropic is not part", protocol)
        self.assertIn("Codex never merges or advances itself", protocol)


if __name__ == "__main__":
    unittest.main()
