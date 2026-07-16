"""Local, neutral FXD project persistence and deterministic revision workflow."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from .annotations import (
    Assumption, CriticalCharacteristic, EngineeringAnnotations, GeometryReference, WeldJoint,
)
from .aabb import Vec3
from .concepts import CompleteFixtureConcept, FixtureCorrection, generate_fixture_concepts
from .fixture import FixtureFeature, FixtureFinding, FixtureParameters, ManufacturingSpec
from .product_model import ProductModel
from .step_import import import_step
from .validation import ValidationResult, validate_fixture_concept


class ProjectFormatError(ValueError):
    """Raised when a saved project is incomplete, unsafe, or incompatible."""


SUPPORTED_LAYERS = frozenset({"product", "fixture", "datums", "welds", "access", "warnings"})
PROJECT_FORMAT = "fxd-neutral-project-v2"


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

    @classmethod
    def from_product(cls, product: ProductModel, annotations: EngineeringAnnotations) -> "FxdProject":
        annotations.validate_references(product)
        concepts = generate_fixture_concepts(product, annotations).concepts
        if not concepts:
            raise ProjectFormatError("fixture generation produced no concepts")
        return cls(product, annotations, concepts, concepts[0].identity)._record_revision(None)

    @property
    def active(self) -> CompleteFixtureConcept:
        return next(concept for concept in self.concepts if concept.identity == self.active_concept)

    @property
    def active_validation(self) -> ValidationResult:
        return validate_fixture_concept(self.product, self.active)

    @property
    def revision_id(self) -> str:
        payload = {
            "source_sha256": self.product.source_sha256,
            "active_concept": self.active_concept,
            "suppressed_features": sorted(self.suppressed_features),
            "edits": [_edit_dict(item) for item in self.edit_log],
        }
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
        candidate = replace(self, active_concept=identity, suppressed_features=frozenset(),
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

        generated = generate_fixture_concepts(self.product, self.annotations, params).concepts
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
            result.append(replace(concept, fixture=fixture, corrections=tuple(corrections)))
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
        candidate = replace(self, concepts=concepts, suppressed_features=target_suppressed,
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
        candidate = replace(self, concepts=concepts, active_concept=revision.active_concept,
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
            if validation.blocked:
                raise ProjectFormatError(
                    "invalid deterministic validation result cannot be approved for engineering review")
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
            for result in (validate_fixture_concept(self.product, concept),)
        }
        return {
            "format": PROJECT_FORMAT, "schema_version": 2, "units": "mm",
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
            if data.get("format") not in {"fxd-neutral-project-v1", PROJECT_FORMAT} or data.get("units") != "mm":
                raise ProjectFormatError("unsupported FXD project format or units")
            raw = base64.b64decode(data["source_step_base64"], validate=True)
            product = import_step(raw.decode("utf-8"), source_name=data["source_name"])
            if product.source_sha256 != data["source_sha256"]:
                raise ProjectFormatError("project source hash does not match embedded source")
            project = cls.from_product(product, cls._annotations(data["annotations"], product))
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
            for layer in data.get("hidden_layers", []):
                if layer not in project.hidden_layers:
                    project = project.toggle_layer(layer)
            saved_validations = data.get("validations", {})
            for concept in project.concepts:
                saved = saved_validations.get(concept.identity)
                if saved:
                    current = validate_fixture_concept(project.product, concept)
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
                               approved_revision=data.get("approved_revision"))
            if restored.approved_revision is not None and restored.approved_revision != restored.revision_id:
                raise ProjectFormatError("saved approval does not belong to the restored revision")
            return restored
        except ProjectFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectFormatError(f"invalid FXD project: {exc}") from exc
