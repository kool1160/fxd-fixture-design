from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_api_spend_firewall import validate


ROOT = Path(__file__).resolve().parents[1]


class ApiSpendFirewallTests(unittest.TestCase):
    def test_real_standing_codex_prompt_is_fail_closed_for_api_spend(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_generic_continue_prompt_cannot_pass_without_explicit_firewall(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt_dir = root / ".github" / "codex" / "prompts"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "run-milestone.md").write_text(
                "# Continue FXD\n\nRun tests, including explicit opt-in live OpenAI evidence; then finish.\n",
                encoding="utf-8",
            )
            errors = validate(root)
        self.assertTrue(errors)
        self.assertTrue(any("CONTINUE" in error or "firewall" in error for error in errors))

    def test_live_evidence_by_generic_applicability_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt_dir = root / ".github" / "codex" / "prompts"
            prompt_dir.mkdir(parents=True)
            real = (ROOT / ".github" / "codex" / "prompts" / "run-milestone.md").read_text(
                encoding="utf-8"
            )
            real += "\n## Evidence\n\n- explicit opt-in live OpenAI evidence;\n"
            (prompt_dir / "run-milestone.md").write_text(real, encoding="utf-8")
            errors = validate(root)
        self.assertTrue(any("generic applicability" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
