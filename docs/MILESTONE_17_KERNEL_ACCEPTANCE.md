# Milestone 17 kernel acceptance evidence

## Accepted runtime gate

GitHub Actions Kernel acceptance run 45 passed on commit
`1452fa8e8a8345e02804221aad8d7eb1de24c226` using:

- Python 3.12
- `cadquery-ocp==7.9.3.1.1`
- 82 repository tests
- the legally shareable synthetic STEP fixture

The workflow is parser-safe and automatically maintains Issue #27 as the latest
kernel diagnostic record. The issue closes on success and reopens on failure.

## Deterministic evidence proven

The real OCP path now proves:

- STEP import and assembly hierarchy
- stable component and face references across reload
- topology inspection
- Boolean operations
- shape-to-shape distance and clearance
- contact versus volumetric penetration semantics
- zero-based tessellation linked to stable face references
- placed edge coordinates through the supported OCP curve adaptor
- section geometry
- deterministic normalized STEP output
- deterministic STEP and DXF manufacturing artifacts generated from one cut plan
- real-kernel manufacturability validation without kernel-operation failures

OCCT process-global `NEXT_ASSEMBLY_USAGE_OCCURRENCE` labels are canonicalized by
file order because those labels are writer metadata, not geometric identity.

## Remaining Milestone 17 application work

Milestone 17 should remain Pending until the engineer-facing application also
completes the visual exposure criteria:

- render and select real fixture B-Rep geometry, not only imported product faces
- expose holes, slots, tabs, risers, pins, supports, and clamps as selectable items
- link selected visual items to rules, parameters, geometry references, and findings
- provide section, transparency, wireframe, fit-to-view, and collision highlighting
- keep provisional fallback geometry visually unmistakable when OCP evidence is unavailable

The next Foreman run should continue Milestone 17 from this accepted kernel
foundation rather than rebuilding the runtime gate.
