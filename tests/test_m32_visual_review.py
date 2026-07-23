"""Focused persistent-bundle coverage for M32 Windows visual review."""
from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from fxd_geometry.project import FxdProject
from scripts.m32_self_check import VISUAL_REVIEW_SCHEMA
from scripts.m32_visual_review import (
    APPLICATION_SCREENSHOT_NAME,
    CHECKLIST_NAME,
    REPORT_NAME,
    SOFTWARE_SCREENSHOT_NAME,
    create_visual_review_bundle,
)


class M32VisualReviewBundleTests(unittest.TestCase):
    def test_bundle_persists_exact_reloadable_governed_scenario_outside_repository(self):
        with tempfile.TemporaryDirectory() as parent:
            bundle = Path(parent) / "persistent-review"
            report = create_visual_review_bundle(bundle)
            project_path = bundle / report["visual_review_bundle"]["reloadable_project"]
            step_path = bundle / report["visual_review_bundle"]["synthetic_step"]
            restored = FxdProject.load(project_path)

            self.assertTrue(bundle.is_dir())
            self.assertEqual(report["schema"], VISUAL_REVIEW_SCHEMA)
            self.assertEqual(report["fixture_build"]["requested_station_count"], 5)
            self.assertEqual(report["fixture_build"]["accepted_feasible_station_count"], 5)
            self.assertAlmostEqual(report["fixture_build"]["maximum_fixture_length_mm"], 1219.2)
            self.assertFalse(report["authored_geometry"]["aabb_fallback_used"])
            self.assertGreater(report["authored_geometry"]["real_ocp_component_count"], 0)
            self.assertEqual(report["authored_geometry"]["local_station_plate_count"], 5)
            self.assertEqual(report["authored_geometry"]["provisional_closed_clamp_count"], 5)
            self.assertEqual(report["authored_geometry"]["provisional_open_clamp_envelope_count"], 5)
            self.assertTrue(report["authored_geometry"]["supplier_neutral_clamps_excluded_from_authored_ocp"])
            self.assertTrue(report["access_review"]["loading_and_unloading_evaluated"])
            self.assertTrue(report["access_review"]["first_and_last_station_end_clearance"])
            self.assertTrue(report["access_review"]["trapped_part_detected"])
            self.assertEqual(report["access_review"]["weld_access_status"],
                             "not_evaluated_unconfirmed_weld_intent")
            self.assertTrue(report["authored_geometry"]["provisional"])
            self.assertTrue(report["release_gates"]["engineering_approval_blocked"])
            self.assertTrue(report["release_gates"]["release_export_blocked"])
            self.assertEqual(restored.fixture_build.authoring_state, "provisional")
            self.assertEqual(sha256(step_path.read_bytes()).hexdigest(), restored.product.source_sha256)
            self.assertEqual(step_path.read_bytes(), restored.product.source_bytes)
            for name in (REPORT_NAME, CHECKLIST_NAME, SOFTWARE_SCREENSHOT_NAME):
                self.assertTrue((bundle / name).is_file())
            self.assertFalse((bundle / APPLICATION_SCREENSHOT_NAME).exists())

    def test_persisted_reports_are_redacted_and_contain_no_private_absolute_path(self):
        with tempfile.TemporaryDirectory() as parent:
            bundle = Path(parent) / "redacted-review"
            create_visual_review_bundle(bundle)
            public_text = "\n".join(
                (bundle / name).read_text(encoding="utf-8")
                for name in (REPORT_NAME, CHECKLIST_NAME, "m32-visual-review-summary.txt")
            ).lower()
            parsed = json.loads((bundle / REPORT_NAME).read_text(encoding="utf-8"))

        self.assertNotIn(str(bundle).lower(), public_text)
        for forbidden in (
            "openai_api_key", "authorization header", "provider_response",
            "source_step_base64", "customer cad",
        ):
            self.assertNotIn(forbidden, public_text)
        self.assertFalse(parsed["network_provider_used"])
        self.assertFalse(parsed["engineering_disposition"]["software_acceptance_is_engineering_approval"])

    def test_repository_destination_is_rejected(self):
        repository_child = Path(__file__).resolve().parents[1] / "forbidden-m32-review-bundle"
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            create_visual_review_bundle(repository_child)


if __name__ == "__main__":
    unittest.main()
