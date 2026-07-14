"""CAD-neutral boundary and reviewed OCP implementation for real B-Rep geometry."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.util import find_spec
from pathlib import Path
import re
import tempfile
from typing import Protocol


class KernelUnavailable(RuntimeError):
    """Raised when the reviewed B-Rep backend is unavailable or incomplete."""


class KernelOperationError(RuntimeError):
    """Raised when a real geometry operation fails explicitly."""


@dataclass(frozen=True)
class KernelCapabilities:
    backend: str
    version: str
    step_import: bool
    topology: bool
    transforms: bool
    booleans: bool
    distance_and_clearance: bool
    neutral_export: bool

    @property
    def is_complete(self) -> bool:
        return all((self.step_import, self.topology, self.transforms,
                    self.booleans, self.distance_and_clearance,
                    self.neutral_export))


@dataclass(frozen=True)
class TopologyCounts:
    solids: int
    shells: int
    faces: int
    edges: int


@dataclass(frozen=True)
class KernelFace:
    """Stable, neutral face metadata. No OCP object crosses this boundary."""

    reference: str
    area_mm2: float
    center_mm: tuple[float, float, float]
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class KernelComponent:
    """A neutral component extracted from a STEP assembly/compound."""

    reference: str
    parent_reference: str
    transform: tuple[float, ...]
    topology: TopologyCounts
    faces: tuple[KernelFace, ...]


@dataclass(frozen=True)
class KernelAssembly:
    root_reference: str
    source_sha256: str
    units: str
    components: tuple[KernelComponent, ...]


class RealKernel(Protocol):
    @property
    def capabilities(self) -> KernelCapabilities: ...

    def import_step(self, source: str | bytes | Path) -> object: ...
    def import_step_assembly(self, source: str | bytes | Path) -> KernelAssembly: ...
    def export_step(self, model: object) -> bytes: ...
    def boolean(self, operation: str, left: object, right: object) -> object: ...
    def clearance(self, left: object, right: object) -> float: ...
    def topology_counts(self, model: object) -> TopologyCounts: ...
    def face_records(self, model: object) -> tuple[KernelFace, ...]: ...


class OcpKernel:
    """Reviewed adapter for cadquery-ocp 7.9.3.1.1 / OCCT 7.9.3."""

    PINNED_DISTRIBUTION = "cadquery-ocp==7.9.3.1.1"

    def __init__(self) -> None:
        try:
            import OCP
        except ImportError as exc:
            raise KernelUnavailable(
                f"{self.PINNED_DISTRIBUTION} is required for real geometry"
            ) from exc
        version = getattr(OCP, "__version__", "unknown")
        if not str(version).startswith("7.9.3.1"):
            raise KernelUnavailable(
                f"unsupported OCP runtime {version!r}; expected {self.PINNED_DISTRIBUTION}"
            )
        self._version = str(version)

    @property
    def capabilities(self) -> KernelCapabilities:
        return KernelCapabilities("cadquery-ocp", self._version, True, True,
                                  True, True, True, True)

    @staticmethod
    def _source_bytes(source: str | bytes | Path) -> bytes:
        if isinstance(source, bytes):
            return source
        path = Path(source)
        if not path.is_file():
            raise KernelOperationError(f"STEP source does not exist: {path}")
        return path.read_bytes()

    def import_step(self, source: str | bytes | Path) -> object:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader

        source_bytes = self._source_bytes(source)
        if b"ISO-10303-21" not in source_bytes or b"END-ISO-10303-21" not in source_bytes:
            raise KernelOperationError("STEP source is malformed or partial")

        temporary = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
        try:
            temporary.write(source_bytes)
            temporary.close()
            reader = STEPControl_Reader()
            if reader.ReadFile(temporary.name) != IFSelect_RetDone:
                raise KernelOperationError("OCCT could not read STEP source")
            if reader.TransferRoots() <= 0:
                raise KernelOperationError("STEP source contains no transferable roots")
            shape = reader.OneShape()
            if shape.IsNull():
                raise KernelOperationError("STEP import produced a null shape")
            return shape
        finally:
            Path(temporary.name).unlink(missing_ok=True)

    def import_step_assembly(self, source: str | bytes | Path) -> KernelAssembly:
        source_bytes = self._source_bytes(source)
        shape = self.import_step(source_bytes)
        solids = self._subshapes(shape, "solid")
        if not solids:
            raise KernelOperationError("STEP source contains no solid components")

        components = []
        for solid in solids:
            faces = self.face_records(solid)
            transform = self._transform_record(solid)
            payload = repr((transform, self.topology_counts(solid), faces)).encode("utf-8")
            reference = "component:" + hashlib.sha256(payload).hexdigest()[:24]
            components.append(KernelComponent(reference, "assembly:root", transform,
                                              self.topology_counts(solid), faces))
        components.sort(key=lambda item: item.reference)
        return KernelAssembly(
            root_reference="assembly:root",
            source_sha256=hashlib.sha256(source_bytes).hexdigest(),
            units="mm",
            components=tuple(components),
        )

    def export_step(self, model: object) -> bytes:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.step"
            writer = STEPControl_Writer()
            if writer.Transfer(model, STEPControl_AsIs) != IFSelect_RetDone:
                raise KernelOperationError("OCCT could not transfer shape for STEP export")
            if writer.Write(str(path)) != IFSelect_RetDone:
                raise KernelOperationError("OCCT could not write STEP output")
            data = path.read_bytes()
        # OCCT writes the current timestamp into FILE_NAME. Normalize it so
        # identical geometry produces deterministic bytes.
        return re.sub(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                      b"1970-01-01T00:00:00", data)

    def boolean(self, operation: str, left: object, right: object) -> object:
        from OCP.BRepAlgoAPI import (BRepAlgoAPI_Common, BRepAlgoAPI_Cut,
                                     BRepAlgoAPI_Fuse)

        builders = {"fuse": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut,
                    "common": BRepAlgoAPI_Common}
        if operation not in builders:
            raise KernelOperationError(f"unsupported Boolean operation: {operation}")
        builder = builders[operation](left, right)
        builder.Build()
        if not builder.IsDone():
            raise KernelOperationError(f"OCCT Boolean {operation} failed")
        shape = builder.Shape()
        if shape.IsNull():
            raise KernelOperationError(f"OCCT Boolean {operation} produced a null shape")
        return shape

    def clearance(self, left: object, right: object) -> float:
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape

        distance = BRepExtrema_DistShapeShape(left, right)
        distance.Perform()
        if not distance.IsDone():
            raise KernelOperationError("OCCT distance calculation failed")
        return float(distance.Value())

    def topology_counts(self, model: object) -> TopologyCounts:
        return TopologyCounts(len(self._subshapes(model, "solid")),
                              len(self._subshapes(model, "shell")),
                              len(self._subshapes(model, "face")),
                              len(self._subshapes(model, "edge")))

    def face_records(self, model: object) -> tuple[KernelFace, ...]:
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.gp import gp_Pnt, gp_Vec

        records = []
        for face in self._subshapes(model, "face"):
            surface = BRepAdaptor_Surface(face)
            u = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0
            v = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0
            point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
            surface.D1(u, v, point, du, dv)
            normal = du.Crossed(dv)
            if normal.Magnitude() <= 1e-12:
                raise KernelOperationError("face normal is undefined at sample point")
            normal.Normalize()
            if face.Orientation().name == "TopAbs_REVERSED":
                normal.Reverse()
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, props)
            area = round(float(props.Mass()), 9)
            center = tuple(round(value, 9) for value in (point.X(), point.Y(), point.Z()))
            direction = tuple(round(value, 9) for value in (normal.X(), normal.Y(), normal.Z()))
            fingerprint = hashlib.sha256(repr((area, center, direction,
                                                int(surface.GetType()))).encode("utf-8")).hexdigest()[:24]
            records.append(KernelFace("face:" + fingerprint, area, center, direction))
        return tuple(sorted(records, key=lambda item: item.reference))

    @staticmethod
    def _transform_record(shape: object) -> tuple[float, ...]:
        transform = shape.Location().Transformation()
        values = []
        for row in range(1, 4):
            for column in range(1, 5):
                values.append(round(float(transform.Value(row, column)), 12))
        return tuple(values)

    @staticmethod
    def _subshapes(model: object, kind: str) -> list[object]:
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer

        kinds = {"solid": TopAbs_SOLID, "shell": TopAbs_SHELL,
                 "face": TopAbs_FACE, "edge": TopAbs_EDGE}
        explorer = TopExp_Explorer(model, kinds[kind])
        result = []
        while explorer.More():
            result.append(explorer.Current())
            explorer.Next()
        return result


def installed_backend_candidates() -> tuple[str, ...]:
    return tuple(module for module in ("OCP", "OCC") if find_spec(module) is not None)


def require_real_kernel() -> RealKernel:
    if find_spec("OCP") is None:
        raise KernelUnavailable(
            "No approved B-Rep backend is installed. Install "
            f"{OcpKernel.PINNED_DISTRIBUTION}; the AABB test double is not a fallback."
        )
    kernel = OcpKernel()
    if not kernel.capabilities.is_complete:
        raise KernelUnavailable("the reviewed OCP adapter does not expose every required capability")
    return kernel
