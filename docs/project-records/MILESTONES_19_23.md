# FXD Milestone Records 19–23

This addendum extends the professional project binder from Milestone 18 through the current governed milestone.

## Milestone 19 — Deepen weld-fixture and automation workflow

**Status:** Complete  
**Controlling evidence:** PR #39, merged to `main`.

FXD added the engineer-review workflow on top of the deterministic weld-rule contracts. The milestone introduced editable weld, tack, clamp, release, loading, and unloading sequence plans; traceable heat, distortion, spatter, and restricted-contact zones; and shared torch, hand, operator, robot, cobot, load, and unload envelopes.

Findings are linked to both the responsible workflow object and the exact collided fixture geometry. Manual-versus-robotic/cobot comparisons remain bound to the authoritative `ValidationResult`, source hash, status, version, and evidence digest.

**Validation evidence:** GitHub Actions kernel acceptance passed on the repaired head with the pinned `cadquery-ocp==7.9.3.1.1` runtime. Repository validation and focused workflow regressions passed.

**Protected boundary:** This milestone does not perform thermal simulation, force simulation, weld-quality certification, or robot kinematic planning, and it does not approve production fixtures.

## Milestone 20 — Harden projects, packaging, and release operations

**Status:** Complete  
**Controlling evidence:** PR #40, merged to `main`.

FXD added explicit `fxd-neutral-project-v2` schema support with true v1 compatibility, atomic project saves, adjacent autosave, explicit recovery, structured local diagnostics, and separation of user preferences from deterministic engineering rules.

Fabrication-package export remains behind the existing fail-closed validation gate. The milestone also added reproducible installation and update procedures, large legally shareable synthetic-assembly performance evidence, controlled release-manifest generation, sensitive-path rejection, and a documented authorized signing procedure without embedding private keys or pretending an unsigned release is signed.

**Validation evidence:** GitHub Actions kernel acceptance passed on the repaired head. Full repository validation passed, including large-assembly performance, autosave and recovery, project migration, release-manifest safety, and sensitive-path rejection.

**Protected boundary:** A documented release procedure is not itself a published or production-approved release.

## Milestone 21 — Generate complete fixture structures

**Status:** Complete  
**Controlling evidence:** PR #43, merged to `main`.

FXD added a deterministic, CAD-neutral structural concept layer around imported product assemblies. The system can select explainable baseplate or welded-frame strategies from product evidence and caller-supplied engineering intent, then generate connected structural members, explicit load paths, sizing assumptions, evidence, and fail-closed findings.

Structural concepts integrate with fixture concepts, project regeneration, deterministic validation, persistence, and review documentation.

**Validation evidence:** 9 focused structural tests passed; the full suite passed 110 tests with no failures, errors, or skips; backlog validation, planning-handoff validation, compilation, secret scanning, and the real OCP kernel proof passed.

**Protected boundary:** This is an engineering-review structural concept layer. It does not claim structural adequacy, final fabrication geometry, drawings, thermal simulation, robot path planning, safety certification, or production approval.

## Milestone 22 — Optimize locator, support, and clamp placement

**Status:** Complete  
**Controlling evidence:** PR #44, merged to `main`.

FXD added deterministic datum-candidate ranking and editable placement contracts for locators, supports, stops, and clamps. The workflow composes the six-degree-of-freedom constraint solver, access findings, vendor-neutral tooling library, weld intent, and Milestone 21 structural members.

The placement system preserves alternatives, assumptions, confidence, deterministic digests, and evidence. It fails closed for invalid references, duplicate directions, overconstraint, blocked access, unsupported mounts, and insufficient clamp capacity. Placement information may round-trip through neutral project persistence.

**Validation evidence:** 10 focused placement tests passed; the full suite passed 121 tests with no failures, errors, or skips; compilation, backlog validation, planning-handoff validation, secret scanning, and the real OCP kernel proof passed.

**Protected boundary:** This milestone does not author final B-Rep tooling, simulate structural or thermal behavior, plan robot motion, certify safety, or approve production fixtures.

## Milestone 23 — Produce manufacturing-ready fixture geometry

**Status:** Current / Pending

Milestone 23 is the next governed milestone after the completed structural and placement layers.

The objective is to convert complete fixture structures and optimized locator, support, stop, and clamp placements into editable manufacturing geometry suitable for serious engineering review. Expected work includes true baseplates, frames, risers, tabs, slots, holes, mounts, supports, locator details, and purchased-tooling interfaces generated through the CAD-neutral real-kernel boundary.

The milestone must preserve:

- immutable source customer CAD;
- traceability from every generated feature to engineering intent, placement evidence, rules, parameters, units, assumptions, and warnings;
- deterministic interference, clearance, identity, and manufacturability checks;
- agreement between 3D geometry, 2D profiles, BOM, and validation evidence;
- explicit provisional or invalid status when required evidence is incomplete;
- qualified human engineering approval before any production release.

Completion must not be claimed until implementation, independent review, required tests, GitHub Actions acceptance, and merge are all complete.

## Forward queue

- Milestone 24 — Generate fixture drawings and documentation.
- Milestone 25 — Optimize cost, volume, and manufacturability.
- Milestone 26 — Complete end-to-end engineering pilots.

## Record-control statement

This addendum is retrospective. Pull requests, commits, tests, workflow runs, review comments, backlog records, and repository source remain the controlling implementation history. Nothing in this document constitutes fixture certification, weld-process approval, structural validation, manufacturability approval, safety certification, or production release.
