# Geometry-kernel boundary — Milestone 11

FXD's engineering core depends on a CAD-neutral `RealKernel` contract in
`fxd_geometry/kernel.py`. Kernel objects are opaque to the product model and
must not cross into fixture, annotation, AI, or connector code. An adapter is
responsible for translating real STEP solids, shells, faces, edges, and
placements into neutral records while preserving immutable source identity.

The current checkout deliberately contains no kernel dependency. `OCC` and
`OCP` are detected only for diagnostics; neither is imported or treated as
approved. `require_real_kernel()` fails explicitly rather than falling back to
the AABB test double. The AABB module is therefore a test double only, not a
partial production implementation.

## Acceptance gate before enabling an adapter

The Foreman must record the exact backend and binding versions, licenses,
transitive dependencies, binary redistribution obligations, and supported
platforms. A legally shareable synthetic STEP corpus must then prove:

- assembly hierarchy, stable component identity, and composed transforms;
- immutable source bytes and explicit units;
- solid/shell/face/edge topology and stable reference behavior after reload;
- Boolean, distance, interference, and clearance operations;
- deterministic STEP round-trip output; and
- clear failures for malformed, partial, and unsupported input.

No result from the current AABB proof may be described as B-Rep, fabrication
ready, certified, or production approved.

