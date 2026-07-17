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

from .export import FabricationPackage, build_fabrication_package, write_fabrication_package
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


def export_project_package(project: FxdProject, destination: str | Path,
                           *, kernel: object | None = None) -> tuple[Path, ...]:
    """Export through the same deterministic, fail-closed gate used by the core."""
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
    return tuple(paths)
