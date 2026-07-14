"""Deterministic, vendor-neutral fabrication-package export.

The current geometry proof contains AABBs rather than B-Rep solids. Exports
therefore identify themselves as proof-layer artifacts and never imply CAD
fidelity, certification, or production approval.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .access import AccessAnalysis
from .concepts import CompleteFixtureConcept
from .fixture import FixtureFeature
from .manufacturing import ManufacturingGeometry
from .tooling import ToolingLibrary, generic_tooling_library


class ExportError(ValueError):
    """Raised when a concept cannot be exported safely."""


@dataclass(frozen=True)
class FabricationPackage:
    """In-memory deterministic package artifacts, all encoded as UTF-8 text."""

    manifest: str
    step: str
    dxf: str
    bom: str
    setup: str
    validation: str

    def files(self) -> dict[str, str]:
        return {
            "manifest.json": self.manifest,
            "fixture.step": self.step,
            "profiles.dxf": self.dxf,
            "bom.json": self.bom,
            "setup.md": self.setup,
            "validation.json": self.validation,
        }


def _number(value: float) -> str:
    return format(value, ".9g")


def _box(feature: FixtureFeature) -> tuple[float, float, float, float, float, float]:
    low, high = feature.bounds.minimum, feature.bounds.maximum
    return low.x, low.y, low.z, high.x, high.y, high.z


def _step(concept: CompleteFixtureConcept, revision: str,
          manufacturing: ManufacturingGeometry | None = None) -> str:
    if manufacturing is not None:
        # The kernel owns STEP serialization. Decode only after it has emitted
        # a neutral ISO-10303 file; no vendor object crosses this contract.
        return manufacturing.step_bytes.decode("utf-8")
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('FXD proof-layer fixture export'),'2;1');",
        "FILE_NAME('fixture.step','2026-01-01T00:00:00',('FXD'),('FXD'),'FXD','FXD','');",
        "FILE_SCHEMA(('FXD_PROOF_LAYER'));",
        "ENDSEC;",
        "DATA;",
        f"#1=FXD_PACKAGE('{concept.identity}','{revision}','mm','ENGINEERING_REVIEW_REQUIRED');",
    ]
    for index, feature in enumerate(concept.fixture.features, 2):
        values = ",".join(_number(value) for value in _box(feature))
        lines.append(f"#{index}=FXD_BOX('{feature.identity}','{feature.kind}',({values}));")
    lines += ["ENDSEC;", "END-ISO-10303-21;"]
    return "\n".join(lines) + "\n"


def _dxf(concept: CompleteFixtureConcept) -> str:
    # Rectangular XY envelopes are the only profiles supported by the AABB proof.
    lines = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for feature in concept.fixture.features:
        xmin, ymin, _, xmax, ymax, _ = _box(feature)
        if xmax == xmin:
            xmax += 0.001
        if ymax == ymin:
            ymax += 0.001
        points = ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin))
        lines += ["0", "LWPOLYLINE", "8", feature.kind, "100", "AcDbEntity", "100", "AcDbPolyline", "90", "5", "70", "1"]
        for x, y in points:
            lines += ["10", _number(x), "20", _number(y)]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(lines) + "\n"


def _bom(concept: CompleteFixtureConcept, tooling: ToolingLibrary) -> dict[str, object]:
    counts: dict[tuple[str, str], int] = {}
    for feature in concept.fixture.features:
        key = (feature.kind, feature.kind.replace("_", " ").title())
        counts[key] = counts.get(key, 0) + 1
    items = [{"identity": identity, "description": description, "quantity": quantity, "source": "generated feature"}
             for (identity, description), quantity in sorted(counts.items())]
    clamp_count = sum(1 for feature in concept.fixture.features if feature.kind == "clamp_mount")
    if clamp_count:
        selected = tooling.select("clamp")
        if selected is None:
            raise ExportError("concept contains clamps but no neutral clamp tooling is available")
        items.append({"identity": selected.item.identity, "description": selected.item.kind,
                      "quantity": clamp_count, "source": selected.item.source,
                      "license": selected.item.license})
    return {"units": "mm", "items": sorted(items, key=lambda item: str(item["identity"])),
            "warnings": ["BOM quantities are proof-layer reconciliation and require engineering review."]}


def _validation(concept: CompleteFixtureConcept, access: AccessAnalysis | None) -> dict[str, object]:
    findings = [{"code": item.code, "severity": item.severity, "feature": item.feature_identity, "message": item.message}
                for item in concept.fixture.findings]
    if access is not None:
        findings.extend({"code": item.code, "severity": item.severity, "feature": item.feature_identity,
                         "request": item.request_identity, "message": item.message} for item in access.findings)
    return {"status": "engineering_review_required", "units": "mm", "findings": findings,
            "assumptions": ["AABB evidence is not B-Rep, tolerance-stack, weld-quality, or robot-motion validation."]}


def build_fabrication_package(concept: CompleteFixtureConcept, revision: str = "A",
                              access: AccessAnalysis | None = None,
                              tooling: ToolingLibrary | None = None,
                              manufacturing: ManufacturingGeometry | None = None) -> FabricationPackage:
    """Build deterministic artifacts for an eligible concept.

    Provisional concepts may be exported for review. Invalid concepts and
    concepts with known access errors may not be exported.
    """
    if not revision.strip() or any(char in revision for char in "\\/:\n"):
        raise ExportError("revision must be a non-empty path-safe identifier")
    if not concept.eligible_for_recommendation:
        raise ExportError("invalid fixture concepts cannot be exported")
    if access is not None and access.blocked:
        raise ExportError("fixture concepts with blocked weld, operator, robot, or unload access cannot be exported")
    tooling = tooling or generic_tooling_library()
    validation = _validation(concept, access)
    bom = _bom(concept, tooling)
    manifest_data = {
        "format": "fxd-fabrication-package-proof-v1", "concept": concept.identity,
        "revision": revision, "units": "mm", "release_status": "engineering_review_required",
        "production_approval": False, "source_sha256": concept.fixture.source_sha256,
        "artifacts": ["fixture.step", "profiles.dxf", "bom.json", "setup.md", "validation.json"],
        "notes": ["STEP and DXF are proof-layer AABB exports unless kernel-authored geometry is supplied.",
                  "This package is not certified, validated, or approved for production."],
    }
    if manufacturing is not None:
        if manufacturing.concept_identity != concept.identity or manufacturing.units != "mm":
            raise ExportError("manufacturing geometry does not match the concept contract")
        manifest_data["geometry_source"] = "reviewed_real_kernel"
        manifest_data["manufacturing_solids"] = list(manufacturing.identities)
    setup = "\n".join([f"# Fixture setup — {concept.identity} revision {revision}", "",
        "Status: ENGINEERING REVIEW REQUIRED (not production approval).", "", "## Strategy",
        f"- Locating: {concept.locating_strategy}", f"- Clamping: {concept.clamping_strategy}",
        "- Units: millimetres", "", "## Assumptions and review actions",
        "- Confirm datum/contact surfaces, clamp forces, tolerances, weld sequence, access, and unload path.",
        "- Review validation.json before any fabrication decision.", ""])
    return FabricationPackage(
        json.dumps(manifest_data, indent=2, sort_keys=True) + "\n", _step(concept, revision, manufacturing), _dxf(concept),
        json.dumps(bom, indent=2, sort_keys=True) + "\n", setup,
        json.dumps(validation, indent=2, sort_keys=True) + "\n")


def write_fabrication_package(package: FabricationPackage, output_dir: str | Path) -> tuple[Path, ...]:
    """Write package files in stable order and return their paths."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, content in package.files().items():
        path = root / name
        path.write_text(content, encoding="utf-8", newline="\n")
        paths.append(path)
    return tuple(paths)
