# Milestone 17 kernel acceptance evidence

## Accepted runtime gate

GitHub Actions Kernel acceptance passed with:

- Python 3.12
- `cadquery-ocp==7.9.3.1.1`
- the complete repository test suite
- the legally shareable synthetic STEP fixture

The runtime and manufacturing foundation first passed on `main` and the final
real-kernel visual application changes passed on PR #28 head
`72269104d8c297ed07766375ffcc4e7ebd9eb2f8`.

## Deterministic evidence proven

The real OCP path proves:

- STEP import and assembly hierarchy
- stable component and face references across reload
- topology inspection
- Boolean operations
- shape-to-shape distance and clearance
- contact versus volumetric penetration semantics
- zero-based tessellation linked to stable face references
- placed edge coordinates through the supported OCP curve adaptor
- kernel section geometry and selectable section edges
- deterministic normalized STEP output
- deterministic STEP and DXF manufacturing artifacts generated from one cut plan
- real-kernel manufacturability validation without kernel-operation failures
- product and fixture visual geometry generated from the same active concept and source hash
- exact feature-scoped findings rather than broadcasting one finding to every feature
- selectable faces and edges linked to rules, parameters, source references, and findings
- concept changes, feature suppression, corrections, and project reloads regenerate visual evidence
- visibly provisional AABB fallback when real-kernel evidence cannot be rebuilt

OCCT process-global `NEXT_ASSEMBLY_USAGE_OCCURRENCE` labels are canonicalized by
file order because those labels are writer metadata, not geometric identity.

## Closure

Milestone 17 is complete. Milestone 18 is the next Foreman target and owns the
parameter-edit, revision, regenerate, revalidate, compare, and restore workflow.
