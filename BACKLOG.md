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

**Status:** Pending

Define vendor-neutral clamp, pin, rest, and tooling contracts and support configurable libraries without embedding restricted vendor content.

Acceptance criteria:

- library items have geometry, stroke, force, mounting, and access metadata
- license and attribution requirements are recorded
- preferred standard components can be selected before custom geometry
- custom shop libraries remain separable from the public repository

**Recommended level:** Terra

## Milestone 8 — Export a fabrication-ready fixture package

**Status:** Pending

Export neutral 3D geometry, laser-ready 2D profiles, BOM data, setup instructions, assumptions, and validation findings from an approved fixture concept.

Acceptance criteria:

- STEP and DXF outputs are deterministic
- quantities and purchased components are reconciled
- every exported artifact identifies units and revision
- unverified assumptions appear in the release package
- export does not imply production approval

**Recommended level:** Terra

## Milestone 9 — Capture engineer corrections and reusable knowledge

**Status:** Pending

Record proposed geometry, engineer corrections, rejection reasons, and accepted outcomes in a structured local knowledge format suitable for future learning without exposing confidential source CAD.

Acceptance criteria:

- corrections are explainable and attributable
- private rule packs remain outside the public repository
- training or retrieval data can exclude source geometry
- the system does not silently convert one engineer's preference into a universal rule

**Recommended level:** Sol

## Milestone 10 — Add CAD-specific connectors

**Status:** Pending

Add thin connectors for selected CAD systems after the neutral workflow is proven. Start with a compatibility probe for SOLIDWORKS Connected/Makers and define a commercial SOLIDWORKS add-in path without coupling the core to either.

Acceptance criteria:

- connector failures cannot corrupt the neutral project model
- vendor licensing and API restrictions are documented
- the standalone application remains functional without a connector
- destructive CAD operations require explicit approval

**Recommended level:** Terra
