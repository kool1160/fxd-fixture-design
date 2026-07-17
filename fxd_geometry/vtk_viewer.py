"""Persistent VTK viewport used by the local Windows workbench."""
from __future__ import annotations

from .workbench import WorkbenchDocument


class VtkViewerUnavailable(RuntimeError):
    """The optional local VTK/Tk viewport is not installed or usable."""


class VtkWorkbenchViewer:
    """One persistent GPU-backed actor for a loaded STEP document."""

    def __init__(self, parent: object, document: WorkbenchDocument) -> None:
        self.parent = parent
        self.widget = None
        self._poll_id = None
        try:
            from vtkmodules.tk.vtkTkRenderWindowInteractor import vtkTkRenderWindowInteractor
            from vtkmodules.vtkCommonCore import vtkPoints
            from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData, vtkTriangle
            from vtkmodules.vtkInteractionStyle import vtkInteractorStyleImage, vtkInteractorStyleTrackballCamera
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow
        except Exception:
            try:
                from vtkmodules.vtkInteractionStyle import vtkInteractorStyleImage, vtkInteractorStyleTrackballCamera
                from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow
                from vtkmodules.vtkRenderingCore import vtkRenderWindowInteractor
                vtkTkRenderWindowInteractor = None
            except Exception as exc:
                raise VtkViewerUnavailable(str(exc)) from exc

        self.document = document
        self.wireframe = False
        self.transparent = False
        self.orbit_enabled = True
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.055, 0.075, 0.10)
        self.render_window = vtkRenderWindow()
        self.render_window.SetWindowName("FXD OCP Viewer")
        self.render_window.AddRenderer(self.renderer)
        self.render_window.SetMultiSamples(4)
        if vtkTkRenderWindowInteractor is not None:
            try:
                self.widget = vtkTkRenderWindowInteractor(parent, rw=self.render_window, width=900, height=700)
            except Exception:
                self.widget = None
        if self.widget is not None:
            self.interactor = self.widget.GetRenderWindow().GetInteractor()
        else:
            from vtkmodules.vtkRenderingCore import vtkRenderWindowInteractor
            self.interactor = vtkRenderWindowInteractor()
            self.interactor.SetRenderWindow(self.render_window)
        self._trackball_style = vtkInteractorStyleTrackballCamera()
        self._image_style = vtkInteractorStyleImage()
        self.interactor.SetInteractorStyle(self._trackball_style)

        points = vtkPoints()
        cells = vtkCellArray()
        for mesh in document.meshes:
            offset = points.GetNumberOfPoints()
            for point in mesh.vertices_mm:
                points.InsertNextPoint(*point)
            for triangle in mesh.triangles:
                cell = vtkTriangle()
                for local, index in enumerate(triangle):
                    cell.GetPointIds().SetId(local, offset + index)
                cells.InsertNextCell(cell)
        polydata = vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetPolys(cells)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        self.actor = vtkActor()
        self.actor.SetMapper(mapper)
        color = document.assembly.component_colors[0][1] if len(document.assembly.component_colors) == 1 else (0.58, 0.72, 0.84)
        self.actor.GetProperty().SetColor(*color)
        self.actor.GetProperty().SetInterpolationToPhong()
        self.renderer.AddActor(self.actor)
        if self.widget is not None:
            self.widget.pack(fill="both", expand=True)
            self.widget.Initialize()
        else:
            self.interactor.Initialize()
            self._poll_id = parent.after(16, self._process_events)
        self.fit()
        self.visible = self.widget is not None or bool(self.render_window.GetMapped())

    def _process_events(self) -> None:
        if self.interactor is not None:
            self.interactor.ProcessEvents()
            self._poll_id = self.parent.after(16, self._process_events)

    @property
    def triangle_count(self) -> int:
        return sum(len(mesh.triangles) for mesh in self.document.meshes)

    def render(self) -> None:
        self.render_window.Render()

    def fit(self) -> None:
        self.renderer.ResetCamera()
        self.render()

    def set_wireframe(self, enabled: bool) -> None:
        self.wireframe = enabled
        prop = self.actor.GetProperty()
        if enabled:
            prop.SetRepresentationToWireframe()
            prop.EdgeVisibilityOn()
        else:
            prop.SetRepresentationToSurface()
            prop.EdgeVisibilityOff()
        self.render()

    def set_transparent(self, enabled: bool) -> None:
        self.transparent = enabled
        self.actor.GetProperty().SetOpacity(0.28 if enabled else 1.0)
        self.render()

    def set_orbit(self, enabled: bool) -> None:
        self.orbit_enabled = enabled
        self.interactor.SetInteractorStyle(self._trackball_style if enabled else self._image_style)
        self.render()

    def standard_view(self, view: str) -> None:
        camera = self.renderer.GetActiveCamera()
        self.renderer.ResetCamera()
        focal = camera.GetFocalPoint()
        distance = camera.GetDistance()
        positions = {
            "front": (focal[0], focal[1] - distance, focal[2]),
            "top": (focal[0], focal[1], focal[2] + distance),
            "right": (focal[0] + distance, focal[1], focal[2]),
            "isometric": (focal[0] + distance, focal[1] - distance, focal[2] + distance),
        }
        if view not in positions:
            raise ValueError(f"unsupported standard view {view!r}")
        camera.SetPosition(*positions[view])
        camera.SetFocalPoint(*focal)
        camera.OrthogonalizeViewUp()
        self.render()

    def destroy(self) -> None:
        if self._poll_id is not None:
            self.parent.after_cancel(self._poll_id)
            self._poll_id = None
        self.interactor.TerminateApp()
        self.render_window.Finalize()
        if self.widget is not None:
            self.widget.destroy()
