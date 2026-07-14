"""Dependency-free visual application boundary for FXD.

The browser client is intentionally a review surface, not a second geometry
engine.  It consumes immutable normalized product data and deterministic
concept/validation results; edits are stored as feature overrides beside the
source model.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .aabb import Aabb, Vec3
from .concepts import CompleteFixtureConcept, FixtureCorrection
from .product_model import ProductModel
from .validation import ValidationResult


@dataclass(frozen=True)
class FeatureOverride:
    identity: str
    state: str = "shown"  # shown, suppressed, or replaced
    replacement_kind: str | None = None
    replacement_bounds: Aabb | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.state not in {"shown", "suppressed", "replaced"}:
            raise ValueError("feature state must be shown, suppressed, or replaced")
        if self.state == "replaced" and self.replacement_bounds is None:
            raise ValueError("replaced features require replacement bounds")


@dataclass(frozen=True)
class VisualProject:
    """Complete local review state; source bytes remain immutable evidence."""

    product: ProductModel
    concept: CompleteFixtureConcept
    validation: ValidationResult
    overrides: tuple[FeatureOverride, ...] = ()
    visible_layers: tuple[str, ...] = (
        "product", "fixture", "datums", "welds", "access", "warnings",
    )
    approval_state: str = "review_required"
    revision: int = 0

    def __post_init__(self) -> None:
        if self.product.source_sha256 != self.concept.fixture.source_sha256:
            raise ValueError("visual project product and concept sources do not match")
        if self.validation.concept_identity != self.concept.identity:
            raise ValueError("visual project validation does not match concept")
        if self.approval_state not in {"review_required", "approved", "rejected"}:
            raise ValueError("approval state is not supported")

    @property
    def status(self) -> str:
        return self.validation.status

    def edit_feature(self, identity: str, *, state: str = "shown",
                     replacement_kind: str | None = None,
                     replacement_bounds: Aabb | None = None,
                     note: str = "") -> "VisualProject":
        if identity not in {feature.identity for feature in self.concept.fixture.features}:
            raise ValueError(f"unknown fixture feature: {identity}")
        override = FeatureOverride(identity, state, replacement_kind, replacement_bounds, note)
        existing = tuple(item for item in self.overrides if item.identity != identity)
        return replace(self, overrides=existing + (override,), revision=self.revision + 1,
                       approval_state="review_required")

    def set_layer(self, layer: str, visible: bool) -> "VisualProject":
        valid = {"product", "fixture", "datums", "welds", "access", "warnings"}
        if layer not in valid:
            raise ValueError(f"unknown visual layer: {layer}")
        layers = set(self.visible_layers)
        (layers.add if visible else layers.discard)(layer)
        return replace(self, visible_layers=tuple(sorted(layers)), revision=self.revision + 1)

    def approve(self) -> "VisualProject":
        if self.validation.blocked:
            raise ValueError("blocked validation results cannot be approved")
        return replace(self, approval_state="approved", revision=self.revision + 1)

    def reject(self) -> "VisualProject":
        return replace(self, approval_state="rejected", revision=self.revision + 1)


def _bounds(bounds: Aabb) -> dict[str, list[float]]:
    return {"min": [bounds.minimum.x, bounds.minimum.y, bounds.minimum.z],
            "max": [bounds.maximum.x, bounds.maximum.y, bounds.maximum.z]}


def scene_payload(project: VisualProject) -> dict[str, Any]:
    """Build a traceable, JSON-safe scene for the browser or another UI."""
    overrides = {item.identity: item for item in project.overrides}
    items: list[dict[str, Any]] = []
    if "product" in project.visible_layers:
        for component in project.product.components:
            for body in component.bodies:
                items.append({"identity": body.identity, "kind": "product", "component": component.identity,
                              "bounds": _bounds(body.bounds.transformed(component.transform)),
                              "source_reference": f"{component.identity}/{body.identity}", "state": "source_immutable"})
    if "fixture" in project.visible_layers:
        for feature in project.concept.fixture.features:
            override = overrides.get(feature.identity)
            if override and override.state == "suppressed":
                continue
            bounds, kind = feature.bounds, feature.kind
            if override and override.state == "replaced":
                bounds, kind = override.replacement_bounds, override.replacement_kind or feature.kind
            references = [f"{ref.component_identity}/{ref.body_identity}" for ref in feature.source_references]
            if not references:
                references = [f"rule:{feature.rule}"]
            items.append({"identity": feature.identity, "kind": kind, "bounds": _bounds(bounds),
                          "source_reference": references,
                          "rule": feature.rule, "parameters": feature.parameters,
                          "assumptions": feature.assumptions, "warnings": feature.warnings,
                          "state": "edited" if override else "generated"})
    findings = [item.__dict__ for item in project.validation.findings] if "warnings" in project.visible_layers else []
    return {"schema": "fxd-visual-scene-v1", "units": "mm", "revision": project.revision,
            "status": project.status, "approval_state": project.approval_state,
            "visible_layers": project.visible_layers, "concept": project.concept.identity,
            "source_sha256": project.product.source_sha256, "items": items, "findings": findings}


def save_project(project: VisualProject, destination: str | Path) -> Path:
    """Save a self-contained neutral project, including source identity/evidence."""
    payload = {"schema": "fxd-project-v1", "source_step_b64": base64.b64encode(project.product.source_bytes).decode("ascii"),
               "source_name": project.product.source_name, "scene": scene_payload(project),
               "overrides": [{"identity": x.identity, "state": x.state, "replacement_kind": x.replacement_kind,
                              "replacement_bounds": _bounds(x.replacement_bounds) if x.replacement_bounds else None, "note": x.note}
                             for x in project.overrides]}
    path = Path(destination)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_project(source: str | Path, rebuild: Any) -> VisualProject:
    """Reload source evidence and use caller-supplied deterministic rebuild logic."""
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if payload.get("schema") != "fxd-project-v1":
        raise ValueError("unsupported FXD project schema")
    product, concept, validation = rebuild(base64.b64decode(payload["source_step_b64"]), payload.get("source_name", "project.step"))
    overrides = []
    for raw in payload.get("overrides", []):
        rb = raw.get("replacement_bounds")
        bounds = Aabb(Vec3(*rb["min"]), Vec3(*rb["max"])) if rb else None
        overrides.append(FeatureOverride(raw["identity"], raw["state"], raw.get("replacement_kind"), bounds, raw.get("note", "")))
    return VisualProject(product, concept, validation, tuple(overrides))


HTML = """<!doctype html><meta charset=utf-8><title>FXD Engineering Review</title>
<style>body{margin:0;background:#151a21;color:#e8edf2;font:14px system-ui;display:flex;height:100vh}aside{width:280px;padding:20px;background:#202731;overflow:auto}main{flex:1;position:relative}canvas{width:100%;height:100%;cursor:grab}h1{font-size:20px}.badge{padding:5px 8px;border-radius:4px;background:#b57918}.badge.invalid{background:#a62d38}.badge.valid{background:#287c52}label{display:block;margin:10px 0}button{margin:4px 0;padding:7px;background:#334152;color:white;border:1px solid #607083;border-radius:3px}</style>
<aside><h1>FXD engineering review</h1><div id=status class=badge>loading</div><p id=meta></p><h3>Layers</h3><div id=layers></div><h3>Deterministic findings</h3><div id=findings></div><p>Drag the view to rotate. Generated, edited, and immutable source items remain distinguishable in the scene.</p></aside><main><canvas id=view></canvas></main>
<script>const c=document.querySelector('canvas'),x=c.getContext('2d');let scene,ang=0,drag=false,last=0;fetch('/api/scene').then(r=>r.json()).then(v=>{scene=v;render();status.textContent=v.status+' / '+v.approval_state;status.className='badge '+v.status;meta.textContent='Concept '+v.concept+' · revision '+v.revision+' · '+v.source_sha256.slice(0,12);layers.innerHTML=['product','fixture','datums','welds','access','warnings'].map(k=>`<label><input type=checkbox ${v.visible_layers.includes(k)?'checked':''} onchange="layer('${k}',this.checked)">${k}</label>`).join('');findings.innerHTML=v.findings.map(f=>`<p><b>${f.severity}</b> ${f.code}<br>${f.message}</p>`).join('')||'<p>none recorded</p>'});function layer(k,on){fetch('/api/layer',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({layer:k,visible:on})}).then(r=>r.json()).then(v=>{scene=v;render()})}function render(){c.width=c.clientWidth*devicePixelRatio;c.height=c.clientHeight*devicePixelRatio;x.scale(devicePixelRatio,devicePixelRatio);x.clearRect(0,0,c.clientWidth,c.clientHeight);if(!scene)return;let w=c.clientWidth,h=c.clientHeight,pts=scene.items.flatMap(i=>[i.bounds.min,i.bounds.max]),min=pts.reduce((a,p)=>a.map((v,j)=>Math.min(v,p[j])),[Infinity,Infinity,Infinity]),max=pts.reduce((a,p)=>a.map((v,j)=>Math.max(v,p[j])),[-Infinity,-Infinity,-Infinity]),s=Math.min(w/(max[0]-min[0]||1),h/(max[1]-min[1]||1))*.65;for(const i of scene.items){let b=i.bounds,minx=(b.min[0]+b.max[0])/2,miny=(b.min[1]+b.max[1])/2,px=w/2+(minx-(min[0]+max[0])/2)*s*Math.cos(ang)-(miny-(min[1]+max[1])/2)*s*Math.sin(ang),py=h/2+(minx-(min[0]+max[0])/2)*s*Math.sin(ang)+(miny-(min[1]+max[1])/2)*s*.35*Math.cos(ang)-(b.max[2]-b.min[2])*s*.25;x.fillStyle=i.kind==='product'?'#4da3d9':i.state==='edited'?'#e2b84d':'#d56c55';x.globalAlpha=i.kind==='product'?.35:.7;x.fillRect(px-20,py-20,40,40);x.globalAlpha=1;x.fillStyle='#fff';x.fillText(i.identity,px-20,py-25)}}c.onpointerdown=e=>{drag=true;last=e.clientX};c.onpointerup=()=>drag=false;c.onpointermove=e=>{if(drag){ang+=(e.clientX-last)/100;last=e.clientX;render()}};onresize=render;</script>"""


def serve(project: VisualProject, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Serve the local review UI; caller owns the server lifecycle."""
    class Handler(BaseHTTPRequestHandler):
        current = project
        def do_GET(self):
            body = HTML.encode() if self.path == "/" else json.dumps(scene_payload(self.current)).encode()
            self.send_response(200); self.send_header("Content-Type", "text/html" if self.path == "/" else "application/json"); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            size = int(self.headers.get("Content-Length", 0)); data = json.loads(self.rfile.read(size))
            if self.path == "/api/layer": Handler.current = Handler.current.set_layer(data["layer"], bool(data["visible"]))
            elif self.path == "/api/feature":
                replacement = data.get("replacement_bounds")
                bounds = (Aabb(Vec3(*replacement["min"]), Vec3(*replacement["max"]))) if replacement else None
                Handler.current = Handler.current.edit_feature(
                    data["identity"], state=data.get("state", "shown"),
                    replacement_kind=data.get("replacement_kind"), replacement_bounds=bounds,
                    note=data.get("note", ""))
            else: self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(scene_payload(Handler.current)).encode())
        def log_message(self, *_): pass
    return ThreadingHTTPServer((host, port), Handler)
