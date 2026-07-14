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

The proof-layer implementation is intentionally limited to deterministic AABB
STEP/DXF artifacts until a reviewed geometry kernel can author true B-Rep and
manufacturing-aware profiles.

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

Phase 2 replaces proof-layer shortcuts with production-grade engineering foundations. Each milestone must include runnable proofs and deliberate failure cases, but visual polish is deferred until the geometry and fixture logic are trustworthy.

## Milestone 11 — Integrate a real geometry kernel

**Status:** Complete

Replace AABB-only proof geometry with a reviewed B-Rep kernel boundary capable of importing real STEP assemblies, preserving hierarchy and transforms, exposing topology, and authoring deterministic neutral geometry without coupling FXD to a CAD vendor.

Acceptance criteria:

- the selected kernel and wrapper licenses permit intended distribution
- real STEP solids, shells, faces, edges, normals, and transforms are available through a CAD-neutral interface
- source geometry remains immutable
- stable geometry-reference strategy is documented and tested across reloads
- Boolean, distance, interference, and clearance proofs use real geometry
- malformed, partial, and unsupported geometry fail clearly
- deterministic STEP round-trip behavior is tested with legally shareable fixtures
- the proof-layer AABB implementation remains available only as an explicit test double

Implementation note: FXD uses the pinned `cadquery-ocp==7.9.3.1.1` binding behind the neutral `RealKernel` boundary. Synthetic multi-solid STEP proofs cover topology, transforms, face normals, stable references, Boolean operations, clearance, malformed input, and deterministic round trips. OCP/OCCT licensing and redistribution obligations are recorded separately.

**Recommended level:** Sol

## Milestone 12 — Build a deterministic locating and constraint solver

**Status:** Pending

Implement engineering-first locating analysis using contact geometry, normals, and degrees of freedom. The solver must establish whether a proposed datum and locator strategy actually constrains the product before any AI ranking occurs.

Acceptance criteria:

- translational and rotational degrees of freedom are calculated explicitly
- 3-2-1 and nontraditional locating schemes are represented without hard-coded assumptions
- underconstraint, redundant constraint, and overconstraint are reported deterministically
- contact normals and locator directions are validated against real product geometry
- round-pin, diamond-pin, rest, stop, and clamp roles are distinguished
- tolerance, repeatability, and datum assumptions remain explicit
- invalid locating strategies cannot be recommended or exported
- golden tests cover known valid and invalid fixture cases

**Recommended level:** Sol

## Milestone 13 — Add weld-fixture engineering rules

**Status:** Pending

Add explainable weld-fixture reasoning for heat input, distortion, restraint, tack sequence, weld access, clamp direction, and support placement. Rules must remain configurable and must never silently become universal shop policy.

Acceptance criteria:

- weld joints carry process, sequence, direction, and heat-input assumptions where known
- expected shrink and distortion directions can influence support and clamp strategy
- clamp-force direction is checked against locating and distortion goals
- supports and clamps near weld zones are assessed for access, heat, and spatter exposure
- tack access and release sequence are represented
- conflicting rules surface warnings instead of being averaged into a score
- every recommendation identifies the rule, evidence, assumptions, and confidence
- private shop rules remain separable from the public rule set

**Recommended level:** Sol

## Milestone 14 — Generate manufacturing-aware fixture geometry

**Status:** Pending

Generate editable, manufacturable fixture solids and profiles instead of abstract boxes. Features should reflect practical sheet-metal and fabricated-fixture construction methods.

Acceptance criteria:

- baseplates, risers, tabs, slots, reliefs, pin holes, support pads, shims, and replaceable wear items are true geometry
- laser-cut and machined features are distinguished
- material, thickness, fit, clearance, and allowance values are explicit
- tabs and slots include assembly and welding allowances
- purchased tooling mounts use validated interfaces rather than generic envelopes alone
- generated features remain traceable to engineering inputs and editable parameters
- resulting geometry passes kernel-level interference and manufacturability checks
- neutral STEP and DXF exports contain actual geometry suitable for engineering review

**Recommended level:** Sol

## Milestone 15 — Build the full deterministic validation pipeline

**Status:** Pending

Unify geometry, constraint, access, tooling, tolerance, and manufacturing checks into one release gate. Validation must decide whether a concept is valid, provisional, or invalid before AI explanation or export.

Acceptance criteria:

- collisions, minimum clearances, trapped-part conditions, and load/unload paths use real geometry
- weld, torch, hand, operator, clamp, and robot approach checks share traceable inputs
- locating adequacy and clamp adequacy are separate deterministic gates
- tolerance-stack and repeatability gaps are surfaced without false precision
- known errors prevent recommendation and package export
- provisional concepts identify exactly what evidence is missing
- validation results are reproducible and versioned
- regression suites include deliberately unsafe and misleading fixture concepts

**Recommended level:** Sol

## Milestone 16 — Build the first serious visual engineering application

**Status:** Pending

Create the first engineer-facing application only after the hardened geometry and validation foundations are working. The application is for inspection, correction, and approval—not for hiding incomplete engineering behind polished graphics.

Acceptance criteria:

- a user can import a legally shareable STEP assembly and inspect the normalized product model
- generated fixture concepts display real product and fixture geometry in a rotatable 3D view
- datums, locators, supports, stops, clamps, welds, access envelopes, assumptions, and warnings can be shown or hidden
- an engineer can edit, suppress, replace, approve, or reject generated features without modifying source CAD
- every visual item links back to its deterministic rule and geometry reference
- invalid and provisional concepts are visually unmistakable
- the application can save and reload a complete neutral FXD project
- packaging and installation planning begins only after the application boundary is proven

**Recommended level:** Terra
