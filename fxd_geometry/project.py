"""Local, neutral FXD project persistence for the engineering review application."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, replace
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
from .fixture import FixtureFeature, FixtureParameters
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
class FeatureEdit:
    """Restricted, serializable edit command; never a free-form geometry edit."""

    operation: str
    feature_identity: str
    values: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        if self.operation not in {"move", "resize", "suppress", "restore", "replace", "parameters"}:
            raise ProjectFormatError(f"unsupported feature edit {self.operation!r}")


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
    revision: int = 0
    parent_revision: int | None = None
    edits: tuple[FeatureEdit, ...] = ()

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

    @classmethod
    def from_product(cls, product: ProductModel, annotations: EngineeringAnnotations) -> "FxdProject":
        annotations.validate_references(product)
        concepts = generate_fixture_concepts(product, annotations).concepts
        if not concepts:
            raise ProjectFormatError("fixture generation produced no concepts")
        return cls(product, annotations, concepts, concepts[0].identity)

    @property
    def active(self) -> CompleteFixtureConcept:
        for concept in self.concepts:
            if concept.identity == self.active_concept:
                return concept
        raise ProjectFormatError(f"active concept {self.active_concept!r} is missing")

    @property
    def active_validation(self) -> ValidationResult:
        return validate_fixture_concept(self.product, self.active)

    @property
    def approval_state(self) -> str:
        """Approval is scoped to the active revision and is never inherited."""
        for decision in reversed(self.decisions):
            if decision.target == self.active_concept:
                return "approved_for_review" if decision.action == "approve_for_review" else "rejected"
        return "unapproved"

    @property
    def approved_for_review(self) -> bool:
        return self.approval_state == "approved_for_review"

    def with_concept(self, identity: str) -> "FxdProject":
        if identity not in {concept.identity for concept in self.concepts}:
            raise ProjectFormatError(f"unknown concept {identity!r}")
        return self.__class__(self.product, self.annotations, self.concepts, identity,
                              self.hidden_layers, frozenset(), self.decisions,
                              self.revision, self.parent_revision, self.edits)

    def toggle_layer(self, layer: str) -> "FxdProject":
        if layer not in SUPPORTED_LAYERS:
            raise ProjectFormatError(f"unknown visual layer {layer!r}")
        hidden = set(self.hidden_layers)
        hidden.remove(layer) if layer in hidden else hidden.add(layer)
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              frozenset(hidden), self.suppressed_features, self.decisions,
                              self.revision, self.parent_revision, self.edits)

    def _regenerate(self, edits: tuple[FeatureEdit, ...]) -> "FxdProject":
        """Regenerate the active objective, then apply only validated edit commands."""
        parameters = self.active.fixture.parameters
        parameter_aliases = {
            "base_thickness": "base_thickness", "support_height": "locator_height",
            "pin_diameter": "locator_wall", "clearance": "contact_clearance",
        }
        for edit in edits:
            if edit.operation == "parameters":
                updates = {parameter_aliases[key]: float(value)
                           for key, value in edit.values if key in parameter_aliases}
                if updates:
                    parameters = replace(parameters, **updates)
        generated = generate_fixture_concepts(self.product, self.annotations, parameters)
        source = next(item for item in generated.concepts if item.objective == self.active.objective)
        features = list(source.fixture.features)
        suppressed: set[str] = set()
        for edit in edits:
            index = next((i for i, item in enumerate(features)
                          if item.identity == edit.feature_identity), None)
            if index is None:
                raise ProjectFormatError(f"unknown fixture feature {edit.feature_identity!r}")
            feature = features[index]
            values = dict(edit.values)
            if edit.operation == "suppress":
                suppressed.add(feature.identity)
            elif edit.operation == "restore":
                suppressed.discard(feature.identity)
            elif edit.operation == "move":
                offset = Vec3(float(values.get("dx", 0)), float(values.get("dy", 0)), float(values.get("dz", 0)))
                bounds = feature.bounds
                feature = replace(feature, bounds=type(bounds)(bounds.minimum + offset, bounds.maximum + offset))
            elif edit.operation == "resize":
                low = Vec3(*[float(values.get(axis + "_min", getattr(feature.bounds.minimum, axis)))
                             for axis in ("x", "y", "z")])
                high = Vec3(*[float(values.get(axis + "_max", getattr(feature.bounds.maximum, axis)))
                              for axis in ("x", "y", "z")])
                if any(getattr(high, axis) <= getattr(low, axis) for axis in ("x", "y", "z")):
                    raise ProjectFormatError("resize must preserve positive feature dimensions")
                feature = replace(feature, bounds=type(feature.bounds)(low, high))
            elif edit.operation == "replace":
                kind = str(values.get("kind", ""))
                allowed = {"support_pad", "hard_stop", "round_pin", "relieved_locator", "clamp_mount"}
                if kind not in allowed:
                    raise ProjectFormatError(f"unsupported replacement feature kind {kind!r}")
                feature = replace(feature, kind=kind, rule=f"engineer_replacement:{kind}")
            elif edit.operation == "parameters":
                supported = {"base_thickness", "support_height", "pin_diameter", "clearance", "fit", "locator_type", "clamp_choice"}
                unknown = set(values) - supported
                if unknown:
                    raise ProjectFormatError(f"unsupported fixture parameters: {sorted(unknown)}")
                feature = replace(feature, parameters={**feature.parameters, **values})
            features[index] = feature
        revised_fixture = replace(source.fixture, features=tuple(features))
        revised = replace(source, identity=f"{source.identity}-r{self.revision + 1}", fixture=revised_fixture)
        concepts = self.concepts + (revised,)
        validation = validate_fixture_concept(self.product, revised)
        decisions = self.decisions + (ReviewDecision(
            "edit_regenerate_revalidate", revised.identity,
            "; ".join(edit.operation for edit in edits), validation.status, validation.evidence_digest),)
        return self.__class__(self.product, self.annotations, concepts, revised.identity,
                              self.hidden_layers, frozenset(suppressed), decisions,
                              self.revision + 1, self.revision, edits)

    def edit_feature(self, feature_id: str, operation: str, **values: object) -> "FxdProject":
        """Apply a supported edit and return a new regenerated, validated revision."""
        if feature_id not in {feature.identity for feature in self.active.fixture.features}:
            raise ProjectFormatError(f"unknown fixture feature {feature_id!r}")
        return self._regenerate(self.edits + (FeatureEdit(operation, feature_id, tuple(sorted(values.items()))),))

    def move_feature(self, feature_id: str, offset: Vec3) -> "FxdProject":
        return self.edit_feature(feature_id, "move", dx=offset.x, dy=offset.y, dz=offset.z)

    def resize_feature(self, feature_id: str, **bounds: float) -> "FxdProject":
        return self.edit_feature(feature_id, "resize", **bounds)

    def replace_feature(self, feature_id: str, kind: str) -> "FxdProject":
        return self.edit_feature(feature_id, "replace", kind=kind)

    def restore_feature(self, feature_id: str) -> "FxdProject":
        return self.edit_feature(feature_id, "restore")

    def edit_parameters(self, feature_id: str, **values: object) -> "FxdProject":
        return self.edit_feature(feature_id, "parameters", **values)

    def restore_revision(self, revision: int) -> "FxdProject":
        """Select an existing immutable revision; no geometry is silently mutated."""
        target = next((item for item in self.concepts
                       if item.identity.endswith(f"-r{revision}") or (revision == 0 and item.identity == self.concepts[0].identity)), None)
        if target is None:
            raise ProjectFormatError(f"unknown project revision {revision}")
        restored = self.with_concept(target.identity)
        return replace(restored, revision=revision, parent_revision=None, edits=())

    def suppress(self, feature_id: str, note: str = "") -> "FxdProject":
        action = "restore" if feature_id in self.suppressed_features else "suppress"
        revised = self.edit_feature(feature_id, action)
        if note:
            decision = ReviewDecision(action, feature_id, note,
                                      revised.active_validation.status,
                                      revised.active_validation.evidence_digest)
            revised = replace(revised, decisions=revised.decisions + (decision,))
        return revised

    def correct(self, key: str, value: str, reason: str) -> "FxdProject":
        regenerated = self._regenerate(self.edits)
        concept = regenerated.active.with_correction(FixtureCorrection(key, value, reason))
        concepts = tuple(concept if item.identity == regenerated.active.identity else item
                         for item in regenerated.concepts)
        validation = validate_fixture_concept(self.product, concept)
        decisions = regenerated.decisions + (ReviewDecision(
            "correct", key, reason, validation.status, validation.evidence_digest),)
        return self.__class__(self.product, self.annotations, concepts, concept.identity,
                              self.hidden_layers, regenerated.suppressed_features, decisions,
                              regenerated.revision, regenerated.parent_revision, regenerated.edits)

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
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              self.hidden_layers, self.suppressed_features,
                              self.decisions + (decision,), self.revision,
                              self.parent_revision, self.edits)

    def to_dict(self) -> dict[str, object]:
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
            "base_concept": next((item.identity for item in self.concepts
                                   if item.objective == self.active.objective and "-r" not in item.identity),
                                  self.concepts[0].identity),
            "hidden_layers": sorted(self.hidden_layers),
            "suppressed_features": sorted(self.suppressed_features),
            "decisions": [decision.__dict__ for decision in self.decisions],
            "annotations": self.annotations.to_dict(),
            "validations": validations,
            "concept_corrections": {
                concept.identity: [correction.__dict__ for correction in concept.corrections]
                for concept in self.concepts if concept.corrections
            },
            "revision": self.revision,
            "parent_revision": self.parent_revision,
            "edits": [
                {"operation": edit.operation, "feature_identity": edit.feature_identity,
                 "values": dict(edit.values)} for edit in self.edits
            ],
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
            raw_edits = tuple(FeatureEdit(
                item["operation"], item["feature_identity"],
                tuple(sorted(item.get("values", {}).items())))
                for item in data.get("edits", ()))
            if raw_edits:
                project = project.with_concept(data.get("base_concept", project.active_concept))
                for edit in raw_edits:
                    project = project.edit_feature(edit.feature_identity, edit.operation,
                                                   **dict(edit.values))
            for identity, corrections in data.get("concept_corrections", {}).items():
                if identity not in {item.identity for item in project.concepts}:
                    for correction in corrections:
                        project = project.correct(
                            correction["key"], correction["value"], correction["reason"])
                    continue
                project = project.with_concept(identity)
                for correction in corrections:
                    project = project.correct(
                        correction["key"], correction["value"], correction["reason"])
            if raw_edits:
                project = replace(project, active_concept=data["active_concept"])
            else:
                project = project.with_concept(data["active_concept"])
            for layer in data.get("hidden_layers", []):
                if layer not in project.hidden_layers:
                    project = project.toggle_layer(layer)
            for feature in (() if raw_edits else data.get("suppressed_features", [])):
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
            return cls(project.product, project.annotations, project.concepts,
                       project.active_concept, project.hidden_layers,
                       project.suppressed_features, decisions,
                       int(data.get("revision", project.revision)),
                       data.get("parent_revision", project.parent_revision),
                       project.edits)
        except ProjectFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectFormatError(f"invalid FXD project: {exc}") from exc
