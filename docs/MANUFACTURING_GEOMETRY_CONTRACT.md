# FXD manufacturing geometry contract

Milestone 14 adds an explicit hand-off from the CAD-neutral fixture concept to
reviewed kernel-authored solids.

`ManufacturingSpec` is public metadata attached to every generated feature. It
requires a fabrication method, material, fit, and explicit clearance and
allowance values; thickness, purchased-interface, and operations metadata are
also retained when applicable. Generic values are synthetic defaults, not shop
standards or certified process parameters.

`generate_manufacturing_geometry` requires a complete `RealKernel`. It creates
kernel solids for supported prismatic and cylindrical fixture features and
applies deterministic slot, relief, and pin-hole Boolean cuts. Each authored
result must contain a solid. Missing or incomplete kernels fail explicitly;
AABB geometry is never used as a manufacturing fallback. Product source
geometry remains immutable.

Supported B-Rep cuts and DXF profiles are generated from one shared immutable
operation plan. A slot, relief, or pin hole may not be added to STEP without the
same operation appearing in the manufacturing DXF. The plan carries stable
operation identity, owning fixture feature, operation kind, layer, and exact
dimensions. Regression tests require the baseplate pin hole, baseplate slots,
and supported reliefs to remain in parity across both artifacts.

Manufacturing geometry is cryptographically bound to the source assembly and
must contain every fixture feature exactly once in deterministic order. STEP
and DXF data are rejected when malformed or partial.

Free-form kernel-edge projection, bend-aware sheet profiles, tolerance-stack
analysis, validated purchased-tooling interfaces, force adequacy, and
production approval remain outside this phase. All packages remain
`engineering_review_required` and never imply fabrication approval.
