"""Deterministic manufacturing-coordinate frames separate from immutable source CAD."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import math
import re
from typing import TYPE_CHECKING

from .aabb import Vec3
from .annotations import GeometryReference

if TYPE_CHECKING:
    from .workbench import WorkbenchDocument


ORIENTATION_SCHEMA = "fxd-manufacturing-orientation-v1"
_EPSILON = 1e-9


class ManufacturingOrientationError(ValueError):
    """Raised when manufacturing-coordinate evidence is incomplete or malformed."""


class OrientationMethod(str, Enum):
    AUTO_RECOMMEND = "auto_recommend"
    SELECT_PLANAR_FACE = "select_planar_face"
    SELECT_REFERENCE_PLANE = "select_reference_plane"
    SOURCE_ORIENTATION = "use_source_orientation"


class ReferencePlane(str, Enum):
    FRONT = "front_plane"
    TOP = "top_plane"
    RIGHT = "right_plane"
    SELECTED_PLANAR_FACE = "selected_planar_face"
    CUSTOM = "custom_plane"


def _dot(left: Vec3, right: Vec3) -> float:
    return left.x * right.x + left.y * right.y + left.z * right.z


def _cross(left: Vec3, right: Vec3) -> Vec3:
    return Vec3(
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    )


def _scale(value: Vec3, scalar: float) -> Vec3:
    return Vec3(value.x * scalar, value.y * scalar, value.z * scalar)


def _subtract(left: Vec3, right: Vec3) -> Vec3:
    return Vec3(left.x - right.x, left.y - right.y, left.z - right.z)


def _length(value: Vec3) -> float:
    return math.sqrt(_dot(value, value))


def _unit(value: Vec3, label: str) -> Vec3:
    length = _length(value)
    if not math.isfinite(length) or length <= _EPSILON:
        raise ManufacturingOrientationError(f"{label} must be a finite non-zero vector")
    return _scale(value, 1.0 / length)


def _matrix_product(left: tuple[float, ...], right: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        sum(left[row * 4 + item] * right[item * 4 + column] for item in range(4))
        for row in range(4) for column in range(4)
    )


def _axis_basis(normal: Vec3, rotation_degrees: float) -> tuple[Vec3, Vec3, Vec3]:
    z_axis = _unit(normal, "plane normal")
    candidates = (Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0))
    anchor = next((item for item in candidates if abs(_dot(item, z_axis)) < 0.9), None)
    if anchor is None:
        raise ManufacturingOrientationError("could not establish a manufacturing X axis")
    x_axis = _unit(_subtract(anchor, _scale(z_axis, _dot(anchor, z_axis))), "manufacturing X axis")
    y_axis = _unit(_cross(z_axis, x_axis), "manufacturing Y axis")
    radians = math.radians(rotation_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    rotated_x = _unit(_subtract(_scale(x_axis, cosine), _scale(y_axis, sine)), "rotated manufacturing X axis")
    rotated_y = _unit(_cross(z_axis, rotated_x), "rotated manufacturing Y axis")
    return rotated_x, rotated_y, z_axis


def _transform_matrices(origin: Vec3, normal: Vec3,
                        rotation_degrees: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    x_axis, y_axis, z_axis = _axis_basis(normal, rotation_degrees)
    source_to_manufacturing = (
        x_axis.x, x_axis.y, x_axis.z, -_dot(x_axis, origin),
        y_axis.x, y_axis.y, y_axis.z, -_dot(y_axis, origin),
        z_axis.x, z_axis.y, z_axis.z, -_dot(z_axis, origin),
        0.0, 0.0, 0.0, 1.0,
    )
    manufacturing_to_source = (
        x_axis.x, y_axis.x, z_axis.x, origin.x,
        x_axis.y, y_axis.y, z_axis.y, origin.y,
        x_axis.z, y_axis.z, z_axis.z, origin.z,
        0.0, 0.0, 0.0, 1.0,
    )
    return source_to_manufacturing, manufacturing_to_source


def _apply(matrix: tuple[float, ...], point: Vec3, *, vector: bool = False) -> Vec3:
    homogeneous = 0.0 if vector else 1.0
    return Vec3(
        matrix[0] * point.x + matrix[1] * point.y + matrix[2] * point.z + matrix[3] * homogeneous,
        matrix[4] * point.x + matrix[5] * point.y + matrix[6] * point.z + matrix[7] * homogeneous,
        matrix[8] * point.x + matrix[9] * point.y + matrix[10] * point.z + matrix[11] * homogeneous,
    )


@dataclass(frozen=True)
class CoordinateSystem:
    """Named right-handed source coordinate-system evidence in millimetres."""

    name: str
    origin_mm: Vec3
    x_axis: Vec3
    y_axis: Vec3
    z_axis: Vec3

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ManufacturingOrientationError("coordinate-system name is required")
        x_axis, y_axis, z_axis = (_unit(self.x_axis, "source X axis"),
                                  _unit(self.y_axis, "source Y axis"),
                                  _unit(self.z_axis, "source Z axis"))
        if any(abs(_dot(left, right)) > 1e-7 for left, right in (
            (x_axis, y_axis), (x_axis, z_axis), (y_axis, z_axis),
        )) or _dot(_cross(x_axis, y_axis), z_axis) < 1.0 - 1e-7:
            raise ManufacturingOrientationError("coordinate system must be right-handed and orthonormal")

    @classmethod
    def source(cls) -> "CoordinateSystem":
        return cls("Source CAD", Vec3(0.0, 0.0, 0.0),
                   Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0))

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name, "origin_mm": self.origin_mm.__dict__,
            "x_axis": self.x_axis.__dict__, "y_axis": self.y_axis.__dict__,
            "z_axis": self.z_axis.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CoordinateSystem":
        return cls(str(data["name"]), Vec3(**data["origin_mm"]), Vec3(**data["x_axis"]),
                   Vec3(**data["y_axis"]), Vec3(**data["z_axis"]))


@dataclass(frozen=True)
class ManufacturingOrientation:
    """Accepted or draft mapping from immutable source coordinates to manufacturing coordinates."""

    source_sha256: str
    method: OrientationMethod
    reference_plane: ReferencePlane
    selected_reference: GeometryReference | None
    plane_origin_mm: Vec3
    plane_normal_source: Vec3
    flip_normal: bool
    rotation_degrees: float
    source_coordinate_system: CoordinateSystem
    source_to_manufacturing: tuple[float, ...]
    manufacturing_to_source: tuple[float, ...]
    accepted: bool = False
    explanation: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    schema_version: str = ORIENTATION_SCHEMA

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ManufacturingOrientationError("orientation requires a SHA-256 source identity")
        if not isinstance(self.method, OrientationMethod) or not isinstance(self.reference_plane, ReferencePlane):
            raise ManufacturingOrientationError("orientation method and reference plane must be supported")
        if self.reference_plane == ReferencePlane.SELECTED_PLANAR_FACE and (
                self.selected_reference is None or not self.selected_reference.face_identity):
            raise ManufacturingOrientationError("a selected planar face requires an exact face reference")
        if self.selected_reference is not None and not self.selected_reference.face_identity:
            raise ManufacturingOrientationError("orientation face reference must identify an exact face")
        _unit(self.plane_normal_source, "plane normal")
        if not math.isfinite(self.rotation_degrees):
            raise ManufacturingOrientationError("rotation about build normal must be finite")
        if self.schema_version != ORIENTATION_SCHEMA:
            raise ManufacturingOrientationError("unsupported manufacturing orientation schema")
        for matrix, label in ((self.source_to_manufacturing, "source-to-manufacturing"),
                              (self.manufacturing_to_source, "manufacturing-to-source")):
            if len(matrix) != 16 or not all(math.isfinite(value) for value in matrix):
                raise ManufacturingOrientationError(f"{label} transform must contain 16 finite values")
        product = _matrix_product(self.source_to_manufacturing, self.manufacturing_to_source)
        expected = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        if any(abs(actual - target) > 1e-7 for actual, target in zip(product, expected)):
            raise ManufacturingOrientationError("orientation transforms are not inverses")

    @property
    def effective_normal_source(self) -> Vec3:
        normal = _unit(self.plane_normal_source, "plane normal")
        return _scale(normal, -1.0) if self.flip_normal else normal

    @property
    def manufacturing_x_source(self) -> Vec3:
        return _unit(_apply(self.manufacturing_to_source, Vec3(1.0, 0.0, 0.0), vector=True), "manufacturing X axis")

    @property
    def manufacturing_y_source(self) -> Vec3:
        return _unit(_apply(self.manufacturing_to_source, Vec3(0.0, 1.0, 0.0), vector=True), "manufacturing Y axis")

    @property
    def manufacturing_z_source(self) -> Vec3:
        return _unit(_apply(self.manufacturing_to_source, Vec3(0.0, 0.0, 1.0), vector=True), "manufacturing Z axis")

    @property
    def identity(self) -> str:
        payload = repr((self.source_sha256, self.method.value, self.reference_plane.value,
                        self.selected_reference, self.plane_origin_mm, self.plane_normal_source,
                        self.flip_normal, self.rotation_degrees, self.source_to_manufacturing,
                        self.manufacturing_to_source, self.accepted, self.explanation, self.evidence)).encode()
        return "orientation-" + sha256(payload).hexdigest()[:16]

    def is_stale_for(self, source_sha256: str) -> bool:
        return self.source_sha256 != source_sha256

    def require_accepted_for(self, source_sha256: str) -> None:
        if self.is_stale_for(source_sha256):
            raise ManufacturingOrientationError("manufacturing orientation belongs to a different source SHA-256")
        if not self.accepted:
            raise ManufacturingOrientationError("engineering analysis requires an accepted manufacturing orientation")

    def source_point_to_manufacturing(self, point: Vec3) -> Vec3:
        return _apply(self.source_to_manufacturing, point)

    def manufacturing_point_to_source(self, point: Vec3) -> Vec3:
        return _apply(self.manufacturing_to_source, point)

    def source_vector_to_manufacturing(self, vector: Vec3) -> Vec3:
        return _apply(self.source_to_manufacturing, vector, vector=True)

    def manufacturing_vector_to_source(self, vector: Vec3) -> Vec3:
        return _apply(self.manufacturing_to_source, vector, vector=True)

    def with_acceptance(self, accepted: bool) -> "ManufacturingOrientation":
        return ManufacturingOrientation(
            self.source_sha256, self.method, self.reference_plane, self.selected_reference,
            self.plane_origin_mm, self.plane_normal_source, self.flip_normal, self.rotation_degrees,
            self.source_coordinate_system, self.source_to_manufacturing, self.manufacturing_to_source,
            accepted, self.explanation, self.evidence, self.schema_version,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256, "method": self.method.value,
            "reference_plane": self.reference_plane.value,
            "selected_reference": self.selected_reference.__dict__ if self.selected_reference else None,
            "plane_origin_mm": self.plane_origin_mm.__dict__,
            "plane_normal_source": self.plane_normal_source.__dict__, "flip_normal": self.flip_normal,
            "rotation_degrees": self.rotation_degrees,
            "source_coordinate_system": self.source_coordinate_system.to_dict(),
            "source_to_manufacturing": list(self.source_to_manufacturing),
            "manufacturing_to_source": list(self.manufacturing_to_source),
            "accepted": self.accepted, "explanation": list(self.explanation),
            "evidence": list(self.evidence), "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ManufacturingOrientation":
        reference = data.get("selected_reference")
        return cls(
            str(data["source_sha256"]), OrientationMethod(data["method"]),
            ReferencePlane(data["reference_plane"]), GeometryReference(**reference) if reference else None,
            Vec3(**data["plane_origin_mm"]), Vec3(**data["plane_normal_source"]),
            bool(data.get("flip_normal", False)), float(data.get("rotation_degrees", 0.0)),
            CoordinateSystem.from_dict(data["source_coordinate_system"]),
            tuple(float(value) for value in data["source_to_manufacturing"]),
            tuple(float(value) for value in data["manufacturing_to_source"]),
            bool(data.get("accepted", False)), tuple(data.get("explanation", ())),
            tuple(data.get("evidence", ())), str(data.get("schema_version", ORIENTATION_SCHEMA)),
        )


@dataclass(frozen=True)
class OrientationRecommendation:
    """Explainable candidate; ranking never grants engineer acceptance."""

    orientation: ManufacturingOrientation
    score: float
    reasons: tuple[str, ...]
    assumptions: tuple[str, ...]


def orientation_from_plane(*, source_sha256: str, method: OrientationMethod,
                           reference_plane: ReferencePlane, plane_origin_mm: Vec3,
                           plane_normal_source: Vec3,
                           selected_reference: GeometryReference | None = None,
                           flip_normal: bool = False, rotation_degrees: float = 0.0,
                           accepted: bool = False, explanation: tuple[str, ...] = (),
                           evidence: tuple[str, ...] = ()) -> ManufacturingOrientation:
    effective_normal = _scale(_unit(plane_normal_source, "plane normal"), -1.0 if flip_normal else 1.0)
    source_to_manufacturing, manufacturing_to_source = _transform_matrices(
        plane_origin_mm, effective_normal, rotation_degrees,
    )
    return ManufacturingOrientation(
        source_sha256, method, reference_plane, selected_reference, plane_origin_mm,
        plane_normal_source, flip_normal, rotation_degrees, CoordinateSystem.source(),
        source_to_manufacturing, manufacturing_to_source, accepted, explanation, evidence,
    )


def source_orientation(source_sha256: str, *, accepted: bool = False) -> ManufacturingOrientation:
    """Return the neutral source-frame option; acceptance remains explicit."""
    return orientation_from_plane(
        source_sha256=source_sha256, method=OrientationMethod.SOURCE_ORIENTATION,
        reference_plane=ReferencePlane.TOP, plane_origin_mm=Vec3(0.0, 0.0, 0.0),
        plane_normal_source=Vec3(0.0, 0.0, 1.0), accepted=accepted,
        explanation=(
            "Source orientation is preserved as a separate manufacturing-frame proposal.",
            "Engineer acceptance is required; source STEP coordinates are not manufacturing truth by default.",
        ), evidence=("reference_plane=source_xy", "source_axes=right_handed"),
    )


def reference_plane_orientation(source_sha256: str, reference_plane: ReferencePlane, *,
                                custom_origin_mm: Vec3 | None = None,
                                custom_normal_source: Vec3 | None = None,
                                flip_normal: bool = False,
                                rotation_degrees: float = 0.0,
                                accepted: bool = False) -> ManufacturingOrientation:
    """Create a familiar CAD-plane proposal without moving source geometry."""
    planes = {
        ReferencePlane.FRONT: (Vec3(0.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), "Front Plane (source XZ, normal +Y)"),
        ReferencePlane.TOP: (Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0), "Top Plane (source XY, normal +Z)"),
        ReferencePlane.RIGHT: (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), "Right Plane (source YZ, normal +X)"),
    }
    if reference_plane == ReferencePlane.CUSTOM:
        if custom_origin_mm is None or custom_normal_source is None:
            raise ManufacturingOrientationError("custom plane requires explicit origin and normal")
        origin, normal, label = custom_origin_mm, custom_normal_source, "Custom plane"
    elif reference_plane in planes:
        origin, normal, label = planes[reference_plane]
    else:
        raise ManufacturingOrientationError("reference-plane orientation requires Front, Top, Right, or Custom")
    return orientation_from_plane(
        source_sha256=source_sha256, method=OrientationMethod.SELECT_REFERENCE_PLANE,
        reference_plane=reference_plane, plane_origin_mm=origin, plane_normal_source=normal,
        flip_normal=flip_normal, rotation_degrees=rotation_degrees, accepted=accepted,
        explanation=(
            f"Manufacturing build plane uses {label}.",
            "The transform is stored separately from immutable source coordinates.",
        ), evidence=(f"reference_plane={reference_plane.value}",),
    )


def orientation_from_face(document: "WorkbenchDocument", reference: GeometryReference, *,
                          method: OrientationMethod = OrientationMethod.SELECT_PLANAR_FACE,
                          flip_normal: bool = False, rotation_degrees: float = 0.0,
                          accepted: bool = False) -> ManufacturingOrientation:
    """Bind a manufacturing frame to exact OCP planar-face evidence or fail closed."""
    if not reference.face_identity:
        raise ManufacturingOrientationError("select an exact planar face before defining manufacturing orientation")
    face = next((face for component in document.assembly.components
                 if component.reference == reference.component_identity
                 for face in component.faces if face.reference == reference.face_identity), None)
    if face is None:
        raise ManufacturingOrientationError("selected face is not mapped to imported OCP assembly evidence")
    if not face.is_planar:
        raise ManufacturingOrientationError("selected face is not confirmed planar by OCP surface evidence")
    return orientation_from_plane(
        source_sha256=document.source_sha256, method=method,
        reference_plane=ReferencePlane.SELECTED_PLANAR_FACE,
        selected_reference=reference, plane_origin_mm=Vec3(*face.center_mm),
        plane_normal_source=Vec3(*face.normal), flip_normal=flip_normal,
        rotation_degrees=rotation_degrees, accepted=accepted,
        explanation=(
            f"Build-down reference is exact OCP face {face.reference}.",
            "Support and gravity axes are derived from its confirmed planar normal.",
            "Source STEP geometry and coordinates remain unchanged.",
        ), evidence=(
            f"ocp_face={face.reference}", f"area_mm2={face.area_mm2}",
            f"normal={face.normal}", "surface_type=plane",
        ),
    )


def recommend_orientations(document: "WorkbenchDocument") -> tuple[OrientationRecommendation, ...]:
    """Rank confirmed planar-face candidates with explicit limits on available evidence."""
    faces = tuple(
        (component, face) for component in document.assembly.components
        for face in component.faces if face.is_planar
    )
    if not faces:
        return ()
    maximum_area = max(face.area_mm2 for _, face in faces)
    vertices = tuple(point for mesh in document.meshes for point in mesh.vertices_mm)
    if not vertices:
        raise ManufacturingOrientationError("source model has no tessellation evidence for orientation ranking")
    bounds_min = Vec3(*(min(point[index] for point in vertices) for index in range(3)))
    bounds_max = Vec3(*(max(point[index] for point in vertices) for index in range(3)))
    center = _scale(Vec3(bounds_min.x + bounds_max.x, bounds_min.y + bounds_max.y,
                         bounds_min.z + bounds_max.z), 0.5)
    span = max(bounds_max.x - bounds_min.x, bounds_max.y - bounds_min.y, bounds_max.z - bounds_min.z, 1.0)
    result: list[OrientationRecommendation] = []
    for component, face in faces:
        normal = Vec3(*face.normal)
        face_center = Vec3(*face.center_mm)
        area_score = face.area_mm2 / maximum_area
        center_offset = _subtract(center, face_center)
        projection_direction = _dot(center_offset, _unit(normal, "face normal"))
        projection = abs(projection_direction) / span
        cog_score = max(0.0, 1.0 - projection)
        stability = 0.65 * area_score + 0.35 * cog_score
        score = round(100.0 * stability, 6)
        reference = GeometryReference(component.reference, "body:" + sha256(component.reference.encode()).hexdigest()[:20], face.reference)
        orientation = orientation_from_face(
            document, reference, method=OrientationMethod.AUTO_RECOMMEND,
            flip_normal=projection_direction < 0.0,
        )
        reasons = (
            f"Confirmed planar support area: {face.area_mm2:.3f} mm^2.",
            f"Approximate bounding-box center projection score: {cog_score:.3f}.",
            "Build normal is oriented toward the approximate product center; gravity points toward the selected build plane.",
            "Weld access, clamp access, load/unload practicality, trapped-part risk, and distortion are not scored until explicit annotations and envelopes exist.",
        )
        result.append(OrientationRecommendation(
            orientation, score, reasons,
            ("Center of gravity is approximated from tessellated bounding-box extent, not mass properties.",
             "Ranking is a proposal only and requires engineer acceptance."),
        ))
    return tuple(sorted(result, key=lambda item: (-item.score, item.orientation.selected_reference.face_identity
                                                    if item.orientation.selected_reference else "")))
