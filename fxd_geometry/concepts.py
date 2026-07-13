"""Deterministic complete-fixture concept generation and ranking.

This module composes the proof-layer primitives into alternatives.  It does
not call an AI model: ranking is an explainable heuristic and all findings are
evidence or explicit review requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from .aabb import Aabb, Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .fixture import (FixtureConcept, FixtureFeature, FixtureFinding,
                      FixtureParameters,
                      generate_fixture_primitives)
from .product_model import Body, ProductModel


@dataclass(frozen=True)
class ConstraintAnalysis:
    """Conservative 3-2-1 proof summary for the proof-layer model."""

    controlled_translations: tuple[str, ...]
    rotational_status: str
    warnings: tuple[str, ...] = ()

    @property
    def underconstrained(self) -> bool:
        return bool(self.warnings)


@dataclass(frozen=True)
class ConceptScore:
    total: float
    breakdown: tuple[tuple[str, float], ...]
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class FixtureCorrection:
    """An engineer-owned correction attached to a concept, never source CAD."""

    key: str
    value: str
    reason: str


@dataclass(frozen=True)
class CompleteFixtureConcept:
    identity: str
    objective: str
    fixture: FixtureConcept
    locating_strategy: str
    clamping_strategy: str
    constraints: ConstraintAnalysis
    score: ConceptScore
    corrections: tuple[FixtureCorrection, ...] = ()

    def with_correction(self, correction: FixtureCorrection) -> "CompleteFixtureConcept":
        """Return an edited concept while preserving the immutable product input."""
        remaining = tuple(item for item in self.corrections if item.key != correction.key)
        return replace(self, corrections=remaining + (correction,))


@dataclass(frozen=True)
class RankedFixtureConcepts:
    source_sha256: str
    units: str
    concepts: tuple[CompleteFixtureConcept, ...]

    @property
    def ranked(self) -> tuple[CompleteFixtureConcept, ...]:
        return tuple(sorted(self.concepts, key=lambda item: (-item.score.total, item.identity)))


def _physical(product: ProductModel) -> tuple[tuple[str, Body], ...]:
    return tuple((component.identity, body) for component in product.components for body in component.bodies)


def _constraint_analysis(annotations: EngineeringAnnotations, primitive: FixtureConcept) -> ConstraintAnalysis:
    kinds = {feature.kind for feature in primitive.features}
    translations = ("build-normal", "loading-direction", "transverse-locator")
    warnings: list[str] = []
    if not annotations.permitted_locating_surfaces:
        warnings.append("underconstrained: permitted locating surfaces are not confirmed")
    if not {"round_pin", "relieved_locator"}.issubset(kinds):
        warnings.append("underconstrained: a complete 3-2-1 locator set is not present")
    # AABB proof geometry cannot verify contact normals or rotational restraint.
    rotational = "requires_geometry_kernel_contact_validation"
    warnings.append("rotation_validation_unavailable: AABB evidence cannot prove rotational restraint")
    return ConstraintAnalysis(translations, rotational, tuple(warnings))


def _clamp_feature(product: ProductModel, parameters: FixtureParameters, index: int) -> FixtureFeature:
    physical = _physical(product)
    component, body = physical[(index - 1) % len(physical)]
    world = body.bounds.transformed(next(item.transform for item in product.components if item.identity == component))
    center = [(low + high) / 2 for low, high in zip(world.minimum.__dict__.values(), world.maximum.__dict__.values())]
    low = [world.minimum.x, world.minimum.y, world.minimum.z]
    high = [world.maximum.x, world.maximum.y, world.maximum.z]
    axis = max(range(3), key=lambda i: high[i] - low[i])
    low[axis] = high[axis] + parameters.contact_clearance
    high[axis] = low[axis] + parameters.locator_wall
    for other in range(3):
        if other != axis:
            low[other] = center[other] - parameters.support_width / 2
            high[other] = center[other] + parameters.support_width / 2
    return FixtureFeature(
        f"clamp-mount-{index}", "clamp_mount", Aabb(Vec3(*low), Vec3(*high)),
        (GeometryReference(component, body.identity),), "standard_clamp_mount_at_reaction_path",
        {"reach": parameters.locator_wall, "contact_clearance": parameters.contact_clearance},
        assumptions=("Clamp force and purchased hardware selection require engineering review.",),
    )


def _score(objective: str, clamp_count: int, constraints: ConstraintAnalysis) -> ConceptScore:
    # Scores are intentionally transparent and bounded. They are not a safety claim.
    base = {"minimum_cost": (92, 82, 62), "fast_loading": (72, 94, 68), "high_repeatability": (55, 70, 94)}[objective]
    penalties = len(constraints.warnings) * 4
    values = tuple(max(0.0, min(100.0, value - penalties)) for value in base)
    breakdown = (("cost", values[0]), ("loading_speed", values[1]), ("repeatability", values[2]))
    total = round(sum(values) / 3, 2)
    return ConceptScore(total, breakdown, (f"objective={objective}", f"clamp_count={clamp_count}", f"constraint_warning_penalty={penalties}"))


def generate_fixture_concepts(product: ProductModel, annotations: EngineeringAnnotations,
                              parameters: FixtureParameters | None = None) -> RankedFixtureConcepts:
    """Generate three deterministic alternatives and rank them by explainable score."""
    annotations.validate_references(product)
    primitive = generate_fixture_primitives(product, annotations, parameters)
    params = parameters or FixtureParameters()
    objectives = ("minimum_cost", "fast_loading", "high_repeatability")
    concepts: list[CompleteFixtureConcept] = []
    for objective in objectives:
        clamp_count = 2 if objective == "high_repeatability" else 1
        features = primitive.features + tuple(_clamp_feature(product, params, index) for index in range(1, clamp_count + 1))
        findings = list(primitive.findings)
        constraints = _constraint_analysis(annotations, primitive)
        for warning in constraints.warnings:
            code = warning.split(":", 1)[0]
            findings.append(FixtureFinding(code, "warning", None, warning))
        fixture = replace(primitive, features=features, findings=tuple(findings))
        concepts.append(CompleteFixtureConcept(
            f"concept-{objective}", objective, fixture, "3-2-1 proof-layer locating", "standard toggle clamp reaction path",
            constraints, _score(objective, clamp_count, constraints)))
    return RankedFixtureConcepts(product.source_sha256, "mm", tuple(concepts))
