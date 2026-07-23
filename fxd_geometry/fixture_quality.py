"""Deterministic concept-quality evidence for supported fixture-build plans.

Quality ranking is subordinate to blockers: a numerically attractive concept
cannot pass when its product contacts, datum strategy, reaction paths, base
connectivity, handling flow, or manufacturing intent are incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .fabrication_workflow import (
    BuildComponentRole,
    FixtureBuildPlan,
    GeometryAuthority,
)
from .fixture_knowledge import PrecedentRetrievalResult, load_fixture_knowledge


FIXTURE_CONCEPT_QUALITY_SCHEMA = "fxd-fixture-concept-quality-v1"


@dataclass(frozen=True)
class FixtureConceptQualityMetric:
    identity: str
    value: float
    unit: str
    status: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class FixtureConceptQualityFinding:
    identity: str
    category: str
    severity: str
    message: str
    affected_identities: tuple[str, ...]
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "affected_identities": list(self.affected_identities),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class FixtureConceptQualityEvidence:
    identity: str
    fixture_length_mm: float
    occupied_length_mm: float
    empty_span_ratio: float
    station_pitch_mm: float
    station_count: int
    product_specific_contacts_per_station: tuple[int, ...]
    role_sets_per_station: tuple[tuple[str, ...], ...]
    clamp_support_mappings: tuple[tuple[str, str], ...]
    connected_component_identities: tuple[str, ...]
    disconnected_component_identities: tuple[str, ...]
    mounting_point_count: int
    datum_dof_mappings: tuple[str, ...]
    loading_steps: tuple[str, ...]
    release_steps: tuple[str, ...]
    unloading_steps: tuple[str, ...]
    weld_strategy: tuple[str, ...]
    manufacturable_component_identities: tuple[str, ...]
    unmanufacturable_component_identities: tuple[str, ...]
    redundant_location_identities: tuple[str, ...]
    foolproof_count: int
    precedent_record_identities: tuple[str, ...]
    rejection_record_identities: tuple[str, ...]
    precedent_current: bool


@dataclass(frozen=True)
class FixtureConceptQualityReport:
    schema_version: str
    evidence_identity: str
    status: str
    score: int
    score_breakdown: tuple[tuple[str, int], ...]
    metrics: tuple[FixtureConceptQualityMetric, ...]
    blockers: tuple[FixtureConceptQualityFinding, ...]
    warnings: tuple[FixtureConceptQualityFinding, ...]
    precedent_record_identities: tuple[str, ...]
    user_rejection_rules_triggered: tuple[str, ...]
    improvement_recommendations: tuple[str, ...]
    affected_identities: tuple[str, ...]
    datum_dof_mappings: tuple[str, ...]
    clamp_support_mappings: tuple[tuple[str, str], ...]

    @property
    def evidence_digest(self) -> str:
        return sha256(json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evidence_identity": self.evidence_identity,
            "status": self.status,
            "score": self.score,
            "score_breakdown": [
                {"category": key, "score": value}
                for key, value in self.score_breakdown
            ],
            "metrics": [item.to_dict() for item in self.metrics],
            "blockers": [item.to_dict() for item in self.blockers],
            "warnings": [item.to_dict() for item in self.warnings],
            "precedent_record_identities": list(self.precedent_record_identities),
            "user_rejection_rules_triggered": list(self.user_rejection_rules_triggered),
            "improvement_recommendations": list(self.improvement_recommendations),
            "affected_identities": list(self.affected_identities),
            "datum_dof_mappings": list(self.datum_dof_mappings),
            "clamp_support_mappings": [
                {"clamp": clamp, "support": support}
                for clamp, support in self.clamp_support_mappings
            ],
        }


_CONTACT_ROLES = {
    BuildComponentRole.SUPPORT_PAD,
    BuildComponentRole.LOCATOR_PLATE,
    BuildComponentRole.HARD_STOP,
    BuildComponentRole.ROUND_PIN,
    BuildComponentRole.DIAMOND_PIN,
    BuildComponentRole.TOGGLE_CLAMP,
}
_REQUIRED_STATION_ROLES = {
    BuildComponentRole.SUPPORT_PAD.value,
    BuildComponentRole.LOCATOR_PLATE.value,
    BuildComponentRole.HARD_STOP.value,
    BuildComponentRole.TOGGLE_CLAMP.value,
}
_STRUCTURAL_ROLES = {
    BuildComponentRole.BASEPLATE,
    BuildComponentRole.STATION_PLATE,
    BuildComponentRole.TUBE_FRAME,
    BuildComponentRole.CROSSMEMBER,
    BuildComponentRole.GUSSET,
    BuildComponentRole.DATUM_RAIL,
    BuildComponentRole.END_BRACE,
    BuildComponentRole.MOUNTING_FOOT,
}
_MANUFACTURABLE_TOKENS = (
    "laser cut", "machine", "drill", "tap", "weld", "shim stock",
    "purchased", "motion envelope",
)


def _component_connected(plan: FixtureBuildPlan, identity: str) -> bool:
    by_identity = {item.identity: item for item in plan.components}
    seen = set()
    current = by_identity.get(identity)
    while current is not None and current.identity not in seen:
        if current.role == BuildComponentRole.BASEPLATE:
            return True
        seen.add(current.identity)
        current = by_identity.get(current.parent_component_identity or "")
    return False


def evidence_from_fixture_build(
    plan: FixtureBuildPlan,
    precedent: PrecedentRetrievalResult | None = None,
) -> FixtureConceptQualityEvidence:
    layout = plan.multi_station_layout
    if layout is None:
        raise ValueError("fixture concept quality currently requires a supported multi-station layout")
    primary = layout.primary_axis
    stations = tuple(sorted(layout.stations, key=lambda item: item.station_index))
    station_span = (
        stations[0].product_bounds.maximum.x - stations[0].product_bounds.minimum.x
        if primary == "x" else
        stations[0].product_bounds.maximum.y - stations[0].product_bounds.minimum.y
    )
    requirements = layout.requirements
    necessary_gap = max(
        requirements.clamp_sweep_mm or 0.0,
        requirements.hand_clearance_mm,
        requirements.weld_clearance_mm,
        requirements.adjustment_allowance_mm,
    )
    excess_per_gap = max(0.0, layout.station_pitch_mm - station_span - necessary_gap)
    excess_span = excess_per_gap * max(0, len(stations) - 1)
    fixture_length = layout.required_fixture_length_mm
    occupied_length = max(0.0, fixture_length - excess_span)
    empty_span_ratio = excess_span / fixture_length if fixture_length else 1.0
    contact_counts, role_sets = [], []
    datum_dof = []
    for station in stations:
        station_components = tuple(
            item for item in plan.components
            if f"station={station.identity}" in item.evidence
        )
        contacts = tuple(item for item in station_components if item.role in _CONTACT_ROLES)
        contact_counts.append(sum(
            any(value.startswith("product_feature=") for value in item.evidence)
            and any(reference.face_identity for reference in item.source_references)
            for item in contacts
        ))
        role_sets.append(tuple(sorted({item.role.value for item in station_components})))
        datum_dof.extend(
            value for item in station_components for value in item.evidence
            if value.startswith(("datum=", "dof=", "floating_dof="))
        )
    clamps = tuple(
        item for item in plan.components if item.role == BuildComponentRole.TOGGLE_CLAMP
    )
    mappings = tuple(sorted(
        (item.identity, item.reaction_support_identity or "") for item in clamps
        if item.reaction_support_identity
    ))
    connected = tuple(sorted(
        item.identity for item in plan.components
        if item.role in _STRUCTURAL_ROLES and _component_connected(plan, item.identity)
    ))
    disconnected = tuple(sorted(
        item.identity for item in plan.components
        if item.role != BuildComponentRole.BASEPLATE
        and item.geometry_authority != GeometryAuthority.PURCHASED_COMPONENT
        and not _component_connected(plan, item.identity)
    ))
    mounting_points = sum(
        len(item.holes) for item in plan.components
        if item.role in {
            BuildComponentRole.BASEPLATE,
            BuildComponentRole.MOUNTING_FOOT,
            BuildComponentRole.TUBE_FRAME,
        }
    )
    unmanufacturable = tuple(sorted(
        item.identity for item in plan.components
        if item.geometry_authority == GeometryAuthority.AUTHORED_MANUFACTURING
        and not any(token in item.manufacturing_process.lower() for token in _MANUFACTURABLE_TOKENS)
    ))
    manufacturable = tuple(sorted(
        item.identity for item in plan.components
        if item.geometry_authority == GeometryAuthority.AUTHORED_MANUFACTURING
        and item.identity not in unmanufacturable
    ))
    repeated_fixed_locators = []
    for station in stations:
        station_locators = tuple(
            item for item in plan.components
            if f"station={station.identity}" in item.evidence and item.locating_constraint
        )
        if len(station_locators) > 5:
            repeated_fixed_locators.extend(item.identity for item in station_locators[5:])
    selected = tuple(sorted(
        precedent.selected_record_identities
        if precedent else plan.precedent_record_identities
    ))
    rejected = (
        tuple(item.record_identity for item in precedent.rejected_constraints)
        if precedent else ()
    )
    return FixtureConceptQualityEvidence(
        plan.identity, round(fixture_length, 6), round(occupied_length, 6),
        round(empty_span_ratio, 6), round(layout.station_pitch_mm, 6), len(stations),
        tuple(contact_counts), tuple(role_sets), mappings, connected, disconnected,
        mounting_points, tuple(sorted(set(datum_dof))), plan.loading_sequence,
        plan.release_sequence, plan.unload_sequence,
        tuple(filter(None, (plan.finish_weld_handoff, *plan.tack_sequence))),
        manufacturable, unmanufacturable, tuple(repeated_fixed_locators),
        len(plan.poka_yokes), selected, rejected,
        plan.precedent_library_evidence_digest
        == load_fixture_knowledge().evidence_digest,
    )


def rejected_generic_m32_evidence() -> FixtureConceptQualityEvidence:
    """Frozen abstract reproduction of the first rejected M32 visual concept."""
    return FixtureConceptQualityEvidence(
        "m32-rejected-generic-benchmark-v1",
        1250.0, 800.0, 0.36, 270.0, 4,
        (0, 0, 0, 0),
        tuple((BuildComponentRole.SUPPORT_PAD.value,
               BuildComponentRole.TOGGLE_CLAMP.value) for _ in range(4)),
        (), ("generic-long-rail",),
        ("station-island-01", "station-island-02", "station-island-03", "station-island-04"),
        0, (), ("load parts",), (), ("remove parts",), (),
        ("generic-long-rail",), ("generic-block-01", "generic-block-02"), (),
        0, (), ("human-rejected-001-generic-m32",), False,
    )


def evaluate_fixture_concept_evidence(
    evidence: FixtureConceptQualityEvidence,
) -> FixtureConceptQualityReport:
    blockers, warnings, recommendations, rejection_rules = [], [], [], []

    def finding(identity: str, category: str, severity: str, message: str,
                affected: tuple[str, ...], facts: tuple[str, ...]) -> None:
        target = blockers if severity == "blocker" else warnings
        target.append(FixtureConceptQualityFinding(
            identity, category, severity, message, affected, facts,
        ))

    min_contacts = min(evidence.product_specific_contacts_per_station, default=0)
    if min_contacts < 6:
        finding(
            "quality-product-contact", "product_specificity", "blocker",
            "Every station requires product-bound support, locate, stop, and clamp contact evidence.",
            tuple(f"station-{index + 1:02d}" for index, value in enumerate(
                evidence.product_specific_contacts_per_station
            ) if value < 6),
            (f"minimum_product_specific_contacts={min_contacts}",),
        )
        rejection_rules.append("insufficient_product_specific_contact_evidence")
        recommendations.append("Bind every station contact to an immutable product feature and distinct role.")
    missing_roles = tuple(
        f"station-{index + 1:02d}"
        for index, roles in enumerate(evidence.role_sets_per_station)
        if not _REQUIRED_STATION_ROLES.issubset(set(roles))
    )
    if missing_roles:
        finding(
            "quality-role-separation", "product_specificity", "blocker",
            "Support, locator, stop, and clamp roles must remain distinct at every station.",
            missing_roles, ("required_roles=" + ",".join(sorted(_REQUIRED_STATION_ROLES)),),
        )
        rejection_rules.append("generic_fixture_component_placement")
    if len(evidence.datum_dof_mappings) < evidence.station_count * 5:
        finding(
            "quality-datum-dof", "datum_and_dof", "blocker",
            "Datum, constrained-DOF, and intentional release evidence is incomplete.",
            (evidence.identity,),
            (f"mapping_count={len(evidence.datum_dof_mappings)}",
             f"required_minimum={evidence.station_count * 5}"),
        )
        rejection_rules.append("incomplete_datum_dof_explanation")
        recommendations.append("Record primary, secondary, tertiary, and release-direction mappings per station.")
    if evidence.redundant_location_identities:
        finding(
            "quality-redundant-location", "datum_and_dof", "blocker",
            "Unjustified redundant locating constraints were detected.",
            evidence.redundant_location_identities,
            ("more_than_five_fixed_locating_components_per_station",),
        )
    if len(evidence.clamp_support_mappings) != evidence.station_count:
        finding(
            "quality-clamp-reaction", "support_and_clamp_reaction", "blocker",
            "Every station clamp requires one named reaction support.",
            (evidence.identity,),
            (f"mapping_count={len(evidence.clamp_support_mappings)}",
             f"station_count={evidence.station_count}"),
        )
        rejection_rules.append("clamp_support_reaction_weakness")
        recommendations.append("Map each clamp contact to a product support directly below or behind it.")
    if evidence.disconnected_component_identities:
        finding(
            "quality-connected-base", "base_and_structure", "blocker",
            "Authored station structure must connect to one coherent mounted base.",
            evidence.disconnected_component_identities,
            ("disconnected_component_count="
             f"{len(evidence.disconnected_component_identities)}",),
        )
        rejection_rules.append("isolated_station_structure")
        recommendations.append("Connect each local nest and brace through an explicit parent path to the base.")
    if evidence.mounting_point_count < 4:
        finding(
            "quality-mounting", "base_and_structure", "blocker",
            "The fixture requires an explicit, distributed table-mounting strategy.",
            (evidence.identity,), (f"mounting_point_count={evidence.mounting_point_count}",),
        )
    if evidence.empty_span_ratio > 0.12:
        finding(
            "quality-empty-span", "compactness_and_flow", "blocker",
            "Unjustified rail span exceeds the product, clamp, access, and maintenance allowance.",
            (evidence.identity,), (f"empty_span_ratio={evidence.empty_span_ratio:.6f}",),
        )
        rejection_rules.append("excessive_empty_rail_span")
        recommendations.append("Derive pitch from the largest simultaneous service envelope, not additive empty margins.")
    if (len(evidence.loading_steps) < 5 or not evidence.release_steps
            or not evidence.unloading_steps):
        finding(
            "quality-handling-sequence", "compactness_and_flow", "blocker",
            "Load, locate, clamp, release, and unload states must be explicit.",
            (evidence.identity,),
            (f"loading_steps={len(evidence.loading_steps)}",
             f"release_steps={len(evidence.release_steps)}",
             f"unloading_steps={len(evidence.unloading_steps)}"),
        )
        rejection_rules.append("unclear_loading_sequence")
    if not evidence.weld_strategy:
        finding(
            "quality-weld-strategy", "weld_and_process_access", "blocker",
            "Tack/full-weld access and handoff assumptions are absent.",
            (evidence.identity,), (),
        )
    elif not any("qualified" in item.lower() or "review" in item.lower()
                 for item in evidence.weld_strategy):
        finding(
            "quality-weld-review", "weld_and_process_access", "warning",
            "Weld strategy needs explicit qualified-human review language.",
            (evidence.identity,), evidence.weld_strategy,
        )
    if evidence.unmanufacturable_component_identities:
        finding(
            "quality-manufacturable-forms", "manufacturability", "blocker",
            "Authored components require a recognizable plate, tube, rail, pin, pad, or machining process.",
            evidence.unmanufacturable_component_identities, (),
        )
    if evidence.foolproof_count < 1:
        finding(
            "quality-foolproof", "datum_and_dof", "warning",
            "No explicit foolproof-loading feature is present.",
            (evidence.identity,), (),
        )
    if not evidence.precedent_record_identities:
        finding(
            "quality-precedent", "precedent", "warning",
            "No public precedent identities were recorded on the concept.",
            (evidence.identity,), (),
        )
    if not evidence.precedent_current:
        finding(
            "quality-precedent-stale", "precedent", "blocker",
            "The concept is not bound to the current public fixture-knowledge library.",
            (evidence.identity,), (),
        )
        recommendations.append(
            "Regenerate the dependent concept after public knowledge or intent changes."
        )
    category_scores = {
        "product_specificity": 20 if min_contacts >= 6 and not missing_roles else 5,
        "datum_and_dof": 15 if len(evidence.datum_dof_mappings) >= evidence.station_count * 5
        and not evidence.redundant_location_identities else 3,
        "support_and_clamp_reaction": 15
        if len(evidence.clamp_support_mappings) == evidence.station_count else 2,
        "base_and_structure": 15
        if not evidence.disconnected_component_identities and evidence.mounting_point_count >= 4 else 3,
        "compactness_and_flow": 15
        if evidence.empty_span_ratio <= 0.12 and len(evidence.loading_steps) >= 5
        and evidence.release_steps and evidence.unloading_steps else 3,
        "weld_and_process_access": 10 if evidence.weld_strategy else 2,
        "manufacturability": 10 if not evidence.unmanufacturable_component_identities else 2,
    }
    score = sum(category_scores.values())
    metrics = (
        FixtureConceptQualityMetric("fixture_length", evidence.fixture_length_mm, "mm", "measured", ()),
        FixtureConceptQualityMetric("occupied_length", evidence.occupied_length_mm, "mm", "measured", ()),
        FixtureConceptQualityMetric(
            "empty_span_ratio", evidence.empty_span_ratio, "ratio",
            "valid" if evidence.empty_span_ratio <= 0.12 else "invalid",
            ("maximum_allowed=0.12",),
        ),
        FixtureConceptQualityMetric("station_pitch", evidence.station_pitch_mm, "mm", "measured", ()),
        FixtureConceptQualityMetric(
            "minimum_product_specific_contacts_per_station", float(min_contacts),
            "count", "valid" if min_contacts >= 6 else "invalid", ("minimum_required=6",),
        ),
        FixtureConceptQualityMetric(
            "connected_base_components", float(len(evidence.connected_component_identities)),
            "count", "measured", (),
        ),
        FixtureConceptQualityMetric(
            "mounting_points", float(evidence.mounting_point_count), "count",
            "valid" if evidence.mounting_point_count >= 4 else "invalid",
            ("minimum_required=4",),
        ),
        FixtureConceptQualityMetric(
            "clamp_support_mappings", float(len(evidence.clamp_support_mappings)),
            "count",
            "valid" if len(evidence.clamp_support_mappings) == evidence.station_count else "invalid",
            (f"required={evidence.station_count}",),
        ),
    )
    affected = tuple(sorted({
        identity for item in blockers + warnings for identity in item.affected_identities
    }))
    return FixtureConceptQualityReport(
        FIXTURE_CONCEPT_QUALITY_SCHEMA, evidence.identity,
        "blocked" if blockers else "passed", score,
        tuple(category_scores.items()), metrics, tuple(blockers), tuple(warnings),
        evidence.precedent_record_identities, tuple(sorted(set(rejection_rules))),
        tuple(dict.fromkeys(recommendations)), affected, evidence.datum_dof_mappings,
        evidence.clamp_support_mappings,
    )


def evaluate_fixture_concept_quality(
    plan: FixtureBuildPlan,
    precedent: PrecedentRetrievalResult | None = None,
) -> FixtureConceptQualityReport:
    return evaluate_fixture_concept_evidence(evidence_from_fixture_build(plan, precedent))
