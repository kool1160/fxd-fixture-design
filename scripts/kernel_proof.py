"""Exercise the pinned real B-Rep adapter without customer geometry."""

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Trsf, gp_Vec

from fxd_geometry.kernel import require_real_kernel

kernel = require_real_kernel()
left = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
translation = gp_Trsf()
translation.SetTranslation(gp_Vec(15.0, 0.0, 0.0))
right = BRepBuilderAPI_Transform(left, translation, True).Shape()

assert kernel.capabilities.is_complete
assert kernel.topology_counts(left).faces == 6
assert abs(kernel.clearance(left, right) - 5.0) < 1e-9
assert not kernel.boolean("fuse", left, right).IsNull()
step_bytes = kernel.export_step(left)
assert kernel.topology_counts(kernel.import_step(step_bytes)) == kernel.topology_counts(left)

print(kernel.capabilities)
print("real OCP geometry proof passed")
