# FXD Strategy Handoff

This is the short-form cross-task repository handoff. It does not override
`BACKLOG.md`, `docs/ROADMAP_QUEUE.md`, or the Engineering Constitution.

## Current repository state

- Repository: `kool1160/fxd-fixture-design`
- Milestone 26 was squash-merged through PR #48 at `c8f831d`.
- PR #48 passed Kernel acceptance and independent Windows visual review.
- The accepted Milestone 26 limitation was a detached VTK viewer window.
- Milestone 27 is active on `milestone-27-unified-engineering-workbench`.

## Active milestone

Milestone 27 replaces the launched Tk shell with one PySide6 main window and
an embedded persistent VTK viewport. The deterministic engineering, geometry,
project, validation, manufacturing, and export contracts remain UI-framework
independent and must not be rewritten to suit Qt.

The application must preserve ordinary vendor STEP import, source bytes and
SHA-256, XCAF color evidence, validated zero-based tessellation, project
workflows, and fail-closed behavior. Metadata-only or malformed input may not
be displayed as real source geometry, and no generated substitute is allowed.

## Review boundary

Milestone 27 remains Pending until automated validation, Kernel acceptance,
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
