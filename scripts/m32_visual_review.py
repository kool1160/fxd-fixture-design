"""Prepare the persistent, offline M32 Windows engineering-review bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fxd_geometry.project import FxdProject
from scripts.m32_self_check import (
    VISUAL_REVIEW_SCHEMA,
    _run_m32_scenario,
    _write_json,
    _write_summary_screenshot,
)


REPORT_NAME = "m32-visual-review-report.json"
SUMMARY_NAME = "m32-visual-review-summary.txt"
CHECKLIST_NAME = "m32-human-engineering-review-checklist.md"
SOFTWARE_SCREENSHOT_NAME = "m32-software-evidence.png"
APPLICATION_SCREENSHOT_NAME = "m32-application-initial-view.png"


def _outside_repository(path: Path) -> Path:
    destination = path.resolve()
    repository = Path(__file__).resolve().parents[1]
    if destination == repository or destination.is_relative_to(repository):
        raise ValueError("M32 visual-review artifacts must remain outside the repository")
    return destination


def _human_checklist() -> str:
    return """# M32 qualified human fixture-engineering review

This bundle is synthetic software-review evidence. Its deterministic build and
authored-geometry gates passed, but it remains **PROVISIONAL** and **NOT
APPROVED** until qualified fixture-engineering review is recorded. Software
acceptance is not engineering approval.

Record qualified engineering judgment for every item before any production decision:

- [ ] Fixture practicality for the intended operation
- [ ] Loading path and unloading path
- [ ] Adjacent-station and component interference
- [ ] Datum locating, supports, hard stops, and repeatability
- [ ] Clamp reach, force direction, open envelope, and suitability
- [ ] Weld, tack, torch, and consumable access using confirmed weld intent
- [ ] Trapped-part and removal risks
- [ ] Operator reach, visibility, ergonomics, and access
- [ ] Component and assembly manufacturability
- [ ] Base mounting and shop-interface suitability
- [ ] Heat, distortion, spatter, cleaning, and maintenance provisions
- [ ] Pinch points, guarding, and all applicable safety review
- [ ] Structural adequacy under qualified calculations and review
- [ ] Accept the governed five-station arrangement or return it for redesign
- [ ] Final production approval by authorized people under the applicable process

Do not use this checklist or the displayed geometry as a release, certification, or safety claim.
"""


def create_visual_review_bundle(destination: Path) -> dict[str, object]:
    """Create persistent governed artifacts and return a redacted manifest."""
    bundle = _outside_repository(destination)
    bundle.mkdir(parents=True, exist_ok=False)
    report, source_path, project_path = _run_m32_scenario(bundle)
    restored = FxdProject.load(project_path)
    if restored.fixture_build is None or restored.fixture_build.authoring_state != "provisional":
        raise AssertionError("visual-review project did not reload its provisional M32 build")

    _write_summary_screenshot(report, bundle / SOFTWARE_SCREENSHOT_NAME)
    (bundle / CHECKLIST_NAME).write_text(_human_checklist(), encoding="utf-8")
    summary = (
        "FXD M32 governed synthetic visual review\n"
        "Requested stations: 5\n"
        "Accepted feasible stations: 5\n"
        f"Calculated pitch: {report['fixture_build']['calculated_pitch_mm']:.1f} mm\n"
        "Maximum fixture length: 1219.2 mm\n"
        f"Real OCP authored components: {report['authored_geometry']['real_ocp_component_count']}\n"
        "Disposition: DETERMINISTIC GATES PASSED / PROVISIONAL / NOT APPROVED\n"
        "Engineering approval: blocked\n"
        "Release export: blocked\n"
        "Source CAD bytes and SHA: unchanged\n"
        "Network provider requests: none\n"
        "Qualified human fixture-engineering review remains required.\n"
    )
    (bundle / SUMMARY_NAME).write_text(summary, encoding="utf-8")

    manifest = {
        **report,
        "schema": VISUAL_REVIEW_SCHEMA,
        "visual_review_bundle": {
            "synthetic_step": source_path.name,
            "reloadable_project": project_path.name,
            "redacted_summary": SUMMARY_NAME,
            "human_checklist": CHECKLIST_NAME,
            "software_evidence_screenshot": SOFTWARE_SCREENSHOT_NAME,
            "application_initial_screenshot": APPLICATION_SCREENSHOT_NAME,
            "artifacts_persist_after_application_close": True,
            "artifacts_outside_repository": True,
        },
        "engineering_disposition": {
            "software_acceptance_is_engineering_approval": False,
            "qualified_human_review_required": True,
        },
    }
    _write_json(bundle / REPORT_NAME, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the offline M32 visual-review bundle.")
    parser.add_argument("--bundle-directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = create_visual_review_bundle(args.bundle_directory)
    except Exception:
        print("FXD_M32_VISUAL_REVIEW_BUNDLE=failed")
        return 1
    artifacts = report["visual_review_bundle"]
    print("FXD_M32_VISUAL_REVIEW_BUNDLE=prepared")
    print(f"FXD_M32_STEP_FILE={artifacts['synthetic_step']}")
    print(f"FXD_M32_PROJECT_FILE={artifacts['reloadable_project']}")
    print(f"FXD_M32_REPORT_FILE={REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
