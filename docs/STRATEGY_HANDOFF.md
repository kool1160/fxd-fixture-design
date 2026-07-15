# FXD Strategy Handoff

This document is the authoritative short-form handoff for continuing FXD strategy and implementation work across chats.

## Current repository state

- Repository: `kool1160/fxd-fixture-design`
- Current `main`: `31b7945ab50cde14280bea6e341ce4010a4a8057`
- Milestones 1–18 are complete.
- Milestone 18 merged in PR #29 after local Windows validation: 91 tests passed, real OCP kernel proof passed, and backlog validation passed.
- Duplicate Milestone 18 PR #31 was closed without merge.
- Roadmap PR #38 is merged and defines Milestones 21–26 in `docs/ROADMAP_QUEUE.md`.
- `AGENTS.md` now explicitly governs the transition from `BACKLOG.md` through Milestone 20 into `docs/ROADMAP_QUEUE.md` for Milestones 21–26.
- Issues #32–#37 track Milestones 21–26.

## Active milestone

Milestone 19 — Deepen weld-fixture and automation workflow.

Remote branch:

`milestone-19-weld-fixture-automation-workflow`

The branch must be aligned with current `main` before Foreman starts and currently has no remote Milestone 19 implementation commits.

## Existing foundation that must not be duplicated

Milestone 13, merged in PR #15, already provides:

- weld process, direction, sequence, heat-input, distortion, tack, release, and assumption metadata
- configurable heat thresholds and clamp-force directions
- weld-zone support and clamp findings
- warnings for missing process, direction, tack, and release evidence
- reinforcing, opposing, and perpendicular clamp-direction handling
- rule, evidence, assumption, and confidence traceability

Milestone 19 must build an engineer-review workflow on top of those contracts rather than recreate the weld-rule engine.

## Milestone 19 remaining acceptance scope

- weld and tack sequences are editable and visually traceable
- clamp and release sequences are represented and validated
- heat, distortion, spatter, and restricted-contact zones are visible
- torch, hand, operator, robot, and cobot approach envelopes use shared geometry references
- loading and unloading sequences expose trapped-part and access conflicts
- warnings link directly to the responsible deterministic rule and geometry
- manual and robotic fixture variants can be compared without weakening deterministic gates

## Required working method

Normal repository implementation should use the GitHub Foreman workflow.

Use local Codex only when the work specifically requires:

- the authorized Windows development PC
- installed OCP or Windows-only behavior
- GUI or manual engineering review
- reproduction of a failure Foreman cannot reproduce
- final independent local validation

Do not default to a chain of loose local coding slices. Keep work milestone-driven and prefer one coherent Milestone 19 PR unless a genuine technical boundary requires more than one.

Before launching new work, inspect existing remote branches, PRs, Foreman runs, and any local-only commits. Do not overwrite or discard local work without explicit authorization.

## Local-only work warning

A local commit referenced as `11b4387` was not found in GitHub at the time of this handoff. It must not be assumed merged, pushed, valid, or redundant. Inspect it locally before deciding whether to push, replace, retain, or abandon it.

## Forward queue

1. Milestone 19 — Deepen weld-fixture and automation workflow
2. Milestone 20 — Harden projects, packaging, and release operations
3. Milestone 21 — Generate complete fixture structures
4. Milestone 22 — Optimize locator, support, and clamp placement
5. Milestone 23 — Produce manufacturing-ready fixture geometry
6. Milestone 24 — Generate fixture drawings and documentation
7. Milestone 25 — Optimize cost, volume, and manufacturability
8. Milestone 26 — Complete end-to-end engineering pilots

## Governing principles

- AI proposes. Engineering validates.
- Never modify source CAD.
- Deterministic engineering overrides AI assumptions.
- Every recommendation must be explainable.
- Manufacturing practicality matters more than geometric perfection.
- Human engineering approval remains mandatory before production release.
