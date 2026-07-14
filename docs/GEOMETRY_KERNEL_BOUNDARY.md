# Geometry-kernel boundary — Milestone 11

FXD's engineering core depends on the CAD-neutral `RealKernel` contract in
`fxd_geometry/kernel.py`. Kernel objects are opaque to the product model and
must not cross into fixture, annotation, AI, knowledge, or connector code.

The approved development backend is:

- `cadquery-ocp==7.9.3.1.1`
- OCP thin Python binding for Open CASCADE Technology
- binding license: Apache-2.0
- underlying OCCT runtime: LGPL-2.1 with the Open CASCADE exception

Exact dependency and packaging obligations are recorded in
`docs/THIRD_PARTY_GEOMETRY.md`.

`OcpKernel` provides real STEP import/export, XCAF assembly hierarchy,
composed component placements, topology counts, oriented face normals,
Boolean operations, shape-to-shape clearance/interference, sectioning,
topological edge records, and display tessellation. Tessellation records keep
each triangle mesh linked to a stable face reference; they are display data,
not a replacement for B-Rep validation. `require_real_kernel()` never falls
back to AABB geometry. The AABB module remains a test double only.

## Acceptance evidence

- pinned runtime installed by `scripts/ci.sh`;
- synthetic true B-Rep box topology proof;
- real OCCT Boolean and clearance proof;
- deterministic STEP export after normalizing OCCT-generated timestamps and
  transient translator sequence labels;
- XCAF nested-assembly proof with named components and composed transforms;
- neutral root, assembly, component, and face references stable across reloads;
- face area, sample center, and oriented unit-normal records;
- immutable source-file proof;
- explicit failures for missing files, malformed or partial STEP, unsupported
  Boolean operations, null/empty imports, and non-solid STEP content;
- runnable `scripts/kernel_proof.py` and unit regression coverage.

The synthetic assembly and solids contain no customer or employer geometry.
No output from this adapter is certified or production approved. Packaging
review remains required before distributing the runtime in an installer.
