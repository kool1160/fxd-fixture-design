"""FXD local engineering review application (dependency-free Tkinter shell)."""
from __future__ import annotations

import math
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from fxd_geometry import (
    EngineeringAnnotations,
    KernelTriangleMesh,
    KernelUnavailable,
    OcpKernel,
    ReviewGeometry,
    Vec3,
    VisualEdge,
    WorkbenchDocument,
    build_review_geometry,
    generate_manufacturing_geometry,
    import_step,
    load_step_for_workbench,
)
from fxd_geometry.project import FxdProject, ProjectFormatError, SUPPORTED_LAYERS
from fxd_geometry.operations import ProjectRecovery, StructuredLog, export_project_package


logger = logging.getLogger("fxd.app")

REVIEW_LAYERS = ("locators", "supports", "stops", "clamps")


class FxdApp:
    def __init__(self, root: tk.Tk, project: FxdProject | None = None) -> None:
        self.root, self.project = root, project
        self.yaw, self.pitch, self.drag = 35.0, 22.0, None
        self.pan_x, self.pan_y, self.zoom = 0.0, 0.0, 1.0
        self.pan_drag = None
        self.kernel = None
        self.product_shape = None
        self.review_geometry: ReviewGeometry | None = None
        self.kernel_meshes: tuple[KernelTriangleMesh, ...] = ()
        self.selected_reference: str | None = None
        self.display_mode = "solid"
        self.section_view = False
        self.hidden_review_layers: set[str] = set()
        self.project_path: Path | None = None
        self.workbench_document: WorkbenchDocument | None = None
        self.log = StructuredLog(Path.home() / ".fxd" / "diagnostics.jsonl")

        root.title("FXD — Engineering Review (not production approval)")
        root.geometry("1180x760")
        self.status = tk.StringVar(value="Open a legally shareable STEP assembly to begin.")
        self.canvas = tk.Canvas(root, background="#18212b", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        side = ttk.Frame(root, padding=10, width=330)
        side.pack(side="right", fill="y")
        ttk.Button(side, text="Import STEP", command=self.import_step).pack(fill="x")
        ttk.Button(side, text="Open FXD project", command=self.open_project).pack(fill="x", pady=3)
        ttk.Button(side, text="Save FXD project", command=self.save_project).pack(fill="x", pady=3)
        ttk.Button(side, text="Export review package", command=self.export_package).pack(fill="x", pady=3)
        ttk.Button(side, text="Recover autosave", command=self.recover_autosave).pack(fill="x", pady=3)
        self.concepts = tk.Listbox(side, height=5, exportselection=False)
        self.concepts.pack(fill="x", pady=8)
        self.concepts.bind("<<ListboxSelect>>", self.select_concept)

        ttk.Label(side, text="Layers").pack(anchor="w")
        for layer in sorted(SUPPORTED_LAYERS):
            ttk.Button(side, text=f"Toggle {layer}",
                       command=lambda item=layer: self.toggle(item)).pack(fill="x", pady=1)
        for layer in REVIEW_LAYERS:
            ttk.Button(side, text=f"Toggle {layer}",
                       command=lambda item=layer: self.toggle_review_layer(item)).pack(fill="x", pady=1)

        ttk.Button(side, text="Suppress / unsuppress feature",
                   command=self.suppress_feature).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Record correction", command=self.correct).pack(fill="x", pady=2)
        ttk.Button(side, text="Approve for engineering review",
                   command=lambda: self.decide("approve_for_review")).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Reject concept",
                   command=lambda: self.decide("reject")).pack(fill="x")
        ttk.Button(side, text="Fit to view", command=self.fit_view).pack(fill="x", pady=(8, 2))
        ttk.Label(side, text="Standard views").pack(anchor="w", pady=(6, 0))
        for view in ("front", "top", "right"):
            ttk.Button(side, text=view.title(),
                       command=lambda item=view: self.set_standard_view(item)).pack(fill="x", pady=1)
        ttk.Button(side, text="Toggle wireframe",
                   command=lambda: self.set_display("wireframe")).pack(fill="x", pady=1)
        ttk.Button(side, text="Toggle transparency",
                   command=lambda: self.set_display("transparent")).pack(fill="x", pady=1)
        ttk.Button(side, text="Toggle kernel section", command=self.toggle_section).pack(fill="x", pady=1)

        self.findings = tk.Text(side, width=42, height=12, wrap="word", state="disabled")
        self.findings.pack(fill="both", expand=True, pady=8)
        ttk.Label(side, textvariable=self.status, wraplength=300).pack(anchor="w", pady=8)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.rotate)
        self.canvas.bind("<ButtonRelease-1>", self.pick_item)
        self.canvas.bind("<ButtonPress-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.pan)
        self.canvas.bind("<ButtonRelease-3>", self.end_pan)
        self.canvas.bind("<MouseWheel>", self.zoom_view)
        self.canvas.bind("<Configure>", lambda _event: self.render())
        if project:
            self._restore_kernel_geometry()
        self.refresh()

    def import_step(self) -> None:
        name = filedialog.askopenfilename(filetypes=(("STEP", "*.step *.stp"), ("All files", "*")))
        if not name:
            return
        self.load_step_path(Path(name))

    def load_step_path(self, source: Path) -> None:
        try:
            product = import_step(source)
            annotations = EngineeringAnnotations.for_product(
                product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
                process_type="manual MIG", production_quantity=1)
            self.project = FxdProject.from_product(product, annotations)
            self.workbench_document = None
            self.project_path = None
            self._restore_kernel_geometry()
            self.root.title(f"FXD — {source.name} · OCP engineering review")
            message = (f"Imported immutable STEP and {len(self.review_geometry.meshes)} selectable "
                       "product/fixture B-Rep face meshes." if self.review_geometry else
                       "Imported immutable STEP; real-kernel display is unavailable and review remains provisional.")
            self.refresh(message)
        except Exception as neutral_error:
            logger.exception("complete neutral STEP import traceback for %s", source.name)
            try:
                self.workbench_document = load_step_for_workbench(source)
                self.project = None
                self.project_path = None
                self.kernel = OcpKernel()
                self.root.title(f"FXD — {source.name} · OCP engineering review")
                self.status.set(
                    f"Loaded {self.workbench_document.source_name}: OCP B-Rep, "
                    f"{self.workbench_document.component_count} OCP components, "
                    f"SHA-256 {self.workbench_document.source_sha256[:12]}."
                )
                self.refresh()
            except Exception as kernel_error:
                messagebox.showerror(
                    "STEP import failed",
                    f"Neutral FXD import failed:\n{neutral_error}\n\n"
                    f"Real OCP import failed:\n{kernel_error}",
                )

    def open_project(self) -> None:
        name = filedialog.askopenfilename(filetypes=(("FXD project", "*.fxd.json"),))
        if not name:
            return
        try:
            self.project = FxdProject.load(name)
            self.project_path = Path(name)
            self.log.record("project_opened", source_sha256=self.project.product.source_sha256,
                            revision=self.project.revision_id)
            self.selected_reference = None
            self._restore_kernel_geometry()
            message = ("Loaded project and rebuilt real-kernel visual evidence from embedded immutable STEP."
                       if self.review_geometry else
                       "Loaded project; kernel evidence unavailable, so visual review remains provisional.")
            self.refresh(message)
        except Exception as exc:
            messagebox.showerror("Project load failed", str(exc))

    def save_project(self) -> None:
        if not self.project:
            return
        name = filedialog.asksaveasfilename(
            defaultextension=".fxd.json", filetypes=(("FXD project", "*.fxd.json"),))
        if name:
            self.project.save(name)
            self.project_path = Path(name)
            ProjectRecovery(self.project_path).autosave(self.project)
            self.log.record("project_saved", revision=self.project.revision_id)
            self.status.set(f"Saved {Path(name).name}; production approval is not implied.")

    def export_package(self) -> None:
        if not self.project:
            return
        destination = filedialog.askdirectory(title="Export engineering review package")
        if not destination:
            return
        try:
            paths = export_project_package(self.project, destination, kernel=self.kernel)
            self.log.record("review_package_exported", revision=self.project.revision_id,
                            artifact_count=len(paths))
            self.status.set("Exported engineering-review package; production approval is not implied.")
        except Exception as exc:
            self.log.record("review_package_export_failed", error=str(exc))
            messagebox.showerror("Package export failed", str(exc))

    def recover_autosave(self) -> None:
        if not self.project_path:
            messagebox.showinfo("Recover autosave", "Open or save a project first so its autosave location is known.")
            return
        try:
            self.project = ProjectRecovery(self.project_path).recover()
            self._restore_kernel_geometry()
            self.refresh("Recovered autosave; review state remains subject to deterministic validation.")
            self.log.record("autosave_recovered", revision=self.project.revision_id)
        except Exception as exc:
            messagebox.showerror("Autosave recovery failed", str(exc))

    def _restore_kernel_geometry(self) -> None:
        self.kernel = None
        self.product_shape = None
        self.review_geometry = None
        self.kernel_meshes = ()
        if not self.project:
            return
        try:
            self.kernel = OcpKernel()
            self.product_shape = load_step_for_workbench(
                self.project.product.source_bytes, kernel=self.kernel,
                source_name=self.project.product.source_name,
            ).shape
            self._rebuild_review_geometry()
        except KernelUnavailable:
            return
        except Exception as exc:
            logger.exception("complete workbench geometry traceback for %s", self.project.product.source_name)
            self.status.set(f"Real-kernel evidence unavailable; provisional view only ({exc}).")

    def _rebuild_review_geometry(self) -> None:
        self.review_geometry = None
        self.kernel_meshes = ()
        if not self.project or not self.kernel or self.product_shape is None:
            return
        manufacturing = generate_manufacturing_geometry(self.project.active, self.kernel)
        geometry = build_review_geometry(
            self.kernel, self.project.product, self.product_shape,
            self.project.active, manufacturing)
        if geometry.concept_identity != self.project.active.identity:
            raise RuntimeError("visual evidence does not match the active deterministic concept")
        self.review_geometry = geometry
        self.kernel_meshes = tuple(item for item in geometry.meshes)
        self.selected_reference = None

    def refresh(self, message: str = "") -> None:
        self.concepts.delete(0, "end")
        if self.project:
            from fxd_geometry import validate_fixture_concept
            for concept in self.project.concepts:
                status = validate_fixture_concept(self.project.product, concept).status
                self.concepts.insert("end", f"{concept.identity} — {status.upper()}")
            index = next(i for i, item in enumerate(self.project.concepts)
                         if item.identity == self.project.active_concept)
            self.concepts.selection_set(index)
            validation = self.project.active_validation
            lines = [f"{item.severity.upper()} · {item.subsystem} · {item.code}\n{item.message}"
                     for item in validation.findings]
            self.findings.configure(state="normal")
            self.findings.delete("1.0", "end")
            self.findings.insert("1.0", "\n\n".join(lines) or "No findings recorded.")
            self.findings.configure(state="disabled")
            if not message:
                message = (f"Validation: {validation.status.upper()} · evidence "
                           f"{validation.evidence_digest[:12]}")
        if message:
            self.status.set(message)
        self.render()

    def select_concept(self, _event=None) -> None:
        if self.project and self.concepts.curselection():
            identity = self.project.concepts[self.concepts.curselection()[0]].identity
            self.project = self.project.with_concept(identity)
            self._rebuild_review_geometry()
            self.refresh("Active concept changed; real-kernel geometry regenerated.")

    def toggle(self, layer: str) -> None:
        if self.project:
            try:
                self.project = self.project.toggle_layer(layer)
                self.render()
            except ProjectFormatError as exc:
                messagebox.showerror("Layer change rejected", str(exc))

    def toggle_review_layer(self, layer: str) -> None:
        if layer in self.hidden_review_layers:
            self.hidden_review_layers.remove(layer)
        else:
            self.hidden_review_layers.add(layer)
        self.render()

    def suppress_feature(self) -> None:
        if not self.project:
            return
        choices = ", ".join(feature.identity for feature in self.project.active.fixture.features)
        identity = simpledialog.askstring("Feature", f"Feature identity:\n{choices}")
        if not identity:
            return
        try:
            self.project = self.project.suppress(identity)
            self._rebuild_review_geometry()
            self.refresh(f"Feature state changed and visual evidence regenerated: {identity}")
        except (ProjectFormatError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Feature edit rejected", str(exc))

    def correct(self) -> None:
        if not self.project:
            return
        key = simpledialog.askstring("Correction", "Correction key:")
        value = simpledialog.askstring("Correction", "Replacement value:")
        reason = simpledialog.askstring("Correction", "Reason:")
        if key and value and reason:
            try:
                self.project = self.project.correct(key, value, reason)
                self._rebuild_review_geometry()
                self.refresh("Correction recorded; geometry and validation evidence regenerated.")
            except (ProjectFormatError, ValueError, RuntimeError) as exc:
                messagebox.showerror("Correction rejected", str(exc))

    def decide(self, action: str) -> None:
        if not self.project:
            return
        try:
            self.project = self.project.decide(action, "Human review action recorded locally.")
            self.refresh(f"Recorded {action}; this is not production approval.")
        except ProjectFormatError as exc:
            messagebox.showerror("Review decision blocked", str(exc))
            self.refresh(str(exc))

    def start_drag(self, event) -> None:
        self.drag = (event.x, event.y, self.yaw, self.pitch)

    def start_pan(self, event) -> None:
        self.pan_drag = (event.x, event.y, self.pan_x, self.pan_y)

    def pan(self, event) -> None:
        if self.pan_drag:
            x, y, pan_x, pan_y = self.pan_drag
            self.pan_x = pan_x + event.x - x
            self.pan_y = pan_y + event.y - y
            self.render()

    def end_pan(self, _event) -> None:
        self.pan_drag = None

    def zoom_view(self, event) -> None:
        self.zoom = max(0.15, min(8.0, self.zoom * (1.1 if event.delta > 0 else 1 / 1.1)))
        self.status.set(f"Zoom {self.zoom:.2f}x")
        self.render()

    def rotate(self, event) -> None:
        if self.drag:
            x, y, yaw, pitch = self.drag
            self.yaw = yaw + (event.x - x) * 0.7
            self.pitch = max(-80, min(80, pitch + (event.y - y) * 0.7))
            self.render()

    def pick_item(self, _event) -> None:
        current = self.canvas.find_withtag("current")
        if current:
            tags = self.canvas.gettags(current[0])
            selected = next((tag[5:] for tag in tags if tag.startswith("pick:")), None)
            if selected:
                self.selected_reference = selected
                item_id = selected.split("/", 1)[0]
                item = self.review_geometry.item(item_id) if self.review_geometry else None
                if item:
                    refs = ", ".join(item.source_references) or "generated"
                    self.status.set(
                        f"Selected {selected} · {item.category} · layer={item.layer} · "
                        f"rule={item.rule or 'source'} · refs={refs} · findings={','.join(item.findings) or 'none'}")
                self.render()
        self.drag = None

    def render(self) -> None:
        self.canvas.delete("all")
        if not self.project:
            if self.workbench_document:
                self._render_workbench_document()
                self.canvas.create_text(
                    12, 12, anchor="nw", fill="#9bd3ff",
                    text=(f"REAL OCP · "
                          f"{self.workbench_document.source_name} · "
                          f"{self.workbench_document.component_count} components · "
                          "engineering review only"),
                )
                return
            self.canvas.create_text(30, 30, anchor="nw", fill="white",
                                    text="FXD visual engineering review\n\nDrag to rotate the 3D projection.")
            return
        if self.review_geometry:
            self._render_review_geometry()
        else:
            self._render_bounds()
        validation = self.project.active_validation
        banner_color = "#ff6666" if validation.blocked else "#ffd166"
        source = "REAL OCP" if self.review_geometry else "PROVISIONAL AABB"
        self.canvas.create_text(
            12, 12, anchor="nw", fill=banner_color,
            text=(f"{source} · {self.project.active.identity}: {validation.status.upper()} · "
                  f"evidence {validation.evidence_digest[:12]} — not production approval"))

    def _render_workbench_document(self) -> None:
        document = self.workbench_document
        if not document:
            return
        vertices = [point for mesh in document.meshes for point in mesh.vertices_mm]
        if not vertices:
            return
        center = tuple((min(point[i] for point in vertices) + max(point[i] for point in vertices)) / 2
                       for i in range(3))
        span = max(max(point[i] for point in vertices) - min(point[i] for point in vertices)
                   for i in range(3)) or 1
        polygons = []
        for mesh in document.meshes:
            for triangle in mesh.triangles:
                points = [mesh.vertices_mm[index] for index in triangle]
                polygons.append((sum(point[2] for point in points) / 3,
                                 [self.project_point(point, center, span) for point in points]))
        for _depth, projected in sorted(polygons):
            flat = [coordinate for point in projected for coordinate in point]
            self.canvas.create_polygon(*flat, fill="#24445c", outline="#66c2ff")

    def _visible_items(self):
        assert self.review_geometry and self.project
        for item in self.review_geometry.items:
            if item.layer in self.hidden_review_layers:
                continue
            if item.category == "product" and "product" in self.project.hidden_layers:
                continue
            if item.category != "product" and "fixture" in self.project.hidden_layers:
                continue
            if item.identity in self.project.suppressed_features:
                continue
            yield item

    def _render_review_geometry(self) -> None:
        visible = tuple(self._visible_items())
        meshes = tuple(mesh for item in visible for mesh in item.meshes)
        edges = tuple(edge for item in visible for edge in
                      (item.section_edges if self.section_view else item.edges))
        vertices = [point for mesh in meshes for point in mesh.vertices_mm]
        vertices += [point for edge in edges for point in (edge.start_mm, edge.end_mm)]
        if not vertices:
            return
        center = tuple((min(point[i] for point in vertices) + max(point[i] for point in vertices)) / 2
                       for i in range(3))
        span = max(max(point[i] for point in vertices) - min(point[i] for point in vertices)
                   for i in range(3)) or 1
        if not self.section_view:
            polygons = []
            for mesh in meshes:
                for triangle in mesh.triangles:
                    points = [mesh.vertices_mm[index] for index in triangle]
                    projected = [self.project_point(point, center, span) for point in points]
                    polygons.append((sum(point[2] for point in points) / 3,
                                     mesh.face_reference, projected))
            for _depth, reference, projected in sorted(polygons):
                item_id = reference.split("/", 1)[0]
                item = self.review_geometry.item(item_id)
                outline = "#ffffff" if reference == self.selected_reference else (
                    "#ff4d4d" if item and item.has_collision else "#66c2ff")
                flat = [coordinate for point in projected for coordinate in point]
                fill = "" if self.display_mode == "wireframe" else "#24445c"
                stipple = "gray50" if self.display_mode == "transparent" else ""
                self.canvas.create_polygon(*flat, fill=fill, stipple=stipple,
                                           outline=outline,
                                           tags=(f"pick:{reference}", "kernel-face"))
        for edge in edges:
            start = self.project_point(edge.start_mm, center, span)
            end = self.project_point(edge.end_mm, center, span)
            color = "#ffffff" if edge.reference == self.selected_reference else (
                "#ffd166" if self.section_view else "#9bd3ff")
            self.canvas.create_line(*start, *end, fill=color, width=2,
                                    tags=(f"pick:{edge.reference}", "kernel-edge"))

    def set_display(self, mode: str) -> None:
        self.display_mode = "solid" if self.display_mode == mode else mode
        self.render()

    def toggle_section(self) -> None:
        self.section_view = not self.section_view
        self.status.set("Kernel section edges enabled." if self.section_view else "Kernel section edges disabled.")
        self.render()

    def fit_view(self) -> None:
        self.yaw, self.pitch = 35.0, 22.0
        self.pan_x, self.pan_y, self.zoom = 0.0, 0.0, 1.0
        self.status.set("Fit all: isometric view")
        self.render()

    def set_standard_view(self, view: str) -> None:
        views = {"front": (0.0, 0.0), "top": (0.0, 90.0), "right": (90.0, 0.0)}
        if view not in views:
            raise ValueError(f"unsupported standard view {view!r}")
        self.yaw, self.pitch = views[view]
        self.pan_x, self.pan_y, self.zoom = 0.0, 0.0, 1.0
        self.status.set(f"Standard view: {view}")
        self.render()

    def _render_bounds(self) -> None:
        items = []
        if "product" not in self.project.hidden_layers:
            for component in self.project.product.components:
                for body in component.bodies:
                    items.append((f"{component.identity}/{body.identity}",
                                  body.bounds.transformed(component.transform), "#66c2ff"))
        if "fixture" not in self.project.hidden_layers:
            for feature in self.project.active.fixture.features:
                if feature.identity not in self.project.suppressed_features:
                    items.append((feature.identity, feature.bounds, "#ffb347"))
        if not items:
            return
        points = [point for _, box, _ in items for point in (box.minimum, box.maximum)]
        center = tuple((min(getattr(point, axis) for point in points)
                        + max(getattr(point, axis) for point in points)) / 2 for axis in "xyz")
        span = max(max(getattr(point, axis) for point in points)
                   - min(getattr(point, axis) for point in points) for axis in "xyz") or 1
        for name, box, color in items:
            corners = [(x, y, z) for x in (box.minimum.x, box.maximum.x)
                       for y in (box.minimum.y, box.maximum.y)
                       for z in (box.minimum.z, box.maximum.z)]
            xy = [self.project_point(corner, center, span) for corner in corners]
            x0, y0 = min(x for x, _ in xy), min(y for _, y in xy)
            x1, y1 = max(x for x, _ in xy), max(y for _, y in xy)
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=2)
            self.canvas.create_text(x0 + 3, y0 + 3, anchor="nw", fill=color, text=name)

    def project_point(self, point, center, span):
        x, y, z = (point[i] - center[i] for i in range(3))
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        xr, zr = x * math.cos(yaw) - z * math.sin(yaw), x * math.sin(yaw) + z * math.cos(yaw)
        yr = y * math.cos(pitch) - zr * math.sin(pitch)
        zr = y * math.sin(pitch) + zr * math.cos(pitch)
        scale = min(self.canvas.winfo_width(), self.canvas.winfo_height()) * 0.72 / span * self.zoom
        return (self.canvas.winfo_width() / 2 + xr * scale + self.pan_x,
                self.canvas.winfo_height() / 2 - yr * scale - zr * scale * 0.15 + self.pan_y)


def main(step_path: Path | None = None) -> None:
    root = tk.Tk()
    app = FxdApp(root)
    if step_path is not None:
        root.after(50, lambda: app.load_step_path(step_path))
    root.mainloop()


if __name__ == "__main__":
    main()
