"""Local, neutral FXD project persistence for the engineering review application."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .annotations import (
    Assumption,
    CriticalCharacteristic,
    EngineeringAnnotations,
    GeometryReference,
    WeldJoint,
)
from .aabb import Vec3
from .concepts import CompleteFixtureConcept, FixtureCorrection, generate_fixture_concepts
from .fixture import FixtureFeature, FixtureFinding, FixtureParameters
from .product_model import ProductModel
from .step_import import import_step
from .validation import ValidationResult, validate_fixture_concept


class ProjectFormatError(ValueError):
    """Raised when a saved project is incomplete, unsafe, or incompatible."""


SUPPORTED_LAYERS = frozenset({"product", "fixture", "datums", "welds", "access", "warnings"})


@dataclass(frozen=True)
class ReviewDecision:
    action: str
    target: str
    note: str
    validation_status: str
    evidence_digest: str


@dataclass(frozen=True)
class FixtureEdit:
    """Restricted, deterministic edit command; never a free-form geometry patch."""

    operation: str
    target: str
    value: object = None
    reason: str = ""


@dataclass(frozen=True)
class ProjectRevision:
    revision_id: str
    parent_id: str | None
    edit_count: int
    changes: tuple[FixtureEdit, ...]
    validation_status: str
    evidence_digest: str
    suppressed_features: frozenset[str] = frozenset()


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
        project = cls(product, annotations, concepts, concepts[0].identity)
        return project._with_revision((), None)

    @property
    def revision_id(self) -> str:
        encoded = json.dumps([item.__dict__ for item in self.edit_log], sort_keys=True,
                             separators=(",", ":"), default=str)
        return "rev-" + hashlib.sha256(encoded.encode()).hexdigest()[:16]

    def _with_revision(self, edits: tuple[FixtureEdit, ...], parent: str | None) -> "FxdProject":
        status = self.active_validation
        revision = ProjectRevision(self.revision_id, parent, len(edits), edits,
                                   status.status, status.evidence_digest, self.suppressed_features)
        history = self.revisions
        if not history or history[-1].revision_id != revision.revision_id:
            history = history + (revision,)
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              self.hidden_layers, self.suppressed_features, self.decisions,
                              edits, history, None)

    @property
    def active(self) -> CompleteFixtureConcept:
        for concept in self.concepts:
            if concept.identity == self.active_concept:
                return concept
        raise ProjectFormatError(f"active concept {self.active_concept!r} is missing")

    @property
    def active_validation(self) -> ValidationResult:
        return validate_fixture_concept(self.product, self.active)

    def with_concept(self, identity: str) -> "FxdProject":
        if identity not in {concept.identity for concept in self.concepts}:
            raise ProjectFormatError(f"unknown concept {identity!r}")
        return self.__class__(self.product, self.annotations, self.concepts, identity,
                              self.hidden_layers, self.suppressed_features, self.decisions,
                              self.edit_log, self.revisions, self.approved_revision)

    def toggle_layer(self, layer: str) -> "FxdProject":
        if layer not in SUPPORTED_LAYERS:
            raise ProjectFormatError(f"unknown visual layer {layer!r}")
        hidden = set(self.hidden_layers)
        hidden.remove(layer) if layer in hidden else hidden.add(layer)
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              frozenset(hidden), self.suppressed_features, self.decisions,
                              self.edit_log, self.revisions, self.approved_revision)

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
        # Preserve the pre-M18 review-note API as a constrained, regenerating
        # edit.  It carries no geometry authority until a supported parameter
        # or feature operation is used.
        return self._material_edit(FixtureEdit("correction", key, value, reason))

    def _regenerate(self, edits: tuple[FixtureEdit, ...]) -> tuple[CompleteFixtureConcept, ...]:
        params = self.active.fixture.parameters
        aliases = {"pin_diameter": "locator_wall", "support_height": "locator_height",
                   "clearance": "contact_clearance"}
        for edit in edits:
            if edit.operation == "set_parameter":
                target = aliases.get(edit.target, edit.target)
                if target not in FixtureParameters.__dataclass_fields__:
                    raise ProjectFormatError(f"unsupported fixture parameter {edit.target!r}")
                try:
                    current = params.__dict__[target]
                    value = float(edit.value) if isinstance(current, (int, float)) else str(edit.value)
                    params = FixtureParameters(**{**params.__dict__, target: value})
                except (TypeError, ValueError) as exc:
                    raise ProjectFormatError(f"invalid value for fixture parameter {edit.target!r}") from exc
        generated = generate_fixture_concepts(self.product, self.annotations, params).concepts
        result = []
        for concept in generated:
            features = list(concept.fixture.features)
            for edit in edits:
                if edit.operation == "move":
                    feature = next((x for x in features if x.identity == edit.target), None)
                    if feature is None: raise ProjectFormatError(f"unknown fixture feature {edit.target!r}")
                    try: delta = edit.value if isinstance(edit.value, Vec3) else Vec3(*edit.value)
                    except (TypeError, ValueError) as exc: raise ProjectFormatError("move requires a 3D offset") from exc
                    features[features.index(feature)] = FixtureFeature(
                        feature.identity, feature.kind,
                        feature.bounds.__class__(feature.bounds.minimum + delta, feature.bounds.maximum + delta),
                        feature.source_references, feature.rule, feature.parameters, feature.units,
                        feature.assumptions, feature.warnings, feature.manufacturing)
                elif edit.operation == "resize":
                    feature = next((x for x in features if x.identity == edit.target), None)
                    if feature is None: raise ProjectFormatError(f"unknown fixture feature {edit.target!r}")
                    if not isinstance(edit.value, dict) or set(edit.value) - {"x", "y", "z"}:
                        raise ProjectFormatError("resize requires x, y, and z dimensions")
                    dims = [feature.bounds.maximum.x-feature.bounds.minimum.x,
                            feature.bounds.maximum.y-feature.bounds.minimum.y,
                            feature.bounds.maximum.z-feature.bounds.minimum.z]
                    for axis, value in edit.value.items():
                        if float(value) <= 0: raise ProjectFormatError("resize dimensions must be positive")
                        dims["xyz".index(axis)] = float(value)
                    center = Vec3(*[(a+b)/2 for a,b in zip(feature.bounds.minimum.__dict__.values(), feature.bounds.maximum.__dict__.values())])
                    half = Vec3(*(value/2 for value in dims))
                    minimum = Vec3(center.x-half.x, center.y-half.y, center.z-half.z)
                    maximum = Vec3(center.x+half.x, center.y+half.y, center.z+half.z)
                    features[features.index(feature)] = FixtureFeature(
                        feature.identity, feature.kind, feature.bounds.__class__(minimum, maximum),
                        feature.source_references, feature.rule, feature.parameters, feature.units,
                        feature.assumptions, feature.warnings, feature.manufacturing)
                elif edit.operation == "replace":
                    feature = next((x for x in features if x.identity == edit.target), None)
                    if feature is None: raise ProjectFormatError(f"unknown fixture feature {edit.target!r}")
                    if edit.value not in {"round_pin", "relieved_locator", "support_pad", "hard_stop", "clamp_mount"}:
                        raise ProjectFormatError(f"unsupported replacement type {edit.value!r}")
                    features[features.index(feature)] = FixtureFeature(
                        feature.identity, edit.value, feature.bounds, feature.source_references,
                        f"engineer_replaced_{edit.value}", feature.parameters, feature.units,
                        feature.assumptions + (f"Replaced by engineer with {edit.value}.",),
                        feature.warnings, feature.manufacturing)
            if params.locator_type != "round_pin":
                features = [FixtureFeature(
                    feature.identity, params.locator_type if feature.kind in {"round_pin", "relieved_locator"} else feature.kind,
                    feature.bounds, feature.source_references, feature.rule, feature.parameters,
                    feature.units, feature.assumptions, feature.warnings, feature.manufacturing)
                    for feature in features]
            fixture = concept.fixture.__class__(concept.fixture.source_sha256, concept.fixture.units,
                                                concept.fixture.parameters, tuple(features), concept.fixture.findings)
            corrections = list(concept.corrections)
            for edit in edits:
                if edit.operation == "correction":
                    corrections = [item for item in corrections if item.key != edit.target]
                    corrections.append(FixtureCorrection(edit.target, str(edit.value), edit.reason))
            result.append(concept.__class__(concept.identity, concept.objective, fixture,
                                            concept.locating_strategy, concept.clamping_strategy,
                                            concept.constraints, concept.score,
                                            tuple(corrections)))
        return tuple(result)

    def _material_edit(self, edit: FixtureEdit, *, suppressed: frozenset[str] | None = None) -> "FxdProject":
        edits = self.edit_log + (edit,)
        concepts = self._regenerate(edits)
        target_suppressed = suppressed if suppressed is not None else self.suppressed_features
        if target_suppressed:
            concepts = tuple(concept.__class__(
                concept.identity, concept.objective,
                concept.fixture.__class__(concept.fixture.source_sha256, concept.fixture.units,
                                          concept.fixture.parameters, concept.fixture.features,
                                          concept.fixture.findings + tuple(
                                              FixtureFinding("feature_suppressed", "warning", identity,
                                                             "feature is suppressed in the current revision")
                                              for identity in sorted(target_suppressed))),
                concept.locating_strategy, concept.clamping_strategy, concept.constraints,
                concept.score, concept.corrections) for concept in concepts)
        candidate = self.__class__(self.product, self.annotations, concepts, self.active_concept,
                                   self.hidden_layers, self.suppressed_features if suppressed is None else suppressed,
                                   self.decisions, edits, self.revisions, None)
        validation = candidate.active_validation
        decisions = candidate.decisions + (ReviewDecision(edit.operation, edit.target, edit.reason,
                                                           validation.status, validation.evidence_digest),)
        return self.__class__(candidate.product, candidate.annotations, candidate.concepts,
                              candidate.active_concept, candidate.hidden_layers,
                              candidate.suppressed_features, decisions,
                              edits, candidate.revisions, None)._with_revision(edits, self.revision_id)

    def edit_parameter(self, name: str, value: object, reason: str = "") -> "FxdProject":
        return self._material_edit(FixtureEdit("set_parameter", name, value, reason))

    def edit_feature(self, feature_id: str, operation: str, value: object = None,
                     reason: str = "") -> "FxdProject":
        if operation not in {"move", "resize", "replace"}:
            raise ProjectFormatError(f"unsupported feature edit {operation!r}")
        return self._material_edit(FixtureEdit(operation, feature_id, value, reason))

    def restore(self, revision_id: str) -> "FxdProject":
        revision = next((item for item in self.revisions if item.revision_id == revision_id), None)
        if revision is None: raise ProjectFormatError(f"unknown project revision {revision_id!r}")
        concepts = self._regenerate(revision.changes)
        return self.__class__(self.product, self.annotations, concepts, self.active_concept,
                              self.hidden_layers, revision.suppressed_features, self.decisions,
                              revision.changes, self.revisions, None)._with_revision(revision.changes, self.revision_id)

    def compare(self, revision_id: str) -> dict[str, object]:
        revision = next((item for item in self.revisions if item.revision_id == revision_id), None)
        if revision is None: raise ProjectFormatError(f"unknown project revision {revision_id!r}")
        return {"current_revision": self.revision_id, "other_revision": revision_id,
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
        decision = ReviewDecision(
            action, self.active_concept, note, validation.status, validation.evidence_digest)
        approved = self.revision_id if action == "approve_for_review" else None
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              self.hidden_layers, self.suppressed_features,
                              self.decisions + (decision,), self.edit_log, self.revisions, approved)

    def to_dict(self) -> dict[str, object]:
        def encode_edit(edit: FixtureEdit) -> dict[str, object]:
            value = edit.value
            if isinstance(value, Vec3):
                value = {"x": value.x, "y": value.y, "z": value.z}
            return {"operation": edit.operation, "target": edit.target,
                    "value": value, "reason": edit.reason}

        validations = {
            concept.identity: {
                "status": result.status,
                "version": result.version,
                "evidence_digest": result.evidence_digest,
            }
            for concept in self.concepts
            for result in (validate_fixture_concept(self.product, concept),)
        }
        return {
            "format": "fxd-neutral-project-v1", "units": "mm",
            "source_name": self.product.source_name,
            "source_sha256": self.product.source_sha256,
            "source_step_base64": base64.b64encode(self.product.source_bytes).decode("ascii"),
            "active_concept": self.active_concept,
            "hidden_layers": sorted(self.hidden_layers),
            "suppressed_features": sorted(self.suppressed_features),
            "decisions": [decision.__dict__ for decision in self.decisions],
            "edit_log": [encode_edit(item) for item in self.edit_log],
            "revisions": [{"revision_id": item.revision_id, "parent_id": item.parent_id,
                           "edit_count": item.edit_count,
                           "changes": [encode_edit(change) for change in item.changes],
                           "validation_status": item.validation_status,
                           "evidence_digest": item.evidence_digest,
                           "suppressed_features": sorted(item.suppressed_features)}
                          for item in self.revisions],
            "approved_revision": self.approved_revision,
            "annotations": self.annotations.to_dict(),
            "validations": validations,
            "concept_corrections": {
                concept.identity: [correction.__dict__ for correction in concept.corrections]
                for concept in self.concepts if concept.corrections
            },
        }

    def save(self, destination: str | Path) -> Path:
        path = Path(destination)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _annotations(data: dict[str, object], product: ProductModel) -> EngineeringAnnotations:
        def ref(value: dict[str, object]) -> GeometryReference:
            return GeometryReference(**value)

        result = EngineeringAnnotations(
            source_sha256=data["source_sha256"],
            source_name=data["source_name"],
            build_orientation=Vec3(**data["build_orientation"]),
            loading_direction=Vec3(**data["loading_direction"]),
            process_type=data["process_type"],
            production_quantity=int(data["production_quantity"]),
            critical_characteristics=tuple(
                CriticalCharacteristic(
                    item["name"], tuple(ref(x) for x in item.get("references", ())),
                    item.get("nominal_value"), item.get("units"), item.get("tolerance"),
                    item.get("notes", ""))
                for item in data.get("critical_characteristics", ())),
            permitted_locating_surfaces=tuple(
                ref(item) for item in data.get("permitted_locating_surfaces", ())),
            forbidden_contact_areas=tuple(
                ref(item) for item in data.get("forbidden_contact_areas", ())),
            weld_joints=tuple(
                WeldJoint(
                    item["identity"], tuple(ref(x) for x in item.get("references", ())),
                    item.get("process"), item.get("notes", ""), item.get("sequence"),
                    Vec3(**item["direction"]) if item.get("direction") else None,
                    item.get("heat_input"), item.get("heat_input_units"),
                    Vec3(**item["distortion_direction"])
                    if item.get("distortion_direction") else None,
                    item.get("tack_required", True), item.get("release_sequence"),
                    tuple(item.get("assumptions", ())))
                for item in data.get("weld_joints", ())),
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
            if data.get("format") != "fxd-neutral-project-v1" or data.get("units") != "mm":
                raise ProjectFormatError("unsupported FXD project format or units")
            raw = base64.b64decode(data["source_step_base64"], validate=True)
            product = import_step(raw.decode("utf-8"), source_name=data["source_name"])
            if product.source_sha256 != data["source_sha256"]:
                raise ProjectFormatError("project source hash does not match embedded source")
            annotations = cls._annotations(data["annotations"], product)
            project = cls.from_product(product, annotations)
            raw_edits = data.get("edit_log", [])
            if raw_edits:
                for raw in raw_edits:
                    edit = FixtureEdit(raw["operation"], raw["target"], raw.get("value"), raw.get("reason", ""))
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
            else:
                for identity, corrections in data.get("concept_corrections", {}).items():
                    project = project.with_concept(identity)
                    for correction in corrections:
                        project = project.correct(
                            correction["key"], correction["value"], correction["reason"])
            project = project.with_concept(data["active_concept"])
            for layer in data.get("hidden_layers", []):
                if layer not in project.hidden_layers:
                    project = project.toggle_layer(layer)
            if not raw_edits:
                for feature in data.get("suppressed_features", []):
                    if feature not in project.suppressed_features:
                        project = project.suppress(feature)
            saved_validations = data.get("validations", {})
            for concept in project.concepts:
                saved = saved_validations.get(concept.identity)
                if saved:
                    current = validate_fixture_concept(project.product, concept)
                    if (saved.get("status"), saved.get("version"), saved.get("evidence_digest")) != (
                            current.status, current.version, current.evidence_digest):
                        raise ProjectFormatError(
                            f"deterministic validation changed for concept {concept.identity}")
            decisions = tuple(ReviewDecision(**item) for item in data.get("decisions", []))
            saved_revisions = tuple(
                ProjectRevision(item["revision_id"], item.get("parent_id"), int(item["edit_count"]),
                                tuple(FixtureEdit(change["operation"], change["target"], change.get("value"),
                                                   change.get("reason", "")) for change in item.get("changes", [])),
                                item["validation_status"], item["evidence_digest"],
                                frozenset(item.get("suppressed_features", [])))
                for item in data.get("revisions", []))
            return cls(project.product, project.annotations, project.concepts,
                       project.active_concept, project.hidden_layers,
                       project.suppressed_features, decisions, project.edit_log,
                       saved_revisions or project.revisions, data.get("approved_revision"))
        except ProjectFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectFormatError(f"invalid FXD project: {exc}") from exc
