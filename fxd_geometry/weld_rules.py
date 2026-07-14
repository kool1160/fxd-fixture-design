"""Deterministic, configurable weld-fixture engineering evidence."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .aabb import Vec3
from .annotations import EngineeringAnnotations, GeometryReference
from .fixture import FixtureConcept
from .product_model import ProductModel


class WeldRuleError(ValueError):
    """Raised when weld-rule inputs are inconsistent."""


@dataclass(frozen=True)
class WeldRuleConfig:
    """Caller-supplied thresholds and directions, never universal shop policy."""

    max_heat_input: float | None = None
    heat_input_units: str | None = None
    clamp_force_directions: tuple[tuple[str, Vec3], ...] = ()
    near_weld_kinds: tuple[str, ...] = ("support_pad", "clamp_mount")

    def __post_init__(self) -> None:
        if self.max_heat_input is not None and (not math.isfinite(self.max_heat_input) or self.max_heat_input < 0):
            raise WeldRuleError("max_heat_input must be finite and non-negative")
        if self.max_heat_input is not None and not self.heat_input_units:
            raise WeldRuleError("heat_input_units is required with max_heat_input")
        if len({identity for identity, _ in self.clamp_force_directions}) != len(self.clamp_force_directions):
            raise WeldRuleError("clamp force feature identities must be unique")


@dataclass(frozen=True)
class WeldRuleFinding:
    code: str
    severity: str
    joint_identity: str | None
    feature_identity: str | None
    rule: str
    message: str
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True)
class WeldRecommendation:
    identity: str
    joint_identity: str
    action: str
    rule: str
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class WeldRuleAnalysis:
    units: str
    findings: tuple[WeldRuleFinding, ...]
    recommendations: tuple[WeldRecommendation, ...]
    assumptions: tuple[str, ...]

    @property
    def warnings(self) -> tuple[WeldRuleFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")


def _same_reference(left: GeometryReference, right: GeometryReference) -> bool:
    return left.component_identity == right.component_identity and (
        left.body_identity is None or right.body_identity is None or left.body_identity == right.body_identity)


def _dot(left: Vec3, right: Vec3) -> float:
    return left.x * right.x + left.y * right.y + left.z * right.z


def evaluate_weld_rules(product: ProductModel, fixture: FixtureConcept,
                        annotations: EngineeringAnnotations,
                        config: WeldRuleConfig | None = None) -> WeldRuleAnalysis:
    """Evaluate explicit heat, distortion, restraint, access, and sequence intent."""
    annotations.validate_references(product)
    if fixture.source_sha256 != product.source_sha256:
        raise WeldRuleError("fixture and product source identities do not match")
    config = config or WeldRuleConfig()
    force_directions = dict(config.clamp_force_directions)
    findings: list[WeldRuleFinding] = []
    recommendations: list[WeldRecommendation] = []
    assumptions = ("Rules use explicit annotations and proof-layer feature references; no thermal or force simulation is performed.",)
    for joint in annotations.weld_joints:
        if not joint.process:
            findings.append(WeldRuleFinding("missing_process", "warning", joint.identity, None,
                "weld_process_required", "Weld process is not specified.",
                assumptions=("Process-specific access and heat interpretation is unavailable.",), confidence=.95))
        if joint.heat_input is not None and config.max_heat_input is not None:
            if joint.heat_input_units != config.heat_input_units:
                findings.append(WeldRuleFinding("heat_units_conflict", "warning", joint.identity, None,
                    "heat_input_units_must_match_config", "Heat-input units do not match the configured threshold.",
                    (f"joint={joint.heat_input_units}", f"config={config.heat_input_units}"), confidence=.99))
            elif joint.heat_input > config.max_heat_input:
                findings.append(WeldRuleFinding("heat_input_exceeds_config", "warning", joint.identity, None,
                    "configured_heat_input_limit", "Heat input exceeds the caller-supplied review threshold.",
                    (f"heat_input={joint.heat_input}", f"limit={config.max_heat_input}"),
                    ("Threshold is a configurable review trigger, not a universal weld standard.",), .99))
        if joint.tack_required and joint.sequence is None:
            findings.append(WeldRuleFinding("missing_tack_sequence", "warning", joint.identity, None,
                "tack_sequence_required", "Tack is required but its sequence is not recorded.", confidence=.98))
        if joint.release_sequence is None:
            findings.append(WeldRuleFinding("missing_release_sequence", "warning", joint.identity, None,
                "release_sequence_required", "Release/unload sequence is not recorded.", confidence=.98))
        if joint.direction is None:
            findings.append(WeldRuleFinding("missing_weld_direction", "warning", joint.identity, None,
                "weld_direction_required", "Weld direction is unknown; approach and sequence reasoning is provisional.", confidence=.98))
        near_features = [feature for feature in fixture.features if feature.kind in config.near_weld_kinds and
                         any(_same_reference(source, target) for source in feature.source_references for target in joint.references)]
        for feature in near_features:
            findings.append(WeldRuleFinding("fixture_near_weld_zone", "warning", joint.identity, feature.identity,
                "weld_zone_clearance_review", f"{feature.kind} is associated with a weld-joint reference and needs heat, spatter, and access review.",
                (f"feature_rule={feature.rule}", "source reference matches weld reference"),
                ("Reference association is not a thermal or spatter simulation.",), .75))
        if not near_features:
            recommendations.append(WeldRecommendation(
                f"review-{joint.identity}", joint.identity, "Confirm support and clamp placement around the weld zone.",
                "weld_zone_clearance_review", ("No fixture feature reference matched the weld joint.",),
                ("Spatial proximity is not established by the current proof layer.",), .55))
        if joint.distortion_direction is not None:
            matched_forces = [(identity, direction) for identity, direction in force_directions.items()
                              if any(feature.identity == identity for feature in near_features)]
            if not matched_forces:
                findings.append(WeldRuleFinding("missing_clamp_force_direction", "warning", joint.identity, None,
                    "clamp_force_direction_required", "Distortion direction is known but no configured nearby clamp force direction is available.",
                    (f"distortion_direction={joint.distortion_direction}",), confidence=.98))
            for identity, direction in matched_forces:
                relation = _dot(direction, joint.distortion_direction)
                if relation > 0:
                    findings.append(WeldRuleFinding("clamp_reinforces_distortion", "warning", joint.identity, identity,
                        "clamp_force_vs_distortion_direction", "Configured clamp force points with the expected distortion direction; review restraint strategy.",
                        (f"dot_product={relation:.6g}",),
                        ("Direction comparison is geometric only; force magnitude and thermal response are unknown.",), .9))
                else:
                    recommendations.append(WeldRecommendation(
                        f"clamp-{joint.identity}-{identity}", joint.identity, "Review clamp reaction path against the locating scheme.",
                        "clamp_force_vs_distortion_direction", (f"dot_product={relation:.6g}",),
                        ("Opposing direction is not proof of adequate force or locator stability.",), .8))
    return WeldRuleAnalysis("mm", tuple(findings), tuple(recommendations), assumptions)
