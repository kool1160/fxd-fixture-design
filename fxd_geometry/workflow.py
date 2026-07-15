"""Deterministic engineer-review workflow for weld-fixture operations.

This module composes existing weld and access contracts.  It does not simulate
thermal distortion, robot motion, or weld quality; missing evidence is a
finding rather than an inferred pass.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .aabb import Aabb
from .annotations import EngineeringAnnotations, GeometryReference, WeldJoint
from .fixture import FixtureConcept
from .product_model import ProductModel
from .weld_rules import WeldRuleAnalysis


class WorkflowError(ValueError):
    """Raised when an engineer-review workflow is malformed."""


@dataclass(frozen=True)
class WorkflowStep:
    identity: str
    order: int
    action: str
    references: tuple[str, ...] = ()
    weld_joint_identity: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.action.strip():
            raise WorkflowError("workflow step identity and action are required")
        if not isinstance(self.order, int) or self.order < 1:
            raise WorkflowError("workflow step order must be positive")
        if self.weld_joint_identity is not None and not self.weld_joint_identity.strip():
            raise WorkflowError("weld_joint_identity must be non-empty")


@dataclass(frozen=True)
class SequencePlan:
    identity: str
    steps: tuple[WorkflowStep, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise WorkflowError("sequence identity is required")
        identities = [step.identity for step in self.steps]
        orders = [step.order for step in self.steps]
        if len(set(identities)) != len(identities) or len(set(orders)) != len(orders):
            raise WorkflowError("sequence step identities and orders must be unique")
        if orders != sorted(orders):
            raise WorkflowError("sequence steps must be ordered")

    def with_step(self, step: WorkflowStep) -> "SequencePlan":
        remaining = tuple(item for item in self.steps if item.identity != step.identity)
        return replace(self, steps=tuple(sorted(remaining + (step,), key=lambda item: item.order)))


@dataclass(frozen=True)
class ReviewZone:
    identity: str
    kind: str
    references: tuple[GeometryReference, ...] = ()
    bounds: Aabb | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.identity.strip() or self.kind not in {"heat", "distortion", "spatter", "restricted_contact"}:
            raise WorkflowError("zone identity and supported zone kind are required")


@dataclass(frozen=True)
class WorkflowEnvelope:
    """Shared neutral envelope contract for manual and automated approaches."""

    identity: str
    mode: str
    bounds: Aabb
    references: tuple[GeometryReference, ...] = ()
    direction: object | None = None
    process_data_complete: bool = False
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or self.mode not in {"torch", "hand", "operator", "robot", "cobot", "unload"}:
            raise WorkflowError("unsupported workflow envelope mode")


@dataclass(frozen=True)
class WorkflowFinding:
    code: str
    severity: str
    rule: str
    message: str
    sequence_identity: str | None = None
    geometry_identity: str | None = None
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowVisualItem:
    identity: str
    category: str
    references: tuple[str, ...]
    findings: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowReport:
    units: str
    findings: tuple[WorkflowFinding, ...]
    visual_items: tuple[WorkflowVisualItem, ...]
    variant_identity: str = "default"

    @property
    def blocked(self) -> bool:
        return any(item.severity == "error" for item in self.findings)

    @property
    def warnings(self) -> tuple[WorkflowFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")


@dataclass(frozen=True)
class WorkflowVariant:
    identity: str
    process: str
    fixture: FixtureConcept
    envelopes: tuple[WorkflowEnvelope, ...] = ()


@dataclass(frozen=True)
class WorkflowComparison:
    reports: tuple[WorkflowReport, ...]

    @property
    def all_deterministic_gates_pass(self) -> bool:
        return all(not report.blocked for report in self.reports)


def _validate_references(product: ProductModel, annotations: EngineeringAnnotations,
                         references: tuple[GeometryReference, ...]) -> None:
    # Reuse the authoritative annotation reference validation without adding
    # workflow-owned geometry to the product model.
    replace(annotations, weld_joints=(WeldJoint("workflow-reference", references),)).validate_references(product)


def _sequence_findings(plan: SequencePlan, required: set[str], kind: str) -> list[WorkflowFinding]:
    present = {step.weld_joint_identity for step in plan.steps if step.weld_joint_identity}
    return [WorkflowFinding("missing_sequence_step", "warning", f"{kind}_sequence_required",
                            f"{kind} sequence does not explicitly include weld joint {identity}.",
                            plan.identity, evidence=(f"joint={identity}",))
            for identity in sorted(required - present)]


def evaluate_workflow(product: ProductModel, fixture: FixtureConcept,
                      annotations: EngineeringAnnotations,
                      weld_rules: WeldRuleAnalysis,
                      weld_sequence: SequencePlan,
                      tack_sequence: SequencePlan,
                      clamp_sequence: SequencePlan,
                      release_sequence: SequencePlan,
                      zones: tuple[ReviewZone, ...] = (),
                      envelopes: tuple[WorkflowEnvelope, ...] = (),
                      variant_identity: str = "default") -> WorkflowReport:
    """Evaluate editable sequence, zone, envelope, and unload evidence."""
    annotations.validate_references(product)
    if fixture.source_sha256 != product.source_sha256:
        raise WorkflowError("fixture and product source identities do not match")
    joints = {joint.identity for joint in annotations.weld_joints}
    findings: list[WorkflowFinding] = []
    findings.extend(_sequence_findings(weld_sequence, joints, "weld"))
    findings.extend(_sequence_findings(tack_sequence,
                                       {joint.identity for joint in annotations.weld_joints if joint.tack_required}, "tack"))
    findings.extend(_sequence_findings(clamp_sequence, joints, "clamp"))
    findings.extend(_sequence_findings(release_sequence,
                                       {joint.identity for joint in annotations.weld_joints if joint.release_sequence is not None}, "release"))
    for item in weld_rules.findings:
        findings.append(WorkflowFinding(item.code, item.severity, item.rule, item.message,
                                        geometry_identity=item.feature_identity or item.joint_identity,
                                        evidence=item.evidence))
    for zone in zones:
        if zone.references:
            _validate_references(product, annotations, zone.references)
        if zone.bounds:
            for feature in fixture.features:
                if zone.bounds.intersects(feature.bounds):
                    findings.append(WorkflowFinding("zone_fixture_conflict", "warning", "zone_clearance_review",
                                                    f"{zone.kind} zone intersects fixture feature {feature.identity}.",
                                                    geometry_identity=feature.identity,
                                                    evidence=(f"zone={zone.identity}",)))
    for envelope in envelopes:
        if envelope.references:
            _validate_references(product, annotations, envelope.references)
        if not envelope.process_data_complete:
            findings.append(WorkflowFinding("incomplete_process_data", "warning", "process_envelope_required",
                                            f"{envelope.mode} envelope lacks complete process data.",
                                            geometry_identity=envelope.identity))
        for feature in fixture.features:
            if envelope.bounds.intersects(feature.bounds):
                code = "blocked_unload_path" if envelope.mode == "unload" else "approach_envelope_conflict"
                findings.append(WorkflowFinding(code, "error", "envelope_clearance",
                                                f"{envelope.mode} envelope intersects fixture feature {feature.identity}.",
                                                geometry_identity=feature.identity,
                                                evidence=(f"envelope={envelope.identity}",)))
    if not any(item.mode == "unload" for item in envelopes):
        findings.append(WorkflowFinding("missing_unload_sequence_evidence", "warning", "unload_envelope_required",
                                        "No unload envelope was supplied; trapped-part risk is not validated."))
    visual: list[WorkflowVisualItem] = []
    for zone in zones:
        visual.append(WorkflowVisualItem(zone.identity, "zone",
                                         tuple(ref.component_identity for ref in zone.references),
                                         tuple(item.code for item in findings if item.evidence and f"zone={zone.identity}" in item.evidence)))
    for envelope in envelopes:
        visual.append(WorkflowVisualItem(envelope.identity, envelope.mode,
                                         tuple(ref.component_identity for ref in envelope.references),
                                         tuple(item.code for item in findings if item.geometry_identity == envelope.identity)))
    return WorkflowReport("mm", tuple(findings), tuple(visual), variant_identity)


def compare_workflow_variants(reports: tuple[WorkflowReport, ...]) -> WorkflowComparison:
    if not reports or len({report.variant_identity for report in reports}) != len(reports):
        raise WorkflowError("variant reports must be non-empty and uniquely identified")
    return WorkflowComparison(reports)
