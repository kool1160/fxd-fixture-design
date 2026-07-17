# FXD Strategy Handoff

This is the short-form cross-task repository handoff. It does not override
`BACKLOG.md`, `docs/ROADMAP_QUEUE.md`, or the Engineering Constitution.

## Current repository state

- Repository: `kool1160/fxd-fixture-design`
- Milestone 27 was independently visually accepted and squash-merged through
  PR #49 at `7a8076a`.
- The unified PySide6 workbench uses one embedded supervised VTK viewport with
  no detached user-facing viewer.
- Milestone 28 is active on
  `milestone-28-interactive-fixture-engineering-workflow`.

## Active milestone

Milestone 28 exposes the existing deterministic annotations, placement,
concept, tooling, validation, edit, revision, and export contracts through the
unified workbench. Workflow orchestration remains CAD-neutral and Qt does not
own engineering rules.

The application preserves ordinary vendor STEP import, source bytes and
SHA-256, XCAF color evidence, zero-based tessellation, and fail-closed behavior.
Generated AABB fixture evidence is explicitly provisional wireframe review
geometry and cannot be represented as source or final manufacturing geometry.

## Review boundary

Milestone 28 remains Pending until automated validation, Kernel acceptance,
local Windows screenshots, independent visual acceptance, review, and merge.
The workbench and all exports remain engineering-review-only and never imply
production, structural, weld-process, or safety approval.

## Governing principles

- AI proposes. Engineering validates.
- Never modify source CAD.
- Deterministic engineering overrides AI assumptions.
- Every recommendation must be explainable.
- Manufacturing practicality matters more than geometric perfection.
- Qualified human approval remains mandatory before production release.
