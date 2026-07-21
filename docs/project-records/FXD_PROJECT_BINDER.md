<!-- FXD-MILESTONE-STATE: docs/MILESTONE_STATE.json -->
<!-- FXD-HISTORICAL-MILESTONE-SNAPSHOT -->
# FXD Professional Project Binder

> Non-authoritative historical snapshot. This binder preserves the record as
> published; current milestone sequence and status come only from
> `docs/MILESTONE_STATE.json`.

## Mission

FXD is a digital fixture engineer. It helps engineers create practical, manufacturable fixtures while preserving engineering judgment and keeping the human engineer in control.

> AI proposes. Engineering validates.

> The software should think like an experienced fixture engineer.

## Product principles

1. Never modify the customer's original CAD.
2. Every recommendation must be explainable.
3. Deterministic geometry, mathematics, and engineering rules own engineering truth.
4. Manufacturing practicality outranks geometric cleverness.
5. Control parts without unnecessary constraint.
6. Weld, operator, robot, maintenance, loading, and unloading access are first-class requirements.
7. Prefer standard purchased components before unnecessary custom geometry.
8. Multiple valid fixture concepts may exist and should expose tradeoffs.
9. Assumptions must remain visible and editable.
10. Engineer corrections may improve future recommendations without silently becoming universal rules.
11. FXD remains CAD-neutral.
12. Human engineering approval is mandatory before production release.

## Product scope

FXD begins with weld fixturing for sheet-metal, plate, tube, structural members, and fabricated assemblies. The initial workflow imports STEP assemblies, captures manufacturing intent, identifies datums and locating surfaces, generates supports, stops, pins, clamp locations, and base structure, evaluates weld and access conditions, compares concepts, validates deterministic engineering evidence, and exports review packages.

The product is not a replacement for CAD software, does not certify fixtures, does not guarantee distortion, and does not authorize production automatically.

## Engineering constitution

- Imported source geometry is immutable.
- The engineering core uses a CAD-neutral domain model.
- Every generated feature is traceable to source geometry, annotations, rules, parameters, assumptions, warnings, and later edits.
- Units and tolerances are explicit.
- Fixture design is treated as constraint design.
- Access and removability are first-class.
- Manufacturable simplicity is preferred.
- AI commands are bounded and validated before execution.
- Privacy is local-first.
- Dependency licensing is an architecture concern.
- Proprietary knowledge remains separated from public code.
- `scripts/ci.sh` remains the authoritative repository-health command.

## Agent operating model

The FXD Foreman selects eligible milestones, reads project law, coordinates specialists, runs validation, and publishes one reviewable pull request. Specialist roles include Geometry, Fixture Engineering, Weld Process, Manufacturing, CAD Integration, Validation, UX, and Intellectual Property Guardian. Manufacturing safety and deterministic validation outrank convenience and visual polish.

# Milestone records

## Milestone 01 — Establish the runnable technical baseline

**Status:** Complete

Established a dependency-free geometry proof with explicit millimetre units, transforms, intersections, clearance checks, and deterministic neutral serialization. Documented geometry-kernel options, licensing considerations, CI entry points, and the CAD-neutral architecture boundary.

**Key boundary:** AABB geometry was a proof layer, not production B-Rep geometry.

## Milestone 02 — Import STEP assemblies into a normalized product model

**Status:** Complete

Created an immutable CAD-neutral product model and synthetic STEP evidence path with assembly hierarchy, repeated instances, nested transforms, units, bounds, topology summaries, source hashing, and explicit import failures.

**Key boundary:** No full ISO 10303 parser or real B-Rep topology at this stage.

## Milestone 03 — Build the engineering-annotation workflow

**Status:** Complete

Added a separate annotation document with stable geometry references, build orientation, loading direction, process, quantity, critical characteristics, locating permissions, forbidden contacts, weld joints, shop constraints, assumptions, source-hash binding, and deterministic JSON persistence.

## Milestone 04 — Generate baseplate, supports, stops, and locator primitives

**Status:** Complete

Generated traceable, parameterized baseplates, supports, stops, pin envelopes, and locator primitives while preserving immutable source geometry. Added initial overlap, forbidden-contact, missing-intent, and trapped-part findings.

## Milestone 05 — Create and rank complete fixture concepts

**Status:** Complete

Produced multiple deterministic fixture concepts optimized for minimum cost, fast loading, and high repeatability. Each concept includes locating and clamping rationale, warnings, explainable score components, and copy-on-write corrections.

## Milestone 06 — Model weld, operator, and robot access

**Status:** Complete

Added weld-approach, manual-tool, robot, operator, and unload envelopes with deterministic obstruction findings and visible uncertainty when process evidence is incomplete.

## Milestone 07 — Add standard clamp and tooling libraries

**Status:** Complete

