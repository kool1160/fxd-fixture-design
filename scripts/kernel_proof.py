"""Exercise the pinned real B-Rep adapter without customer geometry."""
from pathlib import Path
import difflib
import hashlib
import sys

# Direct execution (``python scripts/kernel_proof.py``) puts ``scripts`` rather
# than the repository root on sys.path. Add the root explicitly so the proof
# exercises the checked-out FXD package instead of depending on installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Trsf, gp_Vec

from fxd_geometry import require_real_kernel


def translated(shape: object, x_mm: float) -> object:
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(x_mm, 0.0, 0.0))
    return BRepBuilderAPI_Transform(shape, transform, False).Shape()


kernel = require_real_kernel()
assert kernel.__class__.__module__ == "fxd_geometry.review_kernel"

left = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
right = translated(left, 15.0)
touching = translated(left, 10.0)
overlapping = translated(left, 9.0)

assert kernel.capabilities.is_complete
assert kernel.topology_counts(left).faces == 6
assert abs(kernel.clearance(left, right) - 5.0) < 1e-9
assert not kernel.boolean("fuse", left, right).IsNull()
assert not kernel.intersects(left, touching)
assert kernel.intersects(left, overlapping)

meshes = kernel.tessellate(left)
assert len(meshes) == 6
assert all(mesh.vertices_mm and mesh.triangles for mesh in meshes)
assert all(
    0 <= vertex_index < len(mesh.vertices_mm)
    for mesh in meshes
    for triangle in mesh.triangles
    for vertex_index in triangle
)

edges = kernel.edge_records(right)
assert len(edges) == 12
assert all(
    15.0 - 1e-9 <= point[0] <= 25.0 + 1e-9
    for edge in edges
    for point in (edge.start_mm, edge.end_mm)
)

section = kernel.section(left, (5.0, 0.0, 0.0), (1.0, 0.0, 0.0))
assert kernel.topology_counts(section).edges > 0

compound = TopoDS_Compound()
builder = BRep_Builder()
builder.MakeCompound(compound)
builder.Add(compound, left)
builder.Add(compound, right)
step_bytes = kernel.export_step(compound)
assembly = kernel.import_step_assembly(step_bytes)
assert len(assembly.components) == 2
assert all(component.faces for component in assembly.components)

reloaded = kernel.import_step_assembly(
    kernel.export_step(kernel.import_step(step_bytes))
)
assert tuple(component.reference for component in assembly.components) == tuple(
    component.reference for component in reloaded.components
)

first = kernel.export_step(kernel.import_step(step_bytes))
second = kernel.export_step(kernel.import_step(step_bytes))
if first != second:
    print("STEP export determinism mismatch")
    print("first sha256:", hashlib.sha256(first).hexdigest(), "bytes:", len(first))
    print("second sha256:", hashlib.sha256(second).hexdigest(), "bytes:", len(second))
    first_lines = first.decode("utf-8", errors="replace").splitlines()
    second_lines = second.decode("utf-8", errors="replace").splitlines()
    for line in list(difflib.unified_diff(
        first_lines, second_lines, fromfile="first.step", tofile="second.step", lineterm=""
    ))[:400]:
        print(line)
    raise AssertionError("normalized STEP exports are not deterministic")

print(kernel.capabilities)
print(
    "real OCP assembly, topology, Boolean, clearance, contact semantics, "
    "tessellation, transformed edges, sectioning, and deterministic round-trip proof passed"
)
