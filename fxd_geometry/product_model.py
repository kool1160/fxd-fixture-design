"""Immutable, CAD-neutral product model produced by STEP import."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Tuple

from .aabb import Aabb, Transform, Vec3


@dataclass(frozen=True)
class Edge:
    identity: str


@dataclass(frozen=True)
class Face:
    identity: str


@dataclass(frozen=True)
class Body:
    identity: str
    bounds: Aabb
    faces: Tuple[Face, ...] = ()
    edges: Tuple[Edge, ...] = ()


@dataclass(frozen=True)
class Component:
    identity: str
    name: str
    parent_identity: str | None
    transform: Transform
    bodies: Tuple[Body, ...]
    source_product_identity: str

    @property
    def bounds(self) -> Aabb:
        points = [body.bounds for body in self.bodies]
        if not points:
            raise ValueError(f"component {self.identity!r} has no bodies")
        return Aabb(
            Vec3(*(min(getattr(b.minimum, axis) for b in points) for axis in ("x", "y", "z"))),
            Vec3(*(max(getattr(b.maximum, axis) for b in points) for axis in ("x", "y", "z"))),
        ).transformed(self.transform)


@dataclass(frozen=True)
class ProductModel:
    units: str
    components: Tuple[Component, ...]
    source_name: str
    source_sha256: str
    source_bytes: bytes

    def __post_init__(self) -> None:
        if self.units != "mm":
            raise ValueError("normalized product models must use millimetres")
        if sha256(self.source_bytes).hexdigest() != self.source_sha256:
            raise ValueError("source bytes do not match source_sha256")

