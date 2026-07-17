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
- Milestone 29 is active on `milestone-29-desktop-ui-branding-system`.

## Active milestone

Milestone 29 applies the approved FXD UI & Branding Kit v1.1 to the existing
PySide6 workbench. The new `fxd_ui` presentation package centralizes tokens,
QSS, approved assets, source identity, semantic status, workflow navigation,
and approval-gate widgets. It does not own engineering policy or persistence.

The application preserves ordinary vendor STEP import, source bytes and
SHA-256, XCAF color evidence, zero-based tessellation, and fail-closed behavior.
Generated AABB fixture evidence is explicitly provisional wireframe review
geometry and cannot be represented as source or final manufacturing geometry.

## Review boundary

Milestone 29 remains Pending until automated validation, local Windows visual
acceptance, independent review, CI, and merge. The workbench and all exports
remain engineering-review-only and never imply production, structural,
weld-process, or safety approval.

## Governing principles

- AI proposes. Engineering validates.
- Never modify source CAD.
- Deterministic engineering overrides AI assumptions.
- Every recommendation must be explainable.
- Manufacturing practicality matters more than geometric perfection.
- Qualified human approval remains mandatory before production release.
