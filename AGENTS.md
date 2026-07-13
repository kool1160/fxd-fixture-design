# FXD AI Agent Instructions

All AI coding agents working on FXD must read and follow, in order:

1. `AGENTS.md`
2. `docs/PRODUCT_DIRECTION.md`
3. `docs/ENGINEERING_CONSTITUTION.md`
4. `docs/ARCHITECTURE.md`
5. `BACKLOG.md`

The Engineering Constitution is the highest-priority engineering standard. Product Direction governs what FXD is becoming. The Backlog controls implementation order.

## Product identity

FXD is industrial fixture-design software, beginning with weld fixtures for sheet-metal and fabricated products. It is not a generic chatbot, a contour-skeleton generator, a replacement CAD kernel, or a system that may claim a fixture is production-safe without engineering validation.

## Working style

- Treat each selected milestone as one complete outcome.
- Inspect the real repository before editing.
- Make routine technical decisions without asking Chris when the governing documents are clear.
- Prefer runnable evidence over architecture theater.
- Keep the CAD-neutral core separate from vendor-specific connectors.
- Keep critical engineering decisions deterministic, testable, and explainable.
- Do not publish proprietary fixture heuristics, unreleased invention details, customer geometry, employer data, or confidential shop standards.

## Specialist roles

The Foreman may reason through these roles or assign focused work where supported:

- **Geometry Agent:** topology, transforms, intersections, clearance, spatial indexing, STEP data.
- **Fixture Engineering Agent:** locating schemes, constraints, supports, stops, pins, clamps, and removability.
- **Weld Process Agent:** weld-joint access, torch approach, tack sequence assumptions, heat-sensitive constraints.
- **Manufacturing Agent:** laser-cut construction, formed parts, purchased hardware, tolerances, cost and assembly practicality.
- **CAD Integration Agent:** neutral export and vendor connector contracts.
- **Validation Agent:** invariants, golden models, collision tests, traceability, and regression evidence.
- **UX Agent:** engineer-facing workflows that expose assumptions and allow correction.

No specialist may override the Engineering Constitution.

## Stop-and-ask boundaries

Stop and obtain explicit approval immediately before:

- publishing a proprietary rule pack, secret algorithm, patent-sensitive method, or private research material
- adding a dependency with unclear, viral, commercial, or incompatible licensing
- purchasing or enabling a paid service
- accepting a vendor SDK agreement or distributing vendor-owned binaries
- changing the product from assistive engineering software into unattended production release
- representing generated fixtures as certified, validated, or safe for production without evidence
- processing real customer or employer CAD data in public CI
- deploying a public service, authentication system, billing system, or customer-data backend
- destructive repository, artifact, or data operations
- filing or publicly describing a potentially patentable implementation beyond the approved disclosure level

Agents may prepare code, tests, documents, and exact execution plans up to these boundaries.

## Milestone execution

For each milestone:

1. Read the governing documents.
2. Inspect the repository and report material differences.
3. Complete all safe internal phases.
4. Add tests or reproducible evidence appropriate to the risk.
5. Run `bash scripts/ci.sh` and relevant project checks.
6. Fix failures caused by the work.
7. Review the final diff.
8. Update project records only when evidence supports the claim.
9. Stop only at a real approval boundary or material blocker.
10. Finish with the structured Planning Handoff required by the Foreman schema.

## Completion standard

A milestone is not complete because a plan exists. Completion requires implementation or research evidence matching the milestone acceptance criteria, with changed files, checks, risks, and unresolved items recorded.
