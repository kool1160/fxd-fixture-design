"""FXD local engineering review application (dependency-free Tkinter shell)."""

from __future__ import annotations

import math
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

from fxd_geometry import EngineeringAnnotations, Vec3, import_step
from fxd_geometry.project import FxdProject


class FxdApp:
    def __init__(self, root: tk.Tk, project: FxdProject | None = None) -> None:
        self.root, self.project = root, project
        self.yaw, self.pitch, self.drag = 35.0, 22.0, None
        root.title("FXD — Engineering Review (not production approval)")
        root.geometry("1180x760")
        self.status = tk.StringVar(value="Open a legally shareable STEP assembly to begin.")
        self.canvas = tk.Canvas(root, background="#18212b", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        side = ttk.Frame(root, padding=10, width=300)
        side.pack(side="right", fill="y")
        ttk.Button(side, text="Import STEP", command=self.import_step).pack(fill="x")
        ttk.Button(side, text="Open FXD project", command=self.open_project).pack(fill="x", pady=3)
        ttk.Button(side, text="Save FXD project", command=self.save_project).pack(fill="x", pady=3)
        self.concepts = tk.Listbox(side, height=5, exportselection=False)
        self.concepts.pack(fill="x", pady=8); self.concepts.bind("<<ListboxSelect>>", self.select_concept)
        ttk.Label(side, text="Layers").pack(anchor="w")
        for layer in ("product", "fixture", "welds", "access", "datums", "warnings"):
            ttk.Button(side, text=f"Toggle {layer}", command=lambda item=layer: self.toggle(item)).pack(fill="x", pady=1)
        ttk.Button(side, text="Suppress / unsuppress selected feature", command=self.suppress_feature).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Record correction", command=self.correct).pack(fill="x", pady=2)
        ttk.Button(side, text="Approve for engineering review", command=lambda: self.decide("approve_for_review")).pack(fill="x", pady=(8, 2))
        ttk.Button(side, text="Reject concept", command=lambda: self.decide("reject")).pack(fill="x")
        ttk.Label(side, textvariable=self.status, wraplength=270).pack(anchor="w", pady=12)
        self.canvas.bind("<ButtonPress-1>", self.start_drag); self.canvas.bind("<B1-Motion>", self.rotate)
        self.canvas.bind("<Configure>", lambda _event: self.render())
        self.render()

    def import_step(self) -> None:
        name = filedialog.askopenfilename(filetypes=(("STEP", "*.step *.stp"), ("All files", "*")))
        if not name: return
        try:
            product = import_step(Path(name))
            annotations = EngineeringAnnotations.for_product(product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0), process_type="manual MIG", production_quantity=1)
            self.project = FxdProject.from_product(product, annotations); self.refresh("Imported source geometry; review evidence is provisional.")
        except Exception as exc: messagebox.showerror("STEP import failed", str(exc))

    def open_project(self) -> None:
        name = filedialog.askopenfilename(filetypes=(("FXD project", "*.fxd.json"),))
        if name:
            try: self.project = FxdProject.load(name); self.refresh("Loaded neutral project; source geometry remains immutable.")
            except Exception as exc: messagebox.showerror("Project load failed", str(exc))

    def save_project(self) -> None:
        if not self.project: return
        name = filedialog.asksaveasfilename(defaultextension=".fxd.json", filetypes=(("FXD project", "*.fxd.json"),))
        if name: self.project.save(name); self.status.set(f"Saved {Path(name).name}; production approval is not implied.")

    def refresh(self, message: str = "") -> None:
        self.concepts.delete(0, "end")
        if self.project:
            for concept in self.project.concepts: self.concepts.insert("end", f"{concept.identity} — {concept.engineering_status.upper()}")
            self.concepts.selection_set(next(i for i, item in enumerate(self.project.concepts) if item.identity == self.project.active_concept))
        if message: self.status.set(message)
        self.render()

    def select_concept(self, _event=None) -> None:
        if self.project and self.concepts.curselection(): self.project = self.project.with_concept(self.project.concepts[self.concepts.curselection()[0]].identity); self.render()

    def toggle(self, layer: str) -> None:
        if self.project: self.project = self.project.toggle_layer(layer); self.render()

    def suppress_feature(self) -> None:
        if not self.project: return
        identity = simpledialog.askstring("Feature", "Feature identity to suppress/unsuppress:")
        if identity: self.project = self.project.suppress(identity); self.status.set(f"Recorded feature edit: {identity}"); self.render()

    def correct(self) -> None:
        if not self.project: return
        key = simpledialog.askstring("Correction", "Correction key:")
        value = simpledialog.askstring("Correction", "Replacement value:")
        reason = simpledialog.askstring("Correction", "Reason:")
        if key and value and reason: self.project = self.project.correct(key, value, reason); self.status.set("Correction recorded as an editable review decision.")

    def decide(self, action: str) -> None:
        if self.project: self.project = self.project.decide(action, "Human review action recorded locally."); self.status.set(f"Recorded {action}; this is not production approval.")

    def start_drag(self, event) -> None: self.drag = (event.x, event.y, self.yaw, self.pitch)
    def rotate(self, event) -> None:
        if self.drag: x, y, yaw, pitch = self.drag; self.yaw = yaw + (event.x-x)*0.7; self.pitch = max(-80, min(80, pitch + (event.y-y)*0.7)); self.render()

    def render(self) -> None:
        self.canvas.delete("all")
        if not self.project: self.canvas.create_text(30, 30, anchor="nw", fill="white", text="FXD visual engineering review\n\nDrag to rotate the 3D projection.") ; return
        items = []
        if "product" not in self.project.hidden_layers:
            for component in self.project.product.components:
                for body in component.bodies: items.append((component.name, body.bounds.transformed(component.transform), "#66c2ff"))
        concept = self.project.active
        if "fixture" not in self.project.hidden_layers:
            items += [(feature.identity, feature.bounds, "#ffb347") for feature in concept.fixture.features if feature.identity not in self.project.suppressed_features]
        if not items: return
        points = [p for _, box, _ in items for p in (box.minimum, box.maximum)]
        center = tuple((min(getattr(p, axis) for p in points)+max(getattr(p, axis) for p in points))/2 for axis in "xyz")
        span = max(max(getattr(p, axis) for p in points)-min(getattr(p, axis) for p in points) for axis in "xyz") or 1
        projected = []
        for name, box, color in items:
            corners = [(x,y,z) for x in (box.minimum.x,box.maximum.x) for y in (box.minimum.y,box.maximum.y) for z in (box.minimum.z,box.maximum.z)]
            xy = [self.project_point(c, center, span) for c in corners]; projected.append((name, box, color, xy))
        for name, box, color, xy in projected:
            x0,y0 = min(x for x,y in xy), min(y for x,y in xy); x1,y1 = max(x for x,y in xy), max(y for x,y in xy)
            self.canvas.create_rectangle(x0,y0,x1,y1, outline=color, width=2, stipple="gray50" if color=="#555" else "")
            self.canvas.create_text(x0+3,y0+3, anchor="nw", fill=color, text=name)
        self.canvas.create_text(12,12,anchor="nw",fill="#ff6666" if concept.engineering_status=="invalid" else "#ffd166", text=f"{concept.identity}: {concept.engineering_status.upper()} — not production approval")

    def project_point(self, point, center, span):
        x,y,z = (point[i]-center[i] for i in range(3)); ya, pi = math.radians(self.yaw), math.radians(self.pitch)
        xr, zr = x*math.cos(ya)-z*math.sin(ya), x*math.sin(ya)+z*math.cos(ya); yr = y*math.cos(pi)-zr*math.sin(pi)
        zr = y*math.sin(pi)+zr*math.cos(pi); scale=min(self.canvas.winfo_width(), self.canvas.winfo_height())*0.72/span
        return (self.canvas.winfo_width()/2+xr*scale, self.canvas.winfo_height()/2-yr*scale-zr*scale*0.15)


def main() -> None:
    root = tk.Tk(); FxdApp(root); root.mainloop()


if __name__ == "__main__": main()
