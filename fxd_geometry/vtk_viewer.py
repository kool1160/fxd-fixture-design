"""Persistent VTK scenes for the local engineering workbench."""
from __future__ import annotations

from dataclasses import dataclass
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
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer
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
        """Replace provisional fixture review actors without touching source actors."""
        from vtkmodules.vtkFiltersSources import vtkCubeSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

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
            minimum = item.get("minimum")
            maximum = item.get("maximum")
            status = str(item.get("status", "provisional"))
            if (not identity or identity in self.actors or not isinstance(minimum, (list, tuple))
                    or not isinstance(maximum, (list, tuple)) or len(minimum) != 3 or len(maximum) != 3):
                raise VtkViewerUnavailable("review geometry requires a unique identity and 3D bounds")
            low = tuple(float(value) for value in minimum)
            high = tuple(float(value) for value in maximum)
            if any(left >= right for left, right in zip(low, high)):
                raise VtkViewerUnavailable(f"review geometry {identity} has invalid bounds")
            source = vtkCubeSource()
            source.SetBounds(*(value for pair in zip(low, high) for value in pair))
            source.Update()
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(source.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
            color = colors.get(status, colors["provisional"])
            actor.GetProperty().SetColor(*color)
            actor.GetProperty().SetOpacity(0.55)
            actor.GetProperty().SetRepresentationToWireframe()
            actor.GetProperty().EdgeVisibilityOn()
            actor.GetProperty().SetLineWidth(2.0)
            self.renderer.AddActor(actor)
            self.actors[identity] = actor
            self.polydata[identity] = source.GetOutput()
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
