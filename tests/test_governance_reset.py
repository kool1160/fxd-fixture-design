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

    def test_m33_1_is_held_on_the_existing_implementation_pr(self) -> None:
        state = json.loads((ROOT / "docs" / "CONTROL_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(3, state["revision"])
        self.assertEqual(70, state["authority_issue"])
        self.assertEqual("HELD", state["state"])
        self.assertTrue(state["product_implementation_held"])
        self.assertEqual("owner", state["hold"]["authority"])
        self.assertEqual("cost_control", state["hold"]["reason"])
        self.assertEqual(
            {
                "lane": "product",
                "milestone": 33,
                "id": "M33.1",
                "issue": 69,
                "pull_request": 79,
                "branch": "agent/m33-1-native-product-reconstruction",
                "expected_pr_state": "open_draft_held_cost_control",
                "objective": state["active_gate"]["objective"],
            },
            state["active_gate"],
        )
        self.assertEqual("ACTIVE", state["product_milestone"]["status"])
        self.assertEqual("HELD", state["product_milestone"]["active_gate"]["status"])
        self.assertTrue(state["next_valid_action"].startswith("HOLD."))
        self.assertNotIn("CONTINUE", state["next_valid_action"])

    def test_development_route_is_chatgpt_codex_remote_with_zero_api_budget(self) -> None:
        state = json.loads((ROOT / "docs" / "CONTROL_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "implementation_surface": "chatgpt_codex_remote",
                "repository_api_key_for_development": False,
                "github_paid_codex_dispatchers_allowed": False,
                "product_runtime_api_requires_explicit_review_control_authorization": True,
            },
            state["development_execution"],
        )
        self.assertEqual(0, state["budgets"]["development_api_requests"])
        self.assertEqual(0, state["budgets"]["repository_paid_codex_dispatchers"])

    def test_m33_1_product_runtime_budgets_remain_hard_ceiling(self) -> None:
        state = json.loads((ROOT / "docs" / "CONTROL_STATE.json").read_text(encoding="utf-8"))
        budgets = state["budgets"]
        self.assertEqual(1, budgets["live_requests_per_acceptance_run"])
        self.assertEqual(0, budgets["automatic_provider_retries"])
        self.assertEqual(0, budgets["repair_requests"])
        self.assertEqual(60, budgets["request_timeout_seconds_max"])
        self.assertEqual(
            "explicitly configured high-capability OpenAI model; no default guess",
            budgets["model_policy"],
        )

    def test_current_state_projects_hold_and_cost_boundary(self) -> None:
        current = (ROOT / "CURRENT.md").read_text(encoding="utf-8")
        for token in (
            "HELD — COST CONTROL — M33.1 / ISSUE #69 / PR #79",
            "Implementation PR:** #79",
            "ChatGPT Codex Remote",
            "Development API requests:** 0",
            "Paid GitHub Codex dispatchers:** forbidden",
            "Profile E request remains unspent",
            "**HOLD**",
        ):
            self.assertIn(token, current)
        self.assertNotIn("Implementation PR:** none yet", current)
        self.assertNotIn("**CONTINUE**", current)

    def test_all_github_workflows_reject_paid_development_routes(self) -> None:
        workflows = ROOT / ".github" / "workflows"
        forbidden = (
            "uses: openai/codex-action",
            "openai-api-key:",
            "secrets.OPENAI_API_KEY",
        )
        for path in (*workflows.glob("*.yml"), *workflows.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            active_lines = "\n".join(
                line for line in text.splitlines()
                if not line.lstrip().startswith("#")
            )
            for token in forbidden:
                self.assertNotIn(token, active_lines, f"{path}: {token}")

    def test_retired_paid_dispatcher_is_inert_read_only_and_fail_closed(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "m33-1-codex-continue.yml").read_text(
            encoding="utf-8"
        )
        for token in (
            "RETIRED — M33.1 paid Codex dispatcher",
            "contents: read",
            "Use ChatGPT Codex Remote",
            "exit 1",
        ):
            self.assertIn(token, workflow)
        active_lines = "\n".join(
            line for line in workflow.splitlines()
            if not line.lstrip().startswith("#")
        )
        for token in (
            "push:",
            "openai/codex-action",
            "openai-api-key:",
            "secrets.OPENAI_API_KEY",
            "contents: write",
            "pull-requests: write",
            "issues: write",
            "gh pr create",
            "git push",
        ):
            self.assertNotIn(token, active_lines)

    def test_autonomous_foreman_workflow_is_retired_and_read_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("RETIRED BY ISSUE #66", workflow)
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
            (scripts / "validate_legacy_milestones.py").write_text(
                "raise SystemExit(0)\n", encoding="utf-8"
            )
            (docs / "CONTROL_STATE.json").write_text("{}\n", encoding="utf-8")
            (docs / "MILESTONE_STATE.json").write_text(
                json.dumps({
                    "product_lane": {"paused": False, "active_milestone": 32},
                    "milestones": [],
                }) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", result.stderr)

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
        self.assertIn("frozen historical projection only", result.stdout)
        self.assertNotIn("Active milestone 32", result.stdout)

    def test_operator_protocol_separates_builder_review_and_api_cost_boundary(self) -> None:
        protocol = (ROOT / "docs" / "OPERATOR_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("Review-Control decides and reviews", protocol)
        self.assertIn("ChatGPT Codex Remote", protocol)
        self.assertIn("Permanent API and cost boundary", protocol)
        self.assertIn("Codex never merges or advances itself", protocol)
        self.assertIn("Claude / Anthropic is not part", protocol)


if __name__ == "__main__":
    unittest.main()
