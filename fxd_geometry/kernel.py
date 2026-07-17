"""CAD-neutral boundary and reviewed OCP implementation for real B-Rep geometry."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from importlib.util import find_spec
from pathlib import Path
import re
import tempfile
from typing import Protocol


logger = logging.getLogger("fxd.kernel")


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
class KernelTriangleMesh:
    """Deterministic, kernel-neutral tessellation for review applications.

    Coordinates are millimetres. Triangle indices refer to ``vertices_mm``;
    ``face_reference`` keeps visual selection linked to the kernel face record.
    """

    face_reference: str
    vertices_mm: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class KernelEdgeRecord:
    """Stable inspection record for a topological edge."""

    reference: str
    start_mm: tuple[float, float, float]
    end_mm: tuple[float, float, float]


@dataclass(frozen=True)
class KernelFace:
    reference: str
    area_mm2: float
    center_mm: tuple[float, float, float]
    normal: tuple[float, float, float]
    surface_type: str = "unknown"
    is_planar: bool = False


@dataclass(frozen=True)
class KernelComponent:
    reference: str
    parent_reference: str
    name: str
    transform: tuple[float, ...]
    topology: TopologyCounts
    faces: tuple[KernelFace, ...]


@dataclass(frozen=True)
class KernelAssembly:
    root_reference: str
    source_sha256: str
    units: str
    assembly_references: tuple[str, ...]
    components: tuple[KernelComponent, ...]
    component_colors: tuple[tuple[str, tuple[float, float, float]], ...] = ()

    @property
    def colors_available(self) -> bool:
        return bool(self.component_colors)


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
    def make_box(self, minimum: tuple[float, float, float], maximum: tuple[float, float, float]) -> object: ...
    def make_cylinder(self, center: tuple[float, float, float], radius: float, height: float) -> object: ...
    def cut(self, left: object, right: object) -> object: ...
    def make_slot(self, minimum: tuple[float, float, float], maximum: tuple[float, float, float]) -> object: ...
    def make_hole(self, center: tuple[float, float, float], radius: float, height: float) -> object: ...
    def compound(self, models: tuple[object, ...]) -> object: ...
    def intersects(self, left: object, right: object, tolerance_mm: float = 1e-7) -> bool: ...
    def tessellate(self, model: object, linear_deflection_mm: float = 0.1,
                  angular_deflection_rad: float = 0.5) -> tuple[KernelTriangleMesh, ...]: ...
    def edge_records(self, model: object) -> tuple[KernelEdgeRecord, ...]: ...
    def section(self, model: object, plane_origin_mm: tuple[float, float, float],
                plane_normal: tuple[float, float, float]) -> object: ...


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

    @staticmethod
    def _validate_step_bytes(data: bytes) -> None:
        if b"ISO-10303-21" not in data or b"END-ISO-10303-21" not in data:
            raise KernelOperationError("STEP source is malformed or partial")

    def import_step(self, source: str | bytes | Path) -> object:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
        data = self._source_bytes(source)
        self._validate_step_bytes(data)
        temp = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
        try:
            temp.write(data)
            temp.close()
            reader = STEPControl_Reader()
            read_status = reader.ReadFile(temp.name)
            logger.info("STEP read status=%s", read_status)
            if read_status != IFSelect_RetDone:
                raise KernelOperationError("OCCT could not read STEP source")
            root_count = int(reader.NbRootsForTransfer())
            transferred_roots = int(reader.TransferRoots())
            logger.info("STEP roots=%d transferred_roots=%d", root_count, transferred_roots)
            if transferred_roots <= 0:
                raise KernelOperationError("STEP source contains no transferable roots")
            shape = reader.OneShape()
            logger.info("STEP resulting shape_type=%s null=%s", shape.ShapeType(), shape.IsNull())
            if shape.IsNull():
                logger.error("STEP null-shape detection")
                raise KernelOperationError("STEP import produced a null shape")
            return shape
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def import_step_assembly(self, source: str | bytes | Path) -> KernelAssembly:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.TDF import TDF_Label, TDF_LabelSequence
        from OCP.TDocStd import TDocStd_Document
        from OCP.TopLoc import TopLoc_Location
        from OCP.XCAFApp import XCAFApp_Application
        from OCP.XCAFDoc import (XCAFDoc_ColorType, XCAFDoc_DocumentTool,
                                 XCAFDoc_ShapeTool)
        from OCP.Quantity import Quantity_Color

        data = self._source_bytes(source)
        self._validate_step_bytes(data)
        temporary = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
        try:
            temporary.write(data)
            temporary.close()
            app = XCAFApp_Application.GetApplication_s()
            document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
            app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), document)
            reader = STEPCAFControl_Reader()
            reader.SetNameMode(True)
            read_status = reader.ReadFile(temporary.name)
            logger.info("STEP assembly read status=%s", read_status)
            if read_status != IFSelect_RetDone:
                raise KernelOperationError("OCCT could not read STEP assembly")
            if not reader.Transfer(document):
                raise KernelOperationError("OCCT could not transfer STEP assembly")
            shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
            color_tool = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
            roots = TDF_LabelSequence()
            shape_tool.GetFreeShapes(roots)
            if roots.Length() == 0:
                raise KernelOperationError("STEP assembly contains no free shapes")

            components: list[KernelComponent] = []
            assemblies: list[str] = ["assembly:root"]
            component_colors: list[tuple[str, tuple[float, float, float]]] = []

            def add_component(label: object, parent_reference: str,
                              location: object, path: tuple[int, ...]) -> None:
                base_shape = XCAFDoc_ShapeTool.GetShape_s(label)
                if base_shape.IsNull():
                    raise KernelOperationError("assembly component produced a null shape")
                transformed = BRepBuilderAPI_Transform(
                    base_shape, location.Transformation(), True
                ).Shape()
                if not self._subshapes(transformed, "solid"):
                    raise KernelOperationError("STEP source contains no solid components")
                name = self._label_name(label) or "component-" + ".".join(map(str, path))
                transform = self._location_record(location)
                topology = self.topology_counts(transformed)
                faces = self.face_records(transformed)
                payload = repr((path, name, transform, topology, faces)).encode()
                reference = "component:" + hashlib.sha256(payload).hexdigest()[:24]
                components.append(KernelComponent(reference, parent_reference, name,
                                                  transform, topology, faces))
                try:
                    color = Quantity_Color()
                    for color_type in (XCAFDoc_ColorType.XCAFDoc_ColorGen,
                                       XCAFDoc_ColorType.XCAFDoc_ColorSurf,
                                       XCAFDoc_ColorType.XCAFDoc_ColorCurv):
                        if color_tool.GetColor_s(label, color_type, color):
                            component_colors.append((reference, (color.Red(), color.Green(), color.Blue())))
                            break
                except Exception as exc:
                    logger.warning("STEP color metadata unavailable for %s: %s", reference, exc)

            def visit(label: object, parent_reference: str,
                      parent_location: object, path: tuple[int, ...]) -> None:
                if XCAFDoc_ShapeTool.IsAssembly_s(label):
                    assembly_reference = (
                        "assembly:" + ".".join(map(str, path))
                        if path else "assembly:root"
                    )
                    if assembly_reference not in assemblies:
                        assemblies.append(assembly_reference)
                    children = TDF_LabelSequence()
                    XCAFDoc_ShapeTool.GetComponents_s(label, children, False)
                    for index in range(1, children.Length() + 1):
                        component_label = children.Value(index)
                        referred = TDF_Label()
                        if not XCAFDoc_ShapeTool.GetReferredShape_s(component_label, referred):
                            raise KernelOperationError("assembly component has no referred shape")
                        local_location = XCAFDoc_ShapeTool.GetLocation_s(component_label)
                        combined = parent_location.Multiplied(local_location)
                        child_path = path + (index,)
                        if XCAFDoc_ShapeTool.IsAssembly_s(referred):
                            visit(referred, assembly_reference, combined, child_path)
                        else:
                            add_component(referred, assembly_reference, combined, child_path)
                    return
                add_component(label, parent_reference, parent_location, path)

            identity = TopLoc_Location()
            for index in range(1, roots.Length() + 1):
                root = roots.Value(index)
                root_location = XCAFDoc_ShapeTool.GetLocation_s(root)
                visit(root, "assembly:root", identity.Multiplied(root_location), (index,))

            if not components:
                raise KernelOperationError("STEP source contains no solid components")
            return KernelAssembly(
                "assembly:root",
                hashlib.sha256(data).hexdigest(),
                "mm",
                tuple(sorted(assemblies)),
                tuple(sorted(components, key=lambda item: item.reference)),
                tuple(sorted(component_colors, key=lambda item: item[0])),
            )
        finally:
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
            data = path.read_bytes()
        return self._normalize_step(data)

    @staticmethod
    def _normalize_step(data: bytes) -> bytes:
        data = re.sub(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                      b"1970-01-01T00:00:00", data)
        return re.sub(rb"Open CASCADE STEP translator 7\.9 \d+",
                      b"Open CASCADE STEP translator 7.9 0", data)

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

    def make_box(self, minimum: tuple[float, float, float], maximum: tuple[float, float, float]) -> object:
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt
        dimensions = tuple(high - low for low, high in zip(minimum, maximum))
        if any(value <= 0 for value in dimensions):
            raise KernelOperationError("manufacturing box dimensions must be positive")
        return BRepPrimAPI_MakeBox(gp_Pnt(*minimum), *dimensions).Shape()

    def make_cylinder(self, center: tuple[float, float, float], radius: float, height: float) -> object:
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
        if radius <= 0 or height <= 0:
            raise KernelOperationError("manufacturing cylinder dimensions must be positive")
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*center), gp_Dir(0, 0, 1)), radius, height).Shape()

    def cut(self, left: object, right: object) -> object:
        return self.boolean("cut", left, right)

    def make_slot(self, minimum: tuple[float, float, float], maximum: tuple[float, float, float]) -> object:
        """Create a prismatic laser-cut slot tool in the neutral kernel."""
        return self.make_box(minimum, maximum)

    def make_hole(self, center: tuple[float, float, float], radius: float, height: float) -> object:
        """Create a through-hole tool; callers extend it through the stock."""
        return self.make_cylinder(center, radius, height)

    def compound(self, models: tuple[object, ...]) -> object:
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound
        if not models:
            raise KernelOperationError("cannot compound empty manufacturing geometry")
        result = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(result)
        for model in models:
            if model is None or model.IsNull():
                raise KernelOperationError("cannot compound null manufacturing geometry")
            builder.Add(result, model)
        return result

    def intersects(self, left: object, right: object, tolerance_mm: float = 1e-7) -> bool:
        if tolerance_mm < 0:
            raise KernelOperationError("intersection tolerance must be non-negative")
        return self.clearance(left, right) <= tolerance_mm

    def tessellate(self, model: object, linear_deflection_mm: float = 0.1,
                   angular_deflection_rad: float = 0.5) -> tuple[KernelTriangleMesh, ...]:
        """Mesh faces for display while retaining stable face selection links."""
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.BRep import BRep_Tool
        from OCP.TopAbs import TopAbs_REVERSED

        if linear_deflection_mm <= 0 or angular_deflection_rad <= 0:
            raise KernelOperationError("tessellation tolerances must be positive")
        BRepMesh_IncrementalMesh(model, linear_deflection_mm, False,
                                 angular_deflection_rad, True)
        faces = self._subshapes(model, "face")
        logger.info("STEP tessellation face_count=%d", len(faces))
        result = []
        for face in faces:
            # Resolve the reference from the individual face rather than
            # relying on explorer order, which is not a stable selection key.
            records = self.face_records(face)
            if len(records) != 1:
                raise KernelOperationError("OCCT face did not yield one stable face record")
            record = records[0]
            triangulation = BRep_Tool.Triangulation_s(face, face.Location())
            if triangulation is None:
                raise KernelOperationError("OCCT produced no tessellation for a face")
            location = face.Location()
            vertices = []
            for index in range(1, triangulation.NbNodes() + 1):
                point = triangulation.Node(index).Transformed(location.Transformation())
                vertices.append(tuple(round(float(value), 9)
                                      for value in (point.X(), point.Y(), point.Z())))
            triangles = []
            for index in range(1, triangulation.NbTriangles() + 1):
                triangle = triangulation.Triangle(index)
                raw_values = (int(triangle.Value(1)), int(triangle.Value(2)), int(triangle.Value(3)))
                if any(value < 1 or value > len(vertices) for value in raw_values):
                    raise KernelOperationError(
                        f"tessellation triangle index out of range: {raw_values} for {len(vertices)} vertices"
                    )
                values = tuple(value - 1 for value in raw_values)
                if face.Orientation() == TopAbs_REVERSED:
                    values = (values[0], values[2], values[1])
                triangles.append(values)
            result.append(KernelTriangleMesh(record.reference, tuple(vertices), tuple(triangles)))
        logger.info("STEP tessellation triangle_count=%d", sum(len(mesh.triangles) for mesh in result))
        return tuple(result)

    def edge_records(self, model: object) -> tuple[KernelEdgeRecord, ...]:
        from OCP.BRep import BRep_Tool
        records = []
        for edge in self._subshapes(model, "edge"):
            curve, first, last = BRep_Tool.Curve_s(edge)
            if curve is None:
                raise KernelOperationError("edge has no geometric curve")
            start = curve.Value(first)
            end = curve.Value(last)
            endpoints = tuple(sorted((tuple(round(float(v), 9) for v in
                                              (start.X(), start.Y(), start.Z())),
                                      tuple(round(float(v), 9) for v in
                                            (end.X(), end.Y(), end.Z())))))
            payload = repr(endpoints).encode()
            records.append(KernelEdgeRecord("edge:" + hashlib.sha256(payload).hexdigest()[:24],
                                            tuple(round(float(v), 9) for v in
                                                  (start.X(), start.Y(), start.Z())),
                                            tuple(round(float(v), 9) for v in
                                                  (end.X(), end.Y(), end.Z()))))
        return tuple(sorted(records, key=lambda item: item.reference))

    def section(self, model: object, plane_origin_mm: tuple[float, float, float],
                plane_normal: tuple[float, float, float]) -> object:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
        import math
        if math.sqrt(sum(value * value for value in plane_normal)) <= 1e-12:
            raise KernelOperationError("section plane normal must be non-zero")
        plane = gp_Pln(gp_Pnt(*plane_origin_mm), gp_Dir(*plane_normal))
        builder = BRepAlgoAPI_Section(model, plane)
        builder.Build()
        if not builder.IsDone() or builder.Shape().IsNull():
            raise KernelOperationError("OCCT section operation failed")
        return builder.Shape()

    def topology_counts(self, model: object) -> TopologyCounts:
        return TopologyCounts(*(len(self._subshapes(model, kind))
                                for kind in ("solid", "shell", "face", "edge")))

    def face_records(self, model: object) -> tuple[KernelFace, ...]:
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane
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
            surface_type = surface.GetType()
            planar = surface_type == GeomAbs_Plane
            token = hashlib.sha256(repr((area, center, direction,
                                         int(surface_type))).encode()).hexdigest()[:24]
            records.append(KernelFace(
                "face:" + token, area, center, direction,
                "plane" if planar else str(surface_type), planar,
            ))
        return tuple(sorted(records, key=lambda item: item.reference))

    @staticmethod
    def _label_name(label: object) -> str | None:
        from OCP.TDataStd import TDataStd_Name
        attribute = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
            return attribute.Get().ToExtString()
        return None

    @staticmethod
    def _location_record(location: object) -> tuple[float, ...]:
        transform = location.Transformation()
        return tuple(round(float(transform.Value(row, column)), 12)
                     for row in range(1, 4) for column in range(1, 5))

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
