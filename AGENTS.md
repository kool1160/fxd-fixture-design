# FXD AI Agent Instructions

All AI coding agents working on FXD must read and follow, in order:

1. `AGENTS.md`
2. `docs/PRODUCT_DIRECTION.md`
3. `docs/ENGINEERING_CONSTITUTION.md`
4. `docs/ARCHITECTURE.md`
5. `docs/ENGINEERING_TEAM.md`
6. `BACKLOG.md`
7. `docs/ROADMAP_QUEUE.md`
8. `docs/STRATEGY_HANDOFF.md`

The Engineering Constitution is the highest-priority engineering standard. Product Direction governs what FXD is becoming. The Engineering Team charter defines discipline ownership and collaboration. `BACKLOG.md` controls implementation order through Milestone 20. After Milestone 20, the governed implementation order continues in `docs/ROADMAP_QUEUE.md`. `docs/STRATEGY_HANDOFF.md` records the current cross-chat repository and workflow state but does not override either milestone queue.

## Product identity

FXD is industrial fixture-design software, beginning with weld fixtures for sheet-metal and fabricated products. It is not a generic chatbot, a contour-skeleton generator, a replacement CAD kernel, or a system that may claim a fixture is production-safe without engineering validation.

## Working style

- Treat each selected milestone as one complete outcome.
- Inspect the real repository before editing.
- Make routine technical decisions without asking Chris when the governing documents are clear.
- Prefer runnable evidence over architecture theater.
- Keep the CAD-neutral core separate from vendor-specific connectors.
- Keep critical engineering decisions deterministic, testable, and explainable.
- Apply every materially relevant specialist perspective from `docs/ENGINEERING_TEAM.md`.
- Record specialist disagreement, assumptions, and unresolved risk rather than silently averaging them away.
- Do not publish proprietary fixture heuristics, unreleased invention details, customer geometry, employer data, or confidential shop standards.

## Engineering-team model

The FXD Foreman coordinates an engineering organization, not a collection of generic coding personas.

`docs/ENGINEERING_TEAM.md` is the authoritative role charter. The older `docs/AGENT_ROSTER.md` is a concise compatibility summary and must not override the team charter.

For each milestone, the Foreman must identify which disciplines are materially affected, apply their required questions and responsibility boundaries, and integrate one reviewable result.

No specialist may override the Engineering Constitution, deterministic validation, or protected approval boundaries.

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
3. Identify the engineering disciplines materially affected.
4. Apply those specialist perspectives before finalizing implementation decisions.
5. Complete all safe internal phases.
6. Add tests or reproducible evidence appropriate to the risk.
7. Run `bash scripts/ci.sh` and relevant project checks.
8. Fix failures caused by the work.
9. Review the final diff.
10. Update project records only when evidence supports the claim.
11. Stop only at a real approval boundary or material blocker.
12. Finish with the structured Planning Handoff required by the Foreman schema.

## Completion standard

A milestone is not complete because a plan exists. Completion requires implementation or research evidence matching the milestone acceptance criteria, with changed files, checks, discipline impacts, risks, disagreements, and unresolved items recorded.
