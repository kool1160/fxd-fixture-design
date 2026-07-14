# FXD Milestone Backlog

The Foreman selects the first milestone whose status is not Complete, Blocked, Waiting, or Paused unless a milestone number is supplied explicitly.

## Milestone 1 — Establish the runnable technical baseline

**Status:** Complete

Create a minimal, reproducible project baseline and perform a geometry-stack spike. Compare viable approaches for STEP assembly import, topology access, transforms, Boolean operations, clearance checks, and neutral export. Produce a small runnable proof using synthetic geometry and record the decision with licensing implications.

Acceptance criteria:

- one command builds or runs repository validation
- at least one runnable geometry proof exists
- the candidate stack is evaluated against FXD requirements, not popularity alone
- dependency licenses and redistribution constraints are recorded
- the chosen architecture preserves a CAD-neutral core
- no customer or employer geometry is committed

**Recommended level:** Terra

## Milestone 2 — Import STEP assemblies into a normalized product model

**Status:** Complete

Import a representative synthetic STEP assembly, preserve component identity and transforms, and expose a normalized model containing components, bodies, faces, edges, bounding volumes, units, and source metadata.

Acceptance criteria:

- assembly hierarchy and transforms are preserved
- units are explicit and normalized
- malformed or unsupported input fails clearly
- tests cover repeated components and nested transforms
- imported source geometry remains immutable

**Recommended level:** Terra

## Milestone 3 — Build the engineering-annotation workflow

**Status:** Complete

Allow an engineer to define build orientation, critical characteristics, permitted locating surfaces, forbidden contact areas, weld joints, loading direction, process type, production quantity, and shop constraints without modifying source geometry.

Acceptance criteria:

- annotations are stored separately from imported CAD
- every annotation references stable geometric identity where possible
- assumptions are visible and editable
- project data can be saved and reloaded

**Recommended level:** Terra

## Milestone 4 — Generate baseplate, supports, stops, and locator primitives

**Status:** Complete

Generate deterministic fixture primitives around annotated product geometry, beginning with flat baseplates, laser-cut risers, hard stops, support pads, round pins, and relieved contact geometry.

Acceptance criteria:

- generated features remain editable and traceable to inputs
- clearances and manufacturing allowances are parameterized
- trapped-part and obvious collision conditions are detected
- outputs use explicit units and tolerances

**Recommended level:** Terra

## Milestone 5 — Create and rank complete fixture concepts

**Status:** Complete

Combine fixture primitives into multiple coherent concepts optimized for minimum cost, fast loading, or high repeatability. Enforce deterministic locating and constraint rules before AI ranking or explanation.

Acceptance criteria:

- each concept documents its locating and clamping strategy
- underconstraint and overconstraint warnings are surfaced
- concept scoring is explainable
- user corrections do not mutate the original assembly

**Recommended level:** Sol

## Milestone 6 — Model weld, operator, and robot access

**Status:** Complete

Represent weld seams and approach envelopes, then evaluate torch, hand, clamp, cobot, and unload access against fixture geometry.

Acceptance criteria:

- access assumptions are explicit
- blocked welds and approach conflicts are reported geometrically
- manual and robotic processes may use different envelopes
- false certainty is avoided where process data is incomplete

**Recommended level:** Sol

## Milestone 7 — Add standard clamp and tooling libraries

**Status:** Complete

Define vendor-neutral clamp, pin, rest, and tooling contracts and support configurable libraries without embedding restricted vendor content.

Acceptance criteria:

- library items have geometry, stroke, force, mounting, and access metadata
- license and attribution requirements are recorded
- preferred standard components can be selected before custom geometry
- custom shop libraries remain separable from the public repository

**Recommended level:** Terra

## Milestone 8 — Export a fabrication-ready fixture package

**Status:** Complete

Export neutral 3D geometry, laser-ready 2D profiles, BOM data, setup instructions, assumptions, and validation findings from an approved fixture concept.

Acceptance criteria:

- STEP and DXF outputs are deterministic
- quantities and purchased components are reconciled
- every exported artifact identifies units and revision
- unverified assumptions appear in the release package
- export does not imply production approval

The proof-layer implementation remains review-only until real-kernel acceptance proves the authored B-Rep and manufacturing profiles.

**Recommended level:** Terra

## Milestone 9 — Capture engineer corrections and reusable knowledge

**Status:** Complete

Record proposed geometry, engineer corrections, rejection reasons, and accepted outcomes in a structured local knowledge format suitable for future learning without exposing confidential source CAD.

