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

`OcpKernel` now provides real STEP import/export, topology counts, Boolean
operations, and shape-to-shape clearance. `require_real_kernel()` never falls
back to AABB geometry. The AABB module remains a test double only.

## Acceptance evidence currently implemented

- pinned runtime installed by `scripts/ci.sh`;
- synthetic true B-Rep box topology proof;
- real OCCT Boolean and clearance proof;
- STEP export, byte import, reload, and topology reconciliation;
- explicit failures for missing runtime, missing files, unreadable STEP,
  unsupported Boolean operations, and null/empty import results;
- runnable `scripts/kernel_proof.py`.

## Remaining Milestone 11 work

Before Milestone 11 is marked complete, the adapter still needs a legally
shareable multi-component STEP assembly proof covering hierarchy and composed
transforms, face normals, stable neutral geometry references across reloads,
and malformed/partial assembly cases. Those references must be neutral records,
not persisted OCCT object addresses or transient topology handles.

No output from this adapter is certified or production approved. Source CAD
must remain immutable, and packaging review is required before distributing the
runtime in an installer.
