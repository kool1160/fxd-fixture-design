"""Persistent VTK scenes for the local engineering workbench."""
from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter

from .workbench import WorkbenchDocument


class VtkViewerUnavailable(RuntimeError):
    """The optional local VTK viewport is not installed or usable."""


@dataclass(frozen=True)
class RenderDiagnostics:
    backend: str
    actor_count: int
    point_count: int
    triangle_count: int
    initialized: bool
    native_rendering_active: bool
    fallback_active: bool
    average_render_ms: float | None = None
    frames_per_second: float | None = None


class VtkSceneController:
    """Framework-neutral persistent VTK scene built from real STEP meshes."""

    NEUTRAL_COLOR = (0.58, 0.72, 0.84)
    SELECTED_COLOR = (1.0, 0.72, 0.18)

    def __init__(self, render_window: object, interactor: object,
                 document: WorkbenchDocument) -> None:
        try:
            from vtkmodules.vtkCommonCore import vtkPoints
            from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData, vtkTriangle
            from vtkmodules.vtkInteractionStyle import vtkInteractorStyleImage, vtkInteractorStyleTrackballCamera
            from vtkmodules.vtkRenderingCore import vtkActor, vtkCellPicker, vtkPolyDataMapper, vtkRenderer
        except Exception as exc:
            raise VtkViewerUnavailable(str(exc)) from exc

        self.document = document
        self.render_window = render_window
        self.interactor = interactor
        self.wireframe = False
        self.transparent = False
        self.orbit_enabled = True
        self.navigation_mode = "orbit"
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.035, 0.047, 0.064)
        self.renderer.SetBackground2(0.10, 0.125, 0.15)
        self.renderer.GradientBackgroundOn()
        self.render_window.AddRenderer(self.renderer)
        self.render_window.SetMultiSamples(4)
        self._trackball_style = vtkInteractorStyleTrackballCamera()
        self._image_style = vtkInteractorStyleImage()
        self.interactor.SetInteractorStyle(self._trackball_style)
        self.actors: dict[str, object] = {}
        self.polydata: dict[str, object] = {}
        self._base_colors: dict[str, tuple[float, float, float]] = {}
        self.source_actor_identities: set[str] = set()
        self.review_actor_identities: set[str] = set()
        self.selection_aliases: dict[str, str] = {}
        self.selected_identity: str | None = None
        self._face_for_cell: dict[tuple[str, int], str] = {}
        self._cell_picker = vtkCellPicker()
        self._cell_picker.SetTolerance(0.0005)

        component_for_face = {
            face.reference: component.reference
            for component in document.assembly.components
            for face in component.faces
        }
        self.selection_aliases.update(component_for_face)
        groups: dict[str, list[object]] = {}
        for mesh in document.meshes:
            identity = component_for_face.get(mesh.face_reference, "source:geometry")
            groups.setdefault(identity, []).append(mesh)
        colors = dict(document.assembly.component_colors)

        for identity, meshes in sorted(groups.items()):
            points = vtkPoints()
            cells = vtkCellArray()
            for mesh in meshes:
                offset = points.GetNumberOfPoints()
                for point in mesh.vertices_mm:
                    points.InsertNextPoint(*point)
                for triangle in mesh.triangles:
                    cell = vtkTriangle()
                    for local, index in enumerate(triangle):
                        if index < 0 or index >= len(mesh.vertices_mm):
                            raise VtkViewerUnavailable(
                                f"mesh triangle index {index} is outside its vertex array"
                            )
                        cell.GetPointIds().SetId(local, offset + index)
                    cells.InsertNextCell(cell)
                    self._face_for_cell[(identity, cells.GetNumberOfCells() - 1)] = (
                        mesh.face_reference
                    )
            geometry = vtkPolyData()
            geometry.SetPoints(points)
            geometry.SetPolys(cells)
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(geometry)
            actor = vtkActor()
            actor.SetMapper(mapper)
            color = colors.get(identity, self.NEUTRAL_COLOR)
            actor.GetProperty().SetColor(*color)
            actor.GetProperty().SetInterpolationToPhong()
            actor.GetProperty().SetSpecular(0.18)
            actor.GetProperty().SetSpecularPower(24.0)
            actor.GetProperty().EdgeVisibilityOff()
            self.renderer.AddActor(actor)
            self.actors[identity] = actor
            self.polydata[identity] = geometry
            self._base_colors[identity] = color
            self.source_actor_identities.add(identity)

        self.fit(render=False)

    @property
    def actor(self) -> object:
        """Compatibility accessor for single-actor tests and legacy callers."""
        return next(iter(self.actors.values()))

    @property
    def triangle_count(self) -> int:
        return sum(item.GetNumberOfPolys() for item in self.polydata.values())

    @property
    def point_count(self) -> int:
        return sum(item.GetNumberOfPoints() for item in self.polydata.values())

    def render(self) -> None:
        self.render_window.Render()

    def fit(self, *, render: bool = True) -> None:
        self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()
        if render:
            self.render()

    def set_wireframe(self, enabled: bool) -> None:
        self.wireframe = enabled
        for actor in self.actors.values():
            prop = actor.GetProperty()
            if enabled:
                prop.SetRepresentationToWireframe()
                prop.EdgeVisibilityOn()
            else:
                prop.SetRepresentationToSurface()
                prop.EdgeVisibilityOff()
        self.render()

    def set_transparent(self, enabled: bool) -> None:
        self.transparent = enabled
        for actor in self.actors.values():
            actor.GetProperty().SetOpacity(0.28 if enabled else 1.0)
        self.render()

    def set_visible(self, enabled: bool) -> None:
        for identity in self.source_actor_identities:
            self.actors[identity].SetVisibility(enabled)
        self.render()

    def set_review_geometry(self, items: tuple[dict[str, object], ...]) -> None:
        """Replace review-only actors without touching immutable source actors."""
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData, vtkTriangle
        from vtkmodules.vtkCommonTransforms import vtkTransform
        from vtkmodules.vtkFiltersSources import vtkArrowSource, vtkCubeSource, vtkPlaneSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        def vector(value: object, label: str) -> tuple[float, float, float]:
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                raise VtkViewerUnavailable(f"{label} must be a 3D vector")
            result = tuple(float(item) for item in value)
            if not all(math.isfinite(item) for item in result):
                raise VtkViewerUnavailable(f"{label} must contain finite values")
            return result

        def unit(value: tuple[float, float, float], label: str) -> tuple[float, float, float]:
            length = math.sqrt(sum(item * item for item in value))
            if length <= 1e-9:
                raise VtkViewerUnavailable(f"{label} must not be zero")
            return tuple(item / length for item in value)

        for identity in tuple(self.review_actor_identities):
            actor = self.actors.pop(identity)
            self.renderer.RemoveActor(actor)
            self.polydata.pop(identity, None)
            self._base_colors.pop(identity, None)
        self.review_actor_identities.clear()
        colors = {
            "valid": (0.25, 0.78, 0.46),
            "provisional": (0.95, 0.65, 0.18),
            "invalid": (0.90, 0.25, 0.25),
        }
        for item in sorted(items, key=lambda value: str(value.get("identity", ""))):
            identity = str(item.get("identity", "")).strip()
            kind = str(item.get("kind", "bounds"))
            status = str(item.get("status", "provisional"))
            if not identity or identity in self.actors:
                raise VtkViewerUnavailable("review geometry requires a unique identity")
            source: object
            geometry: object
            actor_transform: object | None = None
            if kind in {"orientation_plane", "orientation_selected_face_plane"}:
                origin = vector(item.get("origin"), "orientation plane origin")
                x_axis = unit(vector(item.get("x_axis"), "orientation plane X axis"), "orientation plane X axis")
                y_axis = unit(vector(item.get("y_axis"), "orientation plane Y axis"), "orientation plane Y axis")
                if abs(sum(left * right for left, right in zip(x_axis, y_axis))) > 1e-6:
                    raise VtkViewerUnavailable("orientation plane axes must be orthogonal")
                half_width = float(item.get("half_width", 0.0))
                if not math.isfinite(half_width) or half_width <= 0.0:
                    raise VtkViewerUnavailable("orientation plane half width must be positive")
                corners = (
                    tuple(origin[index] - half_width * x_axis[index] - half_width * y_axis[index] for index in range(3)),
                    tuple(origin[index] + half_width * x_axis[index] - half_width * y_axis[index] for index in range(3)),
                    tuple(origin[index] - half_width * x_axis[index] + half_width * y_axis[index] for index in range(3)),
                )
                source = vtkPlaneSource()
                source.SetOrigin(*corners[0])
                source.SetPoint1(*corners[1])
                source.SetPoint2(*corners[2])
                source.SetXResolution(1)
                source.SetYResolution(1)
                source.Update()
                geometry = source.GetOutput()
            elif kind == "orientation_arrow":
                origin = vector(item.get("origin"), "orientation arrow origin")
                direction = unit(vector(item.get("direction"), "orientation arrow direction"), "orientation arrow direction")
                length = float(item.get("length", 0.0))
                if not math.isfinite(length) or length <= 0.0:
                    raise VtkViewerUnavailable("orientation arrow length must be positive")
                source = vtkArrowSource()
                source.Update()
                transform = vtkTransform()
                transform.PostMultiply()
                transform.Scale(length, length, length)
                dot = max(-1.0, min(1.0, direction[0]))
                if dot < 1.0 - 1e-9:
                    if dot <= -1.0 + 1e-9:
                        transform.RotateWXYZ(180.0, 0.0, 1.0, 0.0)
                    else:
                        axis = (0.0, -direction[2], direction[1])
                        transform.RotateWXYZ(math.degrees(math.acos(dot)), *unit(axis, "orientation arrow axis"))
                transform.Translate(*origin)
                actor_transform = transform
                geometry = source.GetOutput()
            elif kind == "orientation_face_highlight":
                vertices = item.get("vertices")
                triangles = item.get("triangles")
                if not isinstance(vertices, (list, tuple)) or not isinstance(triangles, (list, tuple)):
                    raise VtkViewerUnavailable("orientation face highlight requires tessellation")
                points = vtkPoints()
                for point in vertices:
                    points.InsertNextPoint(*vector(point, "orientation face vertex"))
                cells = vtkCellArray()
                for triangle in triangles:
                    if not isinstance(triangle, (list, tuple)) or len(triangle) != 3:
                        raise VtkViewerUnavailable("orientation face highlight requires triangles")
                    cell = vtkTriangle()
                    for local, index in enumerate(triangle):
                        if not isinstance(index, int) or index < 0 or index >= len(vertices):
                            raise VtkViewerUnavailable("orientation face triangle index is invalid")
                        cell.GetPointIds().SetId(local, index)
                    cells.InsertNextCell(cell)
                source = vtkPolyData()
                source.SetPoints(points)
                source.SetPolys(cells)
                geometry = source
            else:
                minimum = item.get("minimum")
                maximum = item.get("maximum")
                low = vector(minimum, "review geometry minimum")
                high = vector(maximum, "review geometry maximum")
                if any(left >= right for left, right in zip(low, high)):
                    raise VtkViewerUnavailable(f"review geometry {identity} has invalid bounds")
                source = vtkCubeSource()
                source.SetBounds(*(value for pair in zip(low, high) for value in pair))
                source.Update()
                geometry = source.GetOutput()
            mapper = vtkPolyDataMapper()
            if isinstance(source, vtkPolyData):
                mapper.SetInputData(source)
            else:
                mapper.SetInputConnection(source.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
            if "color" in item:
                color = vector(item["color"], "review geometry color")
                if any(item < 0.0 or item > 1.0 for item in color):
                    raise VtkViewerUnavailable("review geometry color must be normalized")
            else:
                color = colors.get(status, colors["provisional"])
            actor.GetProperty().SetColor(*color)
            opacity = float(item.get("opacity", 0.55))
            if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
                raise VtkViewerUnavailable("review geometry opacity must be between zero and one")
            actor.GetProperty().SetOpacity(opacity)
            if str(item.get("representation", "wireframe")) == "surface":
                actor.GetProperty().SetRepresentationToSurface()
                actor.GetProperty().EdgeVisibilityOff()
            else:
                actor.GetProperty().SetRepresentationToWireframe()
                actor.GetProperty().EdgeVisibilityOn()
            actor.GetProperty().SetLineWidth(2.0)
            if actor_transform is not None:
                actor.SetUserTransform(actor_transform)
            self.renderer.AddActor(actor)
            self.actors[identity] = actor
            self.polydata[identity] = geometry
            self._base_colors[identity] = color
            self.review_actor_identities.add(identity)
        self.render()

    def set_orbit(self, enabled: bool) -> None:
        self.orbit_enabled = enabled
        self.interactor.SetInteractorStyle(
            self._trackball_style if enabled else self._image_style
        )
        self.render()

    def set_navigation_mode(self, mode: str) -> None:
        if mode not in {"orbit", "pan", "zoom"}:
            raise ValueError(f"unsupported navigation mode {mode!r}")
        self.navigation_mode = mode
        self.set_orbit(True)

    def standard_view(self, view: str) -> None:
        camera = self.renderer.GetActiveCamera()
        self.renderer.ResetCamera()
        focal = camera.GetFocalPoint()
        distance = max(camera.GetDistance(), 1.0)
        positions = {
            "front": (focal[0], focal[1] - distance, focal[2]),
            "back": (focal[0], focal[1] + distance, focal[2]),
            "left": (focal[0] - distance, focal[1], focal[2]),
            "right": (focal[0] + distance, focal[1], focal[2]),
            "top": (focal[0], focal[1], focal[2] + distance),
            "bottom": (focal[0], focal[1], focal[2] - distance),
            "isometric": (focal[0] + distance, focal[1] - distance, focal[2] + distance),
        }
        view_up = {
            "top": (0.0, 1.0, 0.0),
            "bottom": (0.0, 1.0, 0.0),
        }.get(view, (0.0, 0.0, 1.0))
        if view not in positions:
            raise ValueError(f"unsupported standard view {view!r}")
        camera.SetPosition(*positions[view])
        camera.SetFocalPoint(*focal)
        camera.SetViewUp(*view_up)
        self.renderer.ResetCameraClippingRange()
        self.render()

    def preview_orientation(
        self,
        right: tuple[float, float, float],
        front: tuple[float, float, float],
        up: tuple[float, float, float],
    ) -> None:
        """Align only the review camera; immutable source actors are not transformed."""
        def normalized(value: tuple[float, float, float], label: str) -> tuple[float, float, float]:
            if len(value) != 3 or not all(math.isfinite(item) for item in value):
                raise ValueError(f"{label} must contain three finite values")
            length = math.sqrt(sum(item * item for item in value))
            if length <= 1e-9:
                raise ValueError(f"{label} must be non-zero")
            return tuple(item / length for item in value)

        right = normalized(right, "manufacturing right")
        front = normalized(front, "manufacturing front")
        up = normalized(up, "manufacturing up")
        camera = self.renderer.GetActiveCamera()
        self.renderer.ResetCamera()
        focal = camera.GetFocalPoint()
        distance = max(camera.GetDistance(), 1.0)
        camera.SetPosition(*(
            focal[index]
            + distance * front[index]
            + 0.20 * distance * right[index]
            + 0.25 * distance * up[index]
            for index in range(3)
        ))
        camera.SetFocalPoint(*focal)
        camera.SetViewUp(*up)
        camera.OrthogonalizeViewUp()
        self.renderer.ResetCameraClippingRange()
        self.render()

    def pick_face(self, display_x: int, display_y: int) -> str | None:
        """Return the exact source OCP face mapped to a picked tessellation cell."""
        if self._cell_picker.Pick(display_x, display_y, 0.0, self.renderer) == 0:
            return None
        actor = self._cell_picker.GetActor()
        identity = next((key for key, candidate in self.actors.items()
                         if candidate == actor and key in self.source_actor_identities), None)
        cell_id = int(self._cell_picker.GetCellId())
        if identity is None or cell_id < 0:
            return None
        return self._face_for_cell.get((identity, cell_id))

    def select(self, identity: str | None, *, focus: bool = False) -> bool:
        for key, actor in self.actors.items():
            actor.GetProperty().SetColor(*self._base_colors[key])
        mapped_identity = self.selection_aliases.get(identity or "", identity)
        self.selected_identity = identity if mapped_identity in self.actors else None
        actor = self.actors.get(mapped_identity or "")
        if actor is None:
            self.render()
            return False
        actor.GetProperty().SetColor(*self.SELECTED_COLOR)
        if focus:
            self.renderer.ResetCamera(actor.GetBounds())
            self.renderer.ResetCameraClippingRange()
        self.render()
        return True

    def diagnostics(self, *, fallback_active: bool = False,
                    average_render_ms: float | None = None,
                    frames_per_second: float | None = None) -> RenderDiagnostics:
        mapped = bool(self.render_window.GetMapped())
        return RenderDiagnostics(
            backend=self.render_window.GetClassName(),
            actor_count=len(self.actors),
            point_count=self.point_count,
            triangle_count=self.triangle_count,
            initialized=bool(self.actors),
            native_rendering_active=mapped,
            fallback_active=fallback_active,
            average_render_ms=average_render_ms,
            frames_per_second=frames_per_second,
        )

    def benchmark(self, frames: int = 20) -> RenderDiagnostics:
        if frames <= 0:
            raise ValueError("benchmark frame count must be positive")
        camera = self.renderer.GetActiveCamera()
        started = perf_counter()
        for _ in range(frames):
            camera.Azimuth(2.0)
            self.render()
        elapsed = perf_counter() - started
        average_ms = elapsed * 1000.0 / frames
        return self.diagnostics(
            average_render_ms=average_ms,
            frames_per_second=(1000.0 / average_ms if average_ms else None),
        )


class VtkWorkbenchViewer:
    """Legacy Tk wrapper retained for Milestone 26 project compatibility."""

    def __init__(self, parent: object, document: WorkbenchDocument) -> None:
        self.parent = parent
        self.widget = None
        self._poll_id = None
        try:
            from vtkmodules.tk.vtkTkRenderWindowInteractor import vtkTkRenderWindowInteractor
            from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkRenderWindowInteractor
        except Exception as exc:
            raise VtkViewerUnavailable(str(exc)) from exc

        render_window = vtkRenderWindow()
        render_window.SetWindowName("FXD OCP Viewer")
        try:
            self.widget = vtkTkRenderWindowInteractor(
                parent, rw=render_window, width=900, height=700
            )
        except Exception:
            self.widget = None
        if self.widget is not None:
            self.interactor = self.widget.GetRenderWindow().GetInteractor()
        else:
            self.interactor = vtkRenderWindowInteractor()
            self.interactor.SetRenderWindow(render_window)
        self.scene = VtkSceneController(render_window, self.interactor, document)
        self.render_window = render_window
        if self.widget is not None:
            self.widget.pack(fill="both", expand=True)
            self.widget.Initialize()
        else:
            self.interactor.Initialize()
            self._poll_id = parent.after(16, self._process_events)
        self.scene.fit()
        self.visible = self.widget is not None or bool(self.render_window.GetMapped())

    def __getattr__(self, name: str) -> object:
        return getattr(self.scene, name)

    def _process_events(self) -> None:
        if self.interactor is not None:
            self.interactor.ProcessEvents()
            self._poll_id = self.parent.after(16, self._process_events)

    def destroy(self) -> None:
        if self._poll_id is not None:
            self.parent.after_cancel(self._poll_id)
            self._poll_id = None
        self.interactor.TerminateApp()
        self.render_window.Finalize()
        if self.widget is not None:
            self.widget.destroy()
