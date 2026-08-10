from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GovernanceResetTests(unittest.TestCase):
    def test_autonomous_foreman_workflow_is_retired_and_read_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("RETIRED BY ISSUE #66", workflow)
        self.assertIn("Use docs/OPERATOR_PROTOCOL.md", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("exit 1", workflow)
        self.assertNotIn("openai/codex-action", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("gh pr create", workflow)
        self.assertNotIn("git push", workflow)

    def test_real_repository_selector_fails_closed_under_review_control(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = Path(temp) / "selected.md"
            result = subprocess.run(
                [
                    "node",
                    "scripts/fxd-backlog.mjs",
                    "select",
                    "--context",
                    str(context),
                ],
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
            # This test isolates selector authority. Historical registry semantics
            # are covered separately by the real legacy validator suite.
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
            'FROZEN_MILESTONE_REGISTRY_PATH = "docs/MILESTONE_STATE.json"',
            validator,
        )
        self.assertIn(
            'legacy.get("path") != FROZEN_MILESTONE_REGISTRY_PATH',
            validator,
        )
        self.assertIn(
            "legacy_path = repo_root / FROZEN_MILESTONE_REGISTRY_PATH",
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
        self.assertIn("pre-reset milestone marker 32 recorded", result.stdout)
        self.assertNotIn("Active milestone 32", result.stdout)
        self.assertNotIn("Active Milestone 32", result.stdout)

    def test_current_state_holds_product_work_and_targets_review_ready_pr(self) -> None:
        current = (ROOT / "CURRENT.md").read_text(encoding="utf-8")
        self.assertIn("AWAITING_REVIEW — GOVERNANCE REPAIR", current)
        self.assertIn("PRODUCT IMPLEMENTATION HELD", current)
        self.assertIn("Issue:** #74", current)
        self.assertIn("Implementation PR:** #72", current)
        self.assertIn("ready for exact-head review", current)
        self.assertIn("592876fefde118b5325bbb5b4949eeb1490cdf6c", current)
        self.assertIn("PR #54 — closed unmerged", current)

    def test_operator_protocol_separates_builder_and_review_control(self) -> None:
        protocol = (ROOT / "docs" / "OPERATOR_PROTOCOL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Review-Control decides and reviews", protocol)
        self.assertIn("Codex implements one bounded gate", protocol)
        self.assertIn("AWAITING_REVIEW", protocol)
        self.assertIn("Claude / Anthropic is not part", protocol)
        self.assertIn("Codex never merges or advances itself", protocol)


if __name__ == "__main__":
    unittest.main()
