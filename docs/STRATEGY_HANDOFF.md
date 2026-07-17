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

## Active milestone

Milestone 30 is active on
`milestone-30-real-manufacturing-geometry-and-tack-location-fixtures`. It adds
typed fixture-construction and lifecycle evidence, purpose-specific tack/location
validation, Cleco strategy checks, real OCP authored manufacturing components,
and review-only package outputs. It composes existing structure, placement,
manufacturing, validation, and workbench contracts.

The application preserves ordinary vendor STEP import, source bytes and
SHA-256, XCAF color evidence, zero-based tessellation, and fail-closed behavior.
Generated AABB fixture evidence is explicitly provisional wireframe review
geometry and cannot be represented as source or final manufacturing geometry.

## Review boundary

Milestone 30 remains Pending until automated validation, local Windows visual
acceptance, independent review, CI, user engineering acceptance, and merge.
The workbench and all exports remain engineering-review-only and never imply
production, structural, weld-process, or safety approval.

## Governing principles

- AI proposes. Engineering validates.
- Never modify source CAD.
- Deterministic engineering overrides AI assumptions.
- Every recommendation must be explainable.
- Manufacturing practicality matters more than geometric perfection.
- Qualified human approval remains mandatory before production release.
