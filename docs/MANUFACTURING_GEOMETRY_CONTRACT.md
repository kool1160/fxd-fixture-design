# FXD manufacturing geometry contract

Milestone 14 adds an explicit hand-off from the CAD-neutral fixture concept to
reviewed kernel-authored solids.

`ManufacturingSpec` is public metadata attached to every generated feature. It
requires a fabrication method, material, fit, and explicit clearance and
allowance values; thickness, purchased-interface, and operations metadata are
also retained when applicable. Generic values are synthetic defaults, not shop
standards or certified process parameters.

`generate_manufacturing_geometry` requires a complete `RealKernel`. It creates
opaque boxes and cylinders, preserves feature identity and manufacturing
metadata, and exports the resulting compound through the kernel boundary.
Missing or incomplete kernels fail explicitly; AABB geometry is never used as
a manufacturing fallback. Product source geometry remains immutable.

The current safe internal phase does not yet author dedicated tab, slot,
relief, or pin-hole cut operations, nor does it derive true DXF profiles from
kernel edges. Those are required before this milestone can be marked
complete. All packages remain `engineering_review_required` and never imply
fabrication approval.
