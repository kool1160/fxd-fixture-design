"""Deterministic proof-layer access and unload analysis.

Access envelopes are explicit neutral AABBs supplied by an engineer or a
future process planner.  They are not a robot motion planner or a weld-quality
solver.  A blocked envelope is evidence requiring review, never a production
approval claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .aabb import Aabb, Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .fixture import FixtureConcept
from .product_model import ProductModel


class AccessAnalysisError(ValueError):
    """Raised when an access request is incomplete or references unknown data."""


@dataclass(frozen=True)
class AccessEnvelope:
    identity: str
    mode: str
    bounds: Aabb
    direction: Vec3 | None = None
    reach: float | None = None
    assumptions: tuple[str, ...] = ()
    process_data_complete: bool = False
    units: str = "mm"

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise AccessAnalysisError("access envelope identity must not be empty")
        if self.mode not in {"manual", "robot", "operator", "unload"}:
            raise AccessAnalysisError("access envelope mode must be manual, robot, operator, or unload")
        if self.units != "mm":
            raise AccessAnalysisError("access envelopes must use millimetres")
        if self.direction is not None and self.direction == Vec3(0.0, 0.0, 0.0):
            raise AccessAnalysisError("access envelope direction must not be zero")
        if self.reach is not None and (not math.isfinite(self.reach) or self.reach < 0):
            raise AccessAnalysisError("access envelope reach must be finite and non-negative")


@dataclass(frozen=True)
class WeldAccessRequest:
    identity: str
    weld_joint_identity: str
    envelope: AccessEnvelope
    target_reference: GeometryReference | None = None

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.weld_joint_identity.strip():
            raise AccessAnalysisError("weld access identities must not be empty")
        if self.envelope.mode not in {"manual", "robot"}:
            raise AccessAnalysisError("weld access envelope must be manual or robot")


@dataclass(frozen=True)
class AccessFinding:
    code: str
    severity: str
    request_identity: str | None
    feature_identity: str | None
    message: str


@dataclass(frozen=True)
class AccessAnalysis:
    units: str
    findings: tuple[AccessFinding, ...]
    assumptions: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return any(item.severity == "error" for item in self.findings)

    @property
    def warnings(self) -> tuple[AccessFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")


def _validate_reference(product: ProductModel, reference: GeometryReference) -> None:
    components = {item.identity: item for item in product.components}
    component = components.get(reference.component_identity)
    if component is None:
        raise AccessAnalysisError(f"unknown access component {reference.component_identity!r}")
    if reference.body_identity and reference.body_identity not in {body.identity for body in component.bodies}:
        raise AccessAnalysisError(f"unknown access body {reference.body_identity!r}")


def evaluate_access(product: ProductModel, fixture: FixtureConcept,
                    annotations: EngineeringAnnotations,
                    weld_requests: tuple[WeldAccessRequest, ...] = (),
                    envelopes: tuple[AccessEnvelope, ...] = ()) -> AccessAnalysis:
    """Evaluate explicit weld, operator, robot, and unload envelopes.

    Envelope geometry is checked against fixture features only.  The product
    remains the target of the request and is never modified.  The caller must
    supply envelope coverage appropriate to the process; incomplete data is
    surfaced instead of inferred.
    """
    annotations.validate_references(product)
    if fixture.source_sha256 != product.source_sha256:
        raise AccessAnalysisError("fixture and product source identities do not match")
    joints = {joint.identity: joint for joint in annotations.weld_joints}
    findings: list[AccessFinding] = []
    assumptions = ["AABB envelope intersections are conservative proof-layer checks, not B-Rep or motion validation."]
    for request in weld_requests:
        joint = joints.get(request.weld_joint_identity)
        if joint is None:
            raise AccessAnalysisError(f"unknown weld joint {request.weld_joint_identity!r}")
        if request.target_reference is not None:
            _validate_reference(product, request.target_reference)
        if not request.envelope.process_data_complete:
            findings.append(AccessFinding("incomplete_process_data", "warning", request.identity, None,
                f"{request.envelope.mode} access request lacks complete process data; clearance is provisional."))
        for feature in fixture.features:
            if request.envelope.bounds.intersects(feature.bounds):
                findings.append(AccessFinding("blocked_weld_approach", "error", request.identity, feature.identity,
                    f"{request.envelope.mode} approach for weld {joint.identity} intersects fixture feature {feature.identity}."))
    for envelope in envelopes:
        if not envelope.process_data_complete:
            findings.append(AccessFinding("incomplete_process_data", "warning", envelope.identity, None,
                f"{envelope.mode} envelope lacks complete process data; access is provisional."))
        for feature in fixture.features:
            if envelope.bounds.intersects(feature.bounds):
                code = "blocked_unload_path" if envelope.mode == "unload" else "access_envelope_conflict"
                findings.append(AccessFinding(code, "error", envelope.identity, feature.identity,
                    f"{envelope.mode} envelope intersects fixture feature {feature.identity}."))
    if not weld_requests:
        findings.append(AccessFinding("missing_weld_access_intent", "warning", None, None,
            "No weld approach envelopes were supplied; weld access is not validated."))
    if not any(item.mode == "unload" for item in envelopes):
        findings.append(AccessFinding("missing_unload_access_intent", "warning", None, None,
            "No unload envelope was supplied; removability is not validated."))
    return AccessAnalysis("mm", tuple(findings), tuple(assumptions))
