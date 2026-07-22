# FXD AI Agent Instructions

All AI coding agents working on FXD must read and follow, in order:

1. `AGENTS.md`
2. `docs/PRODUCT_DIRECTION.md`
3. `docs/ENGINEERING_CONSTITUTION.md`
4. `docs/ARCHITECTURE.md`
5. `docs/ENGINEERING_TEAM.md`
6. `docs/MILESTONE_CONTRACT.md`
7. `docs/MILESTONE_STATE.json`
8. the Active milestone's authoritative GitHub issue
9. `BACKLOG.md`
10. `docs/ROADMAP_QUEUE.md`
11. `docs/STRATEGY_HANDOFF.md`

The Engineering Constitution is the highest-priority engineering standard. Product Direction governs what FXD is becoming. Accepted architecture and decision records govern technical boundaries, and the Engineering Team charter defines discipline ownership and collaboration. `docs/MILESTONE_CONTRACT.md` governs milestone sequence and completion. `docs/MILESTONE_STATE.json` is the sole current status projection. The Active milestone issue governs its approved scope. Backlogs, roadmaps, strategy handoffs, project records, workbench guides, and binders are derived context and cannot override those authorities.

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
2. Validate the registry and confirm exactly one Active product milestone, or a formally paused lane.
3. Read the complete authoritative milestone issue and any bounded child issues.
4. Inspect the repository and report material differences.
5. Identify the engineering disciplines materially affected.
6. Apply those specialist perspectives before finalizing implementation decisions.
7. Complete all safe internal phases inside the issue and implementation-PR boundaries.
8. Add tests or reproducible evidence for every required evidence profile.
9. Run `bash scripts/ci.sh` and relevant project checks.
10. Fix failures caused by the work.
11. Review the final diff.
12. Update derived records only when evidence supports the update; never change status outside the registry.
13. Preserve the post-governance closeout boundary: a closeout evidence PR while the milestone remains Active, followed after merge by a distinct state-finalization PR that records the now-existing merge SHA.
14. Stop only at a real approval boundary or material blocker.
15. Finish with the structured Planning Handoff required by the Foreman schema.

## Completion standard

A milestone is not complete because a plan exists or an implementation PR merges. Completion requires the contract gates, reviewable results for all selected evidence profiles, changed files, checks, discipline impacts, risks, disagreements, and unresolved items to be reconciled in a separate closeout evidence PR, then finalized only after that PR's merge commit exists in local history.
