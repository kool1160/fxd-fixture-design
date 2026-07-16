"""Deterministic, versioned validation gate for fixture concepts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .access import AccessAnalysis
from .concepts import CompleteFixtureConcept
from .fixture import FixtureConcept
from .kernel import KernelOperationError, RealKernel
from .manufacturing import ManufacturingGeometry, ManufacturingSolid
from .product_model import ProductModel
from .tooling import ToolingLibrary, generic_tooling_library
from .weld_rules import WeldRuleAnalysis

VALIDATION_VERSION = "fxd-validation-v1"


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    severity: str
    subsystem: str
    message: str
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    version: str
    concept_identity: str
    source_sha256: str
    units: str
    status: str
    findings: tuple[ValidationFinding, ...]
    evidence_digest: str

    @property
    def valid(self) -> bool:
        return self.status == "valid"

    @property
    def blocked(self) -> bool:
        return self.status == "invalid"


def _finding(code: str, severity: str, subsystem: str, message: str,
             evidence: tuple[str, ...] = (), assumptions: tuple[str, ...] = ()) -> ValidationFinding:
    return ValidationFinding(code, severity, subsystem, message, evidence, assumptions)


def _aabb_findings(product: ProductModel, fixture: FixtureConcept,
                   minimum_clearance_mm: float) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for component in product.components:
        for body in component.bodies:
            product_box = body.bounds.transformed(component.transform)
            source_identity = f"{component.identity}:{body.identity}"
            for feature in fixture.features:
                # These are intentional contact features; true contact adequacy
                # is owned by the locator solver and kernel checks.
                if feature.kind in {"support_pad", "round_pin", "relieved_locator", "hard_stop"}:
                    continue
                if product_box.intersects(feature.bounds):
                    findings.append(_finding("fixture_product_collision", "error", "geometry",
                        f"fixture feature {feature.identity} intersects product body {source_identity}",
                        (f"feature={feature.identity}", f"product_body={source_identity}")))
                elif product_box.clearance_to(feature.bounds) < minimum_clearance_mm:
                    findings.append(_finding("minimum_clearance_gap", "error", "geometry",
                        f"fixture feature {feature.identity} is below the configured product clearance",
                        (f"feature={feature.identity}", f"minimum_clearance_mm={minimum_clearance_mm}")))
    return findings


# These are explicit manufactured interfaces, not free-space relationships.
# Their geometry is expected to touch, overlap within fit allowance, or be joined.
_INTENTIONAL_INTERFACE_PAIRS = frozenset({
    frozenset(("baseplate", "support_pad")),
    frozenset(("baseplate", "hard_stop")),
    frozenset(("baseplate", "relieved_locator")),
    frozenset(("baseplate", "round_pin")),
    frozenset(("baseplate", "clamp_mount")),
})


def _intentional_interface(left: ManufacturingSolid, right: ManufacturingSolid) -> bool:
    pair = frozenset((left.kind, right.kind))
    if pair not in _INTENTIONAL_INTERFACE_PAIRS:
        return False
    # Interface metadata is required on both sides so generic solids cannot
    # silently opt out of collision checks merely by having familiar kinds.
    return bool(left.interface and right.interface)


def _kernel_findings(manufacturing: ManufacturingGeometry, kernel: RealKernel,
                     minimum_clearance_mm: float) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for index, left in enumerate(manufacturing.solids):
        for right in manufacturing.solids[index + 1:]:
            try:
                clearance = kernel.clearance(left.shape, right.shape)
            except (KernelOperationError, RuntimeError) as exc:
                findings.append(_finding("kernel_clearance_failed", "error", "geometry",
                    f"real-kernel clearance failed for {left.identity} and {right.identity}: {exc}"))
                continue
            if _intentional_interface(left, right):
                # Touching or fitted geometry is expected here. A positive gap
                # larger than the declared fit allowance means the interface
                # is not actually assembled and must be reviewed.
                allowed_gap = max(left.clearance, right.clearance)
                if clearance > allowed_gap:
                    findings.append(_finding("manufacturing_interface_gap", "error", "manufacturing",
                        f"intended interface {left.identity}/{right.identity} exceeds its declared fit gap",
                        (f"clearance_mm={clearance:.9g}", f"allowed_gap_mm={allowed_gap:.9g}",
                         f"left_interface={left.interface}", f"right_interface={right.interface}")))
                continue
            if clearance < minimum_clearance_mm:
                findings.append(_finding("manufacturing_interference", "error", "geometry",
                    f"manufacturing solids {left.identity} and {right.identity} do not meet minimum clearance",
                    (f"clearance_mm={clearance:.9g}", f"minimum_clearance_mm={minimum_clearance_mm}")))
    return findings


def validate_fixture_concept(product: ProductModel, concept: CompleteFixtureConcept,
                             *, access: AccessAnalysis | None = None,
                             weld: WeldRuleAnalysis | None = None,
                             tooling: ToolingLibrary | None = None,
                             manufacturing: ManufacturingGeometry | None = None,
                             kernel: RealKernel | None = None,
                             minimum_clearance_mm: float = 0.5) -> ValidationResult:
    """Run available deterministic gates; scores and AI cannot override them."""
    if product.units != "mm" or concept.fixture.units != "mm":
        raise ValueError("validation requires explicit millimetre units")
    if product.source_sha256 != concept.fixture.source_sha256:
        raise ValueError("concept and product source identities do not match")
    if minimum_clearance_mm < 0:
        raise ValueError("minimum_clearance_mm must be non-negative")
    if (manufacturing is None) != (kernel is None):
        raise ValueError("manufacturing geometry and real kernel must be supplied together")
    findings: list[ValidationFinding] = []
    findings.extend(_finding(item.code, item.severity, "concept", item.message,
                             (item.feature_identity,) if item.feature_identity else ())
                    for item in concept.fixture.findings)
    analysis = concept.constraints.locating_analysis
    if analysis is None:
        findings.append(_finding("locating_evidence_missing", "warning", "locating",
            "geometry-aware locating contact evidence was not supplied"))
    elif not analysis.strategy_valid:
        findings.extend(_finding(item.code, item.severity, "locating", item.message,
                                 (item.locator_identity,) if item.locator_identity else ())
                        for item in analysis.findings)
    findings.extend(_aabb_findings(product, concept.fixture, minimum_clearance_mm))
    if access is None:
        findings.append(_finding("access_evidence_missing", "warning", "access",
            "weld, operator, robot, and unload access analysis was not supplied"))
    else:
        findings.extend(_finding(item.code, item.severity, "access", item.message,
                                 tuple(x for x in (item.request_identity, item.feature_identity) if x))
                        for item in access.findings)
    if weld is None:
        findings.append(_finding("weld_evidence_missing", "warning", "weld",
            "weld process and distortion analysis was not supplied"))
    else:
        findings.extend(_finding(item.code, item.severity, "weld", item.message,
                                 item.evidence, item.assumptions) for item in weld.findings)
    if concept.structure is not None:
        for item in concept.structure.findings:
            findings.append(_finding(item.code, item.severity, "structure", item.message,
                                     item.evidence + tuple(f"member={value}" for value in item.member_identities),
                                     item.assumptions))
    tooling = tooling or generic_tooling_library()
    if not any(feature.kind == "clamp_mount" for feature in concept.fixture.features):
        findings.append(_finding("clamp_evidence_missing", "error", "clamp", "fixture concept contains no clamp mount"))
    elif tooling.select("clamp") is None:
        findings.append(_finding("clamp_tooling_missing", "error", "clamp", "no neutral clamp tooling item satisfies the contract"))
    else:
        findings.append(_finding("clamp_force_review_required", "warning", "clamp",
            "clamp force and reaction adequacy remain engineering review items"))
    if manufacturing is not None and kernel is not None:
        if manufacturing.concept_identity != concept.identity or manufacturing.source_sha256 != product.source_sha256:
            findings.append(_finding("manufacturing_identity_mismatch", "error", "manufacturing",
                "kernel-authored manufacturing geometry does not match the validated concept source"))
        else:
            findings.extend(_kernel_findings(manufacturing, kernel, minimum_clearance_mm))
    else:
        findings.append(_finding("manufacturing_geometry_missing", "warning", "manufacturing",
            "kernel-authored manufacturing solids were not supplied"))
    if analysis is not None:
        if analysis.tolerance_mm is None or analysis.repeatability_mm is None:
            findings.append(_finding("tolerance_repeatability_missing", "warning", "tolerance",
                "locating tolerance and repeatability evidence are incomplete"))
        elif analysis.repeatability_mm > analysis.tolerance_mm:
            findings.append(_finding("repeatability_exceeds_tolerance", "error", "tolerance",
                "specified repeatability exceeds specified locating tolerance",
                (f"repeatability_mm={analysis.repeatability_mm}", f"tolerance_mm={analysis.tolerance_mm}")))
    status = "invalid" if any(item.severity == "error" for item in findings) else (
        "provisional" if any(item.severity == "warning" for item in findings) else "valid")
    encoded = json.dumps([item.__dict__ for item in findings], sort_keys=True, separators=(",", ":"))
    return ValidationResult(VALIDATION_VERSION, concept.identity, product.source_sha256, "mm", status,
                            tuple(findings), hashlib.sha256(encoded.encode()).hexdigest())
