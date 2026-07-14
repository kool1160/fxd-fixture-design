"""Deterministic locating and six-degree-of-freedom analysis.

The solver consumes explicit contact evidence.  It never infers a contact
normal from an AABB, and it never treats a clamp as a locator.  A contact
contributes rigid-body constraint rows ``[direction, point x direction]``;
rank and incremental rank are then used to report controlled, redundant, and
missing degrees of freedom.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .aabb import Vec3
from .annotations import GeometryReference
from .product_model import ProductModel

_ROLES = {"rest", "support", "stop", "round_pin", "diamond_pin", "clamp"}
_EPS = 1.0e-9


class ConstraintAnalysisError(ValueError):
    """Raised when locating analysis input is not explicit or well formed."""


@dataclass(frozen=True)
class LocatorContact:
    identity: str
    role: str
    reference: GeometryReference
    point_mm: Vec3
    normal: Vec3
    constrained_directions: tuple[Vec3, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise ConstraintAnalysisError("locator identity must be non-empty")
        if self.role not in _ROLES:
            raise ConstraintAnalysisError(f"unsupported locator role: {self.role!r}")
        values = (*self.point_mm.__dict__.values(), *self.normal.__dict__.values())
        if not all(math.isfinite(value) for value in values):
            raise ConstraintAnalysisError("locator point and normal must be finite")
        if self.normal == Vec3(0.0, 0.0, 0.0):
            raise ConstraintAnalysisError("locator normal must not be zero")
        if self.role == "clamp" and self.constrained_directions:
            raise ConstraintAnalysisError("clamps cannot provide locating constraints")


@dataclass(frozen=True)
class LocatingStrategy:
    contacts: tuple[LocatorContact, ...]
    tolerance_mm: float | None = None
    repeatability_mm: float | None = None
    datum_assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (("tolerance_mm", self.tolerance_mm),
                             ("repeatability_mm", self.repeatability_mm)):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ConstraintAnalysisError(f"{label} must be finite and non-negative")
        if len({item.identity for item in self.contacts}) != len(self.contacts):
            raise ConstraintAnalysisError("locator identities must be unique")


@dataclass(frozen=True)
class ConstraintFinding:
    code: str
    severity: str
    locator_identity: str | None
    message: str


@dataclass(frozen=True)
class LocatingAnalysis:
    rank: int
    controlled_dofs: tuple[str, ...]
    uncontrolled_dofs: tuple[str, ...]
    redundant_locators: tuple[str, ...]
    strategy_valid: bool
    findings: tuple[ConstraintFinding, ...]
    tolerance_mm: float | None
    repeatability_mm: float | None
    datum_assumptions: tuple[str, ...]


def _norm(vector: Vec3) -> tuple[float, float, float]:
    length = math.sqrt(sum(value * value for value in vector.__dict__.values()))
    return tuple(value / length for value in vector.__dict__.values())


def _cross(left: tuple[float, ...], right: tuple[float, ...]) -> tuple[float, float, float]:
    return (left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0])


def _row(contact: LocatorContact, direction: Vec3) -> tuple[float, ...]:
    vector = _norm(direction)
    point = tuple(contact.point_mm.__dict__.values())
    return vector + _cross(point, vector)


def _rank(rows: list[tuple[float, ...]]) -> int:
    matrix = [list(row) for row in rows]
    rank = 0
    for column in range(6):
        pivot = next((index for index in range(rank, len(matrix))
                      if abs(matrix[index][column]) > _EPS), None)
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        scale = matrix[rank][column]
        matrix[rank] = [value / scale for value in matrix[rank]]
        for index in range(len(matrix)):
            if index != rank and abs(matrix[index][column]) > _EPS:
                factor = matrix[index][column]
                matrix[index] = [a - factor * b for a, b in zip(matrix[index], matrix[rank])]
        rank += 1
    return rank


def _directions(contact: LocatorContact) -> tuple[Vec3, ...]:
    if contact.constrained_directions:
        return contact.constrained_directions
    if contact.role in {"clamp"}:
        return ()
    if contact.role in {"round_pin"}:
        axis = _norm(contact.normal)
        seed = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
        first = _cross(axis, seed)
        return (Vec3(*first), Vec3(*_cross(axis, first)))
    return (contact.normal,)


def analyze_locating_strategy(product: ProductModel, strategy: LocatingStrategy) -> LocatingAnalysis:
    """Validate contacts and calculate deterministic rigid-body constraint rank."""
    components = {component.identity: component for component in product.components}
    findings: list[ConstraintFinding] = []
    rows: list[tuple[float, ...]] = []
    redundant: list[str] = []
    for contact in strategy.contacts:
        component = components.get(contact.reference.component_identity)
        if component is None:
            findings.append(ConstraintFinding("invalid_reference", "error", contact.identity,
                                              "locator references an unknown component"))
            continue
        bodies = {body.identity: body for body in component.bodies}
        body = bodies.get(contact.reference.body_identity) if contact.reference.body_identity else None
        if contact.reference.body_identity and body is None:
            findings.append(ConstraintFinding("invalid_reference", "error", contact.identity,
                                              "locator references an unknown body"))
            continue
        if contact.reference.face_identity and (body is None or contact.reference.face_identity not in
                                                {face.identity for face in body.faces}):
            findings.append(ConstraintFinding("invalid_reference", "error", contact.identity,
                                              "locator references an unknown face"))
            continue
        if contact.role == "clamp":
            findings.append(ConstraintFinding("clamp_excluded", "info", contact.identity,
                                              "clamps apply force but do not establish locating DOF"))
            continue
        previous = len(rows)
        for direction in _directions(contact):
            if direction == Vec3(0.0, 0.0, 0.0):
                findings.append(ConstraintFinding("invalid_contact_normal", "error", contact.identity,
                                                  "constrained direction must not be zero"))
                continue
            rows.append(_row(contact, direction))
        if _rank(rows) == _rank(rows[:previous]) and previous != len(rows):
            redundant.append(contact.identity)
            findings.append(ConstraintFinding("redundant_constraint", "error", contact.identity,
                                              "locator adds no independent rigid-body constraint"))
    rank = _rank(rows)
    names = ("tx", "ty", "tz", "rx", "ry", "rz")
    # Rank identifies independent constraints; the exact individual DOF basis
    # is not unique, so report the conservative count plus stable labels.
    controlled = names[:rank]
    uncontrolled = names[rank:]
    if rank < 6:
        findings.append(ConstraintFinding("underconstrained", "error", None,
                                          f"locating strategy controls {rank} of 6 rigid-body DOF"))
    if rank == 6 and not strategy.datum_assumptions:
        findings.append(ConstraintFinding("missing_datum_assumptions", "warning", None,
                                          "full rank is shown, but datum assumptions are not recorded"))
    valid = not any(item.severity == "error" for item in findings)
    return LocatingAnalysis(rank, controlled, uncontrolled, tuple(redundant), valid,
                            tuple(findings), strategy.tolerance_mm, strategy.repeatability_mm,
                            strategy.datum_assumptions)
