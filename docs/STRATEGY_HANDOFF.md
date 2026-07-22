<!-- FXD-MILESTONE-STATE: docs/MILESTONE_STATE.json -->
# FXD Strategy Handoff

This is derived short-form cross-task context. It does not override the
Engineering Constitution, Product Direction, accepted decisions,
`docs/MILESTONE_CONTRACT.md`, `docs/MILESTONE_STATE.json`, or the Active
milestone's authoritative GitHub issue.

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
- Milestone 31 was accepted and squash-merged through PR #53 at `ac1e7a1`.
- Milestones 1 through 31 are reconciled as legacy Complete by Issue #56.

## Active milestone

Milestone 32 is the sole Active product milestone. Issue #57 is authoritative,
and draft PR #54 is its implementation PR. Evidence profiles A, B, C, D, and E
are required. The milestone remains Active through implementation merge and
requires a separate closeout evidence PR followed, after merge, by a distinct
state-finalization PR that records the already-existing closeout merge SHA.

The implementation adds the first supported
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

PR #54 remains draft, open, and unmerged. Its implementation evidence does not
complete Milestone 32. Integrated-head automated validation must pass before
the remaining Windows visual and qualified fixture-engineering acceptance.
A closeout evidence PR must then reconcile the required evidence profiles,
explicit human acceptance, merge evidence, remaining risks, and Issue #57 while
M32 remains Active. After that PR merges, a distinct state-finalization PR
records its merge SHA, sets Complete, and formally pauses the product lane with
zero Active milestones. No Milestone 33 is created or implied.

The workbench and all exports remain engineering-review-only and never imply
production, structural, weld-process, or safety approval.

PR #55 is blocked documentation maintenance governed by Issue #58. It does not
own product status, and its dependency/licensing, byte-determinism, and
unsupported-bookmark findings remain in the maintenance lane.

## Governing principles

- AI proposes. Engineering validates.
- Never modify source CAD.
- Deterministic engineering overrides AI assumptions.
- Every recommendation must be explainable.
- Manufacturing practicality matters more than geometric perfection.
- Qualified human approval remains mandatory before production release.
