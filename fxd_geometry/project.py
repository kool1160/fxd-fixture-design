"""Local, neutral FXD project persistence for the engineering review application."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from .annotations import EngineeringAnnotations
from .aabb import Vec3
from .concepts import CompleteFixtureConcept, FixtureCorrection, generate_fixture_concepts
from .product_model import ProductModel
from .step_import import import_step


class ProjectFormatError(ValueError):
    """Raised when a saved project is incomplete or incompatible."""


@dataclass(frozen=True)
class ReviewDecision:
    action: str
    target: str
    note: str


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

    @classmethod
    def from_product(cls, product: ProductModel, annotations: EngineeringAnnotations) -> "FxdProject":
        concepts = generate_fixture_concepts(product, annotations).concepts
        return cls(product, annotations, concepts, concepts[0].identity)

    @property
    def active(self) -> CompleteFixtureConcept:
        for concept in self.concepts:
            if concept.identity == self.active_concept:
                return concept
        raise ProjectFormatError(f"active concept {self.active_concept!r} is missing")

    def with_concept(self, identity: str) -> "FxdProject":
        if identity not in {concept.identity for concept in self.concepts}:
            raise ProjectFormatError(f"unknown concept {identity!r}")
        return self.__class__(self.product, self.annotations, self.concepts, identity,
                              self.hidden_layers, self.suppressed_features, self.decisions)

    def toggle_layer(self, layer: str) -> "FxdProject":
        hidden = set(self.hidden_layers)
        (hidden.remove(layer) if layer in hidden else hidden.add(layer))
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              frozenset(hidden), self.suppressed_features, self.decisions)

    def suppress(self, feature_id: str, note: str = "") -> "FxdProject":
        hidden = set(self.suppressed_features)
        action = "unsuppress" if feature_id in hidden else "suppress"
        if feature_id in hidden:
            hidden.remove(feature_id)
        else:
            hidden.add(feature_id)
        decisions = self.decisions + (ReviewDecision(action, feature_id, note),)
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              self.hidden_layers, frozenset(hidden), decisions)

    def correct(self, key: str, value: str, reason: str) -> "FxdProject":
        concept = self.active.with_correction(FixtureCorrection(key, value, reason))
        concepts = tuple(concept if item.identity == concept.identity else item for item in self.concepts)
        decisions = self.decisions + (ReviewDecision("correct", key, reason),)
        return self.__class__(self.product, self.annotations, concepts, self.active_concept,
                              self.hidden_layers, self.suppressed_features, decisions)

    def decide(self, action: str, note: str = "") -> "FxdProject":
        if action not in {"approve_for_review", "reject"}:
            raise ProjectFormatError("review action must be approve_for_review or reject")
        return self.__class__(self.product, self.annotations, self.concepts, self.active_concept,
                              self.hidden_layers, self.suppressed_features,
                              self.decisions + (ReviewDecision(action, self.active_concept, note),))

    def to_dict(self) -> dict[str, object]:
        return {
            "format": "fxd-neutral-project-v1", "units": "mm",
            "source_name": self.product.source_name,
            "source_sha256": self.product.source_sha256,
            "source_step_base64": base64.b64encode(self.product.source_bytes).decode("ascii"),
            "active_concept": self.active_concept,
            "hidden_layers": sorted(self.hidden_layers),
            "suppressed_features": sorted(self.suppressed_features),
            "decisions": [decision.__dict__ for decision in self.decisions],
            "annotations": {"process_type": self.annotations.process_type,
                            "production_quantity": self.annotations.production_quantity,
                            "build_orientation": self.annotations.build_orientation.__dict__,
                            "loading_direction": self.annotations.loading_direction.__dict__},
            "concept_corrections": {
                concept.identity: [correction.__dict__ for correction in concept.corrections]
                for concept in self.concepts if concept.corrections
            },
        }

    def save(self, destination: str | Path) -> Path:
        path = Path(destination)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

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
            saved_annotations = data.get("annotations", {})
            annotations = EngineeringAnnotations.for_product(
                product,
                build_orientation=Vec3(**saved_annotations.get("build_orientation", {"x": 0, "y": 0, "z": 1})),
                loading_direction=Vec3(**saved_annotations.get("loading_direction", {"x": 1, "y": 0, "z": 0})),
                process_type=saved_annotations.get("process_type", "manual MIG"),
                production_quantity=int(saved_annotations.get("production_quantity", 1)))
            project = cls.from_product(product, annotations)
            for identity, corrections in data.get("concept_corrections", {}).items():
                project = project.with_concept(identity)
                for correction in corrections:
                    project = project.correct(correction["key"], correction["value"], correction["reason"])
            for layer in data.get("hidden_layers", []):
                if layer not in project.hidden_layers:
                    project = project.toggle_layer(layer)
            for feature in data.get("suppressed_features", []):
                if feature not in project.suppressed_features:
                    project = project.suppress(feature)
            decisions = tuple(ReviewDecision(**item) for item in data.get("decisions", []))
            return cls(project.product, project.annotations, project.concepts,
                       data["active_concept"], project.hidden_layers,
                       project.suppressed_features, decisions)
        except ProjectFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectFormatError(f"invalid FXD project: {exc}") from exc