Acceptance criteria:

- corrections are explainable and attributable
- private rule packs remain outside the public repository
- training or retrieval data can exclude source geometry
- the system does not silently convert one engineer's preference into a universal rule

**Recommended level:** Sol

## Milestone 10 — Add CAD-specific connectors

**Status:** Complete

Add thin connectors for selected CAD systems after the neutral workflow is proven. Start with a compatibility probe for SOLIDWORKS Connected/Makers and define a commercial SOLIDWORKS add-in path without coupling the core to either.

Acceptance criteria:

- connector failures cannot corrupt the neutral project model
- vendor licensing and API restrictions are documented
- the standalone application remains functional without a connector
- destructive CAD operations require explicit approval

**Recommended level:** Terra

# Phase 2 — Engineering hardening

Phase 2 establishes the deterministic engineering foundations and the first engineer-facing application boundary.

## Milestone 11 — Integrate a real geometry kernel

**Status:** Complete

Replace AABB-only proof geometry with a reviewed B-Rep kernel boundary capable of importing real STEP assemblies, preserving hierarchy and transforms, exposing topology, and authoring deterministic neutral geometry without coupling FXD to a CAD vendor.

Acceptance criteria:

- the selected kernel and wrapper licenses permit intended distribution
- real STEP solids, shells, faces, edges, normals, and transforms are available through a CAD-neutral interface
- source geometry remains immutable
- stable geometry-reference strategy is documented and tested across reloads
- malformed, partial, and unsupported geometry fail clearly
- the proof-layer AABB implementation remains available only as an explicit test double

Implementation note: FXD uses the pinned `cadquery-ocp==7.9.3.1.1` binding behind the neutral `RealKernel` boundary. Runtime acceptance of the manufacturing path is deliberately carried into Milestone 17.

**Recommended level:** Sol

## Milestone 12 — Build a deterministic locating and constraint solver

**Status:** Complete

Implement engineering-first locating analysis using contact geometry, normals, and degrees of freedom. The solver must establish whether a proposed datum and locator strategy actually constrains the product before any AI ranking occurs.

Acceptance criteria:

- translational and rotational degrees of freedom are calculated explicitly
- 3-2-1 and nontraditional locating schemes are represented without hard-coded assumptions
- underconstraint, redundant constraint, and overconstraint are reported deterministically
- contact normals and locator directions are validated against product geometry
- round-pin, diamond-pin, rest, stop, and clamp roles are distinguished
- invalid locating strategies cannot be recommended or exported

**Recommended level:** Sol

## Milestone 13 — Add weld-fixture engineering rules

**Status:** Complete

Add explainable weld-fixture reasoning for heat input, distortion, restraint, tack sequence, weld access, clamp direction, and support placement. Rules remain configurable and never silently become universal shop policy.

Acceptance criteria:

- weld joints carry process, sequence, direction, and heat-input assumptions where known
- expected shrink and distortion directions can influence support and clamp strategy
- clamp-force direction is checked against locating and distortion goals
- supports and clamps near weld zones are assessed for access, heat, and spatter exposure
- conflicting rules surface warnings instead of being averaged into a score
- every recommendation identifies its rule, evidence, assumptions, and confidence

**Recommended level:** Sol

## Milestone 14 — Establish the manufacturing-aware geometry foundation

**Status:** Complete

Establish the CAD-neutral manufacturing-geometry model and deterministic authoring boundary for practical fabricated fixtures. This milestone closes the safe foundation work; runtime acceptance and application-grade real geometry are intentionally moved to Milestone 17.

Acceptance criteria:

- baseplates, risers, tabs, slots, reliefs, pin holes, support pads, shims, and wear items have explicit manufacturing intent
- laser-cut and machined features are distinguished
- material, thickness, fit, clearance, and allowance values are explicit
- STEP and DXF are generated from one deterministic cut-operation plan
- generated features remain traceable to engineering inputs and editable parameters
- malformed, reordered, or source-mismatched manufacturing evidence fails closed
- all outputs remain engineering-review-only

Closure note: this does not claim that the pinned OCP runtime, real-kernel interference checks, manufacturability checks, or exported STEP/DXF artifacts have passed acceptance. Those requirements now belong to Milestone 17.

**Recommended level:** Sol

## Milestone 15 — Build the full deterministic validation pipeline

**Status:** Complete

Unify geometry, constraint, access, tooling, tolerance, and manufacturing checks into one release gate. Validation decides whether a concept is valid, provisional, or invalid before AI explanation or export.

Acceptance criteria:

