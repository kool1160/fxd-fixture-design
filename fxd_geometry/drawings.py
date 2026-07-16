"""Deterministic review drawings derived from Milestone 23 components.

The renderer is intentionally small and CAD-neutral.  It presents the
authoritative component bounds, holes, interfaces, exports, and validation
evidence; it does not invent drafting or production-approval semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re

from .component_geometry import ManufacturingAssembly, ManufacturingComponent


class DrawingPackageError(ValueError):
    """Raised when drawing evidence is incomplete or cannot reconcile."""


APPROVAL_TEXT = "ENGINEERING REVIEW REQUIRED"
NOT_RELEASED_TEXT = "NOT RELEASED FOR PRODUCTION"
DRAWING_FORMAT = "fxd-drawing-package-v1"


@dataclass(frozen=True)
class DrawingFinding:
    code: str
    severity: str
    message: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class RevisionBlock:
    drawing_revision: str
    title: str
    concept_identity: str
    source_sha256: str
    approval_text: str = APPROVAL_TEXT
    release_text: str = NOT_RELEASED_TEXT

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.drawing_revision, self.title,
                                               self.concept_identity, self.source_sha256)):
            raise DrawingPackageError("drawing title block is incomplete")
        if self.approval_text != APPROVAL_TEXT or self.release_text != NOT_RELEASED_TEXT:
            raise DrawingPackageError("drawing approval boundary text is fixed")

    def to_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class DrawingView:
    identity: str
    source_component_identity: str | None
    orientation: str
    scale: str
    extents_mm: tuple[float, float, float]
    hidden_line_policy: str
    section_evidence: tuple[str, ...] = ()
    layout_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.orientation.strip() or not self.scale.strip():
            raise DrawingPackageError("drawing view identity, orientation, and scale are required")
        if len(self.extents_mm) != 3 or any(value <= 0 for value in self.extents_mm):
            raise DrawingPackageError("drawing view extents must be positive millimetres")

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"extents_mm": list(self.extents_mm),
                                "section_evidence": list(self.section_evidence),
                                "layout_evidence": list(self.layout_evidence)}


@dataclass(frozen=True)
class DrawingDimension:
    identity: str
    source_component_identity: str
    kind: str
    value_mm: float
    source_evidence: tuple[str, ...]
    tolerance_mm: float | None = None
    fit: str | None = None
    datum: str | None = None
    status: str = "traceable"

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.source_component_identity.strip() or not self.kind.strip():
            raise DrawingPackageError("drawing dimension identity and source are required")
        if self.value_mm <= 0 or not self.source_evidence:
            raise DrawingPackageError("drawing dimension must have positive value and evidence")
        if self.tolerance_mm is not None and self.tolerance_mm < 0:
            raise DrawingPackageError("drawing tolerance must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"source_evidence": list(self.source_evidence)}


@dataclass(frozen=True)
class DrawingAnnotation:
    identity: str
    text: str
    source_component_identity: str | None
    rule: str
    evidence: tuple[str, ...]
    kind: str = "note"

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.text.strip() or not self.rule.strip() or not self.evidence:
            raise DrawingPackageError("drawing annotation must be traceable")

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": list(self.evidence)}


@dataclass(frozen=True)
class HoleTableRow:
    identity: str
    component_identity: str
    x_mm: float
    y_mm: float
    datum: str
    diameter_mm: float
    depth_mm: float
    kind: str
    fit: str
    tolerance_mm: float | None
    source_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.component_identity.strip() or not self.datum.strip():
            raise DrawingPackageError("hole table identity and datum are required")
        if self.diameter_mm <= 0 or self.depth_mm <= 0 or not self.source_evidence:
            raise DrawingPackageError("hole table geometry evidence is incomplete")

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"source_evidence": list(self.source_evidence)}


@dataclass(frozen=True)
class BomEntry:
    item_number: int
    component_identity: str
    part_number: str
    revision: str
    description: str
    classification: str
    material: str
    thickness_mm: float | None
    section_size_mm: tuple[float, ...]
    quantity: int
    finish: str
    process: str
    tooling_identity: str | None
    step_filename: str
    dxf_filename: str | None

    def __post_init__(self) -> None:
        if self.item_number < 1 or self.quantity < 1:
            raise DrawingPackageError("BOM item and quantity must be positive")
        if not all(value.strip() for value in (self.component_identity, self.part_number,
                                                self.revision, self.description, self.material,
                                                self.finish, self.process, self.step_filename)):
            raise DrawingPackageError("BOM entry is incomplete")

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"section_size_mm": list(self.section_size_mm)}


@dataclass(frozen=True)
class DrawingSheet:
    identity: str
    title: str
    sheet_number: int
    required: bool
    revision_block: RevisionBlock
    views: tuple[DrawingView, ...]
    dimensions: tuple[DrawingDimension, ...]
    annotations: tuple[DrawingAnnotation, ...]
    hole_table: tuple[HoleTableRow, ...] = ()
    component_identities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.title.strip() or self.sheet_number < 1:
            raise DrawingPackageError("drawing sheet identity, title, and number are required")
        if self.required and not self.views:
            raise DrawingPackageError("required drawing sheet cannot be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "title": self.title, "sheet_number": self.sheet_number,
            "required": self.required, "revision_block": self.revision_block.to_dict(),
            "views": [item.to_dict() for item in self.views],
            "dimensions": [item.to_dict() for item in self.dimensions],
            "annotations": [item.to_dict() for item in self.annotations],
            "hole_table": [item.to_dict() for item in self.hole_table],
            "component_identities": list(self.component_identities),
        }


@dataclass(frozen=True)
class DrawingPackage:
    source_sha256: str
    concept_identity: str
    manufacturing_evidence_digest: str
    revision: str
    sheets: tuple[DrawingSheet, ...]
    bom: tuple[BomEntry, ...]
    findings: tuple[DrawingFinding, ...]
    pdf_bytes: bytes
    pdf_digest: str

    @property
    def valid(self) -> bool:
        return bool(self.pdf_bytes) and not any(item.severity == "error" for item in self.findings)

    @property
    def blocked(self) -> bool:
        return not self.valid

    @property
    def page_count(self) -> int:
        return len(self.sheets)

    @property
    def evidence_digest(self) -> str:
        """Digest all deterministic drawing evidence, not only rendered bytes."""
        encoded = json.dumps(self.intent_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def intent_dict(self) -> dict[str, object]:
        return {
            "format": DRAWING_FORMAT, "source_sha256": self.source_sha256,
            "concept_identity": self.concept_identity,
            "manufacturing_evidence_digest": self.manufacturing_evidence_digest,
            "revision": self.revision,
            "sheets": [item.to_dict() for item in self.sheets],
            "bom": [item.to_dict() for item in self.bom],
            "findings": [item.__dict__ | {"evidence": list(item.evidence)} for item in self.findings],
            "pdf_digest": self.pdf_digest, "page_count": self.page_count,
        }

    def manifest_dict(self) -> dict[str, object]:
        return self.intent_dict() | {
            "pdf_filename": "fixture-drawings.pdf",
            "approval_boundary": [APPROVAL_TEXT, NOT_RELEASED_TEXT],
            "step_filenames": [item.step_filename for item in self.bom],
            "dxf_filenames": [item.dxf_filename for item in self.bom if item.dxf_filename],
            "evidence_digest": self.evidence_digest,
        }


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _dim(component: ManufacturingComponent, kind: str, value: float, evidence: str,
         *, tolerance: float | None = None, fit: str | None = None, datum: str | None = None) -> DrawingDimension:
    return DrawingDimension(f"dim-{component.identity}-{kind}", component.identity, kind, value,
                            (evidence,), tolerance, fit, datum)


def _bounds_dimensions(component: ManufacturingComponent) -> tuple[DrawingDimension, ...]:
    low, high = component.bounds.minimum, component.bounds.maximum
    return (
        _dim(component, "overall-length", high.x - low.x, "B-Rep component bounds X extents", datum="FIXTURE-DATUM"),
        _dim(component, "overall-width", high.y - low.y, "B-Rep component bounds Y extents", datum="FIXTURE-DATUM"),
        _dim(component, "overall-height", high.z - low.z, "B-Rep component bounds Z extents", datum="FIXTURE-DATUM"),
    )


def _holes(component: ManufacturingComponent) -> tuple[HoleTableRow, ...]:
    return tuple(HoleTableRow(
        hole.identity, component.identity, hole.center_mm.x, hole.center_mm.y, "FIXTURE-DATUM",
        hole.radius_mm * 2.0, hole.depth_mm, hole.kind, hole.fit, hole.tolerance_mm, hole.evidence,
    ) for hole in component.holes)


def _view(identity: str, component: ManufacturingComponent | None, orientation: str,
          extents: tuple[float, float, float], *, section: tuple[str, ...] = ()) -> DrawingView:
    return DrawingView(identity, component.identity if component else None, orientation, "fit-to-sheet",
                       extents, "hidden-lines-deterministic", section,
                       ("authoritative Milestone 23 component bounds",))


def _component_annotation(component: ManufacturingComponent) -> tuple[DrawingAnnotation, ...]:
    notes = [DrawingAnnotation(f"note-{component.identity}-review", APPROVAL_TEXT,
                               component.identity, "drawing_review_boundary", component.evidence)]
    if component.weld_intent:
        notes.append(DrawingAnnotation(f"note-{component.identity}-weld",
            f"WELD INTENT: {component.weld_intent}. Formal weld symbol not supported; review note only.",
            component.identity, "explicit_weld_intent", (component.weld_intent,)))
    for index, assumption in enumerate(component.assumptions, 1):
        notes.append(DrawingAnnotation(f"note-{component.identity}-assumption-{index}",
                                       f"ASSUMPTION: {assumption}", component.identity,
                                       "component_assumption", (assumption,)))
    return tuple(notes)


def _bom(assembly: ManufacturingAssembly) -> tuple[BomEntry, ...]:
    exports = {item.component_identity: item for item in assembly.exports}
    result = []
    for number, component in enumerate(sorted(assembly.components, key=lambda item: item.identity), 1):
        export = exports.get(component.identity)
        if export is None or not export.step_filename:
            raise DrawingPackageError(f"missing STEP export for component {component.identity}")
        result.append(BomEntry(number, component.identity, component.part_number, component.revision,
                               component.description, component.classification.value, component.material,
                               component.thickness_mm, component.section_size_mm, component.quantity,
                               component.finish, component.manufacturing_process,
                               component.purchased_tooling_identity, export.step_filename, export.dxf_filename))
    if len({item.part_number for item in result}) != len(result):
        raise DrawingPackageError("BOM part numbers must be unique")
    return tuple(result)


def _validate_inputs(assembly: ManufacturingAssembly, validation: object) -> None:
    if assembly.units != "mm" or not assembly.source_sha256 or not assembly.concept_identity:
        raise DrawingPackageError("manufacturing assembly identity or units are invalid")
    if assembly.blocked:
        raise DrawingPackageError("blocked manufacturing assembly cannot produce drawings")
    if validation is None or getattr(validation, "blocked", True):
        raise DrawingPackageError("blocked or missing authoritative fixture validation")
    if getattr(validation, "concept_identity", assembly.concept_identity) != assembly.concept_identity:
        raise DrawingPackageError("fixture validation concept identity does not match assembly")
    if getattr(validation, "source_sha256", assembly.source_sha256) != assembly.source_sha256:
        raise DrawingPackageError("fixture validation source identity does not match assembly")
    if not getattr(validation, "evidence_digest", None):
        raise DrawingPackageError("authoritative validation evidence digest is required")
    identities = {item.identity for item in assembly.components}
    if identities != {item.component_identity for item in assembly.exports}:
        raise DrawingPackageError("component and export identities do not reconcile")


def _pdf_escape(value: str) -> str:
    value = value.encode("ascii", "replace").decode("ascii")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf(sheets: tuple[DrawingSheet, ...], bom: tuple[BomEntry, ...],
                source_sha256: str, revision: str) -> bytes:
    """Render stable text-and-line review sheets without timestamps or metadata."""
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
                            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids = []
    for sheet in sheets:
        content_id = len(objects) + 1
        lines = [sheet.title, f"SHEET {sheet.sheet_number}  REV {revision}",
                 f"CONCEPT {sheet.revision_block.concept_identity}",
                 f"SOURCE SHA256 {source_sha256}", APPROVAL_TEXT, NOT_RELEASED_TEXT, "UNITS: MILLIMETRES", ""]
        for view in sheet.views:
            lines.append(f"VIEW {view.identity}: {view.orientation} {view.scale} extents={view.extents_mm}")
        for dimension in sheet.dimensions:
            suffix = f" fit={dimension.fit}" if dimension.fit else ""
            lines.append(f"DIM {dimension.identity}: {dimension.kind} {dimension.value_mm:.9g} mm{suffix}")
        for row in sheet.hole_table:
            lines.append(f"HOLE {row.identity}: {row.component_identity} X={row.x_mm:.9g} Y={row.y_mm:.9g} DIA={row.diameter_mm:.9g} mm")
        for annotation in sheet.annotations:
            lines.append(f"NOTE {annotation.identity}: {annotation.text}")
        if sheet.identity == "exploded-assembly":
            lines.append("BOM ITEMS: " + ", ".join(f"{item.item_number} {item.part_number}" for item in bom))
        stream_lines = ["BT", "/F1 9 Tf", "36 560 Td"]
        for index, line in enumerate(lines):
            if index:
                stream_lines.append("0 -13 Td")
            stream_lines.append(f"({_pdf_escape(line)}) Tj")
        stream_lines.append("ET")
        content = "\n".join(stream_lines).encode("ascii")
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream")
        page_id = len(objects) + 1
        page_ids.append(page_id)
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 3 0 R >> >> /Contents " + str(content_id).encode("ascii") + b" 0 R >>")
    objects[1] = (b"<< /Type /Pages /Kids [" + b" ".join(f"{page_id} 0 R".encode("ascii") for page_id in page_ids) +
                  b"] /Count " + str(len(page_ids)).encode("ascii") + b" >>")
    output = bytearray(b"%PDF-1.4\n%FXD\n")
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii")); output.extend(value); output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def generate_drawing_package(assembly: ManufacturingAssembly, validation: object,
                             *, revision: str = "A") -> DrawingPackage:
    """Create a deterministic review package from one validated assembly."""
    _validate_inputs(assembly, validation)
    if not revision.strip() or any(char in revision for char in "\\/:\n"):
        raise DrawingPackageError("drawing revision must be a non-empty path-safe identifier")
    components = tuple(sorted(assembly.components, key=lambda item: item.identity))
    bom = _bom(assembly)
    block = RevisionBlock(revision, "FXD FIXTURE DRAWING PACKAGE", assembly.concept_identity,
                          assembly.source_sha256)
    all_low = [min(item.bounds.minimum.x for item in components),
               min(item.bounds.minimum.y for item in components),
               min(item.bounds.minimum.z for item in components)]
    all_high = [max(item.bounds.maximum.x for item in components),
                max(item.bounds.maximum.y for item in components),
                max(item.bounds.maximum.z for item in components)]
    overall = tuple(high - low for low, high in zip(all_low, all_high))
    assembly_dims = tuple(DrawingDimension(f"dim-assembly-{axis}", components[0].identity,
                                           f"fixture-overall-{axis}", value,
                                           ("authoritative manufacturing component bounds",), datum="FIXTURE-DATUM")
                          for axis, value in zip(("length", "width", "height"), overall))
    assembly_notes = (DrawingAnnotation("note-assembly-validation", f"VALIDATION DIGEST: {validation.evidence_digest}",
                                        None, "authoritative_validation", (validation.evidence_digest,)),
                      DrawingAnnotation("note-assembly-review", APPROVAL_TEXT, None,
                                        "drawing_review_boundary", (assembly.evidence_digest,)))
    sheets: list[DrawingSheet] = [DrawingSheet(
        "fixture-assembly", "FIXTURE ASSEMBLY", 1, True, block,
        (_view("assembly-isometric", None, "isometric", overall),
         _view("assembly-front", None, "front", overall),
         _view("assembly-top", None, "top", overall)), assembly_dims,
        assembly_notes, component_identities=tuple(item.identity for item in components)),
        DrawingSheet(
            "exploded-assembly", "EXPLODED ASSEMBLY", 2, True, block,
            tuple(_view(f"exploded-{item.identity}", item, "isometric", tuple(
                item.bounds.maximum.__dict__[axis] - item.bounds.minimum.__dict__[axis] for axis in ("x", "y", "z")))
                  for item in components), (),
            (DrawingAnnotation("note-exploded-bom", "BOM BALLOONS FOLLOW DETERMINISTIC ITEM ORDER", None,
                               "bom_item_order", tuple(item.component_identity for item in bom)),),
            component_identities=tuple(item.identity for item in components)),
    ]
    for number, component in enumerate(components, 3):
        dims = _bounds_dimensions(component)
        if component.thickness_mm is not None:
            dims += (_dim(component, "plate-thickness", component.thickness_mm,
                          "authoritative component thickness metadata", fit="nominal"),)
        notes = _component_annotation(component)
        sheets.append(DrawingSheet(
            f"component-{_safe(component.identity)}",
            f"{('FABRICATED COMPONENT' if component.classification.value == 'fabricated' else 'PURCHASED COMPONENT REFERENCE')} {component.part_number}",
            number, True, block,
            (_view(f"{component.identity}-front", component, "front",
                   tuple(component.bounds.maximum.__dict__[axis] - component.bounds.minimum.__dict__[axis]
                         for axis in ("x", "y", "z"))),),
            dims, notes, _holes(component), (component.identity,)))
        if component.holes or component.tab_slots:
            detail_notes = notes + (DrawingAnnotation(
                f"note-{component.identity}-interface", f"INTERFACE: {component.interface or 'not specified'}",
                component.identity, "component_interface", (component.interface or "not specified",)),)
            sheets.append(DrawingSheet(
                f"detail-{_safe(component.identity)}", f"DETAIL {component.part_number} HOLES / INTERFACES",
                len(sheets) + 1, False, block,
                (_view(f"{component.identity}-detail", component, "detail", (10.0, 10.0, 10.0),
                       section=("hole and tab-slot metadata",)),),
                tuple(_dim(component, f"hole-{hole.identity}-diameter", hole.radius_mm * 2.0,
                           f"hole table row {hole.identity}", tolerance=hole.tolerance_mm, fit=hole.fit,
                           datum="FIXTURE-DATUM") for hole in component.holes) +
                tuple(_dim(component, f"tab-slot-{slot.identity}-width", slot.slot_width_mm,
                           f"tab-slot metadata {slot.identity}") for slot in component.tab_slots),
                detail_notes, _holes(component), (component.identity,)))
    ordered = tuple(replace(item, sheet_number=index)
                    for index, item in enumerate(sheets, 1))
    findings = _validate_package_shape(assembly, validation, ordered, bom)
    pdf = _render_pdf(ordered, bom, assembly.source_sha256, revision)
    package = DrawingPackage(assembly.source_sha256, assembly.concept_identity,
                             assembly.evidence_digest, revision, ordered, bom, findings, pdf, "")
    return replace(package, pdf_digest=hashlib.sha256(pdf).hexdigest())


def _validate_package_shape(assembly: ManufacturingAssembly, validation: object,
                            sheets: tuple[DrawingSheet, ...], bom: tuple[BomEntry, ...]) -> tuple[DrawingFinding, ...]:
    findings: list[DrawingFinding] = []
    ids = [item.identity for item in sheets]
    if len(set(ids)) != len(ids):
        findings.append(DrawingFinding("duplicate_sheet_identity", "error", "drawing sheet identities must be unique"))
    if not {"fixture-assembly", "exploded-assembly"} <= set(ids):
        findings.append(DrawingFinding("required_sheet_missing", "error", "assembly and exploded sheets are required"))
    if any(not item.title.strip() or not item.revision_block.title.strip() for item in sheets):
        findings.append(DrawingFinding("title_block_incomplete", "error", "every sheet requires a complete title block"))
    dimensions = [item.identity for sheet in sheets for item in sheet.dimensions]
    if len(set(dimensions)) != len(dimensions):
        findings.append(DrawingFinding("duplicate_dimension_identity", "error", "drawing dimension identities must be unique"))
    if len({item.item_number for item in bom}) != len(bom):
        findings.append(DrawingFinding("bom_item_number_duplicate", "error", "BOM item numbers must be unique"))
    if len({item.component_identity for item in bom}) != len(bom):
        findings.append(DrawingFinding("bom_component_identity_duplicate", "error", "BOM component identities must be unique"))
    components = {item.identity: item for item in assembly.components}
    exports = {item.component_identity: item for item in assembly.exports}
    if len(exports) != len(assembly.exports):
        findings.append(DrawingFinding("bom_export_identity_duplicate", "error", "component exports must have unique identities"))
    component_ids = set(components)
    bom_ids = {item.component_identity for item in bom}
    for identity in sorted(component_ids - bom_ids):
        findings.append(DrawingFinding("bom_component_missing", "error",
                                       f"manufacturing component {identity} is missing from the BOM"))
    for identity in sorted(bom_ids - component_ids):
        findings.append(DrawingFinding("bom_component_orphan", "error",
                                       f"BOM component {identity} is not in the manufacturing assembly"))
    for item in bom:
        component = components.get(item.component_identity)
        export = exports.get(item.component_identity)
        if component is None:
            continue
        if export is None:
            findings.append(DrawingFinding("bom_export_missing", "error",
                                           f"missing component export for {item.component_identity}"))
            continue
        authoritative = {
            "part_number": component.part_number,
            "revision": component.revision,
            "description": component.description,
            "classification": component.classification.value,
            "material": component.material,
            "thickness_mm": component.thickness_mm,
            "section_size_mm": tuple(component.section_size_mm),
            "quantity": component.quantity,
            "finish": component.finish,
            "process": component.manufacturing_process,
            "tooling_identity": component.purchased_tooling_identity,
            "step_filename": export.step_filename,
            "dxf_filename": export.dxf_filename,
        }
        documented = {
            "part_number": item.part_number, "revision": item.revision,
            "description": item.description, "classification": item.classification,
            "material": item.material, "thickness_mm": item.thickness_mm,
            "section_size_mm": tuple(item.section_size_mm), "quantity": item.quantity,
            "finish": item.finish, "process": item.process,
            "tooling_identity": item.tooling_identity, "step_filename": item.step_filename,
            "dxf_filename": item.dxf_filename,
        }
        codes = {
            "part_number": "bom_part_number_mismatch", "revision": "bom_revision_mismatch",
            "description": "bom_description_mismatch", "classification": "bom_classification_mismatch",
            "material": "bom_material_mismatch", "thickness_mm": "bom_thickness_mismatch",
            "section_size_mm": "bom_section_size_mismatch", "quantity": "bom_quantity_mismatch",
            "finish": "bom_finish_mismatch", "process": "bom_process_mismatch",
            "tooling_identity": "bom_tooling_identity_mismatch",
            "step_filename": "bom_step_filename_mismatch", "dxf_filename": "bom_dxf_filename_mismatch",
        }
        for field, code in codes.items():
            if documented[field] != authoritative[field]:
                findings.append(DrawingFinding(code, "error",
                                               f"BOM field {field} for {item.component_identity} does not match authoritative assembly evidence",
                                               (f"component={item.component_identity}", f"field={field}")))
        if not item.step_filename:
            findings.append(DrawingFinding("bom_step_filename_missing", "error",
                                           f"BOM item {item.component_identity} has no STEP link"))
    if not all(sheet.revision_block.approval_text == APPROVAL_TEXT and
               sheet.revision_block.release_text == NOT_RELEASED_TEXT for sheet in sheets):
        findings.append(DrawingFinding("approval_boundary_missing", "error", "drawing approval boundary is missing"))
    if getattr(validation, "blocked", True):
        findings.append(DrawingFinding("validation_blocked", "error", "authoritative validation is blocked"))
    return tuple(findings)


def validate_drawing_package(assembly: ManufacturingAssembly, package: DrawingPackage,
                             validation: object) -> tuple[DrawingFinding, ...]:
    """Recheck drawing provenance and deterministic evidence before export."""
    findings = list(_validate_package_shape(assembly, validation, package.sheets, package.bom))
    if package.source_sha256 != assembly.source_sha256:
        findings.append(DrawingFinding("source_identity_mismatch", "error",
                                       "drawing package source identity does not match assembly"))
    if package.concept_identity != assembly.concept_identity:
        findings.append(DrawingFinding("concept_identity_mismatch", "error",
                                       "drawing package concept identity does not match assembly"))
    if package.manufacturing_evidence_digest != assembly.evidence_digest:
        findings.append(DrawingFinding("manufacturing_identity_mismatch", "error",
                                       "drawing package manufacturing evidence does not match assembly"))
    if any(sheet.revision_block.drawing_revision != package.revision for sheet in package.sheets):
        findings.append(DrawingFinding("drawing_revision_mismatch", "error",
                                       "drawing sheet revisions do not match package revision"))
    if hashlib.sha256(package.pdf_bytes).hexdigest() != package.pdf_digest:
        findings.append(DrawingFinding("pdf_digest_mismatch", "error", "drawing PDF digest does not match bytes"))
    if not package.pdf_bytes.startswith(b"%PDF-1.4"):
        findings.append(DrawingFinding("pdf_signature_invalid", "error", "drawing PDF has no supported PDF signature"))
    if f"REV {package.revision}".encode("ascii", "replace") not in package.pdf_bytes:
        findings.append(DrawingFinding("pdf_package_revision_missing", "error",
                                       f"PDF is missing package revision evidence: {package.revision}"))
    if package.pdf_bytes.count(b"/Type /Page ") != len(package.sheets):
        findings.append(DrawingFinding("pdf_page_count_mismatch", "error", "PDF page count does not match drawing sheet count"))
    for required_text in (APPROVAL_TEXT, NOT_RELEASED_TEXT):
        if required_text.encode("ascii") not in package.pdf_bytes:
            findings.append(DrawingFinding("pdf_approval_boundary_missing", "error",
                                           f"PDF is missing required text: {required_text}"))
    for sheet in package.sheets:
        if sheet.required and sheet.title.encode("ascii", "replace") not in package.pdf_bytes:
            findings.append(DrawingFinding("pdf_required_sheet_title_missing", "error",
                                           f"PDF is missing required sheet title: {sheet.title}"))
        revision_marker = f"REV {sheet.revision_block.drawing_revision}".encode("ascii", "replace")
        if revision_marker not in package.pdf_bytes:
            findings.append(DrawingFinding("pdf_revision_missing", "error",
                                           f"PDF is missing revision evidence: {sheet.revision_block.drawing_revision}"))
    return tuple(findings)


def write_drawing_package(package: DrawingPackage, destination: str | Path, *,
                          assembly: ManufacturingAssembly, validation: object) -> tuple[Path, ...]:
    if package.blocked or any(item.severity == "error"
                              for item in validate_drawing_package(assembly, package, validation)):
        raise DrawingPackageError("drawing package failed authoritative validation")
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, bytes] = {
        "fixture-drawings.pdf": package.pdf_bytes,
        "drawing-manifest.json": (json.dumps(package.manifest_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "drawing-bom.json": (json.dumps([item.to_dict() for item in package.bom], indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    paths = []
    for name, payload in sorted(payloads.items()):
        path = root / name
        path.write_bytes(payload)
        paths.append(path)
    return tuple(paths)
