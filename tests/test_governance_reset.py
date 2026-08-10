from __future__ import annotations

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

    def test_current_state_holds_product_work_and_targets_reset_pr(self) -> None:
        current = (ROOT / "CURRENT.md").read_text(encoding="utf-8")
        self.assertIn("AWAITING_REVIEW — GOVERNANCE RESET", current)
        self.assertIn("PRODUCT IMPLEMENTATION HELD", current)
        self.assertIn("Issue:** #66", current)
        self.assertIn("Implementation PR:** #67", current)
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
