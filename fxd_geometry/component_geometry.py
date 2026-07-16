"""Milestone 23 real-kernel manufacturing component contracts.

The existing ``manufacturing`` module remains the feature-level compatibility
API.  This module adds stable component identities, real OCP/B-Rep shapes,
explicit interfaces and fit metadata, and deterministic per-component neutral
exports.  It never edits imported customer geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re

from .aabb import Aabb, Vec3
from .annotations import GeometryReference
from .concepts import CompleteFixtureConcept
from .fixture import ManufacturingSpec
from .kernel import KernelOperationError, RealKernel
from .placement import PlacementRole
from .product_model import ProductModel
from .tooling import ToolingItem, ToolingLibrary, generic_tooling_library


class ComponentGeometryError(KernelOperationError):
    """Raised when a manufacturing component cannot be authored safely."""


class ComponentClassification(str, Enum):
    FABRICATED = "fabricated"
    PURCHASED = "purchased"


class ComponentType(str, Enum):
    PLATE = "plate"
    STRUCTURAL_MEMBER = "structural_member"
    MACHINED_LOCATOR = "machined_locator"
    PURCHASED_TOOLING = "purchased_tooling"
    SHIM = "shim"
    WEAR_ITEM = "wear_item"


@dataclass(frozen=True)
class HoleSpec:
    identity: str
    kind: str
    center_mm: Vec3
    radius_mm: float
    depth_mm: float
    fit: str
    edge_distance_mm: float
    tolerance_mm: float | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.kind.strip() or not self.fit.strip():
            raise ComponentGeometryError("hole identity, kind, and fit are required")
        if self.radius_mm <= 0 or self.depth_mm <= 0 or self.edge_distance_mm < 0:
            raise ComponentGeometryError("hole dimensions must be positive and edge distance non-negative")
        if self.tolerance_mm is not None and self.tolerance_mm < 0:
            raise ComponentGeometryError("hole tolerance must be non-negative")


@dataclass(frozen=True)
class TabSlotSpec:
    identity: str
    tab_thickness_mm: float
    slot_width_mm: float
    clearance_mm: float
    insertion_direction: Vec3
    assembly_sequence: int
    weld_access: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or self.assembly_sequence < 1:
            raise ComponentGeometryError("tab-slot identity and positive assembly sequence are required")
        if min(self.tab_thickness_mm, self.slot_width_mm, self.clearance_mm) < 0:
            raise ComponentGeometryError("tab-slot dimensions must be non-negative")
        if self.slot_width_mm < self.tab_thickness_mm + self.clearance_mm:
            raise ComponentGeometryError("slot width is smaller than tab thickness plus clearance")
        if self.insertion_direction == Vec3(0.0, 0.0, 0.0):
            raise ComponentGeometryError("tab-slot insertion direction must not be zero")


@dataclass(frozen=True)
class ManufacturingFinding:
    code: str
    rule: str
    severity: str
    message: str
    component_identities: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManufacturingComponent:
    identity: str
    part_number: str
    revision: str
    description: str
    component_type: ComponentType
    classification: ComponentClassification
    source_sha256: str
    source_references: tuple[GeometryReference, ...]
    parent_concept_identity: str
    parent_structural_member: str | None
    related_placement_identities: tuple[str, ...]
    material: str
    thickness_mm: float | None
    section_size_mm: tuple[float, ...]
    quantity: int
    finish: str
    manufacturing_process: str
    purchased_tooling_identity: str | None
    shape: object
    bounds: Aabb
    holes: tuple[HoleSpec, ...] = ()
    tab_slots: tuple[TabSlotSpec, ...] = ()
    weld_intent: str = ""
    interface: str | None = None
    parent_component_identity: str | None = None
    planar_export_eligible: bool = False
    step_export_eligible: bool = True
    dxf_export_eligible: bool = False
    assumptions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.part_number.strip() or not self.revision.strip():
            raise ComponentGeometryError("component identity, part number, and revision are required")
        if not self.source_sha256 or not self.parent_concept_identity or not self.material.strip():
            raise ComponentGeometryError("component source, parent concept, and material are required")
        if self.quantity < 1 or not self.finish.strip() or not self.manufacturing_process.strip():
            raise ComponentGeometryError("component quantity, finish, and manufacturing process are required")
        if self.thickness_mm is not None and self.thickness_mm <= 0:
            raise ComponentGeometryError("component thickness must be positive")
        if any(value <= 0 for value in self.section_size_mm):
            raise ComponentGeometryError("component section dimensions must be positive")
        if self.classification == ComponentClassification.PURCHASED and not self.purchased_tooling_identity:
            raise ComponentGeometryError("purchased components require tooling identity")

    def to_dict(self) -> dict[str, object]:
        def ref(value: GeometryReference) -> dict[str, object]:
            return value.__dict__
        return {
            "identity": self.identity, "part_number": self.part_number, "revision": self.revision,
            "description": self.description, "component_type": self.component_type.value,
            "classification": self.classification.value, "source_sha256": self.source_sha256,
            "source_references": [ref(item) for item in self.source_references],
            "parent_concept_identity": self.parent_concept_identity,
            "parent_structural_member": self.parent_structural_member,
            "parent_component_identity": self.parent_component_identity,
            "related_placement_identities": list(self.related_placement_identities),
            "material": self.material, "thickness_mm": self.thickness_mm,
            "section_size_mm": list(self.section_size_mm), "quantity": self.quantity,
            "finish": self.finish, "manufacturing_process": self.manufacturing_process,
            "purchased_tooling_identity": self.purchased_tooling_identity,
            "bounds": self.bounds.as_dict(),
            "holes": [item.__dict__ | {"center_mm": item.center_mm.__dict__} for item in self.holes],
            "tab_slots": [item.__dict__ | {"insertion_direction": item.insertion_direction.__dict__}
                          for item in self.tab_slots],
            "weld_intent": self.weld_intent, "interface": self.interface,
            "planar_export_eligible": self.planar_export_eligible,
            "step_export_eligible": self.step_export_eligible, "dxf_export_eligible": self.dxf_export_eligible,
            "assumptions": list(self.assumptions), "evidence": list(self.evidence),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ComponentExport:
    component_identity: str
    step_filename: str
    step_bytes: bytes
    dxf_filename: str | None
    dxf_bytes: bytes | None


@dataclass(frozen=True)
class ManufacturingAssembly:
    concept_identity: str
    source_sha256: str
    units: str
    components: tuple[ManufacturingComponent, ...]
    model: object
    findings: tuple[ManufacturingFinding, ...]
    exports: tuple[ComponentExport, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    @property
    def blocked(self) -> bool:
        return not self.valid

    @property
    def evidence_digest(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "concept_identity": self.concept_identity, "source_sha256": self.source_sha256,
            "units": self.units, "components": [item.to_dict() for item in self.components],
            "findings": [item.__dict__ for item in self.findings],
            "exports": [{"component_identity": item.component_identity,
                         "step_filename": item.step_filename,
                         "dxf_filename": item.dxf_filename}
                        for item in self.exports],
        }


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _reference_valid(product: object, reference: GeometryReference) -> bool:
    component = next((item for item in product.components if item.identity == reference.component_identity), None)
    if component is None:
        return False
    if reference.body_identity is None:
        return True
    body = next((item for item in component.bodies if item.identity == reference.body_identity), None)
    if body is None:
        return False
    return (not reference.face_identity or reference.face_identity in {item.identity for item in body.faces}) and \
        (not reference.edge_identity or reference.edge_identity in {item.identity for item in body.edges})


def _component_bounds(component: ManufacturingComponent) -> tuple[float, float, float, float, float, float]:
    low, high = component.bounds.minimum, component.bounds.maximum
    return low.x, low.y, low.z, high.x, high.y, high.z


def _dxf(component: ManufacturingComponent) -> bytes | None:
    if not component.dxf_export_eligible or not component.planar_export_eligible:
        return None
    xmin, ymin, _, xmax, ymax, _ = _component_bounds(component)
    lines = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4",
             "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES",
             "0", "LWPOLYLINE", "8", "PROFILE", "90", "5", "70", "1"]
    points = ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin))
    for x, y in points:
        lines += ["10", format(x, ".9g"), "20", format(y, ".9g")]
    for hole in component.holes:
        lines += ["0", "CIRCLE", "8", "HOLES", "10", format(hole.center_mm.x, ".9g"),
                  "20", format(hole.center_mm.y, ".9g"), "40", format(hole.radius_mm, ".9g")]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return ("\n".join(lines) + "\n").encode("ascii")


def _finding(code: str, rule: str, severity: str, message: str,
             components: tuple[str, ...] = (), evidence: tuple[str, ...] = ()) -> ManufacturingFinding:
    return ManufacturingFinding(code, rule, severity, message, components, evidence)


def validate_manufacturing_assembly(product: object, assembly: ManufacturingAssembly,
                                     *, tooling: ToolingLibrary | None = None,
                                     kernel: RealKernel | None = None) -> tuple[ManufacturingFinding, ...]:
    """Validate component metadata, identity, connectivity, and export eligibility."""
    findings: list[ManufacturingFinding] = []
    if assembly.source_sha256 != product.source_sha256 or assembly.units != "mm":
        findings.append(_finding("source_identity_mismatch", "mfg_source_identity", "error",
                                 "manufacturing assembly source identity or units do not match product"))
    identities = tuple(item.identity for item in assembly.components)
    part_numbers = tuple(item.part_number for item in assembly.components)
    if len(set(identities)) != len(identities):
        findings.append(_finding("duplicate_component_identity", "mfg_component_identity_unique", "error",
                                 "manufacturing component identities must be unique"))
    if len(set(part_numbers)) != len(part_numbers):
        findings.append(_finding("duplicate_part_number", "mfg_part_number_unique", "error",
                                 "manufacturing part numbers must be unique"))
    known = set(identities)
    for component in assembly.components:
        if component.parent_component_identity and component.parent_component_identity not in known:
            findings.append(_finding("orphaned_component", "mfg_parent_required", "error",
                                     f"component {component.identity} has an unknown parent",
                                     (component.identity,)))
        if not component.step_export_eligible:
            findings.append(_finding("step_ineligible", "mfg_step_export_required", "error",
                                     f"component {component.identity} is not STEP export eligible",
                                     (component.identity,)))
        if component.classification == ComponentClassification.FABRICATED and component.thickness_mm is None:
            findings.append(_finding("missing_thickness", "mfg_thickness_required", "error",
                                     f"fabricated component {component.identity} lacks thickness",
                                     (component.identity,)))
        if not component.material.strip() or not component.manufacturing_process.strip():
            findings.append(_finding("missing_manufacturing_intent", "mfg_manufacturing_intent_required", "error",
                                     f"component {component.identity} lacks material or manufacturing intent",
                                     (component.identity,)))
        for reference in component.source_references:
            if not _reference_valid(product, reference):
                findings.append(_finding("invalid_source_reference", "mfg_source_reference_valid", "error",
                                         f"component {component.identity} has an invalid source reference",
                                         (component.identity,)))
        for hole in component.holes:
            low, high = component.bounds.minimum, component.bounds.maximum
            if not (low.x + hole.radius_mm <= hole.center_mm.x <= high.x - hole.radius_mm and
                    low.y + hole.radius_mm <= hole.center_mm.y <= high.y - hole.radius_mm and
                    low.z <= hole.center_mm.z <= high.z):
                findings.append(_finding("hole_outside_parent", "mfg_hole_within_parent", "error",
                                         f"hole {hole.identity} lies outside component {component.identity}",
                                         (component.identity,), (f"hole={hole.identity}",)))
            if hole.edge_distance_mm < hole.radius_mm:
                findings.append(_finding("hole_edge_distance", "mfg_hole_edge_distance", "error",
                                         f"hole {hole.identity} has insufficient edge distance",
                                         (component.identity,)))
        for first_index, left in enumerate(component.holes):
            for right in component.holes[first_index + 1:]:
                if _distance_xy(left.center_mm, right.center_mm) < left.radius_mm + right.radius_mm:
                    findings.append(_finding("overlapping_holes", "mfg_hole_spacing", "error",
                                             f"holes {left.identity} and {right.identity} overlap",
                                             (component.identity,)))
        if component.classification == ComponentClassification.PURCHASED:
            catalog = tooling or generic_tooling_library()
            selected = next((item for item in catalog.items if item.identity == component.purchased_tooling_identity), None)
            if selected is None:
                findings.append(_finding("tooling_mount_mismatch", "mfg_tooling_mount_reconcile", "error",
                                         f"purchased tooling for {component.identity} is absent from the supplied library",
                                         (component.identity,)))
            elif component.interface not in selected.mounting and component.interface:
                findings.append(_finding("tooling_mount_mismatch", "mfg_tooling_mount_reconcile", "error",
                                         f"component {component.identity} interface is not supported by tooling metadata",
                                         (component.identity,), (f"interface={component.interface}",)))
        if component.dxf_export_eligible and not component.planar_export_eligible:
            findings.append(_finding("nonplanar_dxf", "mfg_dxf_planar_only", "error",
                                     f"component {component.identity} is marked DXF eligible without planar evidence",
                                     (component.identity,)))
    if kernel is not None:
        by_identity = {item.identity: item for item in assembly.components}
        for index, left in enumerate(assembly.components):
            for right in assembly.components[index + 1:]:
                if _intentional_structural_interface(left, right, by_identity):
                    continue
                try:
                    if kernel.intersects(left.shape, right.shape):
                        findings.append(_finding("component_collision", "mfg_component_collision", "error",
                                                 f"components {left.identity} and {right.identity} collide without an explicit parent interface",
                                                 (left.identity, right.identity)))
                except KernelOperationError as exc:
                    findings.append(_finding("collision_check_failed", "mfg_component_collision", "error",
                                             f"component collision check failed: {exc}",
                                             (left.identity, right.identity)))
    for component in assembly.components:
        if not component.parent_component_identity:
            continue
        parent = next((item for item in assembly.components if item.identity == component.parent_component_identity), None)
        if parent and component.interface is None:
            findings.append(_finding("implicit_interface", "mfg_interface_explicit", "error",
                                     f"component {component.identity} has a parent but no explicit interface",
                                     (component.identity, parent.identity)))
    return tuple(findings)


def _distance_xy(left: Vec3, right: Vec3) -> float:
    return ((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5


def _structural_root(component: ManufacturingComponent,
                     by_identity: dict[str, ManufacturingComponent]) -> str | None:
    current = component
    seen: set[str] = set()
    while current.parent_component_identity and current.parent_component_identity in by_identity:
        if current.identity in seen:
            return None
        seen.add(current.identity)
        current = by_identity[current.parent_component_identity]
    return current.identity


def _intentional_structural_interface(left: ManufacturingComponent, right: ManufacturingComponent,
                                      by_identity: dict[str, ManufacturingComponent]) -> bool:
    if left.parent_component_identity == right.identity or right.parent_component_identity == left.identity:
        return True
    return (
        left.component_type in {ComponentType.PLATE, ComponentType.STRUCTURAL_MEMBER}
        and right.component_type in {ComponentType.PLATE, ComponentType.STRUCTURAL_MEMBER}
        and left.interface == "welded"
        and right.interface == "welded"
        and _structural_root(left, by_identity) == _structural_root(right, by_identity)
    )


def _structure_members(concept: CompleteFixtureConcept) -> tuple[object, ...]:
    if concept.structure is not None:
        return concept.structure.members
    return ()


def _member_component(concept: CompleteFixtureConcept, member: object, kernel: RealKernel,
                      placement_ids: tuple[str, ...] = ()) -> ManufacturingComponent:
    spec: ManufacturingSpec | None = member.manufacturing
    if spec is None:
        raise ComponentGeometryError(f"structural member {member.identity} has no manufacturing specification")
    shape = kernel.make_box(*_component_bounds_from_aabb(member.bounds))
    holes: tuple[HoleSpec, ...] = ()
    tab_slots: tuple[TabSlotSpec, ...] = ()
    if member.kind in {"baseplate", "welded_frame_base"}:
        low, high = member.bounds.minimum, member.bounds.maximum
        radius = min(3.0, (high.x - low.x) / 10.0, (high.y - low.y) / 10.0)
        centers = ((low.x + 2.0 * radius + 2.0, low.y + 2.0 * radius + 2.0),
                   (high.x - 2.0 * radius - 2.0, low.y + 2.0 * radius + 2.0),
                   (low.x + 2.0 * radius + 2.0, high.y - 2.0 * radius - 2.0),
                   (high.x - 2.0 * radius - 2.0, high.y - 2.0 * radius - 2.0))
        holes = tuple(HoleSpec(f"{member.identity}-mount-hole-{index}", "clearance",
                               Vec3(x, y, low.z), radius, high.z - low.z + 2.0,
                               "clearance", radius + 1.0, evidence=("base support mounting pattern",))
                      for index, (x, y) in enumerate(centers, 1))
        for hole in holes:
            shape = kernel.cut(shape, kernel.make_hole((hole.center_mm.x, hole.center_mm.y, hole.center_mm.z),
                                                       hole.radius_mm, hole.depth_mm))
        slot_width = (member.manufacturing.thickness if member.manufacturing and member.manufacturing.thickness else 2.0) + 0.5
        slot = TabSlotSpec(f"{member.identity}-tab-slot", slot_width - 0.5, slot_width, 0.5,
                           Vec3(1.0, 0.0, 0.0), 1, "weld access remains review-required",
                           evidence=("baseplate tab-and-slot proof interface",))
        tab_slots = (slot,)
        slot_tool = kernel.make_slot((low.x + (high.x - low.x) / 2.0 - slot_width,
                                      low.y + (high.y - low.y) / 2.0 - 2.0, low.z - 1.0),
                                     (low.x + (high.x - low.x) / 2.0 + slot_width,
                                      low.y + (high.y - low.y) / 2.0 + 2.0, high.z + 1.0))
        shape = kernel.cut(shape, slot_tool)
    component_id = f"mfg-{member.identity}"
    parent = f"mfg-{member.parent_identity}" if member.parent_identity else None
    component_type = ComponentType.STRUCTURAL_MEMBER if member.kind in {"frame_rail", "base_support"} else ComponentType.PLATE
    planar = member.kind not in {"frame_rail"}
    return ManufacturingComponent(
        component_id, f"FXD-M23-{_safe_filename(member.identity).upper()}", "A", member.kind,
        component_type, ComponentClassification.FABRICATED, concept.fixture.source_sha256,
        member.source_references, concept.identity, member.parent_identity, placement_ids,
        spec.material, spec.thickness, (), 1, "as-fabricated", spec.method, None, shape, member.bounds,
        holes=holes, tab_slots=tab_slots,
        weld_intent="weld to explicit parent structural member" if parent else "base support / foundation intent",
        interface="welded" if parent else "foundation", parent_component_identity=parent,
        planar_export_eligible=planar, step_export_eligible=True, dxf_export_eligible=planar,
        assumptions=member.assumptions, evidence=(f"structural_member={member.identity}",),
        warnings=("Proof geometry requires qualified manufacturing review.",),
    )


def _component_bounds_from_aabb(bounds: Aabb) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return ((bounds.minimum.x, bounds.minimum.y, bounds.minimum.z),
            (bounds.maximum.x, bounds.maximum.y, bounds.maximum.z))


def _placement_component(concept: CompleteFixtureConcept, placement: object, kernel: RealKernel,
                         tooling: ToolingLibrary) -> ManufacturingComponent:
    parent = f"mfg-{placement.parent_structural_member}" if placement.parent_structural_member else None
    if placement.role == PlacementRole.CLAMP:
        item: ToolingItem | None = next((value for value in tooling.items if value.identity == placement.tooling_identity), None)
        if item is None:
            raise ComponentGeometryError(f"placement {placement.identity} has no reconciled purchased tooling")
        shape = kernel.make_box(*_component_bounds_from_aabb(placement.bounds or Aabb.from_values(
            placement.position_mm.x, placement.position_mm.y, placement.position_mm.z,
            placement.position_mm.x + item.envelope.maximum.x,
            placement.position_mm.y + item.envelope.maximum.y,
            placement.position_mm.z + item.envelope.maximum.z)))
        return ManufacturingComponent(
            f"mfg-placement-{placement.identity}", f"FXD-M23-{_safe_filename(placement.identity).upper()}", "A",
            "purchased clamp", ComponentType.PURCHASED_TOOLING, ComponentClassification.PURCHASED,
            concept.fixture.source_sha256, (placement.reference,), concept.identity,
            placement.parent_structural_member, (placement.identity,), "vendor-neutral metadata", None, (), 1,
            "per tooling metadata", "purchased", item.identity, shape,
            placement.bounds or Aabb.from_values(placement.position_mm.x, placement.position_mm.y, placement.position_mm.z,
                                                  placement.position_mm.x + item.envelope.maximum.x,
                                                  placement.position_mm.y + item.envelope.maximum.y,
                                                  placement.position_mm.z + item.envelope.maximum.z),
            interface="base_plate", parent_component_identity=parent, planar_export_eligible=False,
            step_export_eligible=True, dxf_export_eligible=False,
            assumptions=placement.assumptions, evidence=placement.evidence,
            warnings=("Purchased tooling identity reconciles metadata only; vendor approval remains external.",),
        )
    radius = 4.0
    height = 20.0
    shape = kernel.make_cylinder((placement.position_mm.x, placement.position_mm.y, placement.position_mm.z), radius, height)
    bounds = Aabb.from_values(placement.position_mm.x - radius, placement.position_mm.y - radius,
                              placement.position_mm.z, placement.position_mm.x + radius,
                              placement.position_mm.y + radius, placement.position_mm.z + height)
    return ManufacturingComponent(
        f"mfg-placement-{placement.identity}", f"FXD-M23-{_safe_filename(placement.identity).upper()}", "A",
        placement.role.value, ComponentType.MACHINED_LOCATOR, ComponentClassification.FABRICATED,
        concept.fixture.source_sha256, (placement.reference,), concept.identity,
        placement.parent_structural_member, (placement.identity,), "tool steel", height, (radius * 2,), 1,
        "replaceable", "machined", None, shape, bounds, interface="replaceable_fit",
        parent_component_identity=parent, planar_export_eligible=False, step_export_eligible=True,
        dxf_export_eligible=False, assumptions=placement.assumptions, evidence=placement.evidence,
        warnings=("Locator block is deterministic proof geometry, not released fabrication geometry.",),
    )


def generate_manufacturing_assembly(product: ProductModel, concept: CompleteFixtureConcept, kernel: RealKernel,
                                   *, tooling: ToolingLibrary | None = None) -> ManufacturingAssembly:
    """Author a connected component assembly with real kernel solids."""
    if concept.engineering_status == "invalid":
        raise ComponentGeometryError("invalid fixture concepts cannot author manufacturing components")
    if not kernel.capabilities.is_complete:
        raise ComponentGeometryError("complete real-kernel capabilities are required")
    tooling = tooling or generic_tooling_library()
    members = _structure_members(concept)
    if not members:
        raise ComponentGeometryError("Milestone 23 requires a Milestone 21 structural concept")
    placements = concept.placement.placements if concept.placement else ()
    placement_by_parent: dict[str, tuple[str, ...]] = {}
    for item in placements:
        if item.parent_structural_member:
            placement_by_parent.setdefault(item.parent_structural_member, ())
            placement_by_parent[item.parent_structural_member] += (item.identity,)
    components = [_member_component(concept, member, kernel, placement_by_parent.get(member.identity, ()))
                  for member in members]
    components.extend(_placement_component(concept, item, kernel, tooling)
                      for item in placements if item.role in {PlacementRole.ROUND_PIN, PlacementRole.DIAMOND_PIN,
                                                               PlacementRole.CLAMP})
    shapes = tuple(item.shape for item in components)
    model = kernel.compound(shapes)
    exports = tuple(ComponentExport(
        item.identity, f"{_safe_filename(item.part_number)}.step", kernel.export_step(item.shape),
        f"{_safe_filename(item.part_number)}.dxf" if item.dxf_export_eligible else None,
        _dxf(item),
    ) for item in components)
    provisional = ManufacturingAssembly(concept.identity, concept.fixture.source_sha256, "mm",
                                        tuple(components), model, (), exports)
    findings = validate_manufacturing_assembly(product, provisional, tooling=tooling, kernel=kernel)
    return ManufacturingAssembly(concept.identity, concept.fixture.source_sha256, "mm",
                                  tuple(components), model, findings, exports)


def generate_manufacturing_assembly_for_product(product: ProductModel, concept: CompleteFixtureConcept,
                                                kernel: RealKernel, *,
                                                tooling: ToolingLibrary | None = None) -> ManufacturingAssembly:
    """Compatibility alias for the explicit product-bound entry point."""
    return generate_manufacturing_assembly(product, concept, kernel, tooling=tooling)


def build_manufacturing_export_package(assembly: ManufacturingAssembly,
                                       validation: object | None = None,
                                       drawing_package: object | None = None,
                                       optimization: object | None = None) -> dict[str, bytes | str]:
    """Return a deterministic review-only component export package."""
    if assembly.blocked:
        raise ComponentGeometryError("invalid manufacturing assembly cannot be exported")
    if validation is None or getattr(validation, "blocked", True):
        raise ComponentGeometryError("valid deterministic fixture validation is required before export")
    if drawing_package is not None:
        from .drawings import validate_drawing_package
        drawing_findings = validate_drawing_package(assembly, drawing_package, validation)
        if getattr(drawing_package, "blocked", True) or any(item.severity == "error" for item in drawing_findings):
            raise ComponentGeometryError("invalid drawing package cannot be exported")
        if (getattr(drawing_package, "source_sha256", None) != assembly.source_sha256 or
                getattr(drawing_package, "concept_identity", None) != assembly.concept_identity or
                getattr(drawing_package, "manufacturing_evidence_digest", None) != assembly.evidence_digest):
            raise ComponentGeometryError("drawing package provenance does not match manufacturing assembly")
    if optimization is not None:
        from .optimization import analyze_fixture_cost
        analysis = analyze_fixture_cost(assembly, validation=validation, drawing_package=drawing_package,
                                        rates=getattr(optimization, "rate_table", None),
                                        assumptions=getattr(optimization, "assumptions", None),
                                        production_quantity=getattr(optimization, "selected_quantity", None))
        if analysis.blocked or analysis.evidence_digest != getattr(optimization, "evidence_digest", ""):
            raise ComponentGeometryError("invalid or stale cost analysis cannot be exported")
    files: dict[str, bytes | str] = {
        "manifest.json": json.dumps(assembly.to_dict() | {"review_status": "ENGINEERING_REVIEW_REQUIRED"},
                                     indent=2, sort_keys=True) + "\n",
        "validation.json": json.dumps(getattr(validation, "__dict__", {}), sort_keys=True) + "\n",
    }
    for item in assembly.exports:
        files[item.step_filename] = item.step_bytes
        if item.dxf_filename and item.dxf_bytes is not None:
            files[item.dxf_filename] = item.dxf_bytes
    if drawing_package is not None:
        import json as _json
        files["fixture-drawings.pdf"] = drawing_package.pdf_bytes
        files["drawing-manifest.json"] = _json.dumps(drawing_package.manifest_dict(), indent=2, sort_keys=True) + "\n"
        files["drawing-bom.json"] = _json.dumps([item.to_dict() for item in drawing_package.bom],
                                                 indent=2, sort_keys=True) + "\n"
    if optimization is not None:
        files["fixture-cost-summary.json"] = json.dumps(optimization.summary.to_dict() if optimization.summary else {}, indent=2, sort_keys=True) + "\n"
        files["component-cost-breakdown.json"] = json.dumps([item.to_dict() for item in (optimization.summary.component_costs if optimization.summary else ())], indent=2, sort_keys=True) + "\n"
        files["volume-scenarios.json"] = json.dumps([item.to_dict() for item in optimization.scenarios], indent=2, sort_keys=True) + "\n"
        files["manufacturability-findings.json"] = json.dumps([item.to_dict() for item in optimization.manufacturability_findings], indent=2, sort_keys=True) + "\n"
        files["optimization-recommendations.json"] = json.dumps([item.to_dict() for item in optimization.recommendations], indent=2, sort_keys=True) + "\n"
    return dict(sorted(files.items()))


def write_manufacturing_export_package(assembly: ManufacturingAssembly, destination: str | Path,
                                       validation: object | None = None,
                                       drawing_package: object | None = None,
                                       optimization: object | None = None) -> tuple[Path, ...]:
    files = build_manufacturing_export_package(assembly, validation, drawing_package, optimization)
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in files.items():
        path = root / name
        path.write_bytes(payload if isinstance(payload, bytes) else payload.encode("utf-8"))
        written.append(path)
    return tuple(written)
