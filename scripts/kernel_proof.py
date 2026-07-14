"""Exercise the pinned real B-Rep adapter without customer geometry."""
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Trsf, gp_Vec

from fxd_geometry.kernel import require_real_kernel

kernel = require_real_kernel()
left = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
translation = gp_Trsf()
translation.SetTranslation(gp_Vec(15.0, 0.0, 0.0))
right = BRepBuilderAPI_Transform(left, translation, False).Shape()

assert kernel.capabilities.is_complete
assert kernel.topology_counts(left).faces == 6
assert abs(kernel.clearance(left, right) - 5.0) < 1e-9
assert not kernel.boolean("fuse", left, right).IsNull()

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
assert kernel.export_step(kernel.import_step(step_bytes)) == kernel.export_step(
    kernel.import_step(step_bytes)
)

print(kernel.capabilities)
print("real OCP assembly, topology, Boolean, clearance, and round-trip proof passed")
