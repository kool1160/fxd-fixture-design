"""Deterministic locator, support, and clamp placement contracts.

This module is an engineering-review proof layer.  It consumes explicit datum
surface evidence and composes the existing constraint, access, tooling, weld,
and structural contracts.  It never edits source geometry or invents surface
normals from an AABB.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from .aabb import Aabb, Vec3
from .access import AccessAnalysis
from .annotations import EngineeringAnnotations, GeometryReference
from .constraints import LocatingStrategy, LocatorContact, analyze_locating_strategy
from .product_model import ProductModel
from .structure import StructuralAssembly
from .tooling import ToolingLibrary, ToolingItem, generic_tooling_library


class PlacementError(ValueError):
    """Raised when a placement contract is malformed at its boundary."""


class PlacementRole(str, Enum):
    PRIMARY_DATUM = "primary_datum"
    SECONDARY_DATUM = "secondary_datum"
    TERTIARY_DATUM = "tertiary_datum"
    ROUND_PIN = "round_pin"
    DIAMOND_PIN = "diamond_pin"
    REST = "rest"
    STOP = "stop"
    SUPPORT = "support"
    CLAMP = "clamp"


RULE_INVALID_REFERENCE = "placement_invalid_source_reference"
RULE_MISSING_DATUM_EVIDENCE = "placement_missing_datum_evidence"
RULE_UNDERCONSTRAINED = "placement_underconstrained"
RULE_OVERCONSTRAINED = "placement_overconstrained"
RULE_DUPLICATE_DIRECTION = "placement_duplicate_constraint_direction"
RULE_UNSTABLE_CONTACT = "placement_unstable_contact_arrangement"
RULE_UNREACHABLE_LOCATOR = "placement_unreachable_locator"
RULE_LOCATOR_COLLISION = "placement_locator_collision"
RULE_UNSUPPORTED_MOUNT = "placement_unsupported_mount"
RULE_BLOCKED_ACCESS = "placement_blocked_access"
RULE_SUPPORT_SPAN = "placement_unsupported_span"
RULE_SUPPORT_OVERCOUNT = "placement_excessive_support_count"
RULE_CLAMP_REACTION = "placement_clamp_reaction_conflict"
RULE_CLAMP_CAPACITY = "placement_clamp_capacity_insufficient"
RULE_CLAMP_ACCESS = "placement_clamp_access_conflict"
RULE_STANDARD_TOOLING = "placement_standard_tooling_preferred"


def _values(vector: Vec3) -> tuple[float, float, float]:
    return vector.x, vector.y, vector.z


def _length(vector: Vec3) -> float:
    return math.sqrt(sum(value * value for value in _values(vector)))


def _unit(vector: Vec3) -> Vec3:
    length = _length(vector)
    if length <= 1.0e-9:
        raise PlacementError("placement vector must not be zero")
    return Vec3(*(value / length for value in _values(vector)))


def _dot(left: Vec3, right: Vec3) -> float:
    return sum(a * b for a, b in zip(_values(left), _values(right)))


def _cross(left: Vec3, right: Vec3) -> Vec3:
    return Vec3(left.y * right.z - left.z * right.y,
                left.z * right.x - left.x * right.z,
                left.x * right.y - left.y * right.x)


def _distance(left: Vec3, right: Vec3) -> float:
    return _length(Vec3(left.x - right.x, left.y - right.y, left.z - right.z))


def _translate(box: Aabb, point: Vec3) -> Aabb:
    return Aabb(Vec3(box.minimum.x + point.x, box.minimum.y + point.y, box.minimum.z + point.z),
                Vec3(box.maximum.x + point.x, box.maximum.y + point.y, box.maximum.z + point.z))


@dataclass(frozen=True)
class PlacementParameters:
    """Caller-visible placement assumptions, with all dimensions in mm."""

    minimum_datum_separation_mm: float = 10.0
    minimum_support_separation_mm: float = 20.0
    maximum_support_count: int = 8
    minimum_clamp_stroke_mm: float = 10.0
    minimum_clamp_reach_mm: float = 10.0
    required_clamp_force_n: float = 500.0
    minimum_confidence: float = 0.5
    support_span_warning_mm: float = 300.0
    avoid_weld_distance_mm: float = 15.0

    def __post_init__(self) -> None:
        values = (self.minimum_datum_separation_mm, self.minimum_support_separation_mm,
                  self.minimum_clamp_stroke_mm, self.minimum_clamp_reach_mm,
                  self.required_clamp_force_n, self.support_span_warning_mm,
                  self.avoid_weld_distance_mm)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise PlacementError("placement dimensions and force must be finite and non-negative")
        if self.maximum_support_count < 1:
            raise PlacementError("maximum_support_count must be positive")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise PlacementError("minimum_confidence must be between zero and one")


@dataclass(frozen=True)
class DatumCandidate:
    """Explicit geometry-aware datum evidence supplied by a caller or kernel."""

    identity: str
    reference: GeometryReference
    position_mm: Vec3
    normal: Vec3
    surface_area_mm2: float
    stability: float
    accessibility: float
    criticality: float
    distortion_sensitivity: float
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise PlacementError("datum candidate identity is required")
        if not isinstance(self.reference, GeometryReference):
            raise PlacementError("datum candidate reference must be GeometryReference")
        if _length(self.normal) <= 1.0e-9:
            raise PlacementError("datum candidate normal must not be zero")
        if not math.isfinite(self.surface_area_mm2) or self.surface_area_mm2 <= 0:
            raise PlacementError("datum candidate surface area must be positive")
        values = (self.stability, self.accessibility, self.criticality,
                  self.distortion_sensitivity, self.confidence)
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
            raise PlacementError("datum scores and confidence must be between zero and one")


@dataclass(frozen=True)
class DatumCandidateScore:
    candidate_identity: str
    score: float
    eligible: bool
    normal_alignment: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Placement:
    """Editable, traceable proof-layer placement intent."""

    identity: str
    role: PlacementRole
    reference: GeometryReference
    position_mm: Vec3
    axis: Vec3
    contact_normal: Vec3
    mount_reference: GeometryReference | None = None
    parent_structural_member: str | None = None
    tooling_identity: str | None = None
    stroke_mm: float | None = None
    reach_mm: float | None = None
    force_n: float | None = None
    tolerance_mm: float | None = None
    constrained_directions: tuple[Vec3, ...] = ()
    weld_distortion_intent: str = "not supplied"
    rule: str = ""
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: float = 0.0
    warnings: tuple[str, ...] = ()
    bounds: Aabb | None = None
    constrains_locating: bool = True

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.rule.strip():
            raise PlacementError("placement identity and rule are required")
        if not isinstance(self.role, PlacementRole):
            raise PlacementError("placement role must be PlacementRole")
        if _length(self.axis) <= 1.0e-9 or _length(self.contact_normal) <= 1.0e-9:
            raise PlacementError("placement axis and contact normal must not be zero")
        values = (self.stroke_mm, self.reach_mm, self.force_n, self.tolerance_mm)
        if any(value is not None and (not math.isfinite(value) or value < 0) for value in values):
            raise PlacementError("placement dimensions and force must be finite and non-negative")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise PlacementError("placement confidence must be between zero and one")
        if any(_length(direction) <= 1.0e-9 for direction in self.constrained_directions):
            raise PlacementError("placement constrained directions must not be zero")

    def to_dict(self) -> dict[str, object]:
        def reference(value: GeometryReference | None) -> object:
            return value.__dict__ if value else None
        return {
            "identity": self.identity, "role": self.role.value,
            "reference": reference(self.reference),
            "position_mm": self.position_mm.__dict__, "axis": self.axis.__dict__,
            "contact_normal": self.contact_normal.__dict__,
            "mount_reference": reference(self.mount_reference),
            "parent_structural_member": self.parent_structural_member,
            "tooling_identity": self.tooling_identity, "stroke_mm": self.stroke_mm,
            "reach_mm": self.reach_mm, "force_n": self.force_n,
            "tolerance_mm": self.tolerance_mm,
            "constrained_directions": [item.__dict__ for item in self.constrained_directions],
            "weld_distortion_intent": self.weld_distortion_intent, "rule": self.rule,
            "evidence": list(self.evidence), "assumptions": list(self.assumptions),
            "confidence": self.confidence, "warnings": list(self.warnings),
            "bounds": self.bounds.as_dict() if self.bounds else None,
            "constrains_locating": self.constrains_locating,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Placement":
        def reference(value: dict[str, object] | None) -> GeometryReference | None:
            return GeometryReference(**value) if value is not None else None
        def vector(value: dict[str, object]) -> Vec3:
            return Vec3(**value)
        bounds = data.get("bounds")
        box = Aabb(vector(bounds["minimum"]), vector(bounds["maximum"])) if bounds else None
        return cls(
            data["identity"], PlacementRole(data["role"]), reference(data["reference"]),
            vector(data["position_mm"]), vector(data["axis"]), vector(data["contact_normal"]),
            reference(data.get("mount_reference")), data.get("parent_structural_member"),
            data.get("tooling_identity"), data.get("stroke_mm"), data.get("reach_mm"),
            data.get("force_n"), data.get("tolerance_mm"),
            tuple(vector(item) for item in data.get("constrained_directions", ())),
            data.get("weld_distortion_intent", "not supplied"), data["rule"],
            tuple(data.get("evidence", ())), tuple(data.get("assumptions", ())),
            data.get("confidence", 0.0), tuple(data.get("warnings", ())), box,
            data.get("constrains_locating", True),
        )


@dataclass(frozen=True)
class PlacementFinding:
    code: str
    rule: str
    severity: str
    message: str
    placement_identities: tuple[str, ...] = ()
    geometry_references: tuple[GeometryReference, ...] = ()
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: float | None = None


@dataclass(frozen=True)
class PlacementAlternative:
    identity: str
    placements: tuple[Placement, ...]
    findings: tuple[PlacementFinding, ...]
    rationale: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)


@dataclass(frozen=True)
class PlacementPlan:
    source_sha256: str
    units: str
    placements: tuple[Placement, ...]
    datum_scores: tuple[DatumCandidateScore, ...]
    locating_strategy: LocatingStrategy | None
    findings: tuple[PlacementFinding, ...]
    alternatives: tuple[PlacementAlternative, ...] = ()

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    @property
    def blocked(self) -> bool:
        return not self.valid

    @property
    def warnings(self) -> tuple[PlacementFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")

    @property
    def evidence_digest(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        def reference(value: GeometryReference) -> dict[str, object]:
            return value.__dict__

        def finding(value: PlacementFinding) -> dict[str, object]:
            data = value.__dict__.copy()
            data["geometry_references"] = [reference(item) for item in value.geometry_references]
            return data

        return {
            "source_sha256": self.source_sha256, "units": self.units,
            "placements": [item.to_dict() for item in self.placements],
            "datum_scores": [item.__dict__ for item in self.datum_scores],
            "locating_strategy": {
                "contacts": [{"identity": item.identity, "role": item.role,
                               "reference": reference(item.reference),
                               "point_mm": item.point_mm.__dict__, "normal": item.normal.__dict__,
                               "constrained_directions": [direction.__dict__ for direction in item.constrained_directions]}
                              for item in self.locating_strategy.contacts],
                "tolerance_mm": self.locating_strategy.tolerance_mm,
                "repeatability_mm": self.locating_strategy.repeatability_mm,
                "datum_assumptions": list(self.locating_strategy.datum_assumptions),
            } if self.locating_strategy else None,
            "findings": [finding(item) for item in self.findings],
            "alternatives": [{"identity": item.identity, "findings": [finding(value) for value in item.findings],
                              "rationale": list(item.rationale),
                              "placements": [placement.to_dict() for placement in item.placements]}
                             for item in self.alternatives],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PlacementPlan":
        def reference(value: dict[str, object]) -> GeometryReference:
            return GeometryReference(**value)
        def finding(value: dict[str, object]) -> PlacementFinding:
            return PlacementFinding(value["code"], value["rule"], value["severity"], value["message"],
                                    tuple(value.get("placement_identities", ())),
                                    tuple(reference(item) for item in value.get("geometry_references", ())),
                                    tuple(value.get("evidence", ())), tuple(value.get("assumptions", ())),
                                    value.get("confidence"))
        raw_strategy = data.get("locating_strategy")
        strategy = None
        if raw_strategy:
            contacts = []
            for item in raw_strategy.get("contacts", ()):
                contacts.append(LocatorContact(
                    item["identity"], item["role"], reference(item["reference"]),
                    Vec3(**item["point_mm"]), Vec3(**item["normal"]),
                    tuple(Vec3(**direction) for direction in item.get("constrained_directions", ())),
                ))
            strategy = LocatingStrategy(tuple(contacts), raw_strategy.get("tolerance_mm"),
                                        raw_strategy.get("repeatability_mm"),
                                        tuple(raw_strategy.get("datum_assumptions", ())))
        alternatives = []
        for item in data.get("alternatives", ()):
            alternatives.append(PlacementAlternative(
                item["identity"], tuple(Placement.from_dict(value) for value in item.get("placements", ())),
                tuple(finding(value) for value in item.get("findings", ())), tuple(item.get("rationale", ())),
            ))
        scores = tuple(DatumCandidateScore(item["candidate_identity"], item["score"], item["eligible"],
                                           item["normal_alignment"], tuple(item.get("reasons", ())))
                       for item in data.get("datum_scores", ()))
        return cls(data["source_sha256"], data["units"],
                   tuple(Placement.from_dict(item) for item in data.get("placements", ())), scores,
                   strategy, tuple(finding(item) for item in data.get("findings", ())), tuple(alternatives))


def _validate_reference(product: ProductModel, reference: GeometryReference) -> bool:
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


def rank_datum_candidates(product: ProductModel, candidates: tuple[DatumCandidate, ...],
                          annotations: EngineeringAnnotations,
                          *, parameters: PlacementParameters | None = None) -> tuple[DatumCandidateScore, ...]:
    """Rank explicit datum evidence without manufacturing missing geometry data."""
    params = parameters or PlacementParameters()
    annotations.validate_references(product)
    if len({item.identity for item in candidates}) != len(candidates):
        raise PlacementError("datum candidate identities must be unique")
    permitted = set(annotations.permitted_locating_surfaces)
    forbidden = set(annotations.forbidden_contact_areas)
    build = _unit(annotations.build_orientation)
    maximum_area = max((item.surface_area_mm2 for item in candidates), default=1.0)
    result: list[DatumCandidateScore] = []
    for candidate in candidates:
        valid_reference = _validate_reference(product, candidate.reference)
        alignment = abs(_dot(_unit(candidate.normal), build))
        eligible = valid_reference and candidate.reference not in forbidden
        reasons: list[str] = []
        if not valid_reference:
            reasons.append("source geometry reference is invalid")
        if candidate.reference in forbidden:
            reasons.append("candidate is in an annotated forbidden contact area")
        if permitted and candidate.reference not in permitted:
            eligible = False
            reasons.append("candidate is outside the permitted locating-surface intent")
        score = (0.20 * candidate.surface_area_mm2 / maximum_area +
                 0.15 * alignment + 0.15 * candidate.stability +
                 0.15 * candidate.accessibility + 0.15 * candidate.criticality +
                 0.10 * (1.0 - candidate.distortion_sensitivity) +
                 0.10 * candidate.confidence) if eligible else 0.0
        if candidate.confidence < params.minimum_confidence:
            reasons.append("candidate confidence is below the caller threshold")
        result.append(DatumCandidateScore(candidate.identity, round(score, 9), eligible,
                                          round(alignment, 9), tuple(reasons)))
    return tuple(sorted(result, key=lambda item: (-item.eligible, -item.score, item.candidate_identity)))


def _finding(code: str, rule: str, severity: str, message: str, *, placements: tuple[str, ...] = (),
             references: tuple[GeometryReference, ...] = (), evidence: tuple[str, ...] = (),
             assumptions: tuple[str, ...] = (), confidence: float | None = None) -> PlacementFinding:
    return PlacementFinding(code, rule, severity, message, placements, references, evidence, assumptions, confidence)


def _candidate_map(candidates: tuple[DatumCandidate, ...]) -> dict[str, DatumCandidate]:
    return {item.identity: item for item in candidates}


def _orthogonal(normal: Vec3, direction: Vec3) -> Vec3:
    projected = Vec3(direction.x - normal.x * _dot(direction, normal),
                      direction.y - normal.y * _dot(direction, normal),
                      direction.z - normal.z * _dot(direction, normal))
    if _length(projected) <= 1.0e-9:
        seed = Vec3(1.0, 0.0, 0.0) if abs(normal.x) < 0.9 else Vec3(0.0, 1.0, 0.0)
        projected = _cross(normal, seed)
    return _unit(projected)


def _contact(placement: Placement) -> LocatorContact:
    role = "rest" if placement.role in {PlacementRole.PRIMARY_DATUM, PlacementRole.SECONDARY_DATUM,
                                        PlacementRole.TERTIARY_DATUM} else placement.role.value
    return LocatorContact(placement.identity, role, placement.reference,
                          placement.position_mm, placement.contact_normal,
                          placement.constrained_directions)


def validate_placement_plan(product: ProductModel, plan: PlacementPlan,
                            *, structure: StructuralAssembly | None = None,
                            access: AccessAnalysis | None = None,
                            parameters: PlacementParameters | None = None) -> tuple[PlacementFinding, ...]:
    """Apply fail-closed placement gates and return deterministic findings."""
    params = parameters or PlacementParameters()
    findings: list[PlacementFinding] = list(plan.findings)
    if product.source_sha256 != plan.source_sha256 or plan.units != "mm":
        findings.append(_finding("placement_identity_mismatch", RULE_INVALID_REFERENCE, "error",
                                 "placement plan source identity or units do not match the product"))
    if len({item.identity for item in plan.placements}) != len(plan.placements):
        findings.append(_finding("placement_duplicate_identity", "placement_identity_unique", "error",
                                 "placement identities must be unique"))
    members = {item.identity for item in structure.members} if structure else set()
    for placement in plan.placements:
        if not _validate_reference(product, placement.reference):
            findings.append(_finding("invalid_reference", RULE_INVALID_REFERENCE, "error",
                                     f"placement {placement.identity} references unknown source geometry",
                                     placements=(placement.identity,), references=(placement.reference,)))
        if placement.mount_reference and not _validate_reference(product, placement.mount_reference):
            findings.append(_finding("invalid_mount_reference", RULE_INVALID_REFERENCE, "error",
                                     f"placement {placement.identity} has an invalid mount reference",
                                     placements=(placement.identity,), references=(placement.mount_reference,)))
        if structure and placement.parent_structural_member not in members:
            findings.append(_finding("unsupported_mount", RULE_UNSUPPORTED_MOUNT, "error",
                                     f"placement {placement.identity} has no supported structural parent",
                                     placements=(placement.identity,)))
        if placement.confidence < params.minimum_confidence:
            findings.append(_finding("low_placement_confidence", "placement_confidence_required", "warning",
                                     f"placement {placement.identity} confidence is below the review threshold",
                                     placements=(placement.identity,), confidence=placement.confidence))
        if placement.bounds:
            for other in plan.placements:
                if other.identity >= placement.identity or not other.bounds:
                    continue
                if placement.bounds.intersects(other.bounds):
                    findings.append(_finding("placement_collision", RULE_LOCATOR_COLLISION, "error",
                                             f"placements {placement.identity} and {other.identity} collide",
                                             placements=(placement.identity, other.identity)))
    contacts = tuple(_contact(item) for item in plan.placements
                     if item.constrains_locating and item.role in {PlacementRole.REST, PlacementRole.ROUND_PIN,
                                                                    PlacementRole.DIAMOND_PIN, PlacementRole.STOP,
                                                                    PlacementRole.PRIMARY_DATUM, PlacementRole.SECONDARY_DATUM,
                                                                    PlacementRole.TERTIARY_DATUM})
    if contacts:
        analysis = analyze_locating_strategy(product, LocatingStrategy(
            contacts, tolerance_mm=0.1, repeatability_mm=0.1,
            datum_assumptions=("Placement roles and contact normals were caller-supplied evidence.",)))
        findings.extend(_finding(item.code, RULE_UNDERCONSTRAINED if item.code == "underconstrained" else RULE_OVERCONSTRAINED,
                                 "error", item.message, placements=((item.locator_identity,) if item.locator_identity else ()))
                        for item in analysis.findings if item.severity == "error")
        if any(item.code == "redundant_direction" for item in analysis.findings):
            findings.append(_finding("duplicate_direction", RULE_DUPLICATE_DIRECTION, "error",
                                     "locating roles contain duplicated constraint directions"))
    elif plan.placements:
        findings.append(_finding("missing_datum_evidence", RULE_MISSING_DATUM_EVIDENCE, "error",
                                 "no explicit locating contacts were supplied"))
    support_count = sum(item.role == PlacementRole.SUPPORT for item in plan.placements)
    if support_count > params.maximum_support_count:
        findings.append(_finding("excessive_support_count", RULE_SUPPORT_OVERCOUNT, "warning",
                                 "support count exceeds the caller-supplied maintainability limit",
                                 evidence=(f"support_count={support_count}",)))
    if access and access.blocked:
        findings.append(_finding("blocked_access", RULE_BLOCKED_ACCESS, "error",
                                 "existing access analysis contains blocking weld, load, unload, or operator findings",
                                 evidence=tuple(item.code for item in access.findings if item.severity == "error")))
    for placement in plan.placements:
        if placement.role == PlacementRole.CLAMP:
            if placement.force_n is None or placement.stroke_mm is None or placement.reach_mm is None:
                findings.append(_finding("clamp_evidence_missing", RULE_CLAMP_CAPACITY, "error",
                                         f"clamp {placement.identity} lacks force, stroke, or reach evidence",
                                         placements=(placement.identity,)))
            else:
                if placement.stroke_mm < params.minimum_clamp_stroke_mm or placement.reach_mm < params.minimum_clamp_reach_mm or placement.force_n < params.required_clamp_force_n:
                    findings.append(_finding("clamp_capacity_insufficient", RULE_CLAMP_CAPACITY, "error",
                                             f"clamp {placement.identity} does not meet explicit capacity assumptions",
                                             placements=(placement.identity,), evidence=(f"stroke_mm={placement.stroke_mm}",
                                                                                         f"reach_mm={placement.reach_mm}",
                                                                                         f"force_n={placement.force_n}")))
            if _dot(_unit(placement.axis), _unit(placement.contact_normal)) > 0:
                findings.append(_finding("clamp_reaction_conflict", RULE_CLAMP_REACTION, "error",
                                         f"clamp {placement.identity} force direction pulls away from its contact normal",
                                         placements=(placement.identity,)))
            if placement.tooling_identity is None:
                findings.append(_finding("clamp_tooling_missing", RULE_STANDARD_TOOLING, "warning",
                                         f"clamp {placement.identity} has no selected vendor-neutral tooling item",
                                         placements=(placement.identity,)))
    return tuple(findings)


def _make_placements(product: ProductModel, annotations: EngineeringAnnotations,
                     candidates: tuple[DatumCandidate, ...], scores: tuple[DatumCandidateScore, ...],
                     tooling: ToolingLibrary, structure: StructuralAssembly | None,
                     params: PlacementParameters) -> tuple[Placement, ...]:
    by_id = _candidate_map(candidates)
    eligible = [item for item in scores if item.eligible and item.candidate_identity in by_id]
    if len(eligible) < 3:
        return ()
    selected = [by_id[item.candidate_identity] for item in eligible[:3]]
    parent = next((item.identity for item in structure.members if item.kind in {"baseplate", "welded_frame_base"}), None) if structure else None
    common = ("Explicit datum surface evidence is required; positions and normals are not inferred from AABBs.",)
    placements: list[Placement] = []
    for index, (stage, candidate) in enumerate(zip(("primary", "secondary", "tertiary"), selected), 1):
        role = (PlacementRole.PRIMARY_DATUM if stage == "primary" else
                PlacementRole.SECONDARY_DATUM if stage == "secondary" else PlacementRole.TERTIARY_DATUM)
        placements.append(Placement(
            f"{stage}-rest", role, candidate.reference, candidate.position_mm, candidate.normal,
            candidate.normal, parent_structural_member=parent, tolerance_mm=0.1,
            weld_distortion_intent="support weld-shrink direction and avoid distortion-sensitive contact",
            rule="ranked_datum_surface_rest", evidence=candidate.evidence + (f"datum_score={eligible[index - 1].score}",),
            assumptions=common + candidate.assumptions, confidence=candidate.confidence,
            warnings=("Proof-layer contact requires qualified fixture-engineering review.",),
            constrains_locating=True))
    round_candidate, diamond_candidate, stop_candidate = selected
    placements.append(Placement(
        "round-pin", PlacementRole.ROUND_PIN, round_candidate.reference, round_candidate.position_mm,
        round_candidate.normal, round_candidate.normal, parent_structural_member=parent,
        tolerance_mm=0.05, weld_distortion_intent="primary repeatable locating reference",
        rule="round_pin_primary_datum", evidence=round_candidate.evidence,
        assumptions=common + ("Round pin radial constraints are evaluated by the existing six-DOF solver.",),
        confidence=round_candidate.confidence,
        warnings=("Round pin is retained as a replaceable repeatability option; the stop and diamond own the current constraint rows.",),
        constrains_locating=False))
    diamond_direction = _orthogonal(_unit(diamond_candidate.normal), Vec3(0.0, 1.0, 0.0))
    placements.append(Placement(
        "diamond-pin", PlacementRole.DIAMOND_PIN, diamond_candidate.reference, diamond_candidate.position_mm,
        diamond_direction, diamond_candidate.normal, parent_structural_member=parent,
        tolerance_mm=0.1, constrained_directions=(diamond_direction,),
        weld_distortion_intent="relieve thermal growth in the loading direction",
        rule="diamond_pin_thermal_relief", evidence=diamond_candidate.evidence,
        assumptions=common + ("Diamond pin constrains one explicit direction to avoid overconstraint.",),
        confidence=diamond_candidate.confidence, constrains_locating=True))
    placements.append(Placement(
        "loading-stop", PlacementRole.STOP, stop_candidate.reference, stop_candidate.position_mm,
        annotations.loading_direction, annotations.loading_direction, parent_structural_member=parent,
        tolerance_mm=0.1, weld_distortion_intent="react loading force without adding a duplicate locating direction",
        rule="loading_stop_reaction_path", evidence=(f"loading_direction={annotations.loading_direction}",),
        assumptions=("Stop is retained as a load reaction and locating record; the round pin remains a replaceable option.",),
        confidence=stop_candidate.confidence, constrains_locating=True))
    placements.append(Placement(
        "loading-stop-secondary", PlacementRole.STOP, stop_candidate.reference,
        Vec3(stop_candidate.position_mm.x, stop_candidate.position_mm.y + params.minimum_datum_separation_mm,
             stop_candidate.position_mm.z),
        annotations.loading_direction, annotations.loading_direction, parent_structural_member=parent,
        tolerance_mm=0.1, weld_distortion_intent="share loading reaction without adding a new datum family",
        rule="secondary_loading_stop_reaction_path", evidence=("secondary stop spacing is explicit",),
        assumptions=("Secondary stop is part of the load reaction path and is checked for duplicate directions.",),
        confidence=stop_candidate.confidence, constrains_locating=True))
    support_candidate = selected[2]
    placements.append(Placement(
        "support-1", PlacementRole.SUPPORT, support_candidate.reference, support_candidate.position_mm,
        support_candidate.normal, support_candidate.normal, parent_structural_member=parent,
        weld_distortion_intent="support likely sag and transfer clamp reaction without locating the part",
        rule="support_under_reaction_path", evidence=support_candidate.evidence,
        assumptions=("Support is not added to the locating constraint rows.",),
        confidence=support_candidate.confidence, constrains_locating=False))
    clamp = tooling.select("clamp", minimum_stroke=params.minimum_clamp_stroke_mm,
                           minimum_force=params.required_clamp_force_n)
    clamp_item: ToolingItem | None = clamp.item if clamp else None
    clamp_position = Vec3(stop_candidate.position_mm.x, stop_candidate.position_mm.y,
                           stop_candidate.position_mm.z)
    placements.append(Placement(
        "clamp-1", PlacementRole.CLAMP, stop_candidate.reference, clamp_position,
        Vec3(-stop_candidate.normal.x, -stop_candidate.normal.y, -stop_candidate.normal.z),
        stop_candidate.normal, mount_reference=stop_candidate.reference,
        parent_structural_member=parent, tooling_identity=clamp_item.identity if clamp_item else None,
        stroke_mm=clamp_item.stroke if clamp_item else None, reach_mm=clamp_item.stroke if clamp_item else None,
        force_n=clamp_item.force if clamp_item else None, bounds=_translate(clamp_item.envelope, clamp_position) if clamp_item else None,
        weld_distortion_intent="react clamp force into the stop and support path",
        rule="standard_clamp_reaction_path", evidence=(clamp.reason,) if clamp else (),
        assumptions=("Generic tooling metadata is not a force certificate or production approval.",),
        confidence=stop_candidate.confidence, constrains_locating=False))
    return tuple(placements)


def generate_placement_plan(product: ProductModel, annotations: EngineeringAnnotations,
                            candidates: tuple[DatumCandidate, ...], *,
                            structure: StructuralAssembly | None = None,
                            tooling: ToolingLibrary | None = None,
                            access: AccessAnalysis | None = None,
                            parameters: PlacementParameters | None = None) -> PlacementPlan:
    """Generate one deterministic placement arrangement from explicit evidence."""
    params = parameters or PlacementParameters()
    scores = rank_datum_candidates(product, candidates, annotations, parameters=params)
    findings: list[PlacementFinding] = []
    if not candidates or len([item for item in scores if item.eligible]) < 3:
        findings.append(_finding("missing_datum_evidence", RULE_MISSING_DATUM_EVIDENCE, "error",
                                 "at least three eligible datum candidates are required for placement",
                                 evidence=(f"candidate_count={len(candidates)}",)))
    selected_tooling = tooling or generic_tooling_library()
    placements = _make_placements(product, annotations, candidates, scores, selected_tooling, structure, params)
    plan = PlacementPlan(product.source_sha256, "mm", placements, scores, None, tuple(findings))
    findings.extend(validate_placement_plan(product, plan, structure=structure, access=access, parameters=params))
    # A second candidate arrangement preserves caller intent while making a
    # failed top-ranked placement reviewable rather than silently repairing it.
    alternatives: tuple[PlacementAlternative, ...] = ()
    eligible = [item.candidate_identity for item in scores if item.eligible]
    if len(eligible) >= 4:
        alternate_candidates = tuple(candidates[index] for index in range(len(candidates)) if candidates[index].identity in eligible[1:4])
        alternate_placements = _make_placements(product, annotations, alternate_candidates,
                                                rank_datum_candidates(product, alternate_candidates, annotations, parameters=params),
                                                selected_tooling, structure, params)
        alternate_plan = PlacementPlan(product.source_sha256, "mm", alternate_placements, (), None, ())
        alternate_findings = validate_placement_plan(product, alternate_plan, structure=structure, access=access, parameters=params)
        alternatives = (PlacementAlternative("alternative-datum-spacing", alternate_placements, alternate_findings,
                                              ("Shifted the deterministic datum window to the next eligible surfaces.",)),)
    return PlacementPlan(product.source_sha256, "mm", placements, scores,
                          LocatingStrategy(tuple(_contact(item) for item in placements
                                                 if item.constrains_locating and item.role in {
                                                     PlacementRole.PRIMARY_DATUM, PlacementRole.SECONDARY_DATUM,
                                                     PlacementRole.TERTIARY_DATUM, PlacementRole.ROUND_PIN,
                                                     PlacementRole.DIAMOND_PIN, PlacementRole.REST, PlacementRole.STOP}),
                                            tolerance_mm=0.1, repeatability_mm=0.1,
                                            datum_assumptions=("Placement engine consumed explicit candidate normals and positions.",)) if placements else None,
                          tuple(findings), alternatives)


def compare_placement_plans(plans: tuple[PlacementPlan, ...]) -> tuple[tuple[str, str, float, tuple[str, ...]], ...]:
    """Compare plans deterministically without allowing score to override validity."""
    result = []
    for plan in plans:
        valid_rank = 0 if plan.valid else 1
        confidence = sum(item.confidence for item in plan.placements) / len(plan.placements) if plan.placements else 0.0
        result.append((plan.evidence_digest[:16], "valid" if plan.valid else "blocked",
                       round(valid_rank * 100.0 + (1.0 - confidence) * 10.0, 6),
                       (f"confidence={confidence:.6f}", "deterministic validity precedes preference score")))
    return tuple(sorted(result, key=lambda item: (item[1] != "valid", item[2], item[0])))
