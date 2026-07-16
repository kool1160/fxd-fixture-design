"""Deterministic proof-layer structural fixture concepts.

This module composes the existing fixture primitives into a connected
structure. It is CAD-neutral AABB evidence, not structural simulation or
released fabrication geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING

from .aabb import Aabb, Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .fixture import FixtureConcept, FixtureFeature, ManufacturingSpec
from .product_model import Body, ProductModel

if TYPE_CHECKING:
    from .concepts import CompleteFixtureConcept


class StructuralGenerationError(ValueError):
    """Raised when structural concept inputs are incomplete or malformed."""


class StructuralStrategy(str, Enum):
    BASEPLATE = "baseplate"
    WELDED_FRAME = "welded_frame"


STRUCTURAL_MEMBER_KINDS = frozenset({
    "baseplate", "welded_frame_base", "frame_rail", "base_support", "riser",
    "support", "stop_bracket", "locator_mount", "clamp_tower",
})


@dataclass(frozen=True)
class StructuralParameters:
    """Caller-visible sizing and selection assumptions, all in millimetres."""

    baseplate_max_span: float = 1000.0
    welded_frame_min_quantity: int = 50
    base_support_count: int = 4
    base_support_width: float = 80.0
    base_support_depth: float = 80.0
    base_support_height: float = 20.0
    frame_rail_width: float = 50.0
    frame_rail_height: float = 50.0
    frame_wall: float = 5.0
    connection_clearance: float = 0.1
    access_requirements: tuple[str, ...] = ()
    strategy_override: StructuralStrategy | None = None

    def __post_init__(self) -> None:
        values = (self.baseplate_max_span, self.base_support_width, self.base_support_depth,
                  self.base_support_height, self.frame_rail_width, self.frame_rail_height,
                  self.frame_wall, self.connection_clearance)
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise StructuralGenerationError("structural dimensions must be finite and positive")
        if self.welded_frame_min_quantity < 1 or self.base_support_count < 1:
            raise StructuralGenerationError("structural counts must be positive")
        if any(not isinstance(item, str) or not item.strip() for item in self.access_requirements):
            raise StructuralGenerationError("access requirements must contain non-empty strings")


@dataclass(frozen=True)
class StructuralMember:
    identity: str
    kind: str
    bounds: Aabb
    parent_identity: str | None
    source_references: tuple[GeometryReference, ...]
    rule: str
    parameters: tuple[tuple[str, object], ...]
    manufacturing: ManufacturingSpec | None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or self.kind not in STRUCTURAL_MEMBER_KINDS:
            raise StructuralGenerationError("structural member identity and kind are unsupported")
        if self.parent_identity == self.identity:
            raise StructuralGenerationError("structural member cannot parent itself")
        if any(not isinstance(item, GeometryReference) for item in self.source_references):
            raise StructuralGenerationError("structural source references are invalid")
        if len({key for key, _ in self.parameters}) != len(self.parameters):
            raise StructuralGenerationError("structural parameter keys must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "kind": self.kind,
            "bounds": self.bounds.as_dict(),
            "parent_identity": self.parent_identity,
            "source_references": [item.__dict__ for item in self.source_references],
            "rule": self.rule,
            "parameters": {key: value for key, value in self.parameters},
            "manufacturing": self.manufacturing.__dict__ if self.manufacturing else None,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class StructuralLoadPath:
    identity: str
    member_identities: tuple[str, ...]
    load_case: str
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class StructuralFinding:
    code: str
    severity: str
    rule: str
    message: str
    member_identities: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class StructuralAssembly:
    source_sha256: str
    units: str
    strategy: StructuralStrategy
    strategy_rule: str
    strategy_evidence: tuple[str, ...]
    members: tuple[StructuralMember, ...]
    load_paths: tuple[StructuralLoadPath, ...]
    sizing_assumptions: tuple[tuple[str, object], ...]
    assumptions: tuple[str, ...]
    findings: tuple[StructuralFinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_sha256 or self.units != "mm":
            raise StructuralGenerationError("structural assembly identity and millimetre units are required")
        if len({item.identity for item in self.members}) != len(self.members):
            raise StructuralGenerationError("structural member identities must be unique")
        if len({key for key, _ in self.sizing_assumptions}) != len(self.sizing_assumptions):
            raise StructuralGenerationError("structural sizing assumption keys must be unique")

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    @property
    def blocked(self) -> bool:
        return not self.valid

    @property
    def warnings(self) -> tuple[StructuralFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")

    @property
    def connections(self) -> tuple[tuple[str, str], ...]:
        return tuple((item.parent_identity, item.identity) for item in self.members if item.parent_identity)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256,
            "units": self.units,
            "strategy": self.strategy.value,
            "strategy_rule": self.strategy_rule,
            "strategy_evidence": list(self.strategy_evidence),
            "members": [item.to_dict() for item in self.members],
            "load_paths": [item.__dict__ for item in self.load_paths],
            "sizing_assumptions": {key: value for key, value in self.sizing_assumptions},
            "assumptions": list(self.assumptions),
            "findings": [item.__dict__ for item in self.findings],
        }


@dataclass(frozen=True)
class StructuralComparison:
    concept_identity: str
    strategy: StructuralStrategy
    status: str
    cost: float
    access: float
    loading: float
    repeatability: float
    rationale: tuple[str, ...]


def _physical(product: ProductModel) -> tuple[tuple[str, Body], ...]:
    return tuple((component.identity, body) for component in product.components for body in component.bodies)


def _product_bounds(product: ProductModel) -> Aabb:
    physical = _physical(product)
    if not physical:
        raise StructuralGenerationError("product has no physical bodies for structural generation")
    boxes = tuple(body.bounds.transformed(next(component.transform for component in product.components
                                               if component.identity == component_identity))
                  for component_identity, body in physical)
    return Aabb(
        Vec3(*(min(getattr(box.minimum, axis) for box in boxes) for axis in ("x", "y", "z"))),
        Vec3(*(max(getattr(box.maximum, axis) for box in boxes) for axis in ("x", "y", "z"))),
    )


def select_structural_strategy(product: ProductModel, annotations: EngineeringAnnotations,
                               parameters: StructuralParameters | None = None) -> tuple[StructuralStrategy, tuple[str, ...], tuple[str, ...]]:
    """Select a strategy from explicit product and manufacturing intent."""
    params = parameters or StructuralParameters()
    box = _product_bounds(product)
    spans = tuple(round(high - low, 3) for low, high in zip(box.minimum.__dict__.values(), box.maximum.__dict__.values()))
    process = annotations.process_type.lower()
    access = " ".join(params.access_requirements).lower()
    constraints = " ".join(annotations.shop_constraints).lower()
    reasons: list[str] = []
    if params.strategy_override is not None:
        strategy = params.strategy_override
        reasons.append("caller supplied a structural strategy override")
    else:
        frame = max(spans) > params.baseplate_max_span
        frame = frame or annotations.production_quantity >= params.welded_frame_min_quantity
        frame = frame or any(term in process + " " + constraints + " " + access
                             for term in ("robot", "cobot", "welded frame", "frame", "access"))
        strategy = StructuralStrategy.WELDED_FRAME if frame else StructuralStrategy.BASEPLATE
        if max(spans) > params.baseplate_max_span:
            reasons.append("product span exceeds the caller-supplied baseplate span threshold")
        if annotations.production_quantity >= params.welded_frame_min_quantity:
            reasons.append("production quantity meets the caller-supplied welded-frame threshold")
        if any(term in process + " " + constraints + " " + access
               for term in ("robot", "cobot", "welded frame", "frame", "access")):
            reasons.append("process or shop constraints call for structural-frame access")
    evidence = (
        f"product_spans_mm={spans}",
        f"loading_direction={annotations.loading_direction}",
        f"process_type={annotations.process_type}",
        f"production_quantity={annotations.production_quantity}",
        f"shop_constraints={annotations.shop_constraints}",
        f"access_requirements={params.access_requirements}",
    )
    assumptions = (
        "Strategy thresholds and process/access interpretation are caller-visible review heuristics, not universal shop policy.",
        "Structural strategy selection does not prove load capacity, weld quality, or operator safety.",
    )
    return strategy, evidence + tuple(reasons), assumptions


def _box_from_feature(feature: FixtureFeature) -> Aabb:
    return feature.bounds


def _bridge_bounds(parent: Aabb, child: Aabb, width: float, depth: float) -> Aabb:
    center = tuple((low + high) / 2 for low, high in zip(child.minimum.__dict__.values(), child.maximum.__dict__.values()))
    low = [center[0] - width / 2, center[1] - depth / 2, min(parent.maximum.z, child.minimum.z)]
    high = [center[0] + width / 2, center[1] + depth / 2, max(parent.maximum.z, child.maximum.z)]
    return Aabb(Vec3(*low), Vec3(*high))


def _member(identity: str, kind: str, bounds: Aabb, parent: str | None, references: tuple[GeometryReference, ...],
            rule: str, parameters: tuple[tuple[str, object], ...], manufacturing: ManufacturingSpec | None,
            assumptions: tuple[str, ...], warnings: tuple[str, ...] = ()) -> StructuralMember:
    return StructuralMember(identity, kind, bounds, parent, references, rule, tuple(sorted(parameters)),
                            manufacturing, assumptions, warnings)


def _manufacturing(kind: str, parameters: StructuralParameters, thickness: float) -> ManufacturingSpec:
    if kind in {"baseplate", "welded_frame_base", "frame_rail", "base_support", "riser", "stop_bracket", "clamp_tower"}:
        return ManufacturingSpec("laser_cut", "mild_steel", thickness, "nominal", 0.5, 1.0,
                                 "tab_and_slot", ("profile_cut", "deburr", "weld"))
    return ManufacturingSpec("laser_cut", "mild_steel", thickness, "nominal", 0.5, 1.0,
                             "tab_and_slot", ("profile_cut", "deburr", "weld"))


def _frame_members(base: Aabb, references: tuple[GeometryReference, ...], params: StructuralParameters,
                   parent: str) -> list[StructuralMember]:
    low, high = base.minimum, base.maximum
    w, h = params.frame_rail_width, params.frame_rail_height
    rail_y = min(w, max((high.y - low.y) / 4.0, params.frame_wall * 2.0))
    rail_x = min(w, max((high.x - low.x) / 4.0, params.frame_wall * 2.0))
    boxes = (
        ("frame-rail-x-low", Aabb(Vec3(low.x, low.y, low.z), Vec3(high.x, low.y + rail_y, high.z))),
        ("frame-rail-x-high", Aabb(Vec3(low.x, high.y - rail_y, low.z), Vec3(high.x, high.y, high.z))),
        ("frame-rail-y-low", Aabb(Vec3(low.x, low.y + rail_y, low.z), Vec3(low.x + rail_x, high.y - rail_y, high.z))),
        ("frame-rail-y-high", Aabb(Vec3(high.x - rail_x, low.y + rail_y, low.z), Vec3(high.x, high.y - rail_y, high.z))),
    )
    return [_member(identity, "frame_rail", bounds, parent, references, "welded_frame_perimeter_rail",
                    (("width_mm", w), ("height_mm", h), ("wall_mm", params.frame_wall)),
                    _manufacturing("frame_rail", params, params.frame_wall),
                    ("Tubing section sizing is an explicit proof-layer assumption requiring engineering review.",))
            for identity, bounds in boxes]


def _base_supports(base: Aabb, references: tuple[GeometryReference, ...], params: StructuralParameters,
                   parent: str) -> list[StructuralMember]:
    if params.base_support_count != 4:
        return [_member("base-support-1", "base_support",
                        Aabb(Vec3(base.minimum.x, base.minimum.y, base.minimum.z - params.base_support_height),
                             Vec3(base.minimum.x + params.base_support_width, base.minimum.y + params.base_support_depth, base.minimum.z)),
                        parent, references, "base_support_under_foundation",
                        (("width_mm", params.base_support_width), ("depth_mm", params.base_support_depth),
                         ("height_mm", params.base_support_height)),
                        _manufacturing("base_support", params, params.frame_wall),
                        ("Base support count was caller-configured; stability remains an engineering review item.",))]
    x0, x1 = base.minimum.x, base.maximum.x
    y0, y1 = base.minimum.y, base.maximum.y
    w, d, h = params.base_support_width, params.base_support_depth, params.base_support_height
    locations = ((x0, y0), (x1 - w, y0), (x0, y1 - d), (x1 - w, y1 - d))
    return [_member(f"base-support-{index}", "base_support",
                    Aabb(Vec3(x, y, base.minimum.z - h), Vec3(x + w, y + d, base.minimum.z)),
                    parent, references, "base_support_under_foundation",
                    (("width_mm", w), ("depth_mm", d), ("height_mm", h)),
                    _manufacturing("base_support", params, params.frame_wall),
                    ("Base support sizing is an explicit proof-layer assumption requiring stability review.",))
            for index, (x, y) in enumerate(locations, 1)]


def _path(member: StructuralMember, by_id: dict[str, StructuralMember]) -> StructuralLoadPath:
    ids: list[str] = []
    current: StructuralMember | None = member
    while current is not None:
        if current.identity in ids:
            break
        ids.append(current.identity)
        current = by_id.get(current.parent_identity) if current.parent_identity else None
    ids.reverse()
    return StructuralLoadPath(
        f"load-path-{member.identity}", tuple(ids), "fixture_support_and_clamp_reaction",
        (f"terminal_member={member.identity}", f"member_chain={'/'.join(ids)}"),
        ("Load path is connectivity evidence only; force adequacy and deflection are not simulated.",),
    )


def validate_structural_assembly(assembly: StructuralAssembly, *, connection_clearance: float = 0.1) -> tuple[StructuralFinding, ...]:
    """Fail closed on disconnected, unsupported, or structurally malformed proof geometry."""
    findings: list[StructuralFinding] = []
    by_id = {item.identity: item for item in assembly.members}
    roots = tuple(item for item in assembly.members if item.parent_identity is None)
    if len(roots) != 1:
        findings.append(StructuralFinding("multiple_or_missing_structural_roots", "error", "structural_root_required",
                                          "A complete fixture structure must have exactly one structural root.",
                                          tuple(item.identity for item in roots)))
    for member in assembly.members:
        if member.parent_identity is not None and member.parent_identity not in by_id:
            findings.append(StructuralFinding("unsupported_structural_parent", "error", "structural_parent_required",
                                              f"Structural member {member.identity} references an unknown parent.",
                                              (member.identity,), (f"parent={member.parent_identity}",)))
        if member.parent_identity and member.parent_identity in by_id:
            parent = by_id[member.parent_identity]
            if parent.bounds.clearance_to(member.bounds) > connection_clearance:
                findings.append(StructuralFinding("disconnected_structural_member", "error", "structural_connection_required",
                                                  f"Structural member {member.identity} is physically disconnected from {parent.identity}.",
                                                  (parent.identity, member.identity),
                                                  (f"clearance_mm={parent.bounds.clearance_to(member.bounds):.9g}",)))
        current = member
        seen: set[str] = set()
        while current.parent_identity is not None:
            if current.identity in seen:
                findings.append(StructuralFinding("structural_member_cycle", "error", "structural_graph_acyclic",
                                                  f"Structural parent graph cycles at {current.identity}.", (current.identity,)))
                break
            seen.add(current.identity)
            parent = by_id.get(current.parent_identity)
            if parent is None:
                break
            current = parent
    if not assembly.sizing_assumptions:
        findings.append(StructuralFinding("structural_sizing_missing", "warning", "structural_sizing_required",
                                          "Structural member sizing assumptions are not recorded."))
    if not assembly.load_paths:
        findings.append(StructuralFinding("structural_load_paths_missing", "error", "structural_load_path_required",
                                          "No deterministic load paths were generated."))
    return tuple(findings)


def generate_structural_assembly(product: ProductModel, annotations: EngineeringAnnotations,
                                 fixture: FixtureConcept,
                                 parameters: StructuralParameters | None = None) -> StructuralAssembly:
    """Compose existing primitives into a connected, editable structural concept."""
    if fixture.source_sha256 != product.source_sha256 or fixture.units != "mm":
        raise StructuralGenerationError("fixture and product source identity or units do not match")
    annotations.validate_references(product)
    params = parameters or StructuralParameters()
    strategy, evidence, strategy_assumptions = select_structural_strategy(product, annotations, params)
    base_feature = next((item for item in fixture.features if item.kind == "baseplate"), None)
    if base_feature is None:
        raise StructuralGenerationError("complete structural generation requires a baseplate proof feature")
    physical_refs = tuple(GeometryReference(component_identity, body.identity)
                         for component_identity, body in _physical(product))
    base_identity = "baseplate" if strategy == StructuralStrategy.BASEPLATE else "welded-frame-base"
    base_kind = "baseplate" if strategy == StructuralStrategy.BASEPLATE else "welded_frame_base"
    base = _member(base_identity, base_kind, _box_from_feature(base_feature), None, physical_refs,
                   "baseplate_or_welded_frame_strategy", (("thickness_mm", base_feature.parameters.get("thickness", params.frame_wall)),),
                   base_feature.manufacturing or _manufacturing(base_kind, params, params.frame_wall),
                   ("Base structure thickness is a practical proof-layer assumption requiring engineering review.",) + strategy_assumptions)
    members: list[StructuralMember] = [base]
    members.extend(_base_supports(base.bounds, physical_refs, params, base.identity))
    if strategy == StructuralStrategy.WELDED_FRAME:
        members.extend(_frame_members(base.bounds, physical_refs, params, base.identity))
    feature_kinds = {
        "support_pad": ("support", "support"),
        "hard_stop": ("stop_bracket", "bracket"),
        "round_pin": ("locator_mount", "locator"),
        "relieved_locator": ("locator_mount", "locator"),
        "clamp_mount": ("clamp_tower", "clamp"),
    }
    for feature in fixture.features:
        if feature.kind == "baseplate":
            continue
        mapping = feature_kinds.get(feature.kind)
        if mapping is None:
            raise StructuralGenerationError(f"unsupported fixture feature kind {feature.kind!r}")
        kind, label = mapping
        bridge_identity = f"{feature.identity}-{label}"
        bridge = _member(bridge_identity, kind if kind in {"stop_bracket", "locator_mount", "clamp_tower"} else "riser",
                         _bridge_bounds(base.bounds, feature.bounds, params.base_support_width / 2,
                                        params.base_support_depth / 2), base.identity, feature.source_references,
                         f"connect_{label}_to_structural_root",
                         (("width_mm", params.base_support_width / 2), ("depth_mm", params.base_support_depth / 2)),
                         _manufacturing(kind, params, params.frame_wall),
                         (f"{label} bridge is proof-layer connectivity geometry and requires engineering review.",))
        members.append(bridge)
        terminal = _member(feature.identity, "support" if feature.kind == "support_pad" else kind,
                           feature.bounds, bridge.identity, feature.source_references, feature.rule,
                           tuple(sorted(feature.parameters.items())), feature.manufacturing,
                           feature.assumptions, feature.warnings)
        members.append(terminal)
    members_tuple = tuple(members)
    by_id = {item.identity: item for item in members_tuple}
    paths = tuple(_path(item, by_id) for item in members_tuple if item.identity != base.identity and item.parent_identity)
    assembly = StructuralAssembly(
        product.source_sha256, "mm", strategy, "baseplate_or_welded_frame_strategy", evidence,
        members_tuple, paths,
        tuple(sorted((
            ("baseplate_max_span_mm", params.baseplate_max_span),
            ("frame_rail_height_mm", params.frame_rail_height),
            ("frame_rail_width_mm", params.frame_rail_width),
            ("frame_wall_mm", params.frame_wall),
            ("base_support_count", params.base_support_count),
            ("base_support_height_mm", params.base_support_height),
            ("connection_clearance_mm", params.connection_clearance),
        ))),
        strategy_assumptions,
    )
    findings = validate_structural_assembly(assembly, connection_clearance=params.connection_clearance)
    return StructuralAssembly(assembly.source_sha256, assembly.units, assembly.strategy, assembly.strategy_rule,
                              assembly.strategy_evidence, assembly.members, assembly.load_paths,
                              assembly.sizing_assumptions, assembly.assumptions, findings)


def compare_structural_concepts(concepts: tuple[CompleteFixtureConcept, ...]) -> tuple[StructuralComparison, ...]:
    """Compare generated structural alternatives without overriding validation."""
    result: list[StructuralComparison] = []
    for concept in concepts:
        structure = concept.structure
        if structure is None:
            continue
        breakdown = dict(concept.score.breakdown)
        result.append(StructuralComparison(
            concept.identity, structure.strategy, "invalid" if structure.blocked else concept.engineering_status,
            breakdown.get("cost", 0.0), 100.0 - len(structure.warnings) * 10.0,
            breakdown.get("loading_speed", 0.0), breakdown.get("repeatability", 0.0),
            (f"strategy={structure.strategy.value}", "deterministic eligibility precedes comparison score",
             "cost, access, loading, and repeatability values remain review comparisons, not structural adequacy claims"),
        ))
    return tuple(sorted(result, key=lambda item: item.concept_identity))
