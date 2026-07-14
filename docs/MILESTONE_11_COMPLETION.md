# Milestone 11 completion — real geometry kernel

Milestone 11 is complete. This record supersedes the earlier blocked assessment in `docs/PROJECT_RECORD.md` without rewriting the historical audit trail.

FXD now uses the pinned `cadquery-ocp==7.9.3.1.1` runtime behind the CAD-neutral `RealKernel` boundary.

Verified engineering evidence:

- real STEP import and normalized deterministic STEP export;
- XCAF nested-assembly hierarchy with named components;
- composed component placements preserved as neutral 3x4 transforms;
- solid, shell, face, and edge topology;
- oriented unit face normals and stable neutral references;
- real Boolean fuse, cut, and common operations;
- real shape-to-shape clearance calculations;
- immutable source-file handling;
- explicit malformed, partial, missing, null, empty, and non-solid failures;
- AABB retained only as an explicit test double;
- OCP/OCCT licensing and future installer obligations recorded in `docs/THIRD_PARTY_GEOMETRY.md`.

The proof geometry is synthetic and contains no customer or employer CAD. Results are engineering evidence, not certification or production approval.

Evidence: `tests/test_kernel_boundary.py`, `scripts/kernel_proof.py`, `docs/GEOMETRY_KERNEL_BOUNDARY.md`, and `bash scripts/ci.sh`.
