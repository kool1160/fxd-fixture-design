import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class M33LiveAcceptanceRunnerTests(unittest.TestCase):
    def test_runner_requires_explicit_opt_in_without_exposing_configuration(self):
        environment = os.environ.copy()
        environment.pop("FXD_M33_1_LIVE_ACCEPTANCE", None)
        environment["OPENAI_API_KEY"] = "configuration-only-secret"
        environment["FXD_OPENAI_MODEL"] = "explicit-test-model"
        result = subprocess.run(
            [sys.executable, "scripts/m33_1_live_acceptance.py"],
            cwd=ROOT, env=environment, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("explicit opt-in is required", result.stdout)
        self.assertNotIn("configuration-only-secret", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
