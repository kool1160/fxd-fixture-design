"""Opt-in local fixture for PowerShell runner stderr-capture regression tests."""
import os
import sys
import unittest


@unittest.skipUnless(
    os.environ.get("FXD_M31_RUNNER_CAPTURE_TEST") == "1",
    "only enabled by the local PowerShell runner test",
)
class M31RunnerCaptureFixtureTests(unittest.TestCase):
    def test_stderr_failure_is_captured_without_provider_io(self):
        print(
            "FXD_M31_SANITIZED_PROVIDER_FAILURE=top-level schema mismatch",
            file=sys.stderr,
        )
        self.fail("intentional native stderr capture sentinel")
