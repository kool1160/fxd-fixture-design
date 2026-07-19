# FXD Strategy Handoff

This is the short-form cross-task repository handoff. It does not override
`BACKLOG.md`, `docs/ROADMAP_QUEUE.md`, or the Engineering Constitution.

## Current repository state

- Repository: `kool1160/fxd-fixture-design`
- Milestone 27 was independently visually accepted and squash-merged through
  PR #49 at `7a8076a`.
- The unified PySide6 workbench uses one embedded supervised VTK viewport with
  no detached user-facing viewer.
- Milestone 28 was independently reviewed, accepted by hosted Kernel validation,
  and squash-merged through PR #50 at `1313922`.
- Milestone 29 was independently visually accepted and squash-merged through
  PR #51 at `4b6691a`.
- Milestone 30 was squash-merged through PR #52 at `edf65bb`.
- Milestone 31 was accepted and squash-merged through PR #53 at
  `ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc`.

## Active milestone

Milestone 32 is locally verified on
`milestone-32-multi-station-weld-fixture-synthesis`. It adds the first supported
`linear_multi_station_weld_fixture` family by extending the existing fixture
build, OCP authoring, validation, proposal, export, persistence, and workbench
contracts. It persists stable immutable-source product review instances,
station intent, equal-pitch layout evidence, real component identities, and
deterministic access/connectivity results; it does not create a parallel fixture
system.

The application preserves ordinary vendor STEP import, source bytes and
SHA-256, XCAF color evidence, zero-based tessellation, and fail-closed behavior.
When an M32 build is authored, the workbench displays tessellated real OCP
fixture components and transformed immutable source-product review instances.
AABB evidence is retained only as explicitly labelled fallback/debug evidence.

## Review boundary

Milestone 31 is complete and merged. Milestone 32 has focused and full
regression evidence, governed CI, and a Windows technical smoke check; it still
requires hosted pinned-OCP acceptance, engineering acceptance, and an unmerged
review pull request.
The workbench and all exports remain engineering-review-only and never imply
production, structural, weld-process, or safety approval.

## Governing principles

- AI proposes. Engineering validates.
- Never modify source CAD.
- Deterministic engineering overrides AI assumptions.
- Every recommendation must be explainable.
- Manufacturing practicality matters more than geometric perfection.
- Qualified human approval remains mandatory before production release.
