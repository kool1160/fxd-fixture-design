"""Local-first project operations: recovery, diagnostics, preferences, and export.

This module deliberately contains no engineering rules.  It coordinates existing
project and validation contracts and keeps user preferences separate from them.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .export import (
    ExportError,
    FabricationPackage,
    build_fabrication_package,
    write_fabrication_package,
)
from .project import FxdProject


class OperationsError(ValueError):
    """Raised when a local operational artifact is malformed."""


@dataclass(frozen=True)
class DiagnosticEvent:
    event: str
    timestamp_utc: float
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"event": self.event, "timestamp_utc": self.timestamp_utc,
                "details": self.details}


class StructuredLog:
    """Append-only JSONL log with no source geometry payload."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def record(self, event: str, **details: Any) -> DiagnosticEvent:
        item = DiagnosticEvent(event, time.time(), details)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item.as_dict(), sort_keys=True) + "\n")
        return item


class ProjectRecovery:
    """Crash-safe autosave and explicit recovery discovery."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)
        self.autosave_path = self.project_path.with_suffix(self.project_path.suffix + ".autosave")

    def autosave(self, project: FxdProject) -> Path:
        return project.save(self.autosave_path)

    def available(self) -> bool:
        if not self.autosave_path.is_file():
            return False
        if not self.project_path.exists():
            return True
        return self.autosave_path.stat().st_mtime >= self.project_path.stat().st_mtime

    def recover(self) -> FxdProject:
        if not self.autosave_path.is_file():
            raise OperationsError("no autosave is available")
        return FxdProject.load(self.autosave_path)


DEFAULT_PREFERENCES = {"schema_version": 1, "theme": "dark", "window_geometry": "1180x760"}


def load_preferences(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return dict(DEFAULT_PREFERENCES)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OperationsError(f"invalid preferences: {exc}") from exc
    if value.get("schema_version") != 1 or set(value) - set(DEFAULT_PREFERENCES):
        raise OperationsError("unsupported preferences schema")
    return {**DEFAULT_PREFERENCES, **value}


def save_preferences(path: str | Path, preferences: dict[str, Any]) -> Path:
    unknown = set(preferences) - set(DEFAULT_PREFERENCES)
    if unknown or preferences.get("schema_version", 1) != 1:
        raise OperationsError("preferences may not contain engineering or unknown fields")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({**DEFAULT_PREFERENCES, **preferences}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def project_export_block_reason(project: FxdProject) -> str | None:
    """Return the authoritative project-level reason export must fail closed."""
    workflow = getattr(project, "workflow", None)
    if workflow is not None and not workflow.has_accepted_manufacturing_orientation():
        return (
            "interactive workflow requires an accepted manufacturing orientation "
            "for the current source before export"
        )
    proposal = getattr(project, "fixture_proposal", None)
    if proposal is not None:
        from .ai_fixture_engineer import proposal_engineering_context_identity
        orientation = workflow.setup.manufacturing_orientation if workflow else None
        stale = proposal.stale_reason(
            project.product.source_sha256, orientation.identity if orientation else None,
            proposal_engineering_context_identity(project)
            if workflow and workflow.has_accepted_manufacturing_orientation() else None,
        )
        if stale:
            return f"stale fixture proposal cannot be exported: {stale}"
        if proposal.blocker_count:
            return "fixture proposal has deterministic blockers and cannot be exported"
        if proposal.proposal_decision != "accepted_for_engineering_review":
            return "fixture proposal must be accepted for engineering review before export"
    if project.active_validation.blocked:
        return "invalid deterministic validation result cannot be exported"
    if project.suppressed_features:
        return (
            "suppressed fixture features must be regenerated and deterministically "
            "revalidated before export"
        )
    if project.active.corrections:
        return (
            "active fixture corrections must be regenerated and deterministically "
            "revalidated before export"
        )
    if project.fixture_build is not None:
        from .fabrication_workflow import AdjustmentState, validate_fixture_build_plan
        build_validation = validate_fixture_build_plan(project.product, project.fixture_build)
        if build_validation.blocked:
            return "invalid deterministic fixture-build validation result cannot be exported"
        if build_validation.status != "valid":
            return "fixture-build validation status must be valid before export"
        if project.fixture_build.requirements.adjustment_state in {
                AdjustmentState.PROVISIONAL, AdjustmentState.PROVE_OUT,
                AdjustmentState.REVALIDATION_REQUIRED}:
            return (
                "provisional fixture-build adjustment state must be locked or doweled and "
                "deterministically revalidated before export"
            )
    return None


def export_project_package(project: FxdProject, destination: str | Path,
                           *, kernel: object | None = None) -> tuple[Path, ...]:
    """Export through the same deterministic, fail-closed gate used by the core."""
    block_reason = project_export_block_reason(project)
    if block_reason is not None:
        raise ExportError(block_reason)
    fixture_build_assembly = None
    if project.fixture_build is not None:
        if kernel is None:
            raise ExportError("real OCP kernel is required to export authored fixture-build geometry")
        from .fabrication_workflow import FixtureBuildError, author_fixture_build
        try:
            fixture_build_assembly = author_fixture_build(project.fixture_build, project.product, kernel)
        except (FixtureBuildError, RuntimeError) as exc:
            raise ExportError(f"fixture-build authoring failed closed: {exc}") from exc
    manufacturing = None
    if kernel is not None:
        from .manufacturing import generate_manufacturing_geometry
        manufacturing = generate_manufacturing_geometry(project.active, kernel)
    package: FabricationPackage = build_fabrication_package(
        project.active, revision=project.revision_id,
        validation=project.active_validation, manufacturing=manufacturing)
    paths = list(write_fabrication_package(package, destination))
    if project.workflow is not None:
        target = Path(destination) / "interactive-workflow-evidence.json"
        validation = project.active_validation
        workflow = project.workflow.to_dict()
        workflow["customer_tooling"] = [
            {key: value for key, value in item.items() if key != "source_path"}
            for item in workflow.get("customer_tooling", [])
        ]
        evidence = {
            "format": "fxd-interactive-review-evidence-v1",
            "source_name": project.product.source_name,
            "source_sha256": project.product.source_sha256,
            "active_concept": project.active_concept,
            "revision": project.revision_id,
            "validation_status": validation.status,
            "validation_version": validation.version,
            "evidence_digest": validation.evidence_digest,
            "findings": [item.__dict__ for item in validation.findings],
            "workflow": workflow,
            "approval_boundary": (
                "Engineering review only. This package is not production release, "
                "structural certification, weld approval, or safety approval."
            ),
        }
        target.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(target)
    if fixture_build_assembly is not None:
        from .fabrication_workflow import FixtureBuildError, write_fixture_build_package
        try:
            paths.extend(write_fixture_build_package(
                fixture_build_assembly, project.fixture_build, Path(destination) / "m30-manufacturing",
                project_validation=project.active_validation,
            ))
        except FixtureBuildError as exc:
            raise ExportError(f"fixture-build package failed closed: {exc}") from exc
    return tuple(paths)
