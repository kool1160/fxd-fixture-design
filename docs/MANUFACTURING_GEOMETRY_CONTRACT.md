# FXD manufacturing geometry contract

Milestone 14 adds an explicit hand-off from the CAD-neutral fixture concept to
reviewed kernel-authored solids.

`ManufacturingSpec` is public metadata attached to every generated feature. It
requires a fabrication method, material, fit, and explicit clearance and
allowance values; thickness, purchased-interface, and operations metadata are
also retained when applicable. Generic values are synthetic defaults, not shop
standards or certified process parameters.

`generate_manufacturing_geometry` requires a complete `RealKernel`. It creates
kernel solids for the supported prismatic and cylindrical features, applies
explicit slot, relief, and pin-hole tools through Boolean cuts, verifies that
each result contains a solid, preserves feature identity and manufacturing
metadata, and exports the resulting compound through the kernel boundary.
Missing or incomplete kernels fail explicitly; AABB geometry is never used as
a manufacturing fallback. Product source geometry remains immutable.

The supported authored profiles are exported as deterministic neutral DXF
entities from the same dimensions used to build the kernel solids. Free-form
kernel-edge projection, bend-aware sheet profiles, tolerance-stack analysis,
and validated purchased-tooling interfaces remain outside this phase. All
packages remain `engineering_review_required` and never imply fabrication
approval.