- locating adequacy and clamp adequacy are separate deterministic gates
- tolerance and repeatability gaps are surfaced without false precision
- known errors prevent recommendation and package export
- provisional concepts identify exactly what evidence is missing
- validation results are reproducible and versioned
- regression suites include deliberately unsafe and misleading fixture concepts

Implementation note: the versioned validation contract, mandatory fail-closed export gate, interface-aware checks, and regression coverage were completed in PR #21. Real-kernel evidence remains a Milestone 17 requirement.

**Recommended level:** Sol

## Milestone 16 — Build the first serious visual engineering application

**Status:** Complete

Create the first engineer-facing application for inspection, correction, and approval without hiding incomplete engineering behind polished graphics.

Acceptance criteria:

- a user can import a legally shareable STEP assembly and inspect the normalized product model
- generated concepts display product and fixture review geometry in a rotatable view
- engineering layers, assumptions, findings, and warnings can be shown or hidden
- an engineer can suppress, correct, approve, or reject review items without modifying source CAD
- visual items expose deterministic rules and geometry references
- invalid and provisional concepts are visually unmistakable
- complete neutral FXD projects save and reload with source hashes, annotations, decisions, and validation evidence intact
- unsafe or edited concepts cannot be approved without deterministic regeneration and revalidation

Implementation note: PR #24 established and hardened the application boundary. The current view remains normalized review geometry; production-quality B-Rep visualization is Milestone 17.

**Recommended level:** Terra

# Phase 3 — Real geometry and engineering workflow

Phase 3 turns the proven engineering core and application boundary into a serious fixture-engineering workspace. AI may propose and explain, but deterministic geometry and validation remain authoritative.

## Milestone 17 — Prove and expose real-kernel geometry

**Status:** Pending

Complete the pinned-OCP acceptance gate and replace proof envelopes in the application with traceable real product and fixture geometry.

Acceptance criteria:

- GitHub Actions installs and proves `cadquery-ocp==7.9.3.1.1`
- real-kernel Boolean, distance, interference, clearance, and manufacturability tests pass
- deterministic STEP and DXF artifacts are generated and checked with legally shareable fixtures
- product and fixture B-Rep geometry is tessellated for the visual application
- faces, edges, holes, slots, tabs, risers, pins, supports, and clamps can be inspected and selected
- selected visual geometry links to stable geometry references, rules, parameters, and validation findings
- section, transparency, wireframe, fit-to-view, and collision highlighting support engineering review
- failure to obtain kernel evidence keeps the project provisional and blocks release claims

**Recommended level:** Sol

## Milestone 18 — Build the edit-regenerate-revalidate workflow

**Status:** Pending

Turn visual corrections into deterministic engineering operations that regenerate geometry and validation evidence.

Acceptance criteria:

- engineers can move, resize, suppress, replace, and restore supported fixture features
- locator type, pin diameter, support height, clamp choice, baseplate thickness, fit, and clearance are editable parameters
- every edit creates a new revision without mutating source CAD
- affected geometry is regenerated deterministically
- previous approvals are revoked automatically after material edits
- validation reruns and reports exactly what changed
- original and revised concepts can be compared and restored
- unsupported edits fail clearly rather than becoming unvalidated free-form geometry

**Recommended level:** Sol

## Milestone 19 — Deepen weld-fixture and automation workflow

**Status:** Pending

Expose the existing weld, access, distortion, and sequence reasoning as a complete engineer-review workflow.

Acceptance criteria:

- weld and tack sequences are editable and visually traceable
- clamp and release sequences are represented and validated
- heat, distortion, spatter, and restricted-contact zones are visible
- torch, hand, operator, robot, and cobot approach envelopes use shared geometry references
- loading and unloading sequences expose trapped-part and access conflicts
- warnings link directly to the responsible rule and geometry
- manual and robotic fixture variants can be compared without weakening deterministic gates

**Recommended level:** Sol

## Milestone 20 — Harden projects, packaging, and release operations

**Status:** Pending

Prepare the proven engineering application for dependable installation and controlled release without implying automatic production approval.

Acceptance criteria:

- project schemas support explicit versioning and migrations
- autosave, crash recovery, diagnostics, and structured logs are available
- large legally shareable assemblies have measured performance budgets
- fabrication package generation is available through the application with the same fail-closed gate
- installation and update paths are reproducible
- signed build and release procedures are documented
- user and shop preferences remain separate from deterministic public engineering rules
- every release preserves source-CAD immutability and engineering-review boundaries

**Recommended level:** Terra
