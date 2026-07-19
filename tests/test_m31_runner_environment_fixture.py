"""Opt-in child-environment fixture for local PowerShell runner tests."""
import os
import unittest


_PROVIDER_ENVIRONMENT_NAMES = (
    "OPENAI_API_KEY",
    "FXD_OPENAI_MODEL",
    "FXD_AI_MODEL",
    "FXD_AI_PROVIDER",
    "FXD_AI_ENDPOINT",
    "FXD_AI_API_KEY",
)


@unittest.skipUnless(
    os.environ.get("FXD_M31_RUNNER_ENV_CAPTURE_TEST") == "1",
    "only enabled by the local PowerShell runner test",
)
class M31RunnerEnvironmentFixtureTests(unittest.TestCase):
    def test_reports_only_safe_provider_environment_presence(self):
        expectation = os.environ.get("FXD_M31_RUNNER_ENV_EXPECTATION")
        provider_configuration_present = all(
            name in os.environ for name in _PROVIDER_ENVIRONMENT_NAMES
        )

        if expectation == "focused":
            self.assertEqual(os.environ.get("FXD_OPENAI_LIVE_SMOKE"), "0")
            self.assertFalse(provider_configuration_present)
            print("FXD_M31_FOCUSED_PROVIDER_CONFIGURATION_ABSENT")
            return

        if expectation == "live":
            self.assertEqual(os.environ.get("FXD_OPENAI_LIVE_SMOKE"), "1")
            self.assertTrue(provider_configuration_present)
            print("FXD_M31_LIVE_PROVIDER_CONFIGURATION_PRESERVED")
            return

        self.fail("missing local PowerShell runner environment expectation")
