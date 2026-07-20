"""Local, neutral FXD project persistence and deterministic revision workflow."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .annotations import (
    Assumption, CriticalCharacteristic, EngineeringAnnotations, GeometryReference, WeldJoint,
)
from .aabb import Vec3
from .concepts import CompleteFixtureConcept, FixtureCorrection, generate_fixture_concepts
from .fixture import FixtureFeature, FixtureFinding, FixtureParameters, ManufacturingSpec
from .product_model import ProductModel
from .step_import import import_step
from .validation import ValidationFinding, ValidationResult, validate_fixture_concept
from .structure import generate_structural_assembly
from .placement import PlacementPlan
from .access import evaluate_access
from .weld_rules import evaluate_weld_rules

if TYPE_CHECKING:
    from .ai_fixture_engineer import FixtureProposal
    from .fabrication_workflow import FixtureBuildPlan
    from .interactive_workflow import InteractiveWorkflow


class ProjectFormatError(ValueError):
    """Raised when a saved project is incomplete, unsafe, or incompatible."""


SUPPORTED_LAYERS = frozenset({
    "product", "fixture", "structure", "risers", "datums", "locators",
    "supports", "stops", "clamps", "welds", "access", "keep_out",
    "warnings", "provisional", "product_instances", "purchased_tooling",
    "access_envelopes", "findings",
})
PROJECT_FORMAT = "fxd-neutral-project-v5"


@dataclass(frozen=True)
class ReviewDecision:
    action: str
    target: str
    note: str
    validation_status: str
    evidence_digest: str


@dataclass(frozen=True)
class FixtureEdit:
    """Restricted deterministic edit command; never a free-form geometry patch."""

    operation: str
    target: str
    value: object = None
    reason: str = ""


@dataclass(frozen=True)
class ProjectRevision:
    revision_id: str
    parent_id: str | None
    active_concept: str
    edit_count: int
    changes: tuple[FixtureEdit, ...]
    validation_status: str
    evidence_digest: str
    suppressed_features: frozenset[str] = frozenset()


def _encoded_value(value: object) -> object:
    if isinstance(value, Vec3):
        return {"x": value.x, "y": value.y, "z": value.z}
    return value


def _edit_dict(edit: FixtureEdit) -> dict[str, object]:
    return {
        "operation": edit.operation,
        "target": edit.target,
        "value": _encoded_value(edit.value),
        "reason": edit.reason,
    }


def _manufacturing_for(kind: str, params: FixtureParameters) -> ManufacturingSpec:
    """Return manufacturing intent that agrees with the edited feature kind."""
    fit = params.fit
    if kind == "baseplate":
        return ManufacturingSpec("laser_cut", "mild_steel", params.base_thickness,
                                 fit, params.contact_clearance,
                                 params.manufacturing_allowance, "baseplate_slot",
                                 ("profile_cut", "deburr"))
    if kind in {"support_pad", "hard_stop", "relieved_locator"}:
        return ManufacturingSpec("laser_cut", "mild_steel", params.locator_wall,
                                 fit, params.contact_clearance,
                                 params.manufacturing_allowance, "tab_and_slot",
                                 ("profile_cut", "deburr", "weld"))
    if kind == "round_pin":
        return ManufacturingSpec("machined", "tool_steel", params.locator_wall,
                                 fit, params.contact_clearance,
                                 params.manufacturing_allowance, "reamed_hole",
                                 ("turn", "harden", "replaceable"))
    if kind == "clamp_mount":
        return ManufacturingSpec("laser_cut", "mild_steel", params.locator_wall,
                                 fit, params.contact_clearance,
                                 params.manufacturing_allowance, params.clamp_choice,
                                 ("profile_cut", "deburr", "weld"))
    return ManufacturingSpec("machined", "mild_steel", params.locator_wall,
                             fit, params.contact_clearance,
                             params.manufacturing_allowance, None, ("deburr",))


@dataclass(frozen=True)
class FxdProject:
    """Complete neutral review state; source geometry is retained unchanged."""

    product: ProductModel
    annotations: EngineeringAnnotations
    concepts: tuple[CompleteFixtureConcept, ...]
    active_concept: str
    hidden_layers: frozenset[str] = frozenset()
    suppressed_features: frozenset[str] = frozenset()
    decisions: tuple[ReviewDecision, ...] = ()
    edit_log: tuple[FixtureEdit, ...] = ()
    revisions: tuple[ProjectRevision, ...] = ()
    approved_revision: str | None = None
    placement: PlacementPlan | None = None
    drawing_intent: dict[str, object] | None = None
    optimization_intent: dict[str, object] | None = None
    workflow: "InteractiveWorkflow | None" = None
    fixture_build: "FixtureBuildPlan | None" = None
    fixture_proposal: "FixtureProposal | None" = None

    def __post_init__(self) -> None:
        if self.annotations.source_sha256 != self.product.source_sha256:
            raise ProjectFormatError("annotations do not match the immutable source geometry")
        self.annotations.validate_references(self.product)
        if self.active_concept not in {concept.identity for concept in self.concepts}:
            raise ProjectFormatError(f"active concept {self.active_concept!r} is missing")
        if not self.hidden_layers <= SUPPORTED_LAYERS:
            raise ProjectFormatError("project contains unsupported visual layers")
        known = {feature.identity for feature in self.active.fixture.features}
        if not self.suppressed_features <= known:
            raise ProjectFormatError("project suppresses unknown fixture features")
        if self.approved_revision is not None and self.approved_revision != self.revision_id:
            raise ProjectFormatError("approval does not belong to the current revision")
        if self.workflow is not None and self.workflow.source_sha256 != self.product.source_sha256:
            raise ProjectFormatError("interactive workflow does not match the immutable source geometry")
        if self.workflow is not None:
            self.workflow.validate_references(self.product)
        if self.fixture_build is not None:
            if self.fixture_build.requirements.source_sha256 != self.product.source_sha256:
                raise ProjectFormatError("fixture build does not match the immutable source geometry")
            if self.fixture_build.concept_identity != self.active_concept:
                raise ProjectFormatError("fixture build must belong to the active fixture concept")
        if self.fixture_proposal is not None:
            if self.fixture_proposal.source_sha256 != self.product.source_sha256:
                raise ProjectFormatError("fixture proposal does not match the immutable source geometry")

    @classmethod
    def from_product(cls, product: ProductModel, annotations: EngineeringAnnotations,
                     placement: PlacementPlan | None = None,
                     workflow: "InteractiveWorkflow | None" = None) -> "FxdProject":
        annotations.validate_references(product)
        concepts = generate_fixture_concepts(product, annotations, placement=placement).concepts
        if not concepts:
            raise ProjectFormatError("fixture generation produced no concepts")
        return cls(product, annotations, concepts, concepts[0].identity,
                   placement=placement, workflow=workflow)._record_revision(None)

    @property
    def active(self) -> CompleteFixtureConcept:
        return next(concept for concept in self.concepts if concept.identity == self.active_concept)

    @property
    def active_validation(self) -> ValidationResult:
        return self.validation_for(self.active)

    @property
    def fixture_build_validation(self):
        """Dedicated deterministic evidence for the active build, never AI-owned."""
        if self.fixture_build is None or self.fixture_build.concept_identity != self.active_concept:
            return None
        from .fabrication_workflow import validate_fixture_build_plan
        return validate_fixture_build_plan(self.product, self.fixture_build)

    def assembly_validation_for(self, concept: CompleteFixtureConcept) -> ValidationResult:
        """Return assembly analysis only, without folding fixture-build evidence into it."""
        access = None
        weld = None
        if self.workflow is not None and self.workflow.analysis_completed:
            access = evaluate_access(self.product, concept.fixture, self.annotations)
            if self.annotations.weld_joints:
                weld = evaluate_weld_rules(self.product, concept.fixture, self.annotations)
        return validate_fixture_concept(self.product, concept, access=access, weld=weld)

    def validation_for(self, concept: CompleteFixtureConcept) -> ValidationResult:
        """Compose release-gate evidence while preserving source-specific evidence APIs."""
        result = self.assembly_validation_for(concept)
        if self.fixture_build is None or self.fixture_build.concept_identity != concept.identity:
            return result
        from .fabrication_workflow import validate_fixture_build_plan
        build = validate_fixture_build_plan(self.product, self.fixture_build)
        findings = result.findings + tuple(
            ValidationFinding(item.rule_id, item.severity, "fabrication", item.message,
                              item.evidence + tuple(f"component={value}" for value in item.component_identities),
                              item.assumptions)
            for item in build.findings
        )
        status = "invalid" if any(item.severity == "error" for item in findings) else (
            "provisional" if any(item.severity == "warning" for item in findings) else "valid")
        encoded = json.dumps({
            "base_evidence_digest": result.evidence_digest,
            "fixture_build_evidence_digest": build.evidence_digest,
            "findings": [item.__dict__ for item in findings],
        }, sort_keys=True, separators=(",", ":"))
        return ValidationResult(result.version, result.concept_identity, result.source_sha256, result.units,
                                status, findings, hashlib.sha256(encoded.encode()).hexdigest())

    def _invalidate_derived_intent(self) -> "FxdProject":
        """Clear evidence derived from manufacturing or drawing state."""
        return replace(self, drawing_intent=None, optimization_intent=None, fixture_build=None)

    def with_fixture_proposal(self, proposal: "FixtureProposal") -> "FxdProject":
        """Persist initial proposal evidence without discarding an independent build plan.

        An engineer's later recommendation decision or edit changes design intent
        and therefore still invalidates downstream authored/build evidence.
        """
        if proposal.source_sha256 != self.product.source_sha256:
            raise ProjectFormatError("fixture proposal does not match the immutable source geometry")
        from .ai_fixture_engineer import validate_fixture_proposal
        preserve_existing_build = self.fixture_proposal is None
        candidate = replace(
            self, fixture_proposal=None, drawing_intent=None,
            optimization_intent=None,
            fixture_build=self.fixture_build if preserve_existing_build else None,
            approved_revision=None,
        )
        proposal = validate_fixture_proposal(candidate, proposal)
        candidate = replace(candidate, fixture_proposal=proposal)
        return candidate._record_revision(self.revision_id)

    def decide_proposal_recommendation(self, recommendation_id: str, decision: object,
                                       note: str = "") -> "FxdProject":
        if self.fixture_proposal is None:
            raise ProjectFormatError("project has no fixture proposal to review")
        from .ai_fixture_engineer import decide_recommendation, validate_fixture_proposal
        proposal = decide_recommendation(
            self.fixture_proposal, recommendation_id, decision, note,
        )
        proposal = validate_fixture_proposal(self, proposal)
        return self.with_fixture_proposal(proposal)

    def edit_proposal_recommendation(self, recommendation_id: str,
                                     values: dict[str, object], note: str) -> "FxdProject":
        if self.fixture_proposal is None:
            raise ProjectFormatError("project has no fixture proposal to edit")
        from .ai_fixture_engineer import edit_recommendation, validate_fixture_proposal
        proposal = edit_recommendation(self.fixture_proposal, recommendation_id, values, note)
        proposal = validate_fixture_proposal(self, proposal)
        return self.with_fixture_proposal(proposal)

    def decide_fixture_proposal(self, decision: str, note: str = "") -> "FxdProject":
        if self.fixture_proposal is None:
            raise ProjectFormatError("project has no fixture proposal to decide")
        from .ai_fixture_engineer import decide_proposal
        return self.with_fixture_proposal(decide_proposal(self.fixture_proposal, decision, note))

    def with_drawing_intent(self, intent: dict[str, object] | None) -> "FxdProject":
        """Attach drawing evidence and invalidate dependent cost evidence."""
        return replace(self, drawing_intent=intent, optimization_intent=None)

    def with_optimization_intent(self, intent: dict[str, object] | None) -> "FxdProject":
        """Attach cost evidence only after drawing evidence is present."""
        if intent is not None and self.drawing_intent is None:
            raise ProjectFormatError("optimization intent requires persisted drawing intent")
        return replace(self, optimization_intent=intent)

    def with_placement(self, placement: PlacementPlan | None) -> "FxdProject":
        """Regenerate concepts after a placement change and clear derived evidence."""
        concepts = generate_fixture_concepts(self.product, self.annotations, placement=placement).concepts
        candidate = replace(self._invalidate_derived_intent(), concepts=concepts,
                            active_concept=next(item.identity for item in concepts),
                            placement=placement, suppressed_features=frozenset(),
                            approved_revision=None)
        return candidate._record_revision(self.revision_id)

    def with_annotations(self, annotations: EngineeringAnnotations) -> "FxdProject":
        """Regenerate concepts after an engineering-intent change."""
        annotations.validate_references(self.product)
        concepts = generate_fixture_concepts(self.product, annotations, placement=self.placement).concepts
        candidate = replace(self._invalidate_derived_intent(), annotations=annotations,
                            concepts=concepts, active_concept=next(item.identity for item in concepts),
                            suppressed_features=frozenset(), approved_revision=None)
        return candidate._record_revision(self.revision_id)

    def with_workflow(self, workflow: "InteractiveWorkflow") -> "FxdProject":
        """Persist presentation inputs and record their revision deterministically."""
        if workflow.source_sha256 != self.product.source_sha256:
            raise ProjectFormatError("interactive workflow does not match the immutable source geometry")
        candidate = replace(self, workflow=workflow, approved_revision=None)
        if candidate.fixture_proposal is not None:
            from .ai_fixture_engineer import (
                proposal_engineering_context_identity, validate_fixture_proposal,
            )
            original_identity = candidate.fixture_proposal.proposal_identity
            original_blockers = tuple(
                item.issue_id for item in candidate.fixture_proposal.guided_issues
                if item.severity == "error"
            )
            validated = validate_fixture_proposal(candidate, candidate.fixture_proposal)
            proposal_changed = validated.proposal_identity != original_identity
            current_orientation = workflow.setup.manufacturing_orientation
            stale = validated.stale_reason(
                candidate.product.source_sha256,
                current_orientation.identity if current_orientation is not None else None,
                proposal_engineering_context_identity(candidate)
                if candidate.workflow.has_accepted_manufacturing_orientation() else None,
            )
            blocker_state_changed = original_blockers != tuple(
                item.issue_id for item in validated.guided_issues if item.severity == "error"
            )
            invalidate_downstream = (
                proposal_changed or stale is not None or blocker_state_changed
            )
            candidate = replace(
                candidate, fixture_proposal=validated,
                drawing_intent=None if invalidate_downstream else candidate.drawing_intent,
                optimization_intent=None if invalidate_downstream else candidate.optimization_intent,
                fixture_build=None if invalidate_downstream else candidate.fixture_build,
            )
        return candidate._record_revision(self.revision_id)

    def with_fixture_build(self, fixture_build: "FixtureBuildPlan") -> "FxdProject":
        """Persist an editable M30 construction plan and revalidate it with the project."""
        if fixture_build.requirements.source_sha256 != self.product.source_sha256:
            raise ProjectFormatError("fixture build does not match the immutable source geometry")
        if fixture_build.concept_identity != self.active_concept:
            raise ProjectFormatError("fixture build must belong to the active fixture concept")
        candidate = replace(self, fixture_build=fixture_build, approved_revision=None)
        return candidate._record_revision(self.revision_id)

    @property
    def revision_id(self) -> str:
        payload = {
            "source_sha256": self.product.source_sha256,
            "active_concept": self.active_concept,
            "suppressed_features": sorted(self.suppressed_features),
            "edits": [_edit_dict(item) for item in self.edit_log],
            "optimization_intent": self.optimization_intent,
        }
        if self.workflow is not None:
            payload["workflow"] = self.workflow.identity_dict()
            payload["annotations"] = self.annotations.to_dict()
            payload["placement_digest"] = self.placement.evidence_digest if self.placement else None
        if self.fixture_build is not None:
            payload["fixture_build"] = self.fixture_build.to_dict()
        if self.fixture_proposal is not None:
            payload["fixture_proposal"] = self.fixture_proposal.to_dict()
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "rev-" + hashlib.sha256(encoded.encode()).hexdigest()[:16]

    def _record_revision(self, parent: str | None) -> "FxdProject":
        validation = self.active_validation
        revision = ProjectRevision(
            self.revision_id, parent, self.active_concept, len(self.edit_log), self.edit_log,
            validation.status, validation.evidence_digest, self.suppressed_features,
        )
        history = tuple(item for item in self.revisions if item.revision_id != revision.revision_id)
        history += (revision,)
        return replace(self, revisions=history, approved_revision=None)

    def with_concept(self, identity: str) -> "FxdProject":
        if identity not in {concept.identity for concept in self.concepts}:
            raise ProjectFormatError(f"unknown concept {identity!r}")
        if identity == self.active_concept:
            return self
        candidate = replace(self._invalidate_derived_intent(), active_concept=identity, suppressed_features=frozenset(),
                            approved_revision=None)
        return candidate._record_revision(self.revision_id)

    def toggle_layer(self, layer: str) -> "FxdProject":
        if layer not in SUPPORTED_LAYERS:
            raise ProjectFormatError(f"unknown visual layer {layer!r}")
        hidden = set(self.hidden_layers)
        hidden.remove(layer) if layer in hidden else hidden.add(layer)
        return replace(self, hidden_layers=frozenset(hidden))

    def _base_parameters(self) -> FixtureParameters:
        return FixtureParameters()

    def _regenerate(self, edits: tuple[FixtureEdit, ...]) -> tuple[CompleteFixtureConcept, ...]:
        params = self._base_parameters()
        aliases = {"pin_diameter": "locator_wall", "support_height": "locator_height",
                   "clearance": "contact_clearance"}
        for edit in edits:
            if edit.operation != "set_parameter":
                continue
            target = aliases.get(edit.target, edit.target)
            if target not in FixtureParameters.__dataclass_fields__:
                raise ProjectFormatError(f"unsupported fixture parameter {edit.target!r}")
            current = getattr(params, target)
            try:
                value = float(edit.value) if isinstance(current, (int, float)) else str(edit.value)
                params = replace(params, **{target: value})
            except (TypeError, ValueError) as exc:
                raise ProjectFormatError(f"invalid value for fixture parameter {edit.target!r}") from exc

        generated = generate_fixture_concepts(self.product, self.annotations, params, placement=self.placement).concepts
        result: list[CompleteFixtureConcept] = []
        for concept in generated:
            features = list(concept.fixture.features)
            geometry_edits: list[FixtureEdit] = []
            for edit in edits:
                feature = next((item for item in features if item.identity == edit.target), None)
                if edit.operation in {"move", "resize", "replace"} and feature is None:
                    raise ProjectFormatError(f"unknown fixture feature {edit.target!r}")
                if edit.operation == "move":
                    try:
                        delta = edit.value if isinstance(edit.value, Vec3) else Vec3(*edit.value)
                    except (TypeError, ValueError) as exc:
                        raise ProjectFormatError("move requires a 3D offset") from exc
                    changed = replace(feature, bounds=feature.bounds.__class__(
                        feature.bounds.minimum + delta, feature.bounds.maximum + delta))
                    features[features.index(feature)] = changed
                    geometry_edits.append(edit)
                elif edit.operation == "resize":
                    if not isinstance(edit.value, dict) or not edit.value or set(edit.value) - {"x", "y", "z"}:
                        raise ProjectFormatError("resize requires one or more x, y, or z dimensions")
                    dims = [feature.bounds.maximum.x - feature.bounds.minimum.x,
                            feature.bounds.maximum.y - feature.bounds.minimum.y,
                            feature.bounds.maximum.z - feature.bounds.minimum.z]
                    for axis, raw in edit.value.items():
                        value = float(raw)
                        if value <= 0:
                            raise ProjectFormatError("resize dimensions must be positive")
                        dims["xyz".index(axis)] = value
                    center = Vec3((feature.bounds.minimum.x + feature.bounds.maximum.x) / 2,
                                  (feature.bounds.minimum.y + feature.bounds.maximum.y) / 2,
                                  (feature.bounds.minimum.z + feature.bounds.maximum.z) / 2)
                    half = Vec3(*(value / 2 for value in dims))
                    bounds = feature.bounds.__class__(
                        Vec3(center.x-half.x, center.y-half.y, center.z-half.z),
                        Vec3(center.x+half.x, center.y+half.y, center.z+half.z))
                    features[features.index(feature)] = replace(feature, bounds=bounds)
                    geometry_edits.append(edit)
                elif edit.operation == "replace":
                    allowed = {"round_pin", "relieved_locator", "support_pad", "hard_stop", "clamp_mount"}
                    if edit.value not in allowed:
                        raise ProjectFormatError(f"unsupported replacement type {edit.value!r}")
                    changed = replace(
                        feature, kind=str(edit.value), rule=f"engineer_replaced_{edit.value}",
                        assumptions=feature.assumptions + (f"Replaced by engineer with {edit.value}.",),
                        manufacturing=_manufacturing_for(str(edit.value), params),
                    )
                    features[features.index(feature)] = changed
                    geometry_edits.append(edit)

            explicitly_replaced = {
                edit.target for edit in edits if edit.operation == "replace"
            }
            normalized: list[FixtureFeature] = []
            for feature in features:
                kind = (
                    params.locator_type
                    if feature.identity == "round-pin-1" and feature.identity not in explicitly_replaced
                    else feature.kind
                )
                parameters = dict(feature.parameters)
                if feature.identity == "round-pin-1":
                    parameters["diameter"] = params.locator_wall
                    parameters["height"] = params.locator_height
                if feature.kind == "clamp_mount" or feature.identity.startswith("clamp"):
                    parameters["clamp_choice"] = params.clamp_choice
                normalized.append(replace(feature, kind=kind, parameters=parameters,
                                          manufacturing=_manufacturing_for(kind, params)))
            features = normalized

            findings = list(concept.fixture.findings)
            for edit in geometry_edits:
                findings.append(FixtureFinding(
                    "engineer_geometry_edit", "warning", edit.target,
                    "Engineer geometry edit regenerated the concept and requires review of updated validation evidence.",
                ))
            fixture = replace(concept.fixture, parameters=params, features=tuple(features),
                              findings=tuple(findings))
            corrections = list(concept.corrections)
            for edit in edits:
                if edit.operation == "correction":
                    corrections = [item for item in corrections if item.key != edit.target]
                    corrections.append(FixtureCorrection(edit.target, str(edit.value), edit.reason))
            result.append(replace(concept, fixture=fixture, corrections=tuple(corrections),
                                  structure=generate_structural_assembly(self.product, self.annotations, fixture)))
        return tuple(result)

    def _material_edit(self, edit: FixtureEdit,
                       *, suppressed: frozenset[str] | None = None) -> "FxdProject":
        edits = self.edit_log + (edit,)
        concepts = self._regenerate(edits)
        target_suppressed = suppressed if suppressed is not None else self.suppressed_features
        if target_suppressed:
            concepts = tuple(replace(
                concept, fixture=replace(
                    concept.fixture,
                    findings=concept.fixture.findings + tuple(
                        FixtureFinding("feature_suppressed", "warning", identity,
                                       "feature is suppressed in the current revision")
                        for identity in sorted(target_suppressed))))
                for concept in concepts)
        candidate = replace(self._invalidate_derived_intent(), concepts=concepts, suppressed_features=target_suppressed,
                            edit_log=edits, approved_revision=None)
        validation = candidate.active_validation
        decision = ReviewDecision(edit.operation, edit.target, edit.reason,
                                  validation.status, validation.evidence_digest)
        candidate = replace(candidate, decisions=candidate.decisions + (decision,))
        return candidate._record_revision(self.revision_id)

    def suppress(self, feature_id: str, note: str = "") -> "FxdProject":
        known = {feature.identity for feature in self.active.fixture.features}
        if feature_id not in known:
            raise ProjectFormatError(f"unknown fixture feature {feature_id!r}")
        hidden = set(self.suppressed_features)
        action = "unsuppress" if feature_id in hidden else "suppress"
        hidden.remove(feature_id) if feature_id in hidden else hidden.add(feature_id)
        return self._material_edit(FixtureEdit(action, feature_id, None, note),
                                   suppressed=frozenset(hidden))

    def correct(self, key: str, value: str, reason: str) -> "FxdProject":
        return self._material_edit(FixtureEdit("correction", key, value, reason))

    def edit_parameter(self, name: str, value: object, reason: str = "") -> "FxdProject":
        return self._material_edit(FixtureEdit("set_parameter", name, value, reason))

    def edit_feature(self, feature_id: str, operation: str, value: object = None,
                     reason: str = "") -> "FxdProject":
        if operation not in {"move", "resize", "replace"}:
            raise ProjectFormatError(f"unsupported feature edit {operation!r}")
        return self._material_edit(FixtureEdit(operation, feature_id, value, reason))

    def restore(self, revision_id: str) -> "FxdProject":
        revision = next((item for item in self.revisions if item.revision_id == revision_id), None)
        if revision is None:
            raise ProjectFormatError(f"unknown project revision {revision_id!r}")
        concepts = self._regenerate(revision.changes)
        candidate = replace(self._invalidate_derived_intent(), concepts=concepts, active_concept=revision.active_concept,
                            suppressed_features=revision.suppressed_features,
                            edit_log=revision.changes, approved_revision=None)
        if candidate.revision_id != revision.revision_id:
            raise ProjectFormatError("saved revision evidence does not reproduce deterministically")
        return candidate._record_revision(self.revision_id)

    def compare(self, revision_id: str) -> dict[str, object]:
        revision = next((item for item in self.revisions if item.revision_id == revision_id), None)
        if revision is None:
            raise ProjectFormatError(f"unknown project revision {revision_id!r}")
        return {"current_revision": self.revision_id, "other_revision": revision_id,
                "current_concept": self.active_concept, "other_concept": revision.active_concept,
                "current_edits": self.edit_log, "other_edits": revision.changes,
                "current_validation": self.active_validation.status,
                "other_validation": revision.validation_status}

    def decide(self, action: str, note: str = "") -> "FxdProject":
        if action not in {"approve_for_review", "reject"}:
            raise ProjectFormatError("review action must be approve_for_review or reject")
        validation = self.active_validation
        if action == "approve_for_review":
            if self.fixture_proposal is not None:
                orientation = self.workflow.setup.manufacturing_orientation if self.workflow else None
                from .ai_fixture_engineer import proposal_engineering_context_identity
                stale = self.fixture_proposal.stale_reason(
                    self.product.source_sha256, orientation.identity if orientation else None,
                    proposal_engineering_context_identity(self)
                    if self.workflow and self.workflow.has_accepted_manufacturing_orientation()
                    else None,
                )
                if stale:
                    raise ProjectFormatError(f"stale fixture proposal cannot be approved: {stale}")
                if self.fixture_proposal.blocker_count:
                    raise ProjectFormatError(
                        "fixture proposal with deterministic blockers cannot be approved")
                if self.fixture_proposal.proposal_decision != "accepted_for_engineering_review":
                    raise ProjectFormatError(
                        "fixture proposal must be accepted for engineering review before approval")
            if validation.blocked:
                raise ProjectFormatError(
                    "invalid deterministic validation result cannot be approved for engineering review")
            build = self.fixture_build_validation
            if build is not None and build.status != "valid":
                raise ProjectFormatError(
                    "provisional or invalid fixture-build evidence cannot be approved for engineering review")
            if self.suppressed_features or self.active.corrections:
                raise ProjectFormatError(
                    "edited concepts must be regenerated and deterministically revalidated before approval")
        decision = ReviewDecision(action, self.active_concept, note,
                                  validation.status, validation.evidence_digest)
        approved = self.revision_id if action == "approve_for_review" else None
        return replace(self, decisions=self.decisions + (decision,), approved_revision=approved)

    def to_dict(self) -> dict[str, object]:
        validations = {
            concept.identity: {"status": result.status, "version": result.version,
                               "evidence_digest": result.evidence_digest}
            for concept in self.concepts
            for result in (self.validation_for(concept),)
        }
        return {
            "format": PROJECT_FORMAT, "schema_version": 5, "units": "mm",
            "source_name": self.product.source_name,
            "source_sha256": self.product.source_sha256,
            "source_step_base64": base64.b64encode(self.product.source_bytes).decode("ascii"),
            "active_concept": self.active_concept,
            "hidden_layers": sorted(self.hidden_layers),
            "suppressed_features": sorted(self.suppressed_features),
            "decisions": [decision.__dict__ for decision in self.decisions],
            "edit_log": [_edit_dict(item) for item in self.edit_log],
            "revisions": [{"revision_id": item.revision_id, "parent_id": item.parent_id,
                           "active_concept": item.active_concept, "edit_count": item.edit_count,
                           "changes": [_edit_dict(change) for change in item.changes],
                           "validation_status": item.validation_status,
                           "evidence_digest": item.evidence_digest,
                           "suppressed_features": sorted(item.suppressed_features)}
                          for item in self.revisions],
            "approved_revision": self.approved_revision,
            "annotations": self.annotations.to_dict(),
            "placement": self.placement.to_dict() if self.placement else None,
            "drawing_intent": self.drawing_intent,
            "optimization_intent": self.optimization_intent,
            "interactive_workflow": self.workflow.to_dict() if self.workflow else None,
            "fixture_build": self.fixture_build.to_dict() if self.fixture_build else None,
            "fixture_proposal": self.fixture_proposal.to_dict() if self.fixture_proposal else None,
            "validations": validations,
            "concept_corrections": {
                concept.identity: [correction.__dict__ for correction in concept.corrections]
                for concept in self.concepts if concept.corrections},
        }

    def save(self, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return path

    @staticmethod
    def _annotations(data: dict[str, object], product: ProductModel) -> EngineeringAnnotations:
        def ref(value: dict[str, object]) -> GeometryReference:
            return GeometryReference(**value)
        result = EngineeringAnnotations(
            source_sha256=data["source_sha256"], source_name=data["source_name"],
            build_orientation=Vec3(**data["build_orientation"]),
            loading_direction=Vec3(**data["loading_direction"]),
            process_type=data["process_type"], production_quantity=int(data["production_quantity"]),
            critical_characteristics=tuple(CriticalCharacteristic(
                item["name"], tuple(ref(x) for x in item.get("references", ())),
                item.get("nominal_value"), item.get("units"), item.get("tolerance"),
                item.get("notes", "")) for item in data.get("critical_characteristics", ())),
            permitted_locating_surfaces=tuple(ref(item) for item in data.get("permitted_locating_surfaces", ())),
            forbidden_contact_areas=tuple(ref(item) for item in data.get("forbidden_contact_areas", ())),
            weld_joints=tuple(WeldJoint(
                item["identity"], tuple(ref(x) for x in item.get("references", ())),
                item.get("process"), item.get("notes", ""), item.get("sequence"),
                Vec3(**item["direction"]) if item.get("direction") else None,
                item.get("heat_input"), item.get("heat_input_units"),
                Vec3(**item["distortion_direction"]) if item.get("distortion_direction") else None,
                item.get("tack_required", True), item.get("release_sequence"),
                tuple(item.get("assumptions", ()))) for item in data.get("weld_joints", ())),
            shop_constraints=tuple(data.get("shop_constraints", ())),
            assumptions=tuple(Assumption(**item) for item in data.get("assumptions", ())),
            schema_version=data.get("schema_version", "fxd-annotations-v1"),
        )
        result.validate_references(product)
        return result

    @classmethod
    def load(cls, source: str | Path) -> "FxdProject":
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            if data.get("format") not in {
                    "fxd-neutral-project-v1", "fxd-neutral-project-v2", "fxd-neutral-project-v3",
                    "fxd-neutral-project-v4", PROJECT_FORMAT
            } or data.get("units") != "mm":
                raise ProjectFormatError("unsupported FXD project format or units")
            raw = base64.b64decode(data["source_step_base64"], validate=True)
            workflow_data = data.get("interactive_workflow")
            workflow = None
            orientation_revalidation_required = False
            if workflow_data:
                from .interactive_workflow import (
                    InteractiveWorkflow, product_from_workbench_document,
                )
                from .workbench import load_step_for_workbench
                document = load_step_for_workbench(raw, source_name=data["source_name"])
                product = product_from_workbench_document(document)
                workflow = InteractiveWorkflow.from_dict(workflow_data)
                orientation_revalidation_required = not workflow.has_accepted_manufacturing_orientation()
            else:
                product = import_step(raw.decode("utf-8"), source_name=data["source_name"])
            if product.source_sha256 != data["source_sha256"]:
                raise ProjectFormatError("project source hash does not match embedded source")
            placement = PlacementPlan.from_dict(data["placement"]) if data.get("placement") else None
            project = cls.from_product(
                product, cls._annotations(data["annotations"], product),
                placement=placement, workflow=workflow,
            )
            for raw_edit in data.get("edit_log", []):
                edit = FixtureEdit(raw_edit["operation"], raw_edit["target"],
                                   raw_edit.get("value"), raw_edit.get("reason", ""))
                if edit.operation == "set_parameter":
                    project = project.edit_parameter(edit.target, edit.value, edit.reason)
                elif edit.operation == "correction":
                    project = project.correct(edit.target, str(edit.value), edit.reason)
                elif edit.operation in {"move", "resize", "replace"}:
                    value = edit.value
                    if edit.operation == "move" and isinstance(value, dict):
                        value = (value["x"], value["y"], value["z"])
                    project = project.edit_feature(edit.target, edit.operation, value, edit.reason)
                elif edit.operation in {"suppress", "unsuppress"}:
                    project = project.suppress(edit.target, edit.reason)
                else:
                    raise ProjectFormatError(f"unsupported saved edit {edit.operation!r}")
            project = project.with_concept(data["active_concept"])
            fixture_proposal_data = data.get("fixture_proposal")
            if fixture_proposal_data:
                from .ai_fixture_engineer import FixtureProposal
                project = project.with_fixture_proposal(
                    FixtureProposal.from_dict(fixture_proposal_data)
                )
            fixture_build_data = data.get("fixture_build")
            if fixture_build_data:
                from .fabrication_workflow import FixtureBuildPlan
                project = project.with_fixture_build(FixtureBuildPlan.from_dict(fixture_build_data))
            for layer in data.get("hidden_layers", []):
                if layer not in project.hidden_layers:
                    project = project.toggle_layer(layer)
            saved_validations = data.get("validations", {})
            if not orientation_revalidation_required:
                for concept in project.concepts:
                    saved = saved_validations.get(concept.identity)
                    if saved:
                        current = project.validation_for(concept)
                        if (saved.get("status"), saved.get("version"), saved.get("evidence_digest")) != (
                                current.status, current.version, current.evidence_digest):
                            raise ProjectFormatError(f"deterministic validation changed for concept {concept.identity}")
            decisions = tuple(ReviewDecision(**item) for item in data.get("decisions", []))
            saved_revisions = tuple(ProjectRevision(
                item["revision_id"], item.get("parent_id"), item.get("active_concept", data["active_concept"]),
                int(item["edit_count"]), tuple(FixtureEdit(
                    change["operation"], change["target"], change.get("value"), change.get("reason", ""))
                    for change in item.get("changes", [])), item["validation_status"],
                item["evidence_digest"], frozenset(item.get("suppressed_features", [])))
                for item in data.get("revisions", []))
            restored = replace(project, decisions=decisions,
                               revisions=saved_revisions or project.revisions,
                               approved_revision=(None if orientation_revalidation_required
                                                  else data.get("approved_revision")),
                               drawing_intent=data.get("drawing_intent"),
                               optimization_intent=data.get("optimization_intent"),
                               workflow=workflow)
            if restored.approved_revision is not None and restored.approved_revision != restored.revision_id:
                raise ProjectFormatError("saved approval does not belong to the restored revision")
            return restored
        except ProjectFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectFormatError(f"invalid FXD project: {exc}") from exc
