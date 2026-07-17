"""Application-grade OCP review operations behind the CAD-neutral boundary."""
from __future__ import annotations

import hashlib
import logging
import re

from .kernel import (
    KernelEdgeRecord,
    KernelOperationError,
    KernelTriangleMesh,
    OcpKernel as _BaseOcpKernel,
)


logger = logging.getLogger("fxd.review_kernel")


def zero_based_triangle(indices: tuple[int, int, int], vertex_count: int) -> tuple[int, int, int]:
    """Convert OCCT's one-based node numbers to validated Python indices."""
    converted = tuple(index - 1 for index in indices)
    if vertex_count <= 0 or any(index < 0 or index >= vertex_count for index in converted):
        raise KernelOperationError("tessellation triangle references an invalid vertex")
    return converted


def transformed_point(point: object, location: object) -> tuple[float, float, float]:
    """Return a geometric point in the placed shape's world coordinates."""
    placed = point.Transformed(location.Transformation())
    return tuple(round(float(value), 9) for value in (placed.X(), placed.Y(), placed.Z()))


def point_coordinates(point: object) -> tuple[float, float, float]:
    """Return a kernel point as deterministic millimetre coordinates."""
    return tuple(round(float(value), 9) for value in (point.X(), point.Y(), point.Z()))


def has_volumetric_overlap(volume_mm3: float, tolerance_mm: float) -> bool:
    """Distinguish true penetration from intentional touching contact."""
    if tolerance_mm < 0:
        raise KernelOperationError("intersection tolerance must be non-negative")
    return volume_mm3 > tolerance_mm ** 3


class OcpKernel(_BaseOcpKernel):
    """Hardened OCP adapter used by the application and public package API."""

    @staticmethod
    def _normalize_step(data: bytes) -> bytes:
        """Remove OCCT process-global metadata while preserving STEP geometry.

        OCCT increments the first identifier on
        ``NEXT_ASSEMBLY_USAGE_OCCURRENCE`` across writer instances. That value
        is occurrence metadata, not a geometry reference, and makes identical
        exports differ merely because another export happened earlier in the
        process. Renumber those labels deterministically by file order after
        the base timestamp/translator normalization.
        """
        normalized = _BaseOcpKernel._normalize_step(data)
        occurrence = 0
        pattern = re.compile(rb"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')\d+(')")

        def replace_occurrence(match: re.Match[bytes]) -> bytes:
            nonlocal occurrence
            occurrence += 1
            return match.group(1) + str(occurrence).encode("ascii") + match.group(2)

        return pattern.sub(replace_occurrence, normalized)

    def intersects(self, left: object, right: object, tolerance_mm: float = 1e-7) -> bool:
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        common = self.boolean("common", left, right)
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(common, props)
        return has_volumetric_overlap(float(props.Mass()), tolerance_mm)

    def tessellate(
        self,
        model: object,
        linear_deflection_mm: float = 0.1,
        angular_deflection_rad: float = 0.5,
    ) -> tuple[KernelTriangleMesh, ...]:
        from OCP.BRep import BRep_Tool
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopAbs import TopAbs_REVERSED

        if linear_deflection_mm <= 0 or angular_deflection_rad <= 0:
            raise KernelOperationError("tessellation tolerances must be positive")
        BRepMesh_IncrementalMesh(
            model, linear_deflection_mm, False, angular_deflection_rad, True
        )
        result: list[KernelTriangleMesh] = []
        faces = self._subshapes(model, "face")
        logger.info("STEP tessellation face_count=%d", len(faces))
        for face in faces:
            records = self.face_records(face)
            if len(records) != 1:
                raise KernelOperationError("OCCT face did not yield one stable face record")
            triangulation = BRep_Tool.Triangulation_s(face, face.Location())
            if triangulation is None:
                raise KernelOperationError("OCCT produced no tessellation for a face")
            location = face.Location()
            vertices = tuple(
                transformed_point(triangulation.Node(index), location)
                for index in range(1, triangulation.NbNodes() + 1)
            )
            triangles: list[tuple[int, int, int]] = []
            for index in range(1, triangulation.NbTriangles() + 1):
                triangle = triangulation.Triangle(index)
                values = zero_based_triangle(
                    (
                        int(triangle.Value(1)),
                        int(triangle.Value(2)),
                        int(triangle.Value(3)),
                    ),
                    len(vertices),
                )
                if face.Orientation() == TopAbs_REVERSED:
                    values = (values[0], values[2], values[1])
                triangles.append(values)
            result.append(KernelTriangleMesh(records[0].reference, vertices, tuple(triangles)))
        logger.info("STEP tessellation triangle_count=%d", sum(len(mesh.triangles) for mesh in result))
        return tuple(sorted(result, key=lambda mesh: mesh.face_reference))

    def edge_records(self, model: object) -> tuple[KernelEdgeRecord, ...]:
        from OCP.BRepAdaptor import BRepAdaptor_Curve

        records: list[KernelEdgeRecord] = []
        for edge in self._subshapes(model, "edge"):
            curve = BRepAdaptor_Curve(edge)
            first = float(curve.FirstParameter())
            last = float(curve.LastParameter())
            start = point_coordinates(curve.Value(first))
            end = point_coordinates(curve.Value(last))
            canonical = tuple(sorted((start, end)))
            token = hashlib.sha256(repr(canonical).encode()).hexdigest()[:24]
            records.append(KernelEdgeRecord("edge:" + token, start, end))
        return tuple(sorted(records, key=lambda item: item.reference))
