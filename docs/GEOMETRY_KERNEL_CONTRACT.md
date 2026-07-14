# FXD geometry-kernel contract — Milestone 11

`fxd_geometry.kernel` is the CAD-neutral boundary for a reviewed B-Rep
implementation. Adapters expose capability metadata and exchange neutral
FXD-owned model values; vendor kernel objects must not cross into product,
fixture, annotation, or connector contracts.

The boundary requires explicit support for millimetre units, immutable source
bytes and identity, STEP import/export, assembly transforms, topology, Boolean
operations, and distance/clearance checks. An adapter must fail clearly for
malformed, partial, or unsupported input and must provide deterministic output.

`AabbTestDouble` is the only dependency-free implementation. It is suitable
for existing proof-layer tests and explicitly rejects real STEP operations.
`reviewed_kernel()` fails closed while no concrete kernel has passed package,
license, representative-fixture, and redistribution review.

This contract is not evidence that a B-Rep kernel is selected or installed.
The current repository therefore does not claim Milestone 11 complete.
