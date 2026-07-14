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
    """The reviewed B-Rep backend is unavailable or incomplete."""


class KernelOperationError(RuntimeError):
    """A real geometry operation failed explicitly."""


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
        return all((self.step_import, self.topology, self.transforms, self.booleans,
                    self.distance_and_clearance, self.neutral_export))


@dataclass(frozen=True)
class TopologyCounts:
    solids: int
    shells: int
    faces: int
    edges: int


@dataclass(frozen=True)
class KernelFace:
    reference: str
    area_mm2: float
    center_mm: tuple[float, float, float]
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class KernelComponent:
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
            raise KernelUnavailable(f"{self.PINNED_DISTRIBUTION} is required") from exc
        version = str(getattr(OCP, "__version__", "unknown"))
        if not version.startswith("7.9.3.1"):
            raise KernelUnavailable(f"unsupported OCP runtime {version!r}")
        self._version = version

    @property
    def capabilities(self) -> KernelCapabilities:
        return KernelCapabilities("cadquery-ocp", self._version, True, True, True,
                                  True, True, True)

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
        data = self._source_bytes(source)
        if b"ISO-10303-21" not in data or b"END-ISO-10303-21" not in data:
            raise KernelOperationError("STEP source is malformed or partial")
        temp = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
        try:
            temp.write(data)
            temp.close()
            reader = STEPControl_Reader()
            if reader.ReadFile(temp.name) != IFSelect_RetDone:
                raise KernelOperationError("OCCT could not read STEP source")
            if reader.TransferRoots() <= 0:
                raise KernelOperationError("STEP source contains no transferable roots")
            shape = reader.OneShape()
            if shape.IsNull():
                raise KernelOperationError("STEP import produced a null shape")
            return shape
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def import_step_assembly(self, source: str | bytes | Path) -> KernelAssembly:
        data = self._source_bytes(source)
        shape = self.import_step(data)
        solids = self._subshapes(shape, "solid")
        if not solids:
            raise KernelOperationError("STEP source contains no solid components")
        components = []
        for solid in solids:
            faces = self.face_records(solid)
            transform = self._transform_record(solid)
            payload = repr((transform, self.topology_counts(solid), faces)).encode()
            reference = "component:" + hashlib.sha256(payload).hexdigest()[:24]
            components.append(KernelComponent(reference, "assembly:root", transform,
                                              self.topology_counts(solid), faces))
        return KernelAssembly("assembly:root", hashlib.sha256(data).hexdigest(), "mm",
                              tuple(sorted(components, key=lambda item: item.reference)))

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
        return re.sub(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                      b"1970-01-01T00:00:00", data)

    def boolean(self, operation: str, left: object, right: object) -> object:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
        builders = {"fuse": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut,
                    "common": BRepAlgoAPI_Common}
        if operation not in builders:
            raise KernelOperationError(f"unsupported Boolean operation: {operation}")
        builder = builders[operation](left, right)
        builder.Build()
        if not builder.IsDone() or builder.Shape().IsNull():
            raise KernelOperationError(f"OCCT Boolean {operation} failed")
        return builder.Shape()

    def clearance(self, left: object, right: object) -> float:
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        distance = BRepExtrema_DistShapeShape(left, right)
        distance.Perform()
        if not distance.IsDone():
            raise KernelOperationError("OCCT distance calculation failed")
        return float(distance.Value())

    def topology_counts(self, model: object) -> TopologyCounts:
        return TopologyCounts(*(len(self._subshapes(model, kind))
                                for kind in ("solid", "shell", "face", "edge")))

    def face_records(self, model: object) -> tuple[KernelFace, ...]:
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.TopAbs import TopAbs_REVERSED
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
            if face.Orientation() == TopAbs_REVERSED:
                normal.Reverse()
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, props)
            area = round(float(props.Mass()), 9)
            center = tuple(round(x, 9) for x in (point.X(), point.Y(), point.Z()))
            direction = tuple(round(x, 9) for x in (normal.X(), normal.Y(), normal.Z()))
            token = hashlib.sha256(repr((area, center, direction,
                                         int(surface.GetType()))).encode()).hexdigest()[:24]
            records.append(KernelFace("face:" + token, area, center, direction))
        return tuple(sorted(records, key=lambda item: item.reference))

    @staticmethod
    def _transform_record(shape: object) -> tuple[float, ...]:
        trsf = shape.Location().Transformation()
        return tuple(round(float(trsf.Value(r, c)), 12)
                     for r in range(1, 4) for c in range(1, 5))

    @staticmethod
    def _subshapes(model: object, kind: str) -> list[object]:
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
        kinds = {"solid": TopAbs_SOLID, "shell": TopAbs_SHELL,
                 "face": TopAbs_FACE, "edge": TopAbs_EDGE}
        casts = {"solid": TopoDS.Solid_s, "shell": TopoDS.Shell_s,
                 "face": TopoDS.Face_s, "edge": TopoDS.Edge_s}
        explorer = TopExp_Explorer(model, kinds[kind])
        result = []
        while explorer.More():
            result.append(casts[kind](explorer.Current()))
            explorer.Next()
        return result


def installed_backend_candidates() -> tuple[str, ...]:
    return tuple(module for module in ("OCP", "OCC") if find_spec(module) is not None)


def require_real_kernel() -> RealKernel:
    if find_spec("OCP") is None:
        raise KernelUnavailable(f"Install {OcpKernel.PINNED_DISTRIBUTION}; AABB is not a fallback")
    kernel = OcpKernel()
    if not kernel.capabilities.is_complete:
        raise KernelUnavailable("reviewed OCP adapter lacks required capabilities")
    return kernel
