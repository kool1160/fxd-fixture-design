"""Focused regression coverage for the autonomous, offline M32 self-check."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.m32_self_check import SELF_CHECK_SCHEMA, main, run_m32_self_check, write_report


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


class M32SelfCheckTests(unittest.TestCase):
    def test_autonomous_scenario_exercises_governed_reduction_and_release_gates(self):
        report = run_m32_self_check()

        self.assertEqual(report["schema"], SELF_CHECK_SCHEMA)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["network_provider_used"])
        self.assertTrue(report["step_import"]["source_cad_unchanged"])
        self.assertTrue(report["guided_orientation"]["accepted"])
        self.assertEqual(report["fixture_build"]["requested_station_count"], 5)
        self.assertEqual(report["fixture_build"]["accepted_feasible_station_count"], 4)
        self.assertTrue(report["fixture_build"]["original_request_retained"])
        self.assertFalse(report["fixture_build_validation"]["authoring_blocked"])
        self.assertTrue(report["authored_geometry"]["provisional"])
        self.assertFalse(report["authored_geometry"]["aabb_fallback_used"])
        self.assertGreater(report["authored_geometry"]["tessellated_triangle_count"], 0)
        self.assertEqual(report["authored_geometry"]["product_instance_count"], 4)
        self.assertTrue(report["access_review"]["trapped_part_detected"])
        self.assertTrue(report["release_gates"]["engineering_approval_blocked"])
        self.assertTrue(report["release_gates"]["release_export_blocked"])
        self.assertTrue(report["project_persistence"]["passed"])

    def test_m32_self_check_exercises_validation_after_accepted_proposal_binding(self):
        report = run_m32_self_check()

        proposal = report["accepted_proposal"]
        self.assertEqual(proposal["decision"], "accepted_for_engineering_review")
        self.assertEqual(proposal["blocker_count"], 0)
        self.assertTrue(proposal["current"])
        self.assertTrue(proposal["plan_identity_bound"])
        self.assertTrue(proposal["plan_evidence_digest_bound"])
        self.assertTrue(proposal["missing_acceptance_gate_independently_blocked"])

        gates = report["release_gates"]
        self.assertTrue(gates["proposal_gate_satisfied"])
        self.assertEqual(
            gates["engineering_approval_block_reason"],
            "invalid_deterministic_validation_result",
        )
        self.assertEqual(
            gates["release_export_block_reason"],
            "invalid_fixture_build_validation",
        )
        self.assertEqual(
            gates["stale_release_export_block_reason"],
            "authored_fixture_geometry_stale",
        )
        self.assertIn("FXD-WLD-001", gates["validation_gate_rule_ids"])
        self.assertIn("FXD-M32-ACC", gates["stale_validation_gate_rule_ids"])
        self.assertFalse(report["network_provider_used"])

    def test_cli_report_is_redacted_and_contains_no_source_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "m32-self-check.json"
            self.assertEqual(main(["--report", str(destination), "--artifact-directory", directory]), 0)
            report = json.loads(destination.read_text(encoding="utf-8"))
            screenshot = Path(directory) / report["evidence_artifacts"]["summary_screenshot"]
            self.assertTrue(screenshot.is_file())
            self.assertEqual(screenshot.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

        forbidden = {
            "source_bytes", "source_step_base64", "source_sha256", "step_bytes",
            "authorization", "api_key", "prompt", "provider_response",
        }
        self.assertFalse(forbidden & {key.lower() for key in _keys(report)})
        self.assertEqual(report["authored_geometry"]["labels"], [
            "PROVISIONAL", "NOT APPROVED", "INVALID BUILD PLAN",
        ])

    def test_failure_report_uses_only_an_allowlisted_category(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "m32-self-check.json"
            with patch(
                "scripts.m32_self_check.run_m32_self_check",
                side_effect=AssertionError("synthetic source details must not be persisted"),
            ):
                report = write_report(destination)
            persisted = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failure_category"], "deterministic_contract_assertion_failed")
        self.assertEqual(persisted, report)
        self.assertNotIn("synthetic source details", json.dumps(persisted))
