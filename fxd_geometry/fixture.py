"""Deterministic, CAD-neutral fixture primitive generation.

This is intentionally an editable concept model, not a CAD-kernel model.  The
primitive bounds are a safe AABB proof until a licensed kernel adapter is
introduced.  Source product geometry is never modified or embedded in the
generated features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from .aabb import Aabb, Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .product_model import Body, ProductModel


class FixtureGenerationError(ValueError):
    """Raised when fixture generation inputs are incomplete or inconsistent."""


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

    def __post_init__(self) -> None:
        values = (self.base_margin, self.base_thickness, self.support_width,
                  self.support_depth, self.contact_clearance,
                  self.manufacturing_allowance, self.locator_height,
                  self.locator_wall)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise FixtureGenerationError("fixture dimensions must be finite and non-negative")
        if self.base_thickness == 0 or self.support_width == 0 or self.support_depth == 0:
            raise FixtureGenerationError("base and support dimensions must be positive")


@dataclass(frozen=True)
class FixtureFeature:
    """One editable generated feature with complete generation traceability."""

    identity: str
    kind: str
    bounds: Aabb
    source_references: tuple[GeometryReference, ...]
    rule: str
    parameters: dict[str, float]
    units: str = "mm"
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


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
    return math.prod(max(0.0, high - low) for low, high in zip(box.minimum.__dict__.values(), box.maximum.__dict__.values()))


def _ref(component: str, body: Body) -> GeometryReference:
    return GeometryReference(component, body.identity)


def generate_fixture_primitives(product: ProductModel, annotations: EngineeringAnnotations,
                                parameters: FixtureParameters | None = None) -> FixtureConcept:
    """Generate a deterministic starter fixture around the annotated product.

    The current proof uses axis-aligned bounds and translation-only placements.
    It creates one baseplate, one support per physical body, one loading stop,
    and a round/relieved locator pair.  The output is a proposal requiring
    engineering review; findings are evidence, not a release decision.
    """
    if product.units != "mm":
        raise FixtureGenerationError("fixture generation requires an explicit millimetre product")
    annotations.validate_references(product)
    params = parameters or FixtureParameters()
    physical = tuple((component, body) for component in product.components for body in component.bodies)
    if not physical:
        raise FixtureGenerationError("product has no physical bodies to fixture")
    product_box = _bounds(body.bounds.transformed(component.transform) for component, body in physical)
    p = product_box.minimum
    q = product_box.maximum
    base_top = p.z - params.contact_clearance
    features: list[FixtureFeature] = []
    base = Aabb(Vec3(p.x - params.base_margin, p.y - params.base_margin, base_top - params.base_thickness),
                Vec3(q.x + params.base_margin, q.y + params.base_margin, base_top))
    features.append(FixtureFeature("baseplate", "baseplate", base, (), "baseplate_envelope", {
        "margin": params.base_margin, "thickness": params.base_thickness,
    }, assumptions=("Product bounds define the baseplate envelope.",)))

    for index, (component, body) in enumerate(physical, 1):
        world = body.bounds.transformed(component.transform)
        center = Vec3((world.minimum.x + world.maximum.x) / 2, (world.minimum.y + world.maximum.y) / 2, 0)
        support = Aabb(Vec3(center.x - params.support_width / 2, center.y - params.support_depth / 2, base_top),
                       Vec3(center.x + params.support_width / 2, center.y + params.support_depth / 2, world.minimum.z))
        features.append(FixtureFeature(f"support-{index}", "support_pad", support, (_ref(component.identity, body),),
            "support_under_each_body", {"width": params.support_width, "depth": params.support_depth,
                                         "contact_clearance": params.contact_clearance},
            assumptions=("Support location is the body AABB centroid.",)))

    axis = max(range(3), key=lambda i: abs((annotations.loading_direction.x, annotations.loading_direction.y, annotations.loading_direction.z)[i]))
    direction = (annotations.loading_direction.x, annotations.loading_direction.y, annotations.loading_direction.z)[axis]
    mins = (p.x, p.y, p.z)
    maxs = (q.x, q.y, q.z)
    low = list(mins); high = list(maxs)
    if direction >= 0:
        low[axis] = maxs[axis] + params.contact_clearance
        high[axis] = low[axis] + params.locator_wall
    else:
        high[axis] = mins[axis] - params.contact_clearance
        low[axis] = high[axis] - params.locator_wall
    # Stop spans the two non-loading axes and rises above the product contact.
    for other in range(3):
        if other != axis:
            low[other] -= params.locator_wall
            high[other] += params.locator_wall
    low[2] = base_top
    high[2] = max(high[2], q.z + params.locator_height)
    stop = Aabb(Vec3(*low), Vec3(*high))
    references = tuple(_ref(component.identity, body) for component, body in physical)
    features.append(FixtureFeature("loading-stop", "hard_stop", stop, references, "stop_against_loading_direction",
        {"wall": params.locator_wall, "height": params.locator_height, "contact_clearance": params.contact_clearance},
        assumptions=("Loading direction is represented by its dominant axis.",)))

    first_component, first_body = physical[0]
    world = first_body.bounds.transformed(first_component.transform)
    pin_x = world.minimum.x - params.contact_clearance - params.locator_wall / 2
    pin_y = (world.minimum.y + world.maximum.y) / 2
    pin = Aabb(Vec3(pin_x - params.locator_wall / 2, pin_y - params.locator_wall / 2, base_top),
               Vec3(pin_x + params.locator_wall / 2, pin_y + params.locator_wall / 2, base_top + params.locator_height))
    features.append(FixtureFeature("round-pin-1", "round_pin", pin, (_ref(first_component.identity, first_body),),
        "primary_round_locator", {"diameter": params.locator_wall, "height": params.locator_height,
                                   "contact_clearance": params.contact_clearance},
        assumptions=("AABB proof represents a round pin by its envelope.",)))
    relief = Aabb(Vec3(pin_x + params.locator_wall / 2, pin_y - params.locator_wall / 2, base_top),
                  Vec3(pin_x + params.locator_wall / 2 + params.locator_wall, pin_y + params.locator_wall / 2, base_top + params.locator_height))
    features.append(FixtureFeature("relieved-locator-1", "relieved_locator", relief, (_ref(first_component.identity, first_body),),
        "secondary_relieved_locator", {"relief": params.manufacturing_allowance, "height": params.locator_height},
        assumptions=("Relief is an editable manufacturing allowance, not a tolerance guarantee.",)))

    findings: list[FixtureFinding] = []
    for feature in features:
        overlap = _volume(feature.bounds.intersection(product_box))
        if overlap > params.contact_clearance ** 3 and feature.kind not in {"support_pad", "round_pin", "relieved_locator", "hard_stop"}:
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