Implemented vendor-neutral tooling contracts and deterministic selection for clamps, pins, and rests. Standard items are preferred before custom shop items, with explicit force, stroke, mounting, envelope, licensing, and review limitations.

## Milestone 08 — Export a fabrication-ready fixture package

**Status:** Complete

Added deterministic review-package export containing STEP-shaped proof geometry, DXF profiles, BOM, setup instructions, manifest, validation findings, units, revision, and explicit engineering-review-required status.

## Milestone 09 — Capture engineer corrections and reusable knowledge

**Status:** Complete

Added attributable, copy-on-write correction records, local private storage, sanitized training export, decision gating, and protections preventing isolated preferences from becoming universal rules.

## Milestone 10 — Add CAD-specific connectors

**Status:** Complete

Established optional thin CAD connectors around the neutral model, including neutral STEP translation, review-package export, conservative SOLIDWORKS probing, and approval-gated destructive operations.

## Milestone 11 — Integrate a real geometry kernel

**Status:** Complete

Integrated pinned `cadquery-ocp==7.9.3.1.1` behind the CAD-neutral `RealKernel` boundary. Added real STEP import/export, XCAF hierarchy, topology, stable references, Boolean operations, distance, clearance, malformed-input handling, immutable source-file behavior, licensing records, and explicit separation from the AABB test double.

## Milestone 12 — Complete the deterministic locating and constraint solver

**Status:** Complete

Implemented six-degree-of-freedom locating analysis using explicit contact points, normals, roles, rigid-body constraint rows, rank analysis, and physical DOF classification through row-space membership. Reports underconstraint, redundancy, invalid references, and blocks invalid strategies from recommendation.

## Milestone 13 — Complete weld-fixture engineering rules

**Status:** Complete

Added deterministic weld-process reasoning for process, direction, sequence, heat input, distortion, tack, release, support placement, and clamp-force direction. Findings retain rule identity, evidence, assumptions, and confidence. Reinforcing, opposing, and perpendicular clamp directions are handled separately.

## Milestone 14 — Establish the manufacturing-aware geometry foundation

**Status:** Complete

Added explicit manufacturing method, material, thickness, fit, clearance, allowance, interface, and operation metadata. Established deterministic cut-operation planning for slots, reliefs, and pin holes, source binding, feature-order validation, STEP/DXF parity, and fail-closed evidence handling.

**Closure boundary:** Full real-kernel runtime and application-grade acceptance were deliberately carried into Milestone 17.

## Milestone 15 — Build the full deterministic validation pipeline

**Status:** Complete

Unified geometry, locating, access, tooling, tolerance, and manufacturing evidence into a versioned `ValidationResult`. Export requires matching validation evidence and fails closed for missing, invalid, mismatched, unitless, unsupported-version, or empty-digest results. Intentional interfaces are distinguished from unrelated collisions.

## Milestone 16 — Build the first serious visual engineering application

**Status:** Complete

Added the first local engineer-facing application for STEP import, rotatable review, layer control, assumptions, findings, corrections, approval decisions, and complete neutral project save/reload. Invalid, suppressed, corrected, or stale concepts cannot be approved without deterministic regeneration and revalidation.

## Milestone 17 — Prove and expose real-kernel geometry

**Status:** Complete

Completed pinned-OCP acceptance and exposed real product and fixture B-Rep geometry in the visual workspace. Added tessellation, selectable faces and edges, section edges, feature-scoped findings, collision highlighting, wireframe, transparency, sectioning, feature layers, regeneration after changes, and reconstruction from immutable embedded STEP.

**Validation evidence:** Python 3.12, pinned OCP runtime, and 85 repository tests on the accepted code head.

## Milestone 18 — Build the edit-regenerate-revalidate workflow

**Status:** Complete

Implemented supported fixture edits as revisioned engineering operations. Edits regenerate geometry, rerun validation, revoke stale approval, preserve history, support comparison and restoration, persist with the project, and fail closed when unsupported.

**Validation evidence:** 88 tests passed and 4 skipped in the recorded run.

## Milestone 19 — Deepen weld-fixture and automation workflow

**Status:** Pending

Planned scope includes editable weld and tack sequences, clamp and release sequences, visible heat/distortion/spatter zones, shared torch/hand/operator/robot/cobot geometry references, loading and unloading sequence validation, traceable warnings, and comparison of manual versus robotic fixture variants.

## Milestone 20 — Harden projects, packaging, and release operations

**Status:** Pending

Planned scope includes project schema versioning and migrations, autosave and crash recovery, diagnostics and structured logs, measured performance budgets, application-driven fabrication-package generation, reproducible installation and update paths, signed build procedures, and separation of user/shop preferences from deterministic public engineering rules.

# Record-control statement

This binder is retrospective. Pull requests, commits, tests, workflow runs, review comments, and repository source remain the controlling implementation history. No section of this binder constitutes fixture certification, weld-process approval, structural validation, manufacturability approval, or production release.
