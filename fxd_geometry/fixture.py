"""Deterministic, CAD-neutral fixture primitive generation.

This is intentionally an editable concept model, not a CAD-kernel model. The
primitive bounds are a safe AABB proof until a licensed kernel adapter is
introduced. Source product geometry is never modified or embedded.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .aabb import Aabb, Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .product_model import Body, ProductModel


class FixtureGenerationError(ValueError):
    """Raised when fixture generation inputs are incomplete or inconsistent."""


@dataclass(frozen=True)
class ManufacturingSpec:
    """Public, explicit fabrication intent for one generated feature."""

    method: str
    material: str
    thickness: float | None = None
    fit: str = "nominal"
    clearance: float = 0.0
    allowance: float = 0.0
    interface: str | None = None
    operations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.method or not self.material or not self.fit:
            raise FixtureGenerationError("manufacturing method, material, and fit are required")
        values = (self.thickness, self.clearance, self.allowance)
        if any(value is not None and (not math.isfinite(value) or value < 0) for value in values):
            raise FixtureGenerationError("manufacturing dimensions must be finite and non-negative")


@dataclass(frozen=True)
class FixtureParameters:
    """Explicit nominal dimensions and allowances, all in millimetres."""

    base_margin: float = 25.0
    base_thickness: float = 10.0
    support_width: float = 20.0
    support_depth: float = 20.0
    contact_clearance: float = 0.5
    manufacturing_allowance: float = 1.0
    locator_height: float = 12.0
    locator_wall: float = 8.0
    locator_type: str = "round_pin"
    clamp_choice: str = "standard_clamp"
    fit: str = "nominal"

    def __post_init__(self) -> None:
        values = (self.base_margin, self.base_thickness, self.support_width,
                  self.support_depth, self.contact_clearance,
                  self.manufacturing_allowance, self.locator_height,
                  self.locator_wall)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise FixtureGenerationError("fixture dimensions must be finite and non-negative")
        if self.base_thickness == 0 or self.support_width == 0 or self.support_depth == 0:
            raise FixtureGenerationError("base and support dimensions must be positive")
        if self.locator_type not in {"round_pin", "relieved_locator"}:
            raise FixtureGenerationError("unsupported locator type")
        if not self.clamp_choice or not self.fit:
            raise FixtureGenerationError("clamp choice and fit are required")


@dataclass(frozen=True)
class FixtureFeature:
    identity: str
    kind: str
    bounds: Aabb
    source_references: tuple[GeometryReference, ...]
    rule: str
    parameters: dict[str, float]
    units: str = "mm"
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    manufacturing: ManufacturingSpec | None = None


@dataclass(frozen=True)
class FixtureFinding:
    code: str
    severity: str
    feature_identity: str | None
    message: str


@dataclass(frozen=True)
class FixtureConcept:
    source_sha256: str
    units: str
    parameters: FixtureParameters
    features: tuple[FixtureFeature, ...]
    findings: tuple[FixtureFinding, ...] = ()

    @property
    def warnings(self) -> tuple[FixtureFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")


def _bounds(boxes: Iterable[Aabb]) -> Aabb:
    items = tuple(boxes)
    if not items:
        raise FixtureGenerationError("product has no physical bodies to fixture")
    return Aabb(
        Vec3(*(min(getattr(item.minimum, axis) for item in items) for axis in ("x", "y", "z"))),
        Vec3(*(max(getattr(item.maximum, axis) for item in items) for axis in ("x", "y", "z"))),
    )


def _volume(box: Aabb | None) -> float:
    if box is None:
        return 0.0
    return math.prod(max(0.0, high - low) for low, high in
                     zip(box.minimum.__dict__.values(), box.maximum.__dict__.values()))


def _ref(component: str, body: Body) -> GeometryReference:
    return GeometryReference(component, body.identity)


def _dominant_axis(vector: Vec3) -> tuple[int, float]:
    values = (vector.x, vector.y, vector.z)
    axis = max(range(3), key=lambda index: abs(values[index]))
    return axis, 1.0 if values[axis] >= 0 else -1.0


def _aabb(low: list[float], high: list[float]) -> Aabb:
    return Aabb(Vec3(*low), Vec3(*high))


def _manufacturing(kind: str, params: FixtureParameters) -> ManufacturingSpec:
    """Map proof primitives to generic, non-proprietary fabrication intent."""
    if kind == "baseplate":
        return ManufacturingSpec("laser_cut", "mild_steel", params.base_thickness,
                                 "machined_datum", params.contact_clearance,
                                 params.manufacturing_allowance, "baseplate_slot",
                                 ("profile_cut", "deburr"))
    if kind in {"support_pad", "hard_stop", "relieved_locator"}:
        return ManufacturingSpec("laser_cut", "mild_steel", params.locator_wall,
                                 "adjustable_fit", params.contact_clearance,
                                 params.manufacturing_allowance, "tab_and_slot",
                                 ("profile_cut", "deburr", "weld"))
    if kind == "round_pin":
        return ManufacturingSpec("machined", "tool_steel", params.locator_wall,
                                 "replaceable_fit", params.contact_clearance,
                                 params.manufacturing_allowance, "reamed_hole",
                                 ("turn", "harden", "replaceable"))
    if kind == "clamp_mount":
        return ManufacturingSpec("laser_cut", "mild_steel", params.locator_wall,
                                 "slotted_adjustment", params.contact_clearance,
                                 params.manufacturing_allowance, "standard_clamp",
                                 ("profile_cut", "deburr", "weld"))
    return ManufacturingSpec("machined", "mild_steel", params.locator_wall,
                             "nominal", params.contact_clearance,
                             params.manufacturing_allowance, None, ("deburr",))


def generate_fixture_primitives(product: ProductModel, annotations: EngineeringAnnotations,
                                parameters: FixtureParameters | None = None) -> FixtureConcept:
    """Generate an orientation-aware deterministic starter fixture concept."""
    if product.units != "mm":
        raise FixtureGenerationError("fixture generation requires an explicit millimetre product")
    annotations.validate_references(product)
    params = parameters or FixtureParameters()
    physical = tuple((component, body) for component in product.components for body in component.bodies)
    if not physical:
        raise FixtureGenerationError("product has no physical bodies to fixture")

    product_box = _bounds(body.bounds.transformed(component.transform) for component, body in physical)
    mins = [product_box.minimum.x, product_box.minimum.y, product_box.minimum.z]
    maxs = [product_box.maximum.x, product_box.maximum.y, product_box.maximum.z]
    build_axis, build_sign = _dominant_axis(annotations.build_orientation)
    transverse = [axis for axis in range(3) if axis != build_axis]

    # The build vector points from the base toward the part. Positive therefore
    # places the base below the product minimum; negative places it beyond maximum.
    contact_plane = (mins[build_axis] - params.contact_clearance if build_sign > 0
                     else maxs[build_axis] + params.contact_clearance)
    base_low = [mins[i] - params.base_margin for i in range(3)]
    base_high = [maxs[i] + params.base_margin for i in range(3)]
    if build_sign > 0:
        base_low[build_axis] = contact_plane - params.base_thickness
        base_high[build_axis] = contact_plane
    else:
        base_low[build_axis] = contact_plane
        base_high[build_axis] = contact_plane + params.base_thickness

    features: list[FixtureFeature] = [FixtureFeature(
        "baseplate", "baseplate", _aabb(base_low, base_high), (), "baseplate_from_build_orientation",
        {"margin": params.base_margin, "thickness": params.base_thickness,
         "build_axis": float(build_axis), "build_sign": build_sign},
        assumptions=("Dominant build-orientation axis defines the proof-layer base normal.",),
        manufacturing=_manufacturing("baseplate", params),
    )]

    for index, (component, body) in enumerate(physical, 1):
        world = body.bounds.transformed(component.transform)
        world_min = [world.minimum.x, world.minimum.y, world.minimum.z]
        world_max = [world.maximum.x, world.maximum.y, world.maximum.z]
        center = [(world_min[i] + world_max[i]) / 2 for i in range(3)]
        low = center.copy()
        high = center.copy()
        low[transverse[0]] -= params.support_width / 2
        high[transverse[0]] += params.support_width / 2
        low[transverse[1]] -= params.support_depth / 2
        high[transverse[1]] += params.support_depth / 2
        if build_sign > 0:
            low[build_axis] = contact_plane
            high[build_axis] = world_min[build_axis]
        else:
            low[build_axis] = world_max[build_axis]
            high[build_axis] = contact_plane
        features.append(FixtureFeature(
            f"support-{index}", "support_pad", _aabb(low, high), (_ref(component.identity, body),),
            "support_along_build_orientation",
            {"width": params.support_width, "depth": params.support_depth,
             "contact_clearance": params.contact_clearance, "build_axis": float(build_axis)},
            assumptions=("Support location is the body AABB centroid on the transverse plane.",),
            manufacturing=_manufacturing("support_pad", params),
        ))

    load_axis, load_sign = _dominant_axis(annotations.loading_direction)
    stop_low = mins.copy()
    stop_high = maxs.copy()
    if load_sign > 0:
        stop_low[load_axis] = maxs[load_axis] + params.contact_clearance
        stop_high[load_axis] = stop_low[load_axis] + params.locator_wall
    else:
        stop_high[load_axis] = mins[load_axis] - params.contact_clearance
        stop_low[load_axis] = stop_high[load_axis] - params.locator_wall
    for axis in range(3):
        if axis != load_axis:
            stop_low[axis] -= params.locator_wall
            stop_high[axis] += params.locator_wall
    # Extend the stop back to the base plane without overwriting its loading-axis placement.
    if load_axis != build_axis:
        if build_sign > 0:
            stop_low[build_axis] = contact_plane
            stop_high[build_axis] = max(stop_high[build_axis], maxs[build_axis] + params.locator_height)
        else:
            stop_high[build_axis] = contact_plane
            stop_low[build_axis] = min(stop_low[build_axis], mins[build_axis] - params.locator_height)

    references = tuple(_ref(component.identity, body) for component, body in physical)
    features.append(FixtureFeature(
        "loading-stop", "hard_stop", _aabb(stop_low, stop_high), references,
        "stop_against_loading_direction",
        {"wall": params.locator_wall, "height": params.locator_height,
         "contact_clearance": params.contact_clearance, "loading_axis": float(load_axis),
         "loading_sign": load_sign},
        assumptions=("Dominant loading-direction axis defines the proof-layer stop normal.",),
        manufacturing=_manufacturing("hard_stop", params),
    ))

    first_component, first_body = physical[0]
    world = first_body.bounds.transformed(first_component.transform)
    wmin = [world.minimum.x, world.minimum.y, world.minimum.z]
    wmax = [world.maximum.x, world.maximum.y, world.maximum.z]
    pin_low = [(wmin[i] + wmax[i]) / 2 - params.locator_wall / 2 for i in range(3)]
    pin_high = [(wmin[i] + wmax[i]) / 2 + params.locator_wall / 2 for i in range(3)]
    offset_axis = transverse[0]
    pin_center = wmin[offset_axis] - params.contact_clearance - params.locator_wall / 2
    pin_low[offset_axis] = pin_center - params.locator_wall / 2
    pin_high[offset_axis] = pin_center + params.locator_wall / 2
    if build_sign > 0:
        pin_low[build_axis] = contact_plane
        pin_high[build_axis] = contact_plane + params.locator_height
    else:
        pin_high[build_axis] = contact_plane
        pin_low[build_axis] = contact_plane - params.locator_height
    pin = _aabb(pin_low, pin_high)
    features.append(FixtureFeature(
        "round-pin-1", "round_pin", pin, (_ref(first_component.identity, first_body),),
        "primary_round_locator", {"diameter": params.locator_wall, "height": params.locator_height,
                                  "contact_clearance": params.contact_clearance},
        assumptions=("AABB proof represents a round pin by its envelope.",),
        manufacturing=_manufacturing("round_pin", params),
    ))

    relief_low = pin_low.copy()
    relief_high = pin_high.copy()
    relief_low[offset_axis] = pin_high[offset_axis]
    relief_high[offset_axis] = pin_high[offset_axis] + params.locator_wall
    features.append(FixtureFeature(
        "relieved-locator-1", "relieved_locator", _aabb(relief_low, relief_high),
        (_ref(first_component.identity, first_body),), "secondary_relieved_locator",
        {"relief": params.manufacturing_allowance, "height": params.locator_height},
        assumptions=("Relief is an editable manufacturing allowance, not a tolerance guarantee.",),
        manufacturing=_manufacturing("relieved_locator", params),
    ))

    findings: list[FixtureFinding] = []
    for feature in features:
        overlap = _volume(feature.bounds.intersection(product_box))
        if overlap > params.contact_clearance ** 3 and feature.kind not in {
            "support_pad", "round_pin", "relieved_locator", "hard_stop"
        }:
            findings.append(FixtureFinding("obvious_collision", "error", feature.identity,
                f"{feature.identity} overlaps product bounds by {overlap:g} mm^3"))
    if not annotations.permitted_locating_surfaces:
        findings.append(FixtureFinding("missing_locating_surface_intent", "warning", None,
            "No permitted locating surfaces are annotated; generated contacts require review."))
    forbidden = {(ref.component_identity, ref.body_identity) for ref in annotations.forbidden_contact_areas}
    for feature in features:
        if any((ref.component_identity, ref.body_identity) in forbidden for ref in feature.source_references):
            findings.append(FixtureFinding("forbidden_contact", "error", feature.identity,
                f"{feature.identity} is generated from an annotated forbidden contact area"))
    if params.base_margin <= params.contact_clearance:
        findings.append(FixtureFinding("trapped_part", "error", "baseplate",
            "Baseplate unload margin is not greater than contact clearance; unload path may be trapped."))
    findings.append(FixtureFinding("concept_requires_engineering_review", "warning", None,
        "Primitive geometry is a concept proof and is not certified or approved for production."))
    return FixtureConcept(product.source_sha256, "mm", params, tuple(features), tuple(findings))
