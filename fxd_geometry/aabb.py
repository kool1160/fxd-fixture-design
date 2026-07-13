"""Dependency-free axis-aligned geometry for a runnable architecture proof.

This module deliberately is not a CAD kernel. It supplies a deterministic test
double for the neutral domain boundary until a licensed B-rep kernel is selected.
All values are millimetres and all transforms are translations for this spike.
"""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)


@dataclass(frozen=True)
class Transform:
    """Neutral placement contract for the baseline (translation-only spike)."""

    translation: Vec3 = Vec3(0.0, 0.0, 0.0)

    def apply(self, point: Vec3) -> Vec3:
        return point + self.translation


@dataclass(frozen=True)
class Aabb:
    minimum: Vec3
    maximum: Vec3

    @classmethod
    def from_values(cls, xmin: float, ymin: float, zmin: float,
                    xmax: float, ymax: float, zmax: float) -> "Aabb":
        return cls(Vec3(xmin, ymin, zmin), Vec3(xmax, ymax, zmax))

    def __post_init__(self) -> None:
        if any(a > b for a, b in zip(self.minimum.__dict__.values(), self.maximum.__dict__.values())):
            raise ValueError("AABB minimum must not exceed maximum")

    def transformed(self, transform: Transform) -> "Aabb":
        return Aabb(transform.apply(self.minimum), transform.apply(self.maximum))

    def intersects(self, other: "Aabb", clearance: float = 0.0) -> bool:
        return all(
            a_min < b_max + clearance and b_min < a_max + clearance
            for a_min, a_max, b_min, b_max in zip(
                self.minimum.__dict__.values(), self.maximum.__dict__.values(),
                other.minimum.__dict__.values(), other.maximum.__dict__.values(),
            )
        )

    def clearance_to(self, other: "Aabb") -> float:
        gaps = [
            max(other_min - self_max, self_min - other_max, 0.0)
            for self_min, self_max, other_min, other_max in zip(
                self.minimum.__dict__.values(), self.maximum.__dict__.values(),
                other.minimum.__dict__.values(), other.maximum.__dict__.values(),
            )
        ]
        return max(gaps)

    def intersection(self, other: "Aabb") -> "Aabb | None":
        if not self.intersects(other):
            return None
        return Aabb(
            Vec3(*(max(a, b) for a, b in zip(self.minimum.__dict__.values(), other.minimum.__dict__.values()))),
            Vec3(*(min(a, b) for a, b in zip(self.maximum.__dict__.values(), other.maximum.__dict__.values()))),
        )

    def as_dict(self) -> dict[str, object]:
        return {"minimum": self.minimum.__dict__, "maximum": self.maximum.__dict__, "units": "mm"}


@dataclass(frozen=True)
class Box:
    size: Vec3
    placement: Transform = Transform()

    def bounds(self) -> Aabb:
        return Aabb(Vec3(0.0, 0.0, 0.0), self.size).transformed(self.placement)


def neutral_export(boxes: list[Box]) -> str:
    """Serialize synthetic geometry through a vendor-neutral JSON contract."""
    return json.dumps({"format": "fxd-neutral-proof-v1", "units": "mm", "boxes": [box.bounds().as_dict() for box in boxes]}, sort_keys=True)
