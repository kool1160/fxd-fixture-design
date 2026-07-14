"""FXD local engineering review application (dependency-free Tkinter shell)."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

from fxd_geometry import (
    EngineeringAnnotations,
    KernelTriangleMesh,
    KernelUnavailable,
    OcpKernel,
    Vec3,
    import_step,
)
from fxd_geometry.project import FxdProject, ProjectFormatError, SUPPORTED_LAYERS


class FxdApp:
    def __init__(self, root: tk.Tk, project: FxdProject | None = None) -> None:
        self.root, self.project = root, project
        self.yaw, self.pitch, self.drag = 35.0, 22.0, None
        self.kernel_meshes: tuple[KernelTriangleMesh, ...] = ()
        self.selected_face: str | None = None
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
        self.concepts = tk.Listbox(side, height=5, exportselection=False)
        self.concepts.pack(fill="x", pady=8)
        self.concepts.bind("<<ListboxSelect>>", self.select_concept)
        ttk.Label(side, text="Layers").pack(anchor="w")
        for layer in sorted(SUPPORTED_LAYERS):
            ttk.Button(side, text=f"Toggle {layer}",
                       command=lambda item=layer: self.toggle(item)).pack(fill="x", pady=1)
        ttk.Button(side, text="Suppress / unsuppress feature",
                   command=self.suppress_feature).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Record correction", command=self.correct).pack(fill="x", pady=2)
        ttk.Button(side, text="Approve for engineering review",
                   command=lambda: self.decide("approve_for_review")).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Reject concept",
                   command=lambda: self.decide("reject")).pack(fill="x")
        self.findings = tk.Text(side, width=42, height=12, wrap="word", state="disabled")
        self.findings.pack(fill="both", expand=True, pady=8)
        ttk.Label(side, textvariable=self.status, wraplength=300).pack(anchor="w", pady=8)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.rotate)
        self.canvas.bind("<ButtonRelease-1>", self.pick_face)
        self.canvas.bind("<Configure>", lambda _event: self.render())
        self.refresh()

    def import_step(self) -> None:
        name = filedialog.askopenfilename(filetypes=(("STEP", "*.step *.stp"), ("All files", "*")))
        if not name:
            return
        try:
            source = Path(name)
            product = import_step(source)
            annotations = EngineeringAnnotations.for_product(
                product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
                process_type="manual MIG", production_quantity=1)
            self.project = FxdProject.from_product(product, annotations)
            self.kernel_meshes = ()
            try:
                kernel = OcpKernel()
                self.kernel_meshes = kernel.tessellate(kernel.import_step(source))
                message = f"Imported immutable STEP and {len(self.kernel_meshes)} selectable B-Rep face meshes."
            except KernelUnavailable:
                message = "Imported immutable source geometry; real-kernel display is unavailable and review remains provisional."
            self.refresh(message)
        except Exception as exc:
            messagebox.showerror("STEP import failed", str(exc))

    def open_project(self) -> None:
        name = filedialog.askopenfilename(filetypes=(("FXD project", "*.fxd.json"),))
        if not name:
            return
        try:
            self.project = FxdProject.load(name)
            self.kernel_meshes = ()
            self.selected_face = None
            self.refresh("Loaded neutral project; reimport STEP to restore real-kernel display meshes.")
        except Exception as exc:
            messagebox.showerror("Project load failed", str(exc))

    def save_project(self) -> None:
        if not self.project:
            return
        name = filedialog.asksaveasfilename(
            defaultextension=".fxd.json", filetypes=(("FXD project", "*.fxd.json"),))
        if name:
            self.project.save(name)
            self.status.set(f"Saved {Path(name).name}; production approval is not implied.")

    def refresh(self, message: str = "") -> None:
        self.concepts.delete(0, "end")
        if self.project:
            for concept in self.project.concepts:
                from fxd_geometry import validate_fixture_concept
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
                message = (f"Validation: {validation.status.upper()} · "
                           f"evidence {validation.evidence_digest[:12]}")
        if message:
            self.status.set(message)
        self.render()

    def select_concept(self, _event=None) -> None:
        if self.project and self.concepts.curselection():
            identity = self.project.concepts[self.concepts.curselection()[0]].identity
            self.project = self.project.with_concept(identity)
            self.refresh()

    def toggle(self, layer: str) -> None:
        if self.project:
            try:
                self.project = self.project.toggle_layer(layer)
                self.render()
            except ProjectFormatError as exc:
                messagebox.showerror("Layer change rejected", str(exc))

    def suppress_feature(self) -> None:
        if not self.project:
            return
        choices = ", ".join(feature.identity for feature in self.project.active.fixture.features)
        identity = simpledialog.askstring("Feature", f"Feature identity:\n{choices}")
        if not identity:
            return
        try:
            self.project = self.project.suppress(identity)
            self.refresh(f"Recorded validated feature edit: {identity}")
        except ProjectFormatError as exc:
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
                self.refresh("Correction recorded and deterministic validation rerun.")
            except (ProjectFormatError, ValueError) as exc:
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

    def rotate(self, event) -> None:
        if self.drag:
            x, y, yaw, pitch = self.drag
            self.yaw = yaw + (event.x - x) * 0.7
            self.pitch = max(-80, min(80, pitch + (event.y - y) * 0.7))
            self.render()

    def pick_face(self, event) -> None:
        current = self.canvas.find_withtag("current")
        if current:
            tags = self.canvas.gettags(current[0])
            selected = next((tag[5:] for tag in tags if tag.startswith("face:")), None)
            if selected:
                self.selected_face = selected
                self.status.set(f"Selected {selected}; linked to a stable kernel face reference.")
                self.render()
        self.drag = None

    def render(self) -> None:
        self.canvas.delete("all")
        if not self.project:
            self.canvas.create_text(30, 30, anchor="nw", fill="white",
                                    text="FXD visual engineering review\n\nDrag to rotate the 3D projection.")
            return
        if self.kernel_meshes and "product" not in self.project.hidden_layers:
            self._render_meshes(self.kernel_meshes)
        else:
            self._render_bounds()
        validation = self.project.active_validation
        banner_color = "#ff6666" if validation.blocked else "#ffd166"
        self.canvas.create_text(
            12, 12, anchor="nw", fill=banner_color,
            text=(f"{self.project.active.identity}: {validation.status.upper()} · "
                  f"evidence {validation.evidence_digest[:12]} — not production approval"))

    def _render_meshes(self, meshes: tuple[KernelTriangleMesh, ...]) -> None:
        vertices = [point for mesh in meshes for point in mesh.vertices_mm]
        if not vertices:
            return
        center = tuple((min(point[i] for point in vertices) + max(point[i] for point in vertices)) / 2
                       for i in range(3))
        span = max(max(point[i] for point in vertices) - min(point[i] for point in vertices)
                   for i in range(3)) or 1
        polygons = []
        for mesh in meshes:
            for triangle in mesh.triangles:
                points = [mesh.vertices_mm[index] for index in triangle]
                projected = [self.project_point(point, center, span) for point in points]
                depth = sum(point[2] for point in points) / 3
                polygons.append((depth, mesh.face_reference, projected))
        for _depth, reference, projected in sorted(polygons):
            color = "#ffffff" if reference == self.selected_face else "#66c2ff"
            flat = [coordinate for point in projected for coordinate in point]
            self.canvas.create_polygon(*flat, fill="#24445c", outline=color,
                                       tags=(f"face:{reference}", "kernel-mesh"))

    def _render_bounds(self) -> None:
        items = []
        if "product" not in self.project.hidden_layers:
            for component in self.project.product.components:
                for body in component.bodies:
                    items.append((f"{component.identity}/{body.identity}",
                                  body.bounds.transformed(component.transform), "#66c2ff"))
        concept = self.project.active
        if "fixture" not in self.project.hidden_layers:
            for feature in concept.fixture.features:
                if feature.identity in self.project.suppressed_features:
                    continue
                refs = ",".join(f"{ref.component_identity}/{ref.body_identity}"
                                for ref in feature.source_references) or "generated"
                items.append((f"{feature.identity} · {feature.rule} · {refs}",
                              feature.bounds, "#ffb347"))
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
        scale = min(self.canvas.winfo_width(), self.canvas.winfo_height()) * 0.72 / span
        return (self.canvas.winfo_width() / 2 + xr * scale,
                self.canvas.winfo_height() / 2 - yr * scale - zr * scale * 0.15)


def main() -> None:
    root = tk.Tk()
    FxdApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
