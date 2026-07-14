"""CAD-neutral boundary and reviewed OCP implementation for real B-Rep geometry."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
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


class RealKernel(Protocol):
    @property
    def capabilities(self) -> KernelCapabilities: ...

    def import_step(self, source: str | bytes | Path) -> object: ...
    def export_step(self, model: object) -> bytes: ...
    def boolean(self, operation: str, left: object, right: object) -> object: ...
    def clearance(self, left: object, right: object) -> float: ...
    def topology_counts(self, model: object) -> TopologyCounts: ...


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

    def import_step(self, source: str | bytes | Path) -> object:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader

        temporary: tempfile.NamedTemporaryFile | None = None
        try:
            if isinstance(source, bytes):
                temporary = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
                temporary.write(source)
                temporary.close()
                path = Path(temporary.name)
            else:
                path = Path(source)
            if not path.is_file():
                raise KernelOperationError(f"STEP source does not exist: {path}")
            reader = STEPControl_Reader()
            if reader.ReadFile(str(path)) != IFSelect_RetDone:
                raise KernelOperationError(f"OCCT could not read STEP source: {path}")
            if reader.TransferRoots() <= 0:
                raise KernelOperationError("STEP source contains no transferable roots")
            shape = reader.OneShape()
            if shape.IsNull():
                raise KernelOperationError("STEP import produced a null shape")
            return shape
        finally:
            if temporary is not None:
                Path(temporary.name).unlink(missing_ok=True)

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
            return path.read_bytes()

    def boolean(self, operation: str, left: object, right: object) -> object:
        from OCP.BRepAlgoAPI import (BRepAlgoAPI_Common, BRepAlgoAPI_Cut,
                                     BRepAlgoAPI_Fuse)

        builders = {
            "fuse": BRepAlgoAPI_Fuse,
            "cut": BRepAlgoAPI_Cut,
            "common": BRepAlgoAPI_Common,
        }
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
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer

        def count(kind: object) -> int:
            explorer = TopExp_Explorer(model, kind)
            result = 0
            while explorer.More():
                result += 1
                explorer.Next()
            return result

        return TopologyCounts(count(TopAbs_SOLID), count(TopAbs_SHELL),
                              count(TopAbs_FACE), count(TopAbs_EDGE))


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
