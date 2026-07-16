"""Deterministic complete-fixture concept generation and ranking.

This module composes the proof-layer primitives into alternatives. It does
not call an AI model: ranking is an explainable heuristic and deterministic
engineering eligibility always outranks preference scores.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .aabb import Aabb, Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .fixture import (FixtureConcept, FixtureFeature, FixtureFinding,
                      FixtureParameters, ManufacturingSpec, generate_fixture_primitives)
from .constraints import LocatingAnalysis, LocatingStrategy, analyze_locating_strategy
from .product_model import Body, ProductModel
from .structure import StructuralAssembly, generate_structural_assembly


@dataclass(frozen=True)
class ConstraintAnalysis:
    """Conservative 3-2-1 proof summary for the proof-layer model."""

    controlled_translations: tuple[str, ...]
    rotational_status: str
    warnings: tuple[str, ...] = ()
    locating_analysis: LocatingAnalysis | None = None

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
    structure: StructuralAssembly | None = None

    @property
    def engineering_status(self) -> str:
        """Return valid, provisional, or invalid from deterministic evidence."""
        severities = {finding.severity for finding in self.fixture.findings}
        if self.structure is not None:
            severities.update(item.severity for item in self.structure.findings)
        if "error" in severities:
            return "invalid"
        if "warning" in severities or self.constraints.warnings:
            return "provisional"
        return "valid"

    @property
    def eligible_for_recommendation(self) -> bool:
        return self.engineering_status != "invalid"

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
        """Rank engineering eligibility first, then preference score."""
        status_order = {"valid": 0, "provisional": 1, "invalid": 2}
        return tuple(sorted(
            self.concepts,
            key=lambda item: (status_order[item.engineering_status], -item.score.total, item.identity),
        ))

    @property
    def recommended(self) -> CompleteFixtureConcept | None:
        """Return the highest-ranked eligible concept; never recommend invalid work."""
        return next((item for item in self.ranked if item.eligible_for_recommendation), None)


def _physical(product: ProductModel) -> tuple[tuple[str, Body], ...]:
    return tuple((component.identity, body) for component in product.components for body in component.bodies)


def _constraint_analysis(annotations: EngineeringAnnotations, primitive: FixtureConcept,
                         product: ProductModel,
                         locating_strategy: LocatingStrategy | None = None) -> ConstraintAnalysis:
    if locating_strategy is not None:
        analysis = analyze_locating_strategy(product, locating_strategy)
        warnings = tuple(item.message for item in analysis.findings
                         if item.severity in {"warning", "error"})
        return ConstraintAnalysis(
            analysis.controlled_dofs, "validated" if analysis.rank == 6 else "underconstrained",
            warnings, analysis)
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
    return ConstraintAnalysis(translations, rotational, tuple(warnings), None)


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
        manufacturing=ManufacturingSpec(
            "laser_cut", "mild_steel", parameters.locator_wall, "slotted_adjustment",
            parameters.contact_clearance, parameters.manufacturing_allowance,
            "standard_clamp", ("profile_cut", "deburr", "weld")),
    )


def _score(objective: str, clamp_count: int, constraints: ConstraintAnalysis) -> ConceptScore:
    # Scores compare eligible alternatives only; they never override engineering status.
    base = {"minimum_cost": (92, 82, 62), "fast_loading": (72, 94, 68), "high_repeatability": (55, 70, 94)}[objective]
    penalties = len(constraints.warnings) * 4
    values = tuple(max(0.0, min(100.0, value - penalties)) for value in base)
    breakdown = (("cost", values[0]), ("loading_speed", values[1]), ("repeatability", values[2]))
    total = round(sum(values) / 3, 2)
    return ConceptScore(total, breakdown, (
        f"objective={objective}",
        f"clamp_count={clamp_count}",
        f"constraint_warning_penalty={penalties}",
        "engineering_status_is_ranked_before_score",
    ))


def generate_fixture_concepts(product: ProductModel, annotations: EngineeringAnnotations,
                              parameters: FixtureParameters | None = None,
                              locating_strategy: LocatingStrategy | None = None) -> RankedFixtureConcepts:
    """Generate three deterministic alternatives and rank them by gated evidence."""
    annotations.validate_references(product)
    primitive = generate_fixture_primitives(product, annotations, parameters)
    params = parameters or FixtureParameters()
    objectives = ("minimum_cost", "fast_loading", "high_repeatability")
    concepts: list[CompleteFixtureConcept] = []
    for objective in objectives:
        clamp_count = 2 if objective == "high_repeatability" else 1
        features = primitive.features + tuple(
            _clamp_feature(product, params, index) for index in range(1, clamp_count + 1)
        )
        findings = list(primitive.findings)
        constraints = _constraint_analysis(annotations, primitive, product, locating_strategy)
        for warning in constraints.warnings:
            code = warning.split(":", 1)[0]
            severity = "error" if constraints.locating_analysis and not constraints.locating_analysis.strategy_valid else "warning"
            findings.append(FixtureFinding(code, severity, None, warning))
        fixture = replace(primitive, features=features, findings=tuple(findings))
        structure = generate_structural_assembly(product, annotations, fixture)
        concepts.append(CompleteFixtureConcept(
            f"concept-{objective}", objective, fixture,
            "3-2-1 proof-layer locating", "standard toggle clamp reaction path",
            constraints, _score(objective, clamp_count, constraints), structure=structure,
        ))
    return RankedFixtureConcepts(product.source_sha256, "mm", tuple(concepts))
