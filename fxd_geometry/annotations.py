"""CAD-neutral engineering intent stored separately from imported geometry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
from typing import Iterable

from .aabb import Vec3
from .product_model import ProductModel


class AnnotationError(ValueError):
    """Raised when annotation data is incomplete or references unknown geometry."""


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnnotationError(f"{label} must be a non-empty string")
    return value.strip()


def _vector(value: Vec3, label: str, *, nonzero: bool = True) -> Vec3:
    if not isinstance(value, Vec3) or not all(math.isfinite(v) for v in (value.x, value.y, value.z)):
        raise AnnotationError(f"{label} must be a finite Vec3")
    if nonzero and value == Vec3(0.0, 0.0, 0.0):
        raise AnnotationError(f"{label} must not be zero")
    return value


@dataclass(frozen=True)
class GeometryReference:
    """Stable reference into ProductModel; it never stores generated geometry."""

    component_identity: str
    body_identity: str | None = None
    face_identity: str | None = None
    edge_identity: str | None = None

    def __post_init__(self) -> None:
        _text(self.component_identity, "component_identity")
        if self.face_identity and not self.body_identity:
            raise AnnotationError("face_identity requires body_identity")
        if self.edge_identity and not self.body_identity:
            raise AnnotationError("edge_identity requires body_identity")


@dataclass(frozen=True)
class CriticalCharacteristic:
    name: str
    references: tuple[GeometryReference, ...] = ()
    nominal_value: float | None = None
    units: str | None = None
    tolerance: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _text(self.name, "critical characteristic name")
        if self.nominal_value is not None and not math.isfinite(self.nominal_value):
            raise AnnotationError("nominal_value must be finite")
        if self.tolerance is not None and (not math.isfinite(self.tolerance) or self.tolerance < 0):
            raise AnnotationError("tolerance must be finite and non-negative")
        if self.nominal_value is not None:
            _text(self.units or "", "critical characteristic units")


@dataclass(frozen=True)
class WeldJoint:
    identity: str
    references: tuple[GeometryReference, ...] = ()
    process: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _text(self.identity, "weld joint identity")
        if self.process:
            _text(self.process, "weld joint process")


@dataclass(frozen=True)
class Assumption:
    key: str
    value: str
    rationale: str = ""

    def __post_init__(self) -> None:
        _text(self.key, "assumption key")
        _text(self.value, "assumption value")


@dataclass(frozen=True)
class EngineeringAnnotations:
    """Editable annotation document bound to one immutable imported product."""

    source_sha256: str
    source_name: str
    build_orientation: Vec3
    loading_direction: Vec3
    process_type: str
    production_quantity: int
    critical_characteristics: tuple[CriticalCharacteristic, ...] = ()
    permitted_locating_surfaces: tuple[GeometryReference, ...] = ()
    forbidden_contact_areas: tuple[GeometryReference, ...] = ()
    weld_joints: tuple[WeldJoint, ...] = ()
    shop_constraints: tuple[str, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    schema_version: str = "fxd-annotations-v1"

    def __post_init__(self) -> None:
        _text(self.source_sha256, "source_sha256")
        _text(self.source_name, "source_name")
        _vector(self.build_orientation, "build_orientation")
        _vector(self.loading_direction, "loading_direction")
        _text(self.process_type, "process_type")
        if not isinstance(self.production_quantity, int) or isinstance(self.production_quantity, bool) or self.production_quantity < 1:
            raise AnnotationError("production_quantity must be a positive integer")
        if len({item.key for item in self.assumptions}) != len(self.assumptions):
            raise AnnotationError("assumption keys must be unique")

    @classmethod
    def for_product(cls, product: ProductModel, *, build_orientation: Vec3, loading_direction: Vec3,
                    process_type: str, production_quantity: int) -> "EngineeringAnnotations":
        return cls(product.source_sha256, product.source_name, build_orientation, loading_direction,
                   process_type, production_quantity)

    def with_assumption(self, assumption: Assumption) -> "EngineeringAnnotations":
        """Return an edited copy while keeping assumptions visible in the document."""
        remaining = tuple(item for item in self.assumptions if item.key != assumption.key)
        return replace(self, assumptions=remaining + (assumption,))

    def validate_references(self, product: ProductModel) -> None:
        if product.source_sha256 != self.source_sha256:
            raise AnnotationError("annotations belong to a different source geometry")
        components = {component.identity: component for component in product.components}
        refs: Iterable[GeometryReference] = (
            list(self.permitted_locating_surfaces) + list(self.forbidden_contact_areas)
            + [ref for item in self.critical_characteristics for ref in item.references]
            + [ref for item in self.weld_joints for ref in item.references]
        )
        for ref in refs:
            component = components.get(ref.component_identity)
            if component is None:
                raise AnnotationError(f"unknown component reference {ref.component_identity!r}")
            if ref.body_identity:
                bodies = {body.identity: body for body in component.bodies}
                body = bodies.get(ref.body_identity)
                if body is None:
                    raise AnnotationError(f"unknown body reference {ref.body_identity!r}")
                if ref.face_identity and ref.face_identity not in {face.identity for face in body.faces}:
                    raise AnnotationError(f"unknown face reference {ref.face_identity!r}")
                if ref.edge_identity and ref.edge_identity not in {edge.identity for edge in body.edges}:
                    raise AnnotationError(f"unknown edge reference {ref.edge_identity!r}")

    def to_dict(self) -> dict[str, object]:
        def convert(value: object) -> object:
            if isinstance(value, Vec3):
                return asdict(value)
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            if isinstance(value, GeometryReference):
                return asdict(value)
            if isinstance(value, (CriticalCharacteristic, WeldJoint, Assumption)):
                return {key: convert(item) for key, item in asdict(value).items()}
            return value
        return {key: convert(value) for key, value in asdict(self).items()}

    def save(self, path: str | Path, product: ProductModel) -> None:
        self.validate_references(product)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, product: ProductModel) -> "EngineeringAnnotations":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        def ref(value: dict[str, object]) -> GeometryReference:
            return GeometryReference(**value)
        result = cls(
            source_sha256=data["source_sha256"], source_name=data["source_name"],
            build_orientation=Vec3(**data["build_orientation"]), loading_direction=Vec3(**data["loading_direction"]),
            process_type=data["process_type"], production_quantity=data["production_quantity"],
            critical_characteristics=tuple(CriticalCharacteristic(item["name"], tuple(ref(x) for x in item["references"]), item["nominal_value"], item["units"], item["tolerance"], item["notes"]) for item in data["critical_characteristics"]),
            permitted_locating_surfaces=tuple(ref(x) for x in data["permitted_locating_surfaces"]),
            forbidden_contact_areas=tuple(ref(x) for x in data["forbidden_contact_areas"]),
            weld_joints=tuple(WeldJoint(item["identity"], tuple(ref(x) for x in item["references"]), item["process"], item["notes"]) for item in data["weld_joints"]),
            shop_constraints=tuple(data["shop_constraints"]),
            assumptions=tuple(Assumption(**item) for item in data["assumptions"]),
            schema_version=data.get("schema_version", "fxd-annotations-v1"),
        )
        result.validate_references(product)
        return result
