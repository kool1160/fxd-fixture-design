# Milestone 30 Fixture Construction

## Purpose

Milestone 30 adds a deterministic, editable fixture-construction layer on top
of the existing structural concept, placement, component-geometry, validation,
cost, and desktop-workbench contracts. It supports an explicit fixture purpose,
construction method, lifecycle, job revision, Cleco strategy, manufacturing
hole process, tab-and-slot record, poka-yoke record, build sequence, BOM, and nest
classification.

The source is the M30 user-supplied fixture handoff (`M30-USER-SPEC`). Its
representative tube-frame, laser-cut, and Cleco examples are engineering intent
and test direction, not a public proprietary rule pack. No customer CAD, vendor
geometry, fixed plate thickness, tube size, clamp force, or shop standard is
embedded as universal policy.

## Architecture

`fxd_geometry.fabrication_workflow` is CAD-neutral. It persists only typed
review evidence and never alters source STEP bytes. `author_fixture_build` is
the explicit OCP boundary: it creates real B-Rep solids only for components
whose authority is `authored_manufacturing_geometry`. Source geometry,
purchased-component geometry, and provisional envelopes cannot silently change
authority or be exported as authored fixture parts.

The optional `fixture_build` field upgrades an FXD project to schema v4. v1,
v2, and v3 files continue to load with no build plan. When present, the plan
changes the project revision identity and its deterministic findings are merged
into the normal active validation result and evidence digest.

## Deterministic behavior

- Dependencies, dimensions, process intent, and approval evidence are
  caller-supplied and preserved. FXD validates them; it does not invent a weld
  procedure, fixture capacity, safety rating, or universal construction rule.
- A Tack or Location Fixture requires tack, release, and unload evidence. It
  does not require full-weld access, because finish welding is explicitly
  outside this fixture's scope.
- Product Cleco holes require explicit approval and a post-use process. Separate
  fixture holes are represented as the preferred lower-impact alternative, not
  a universal mandate.
- Each Cleco record carries diameter, hole, grip range, installation/removal
  side, plier access, build role, product-location role, retained/removal state,
  and post-use handling. A Cleco remains a temporary aid, never an inferred
  precision locator.
- Poka-yoke intent is an explicit anti-reversal record. It fails closed for a
  known pinch point, hidden seating, reversal risk, or unloading trap.
- Recut/disposable fixture parts require a job revision and are classified
  separately from sellable product parts in nesting outputs.
- Provisional adjustment, prove-out, and revalidation-required states block
  manufacturing package export. The package remains engineering-review-only
  even when the position is locked or doweled.
- Packages contain separate BOM, nest classification, hole-process, tab/slot,
  Cleco, and poka-yoke maps. Fixture nesting is explicitly marked not for
  shipment and remains tied to the job revision for disposable concepts.

## Stable rule catalog

| Rule | Scope | M30 handoff section | Regression mapping |
| --- | --- | --- | --- |
| `FXD-DAT-001` | Three fixed primary pads | Datums | four-pad variant |
| `FXD-LOC-001` | Locator contact and stops | Datums and locating | seam/radius/opposing-stop variants |
| `FXD-SUP-001` | Clamp reaction support | Supports and clamps | clamp-over-support variant |
| `FXD-PIN-001` | Round and diamond pin behavior | Pins | two-round-pin variant |
| `FXD-CLP-001` | Clamp and release evidence | Clamps | fixed-pin unload variant |
| `FXD-ACC-001` | Purpose-specific access | Weld and access | tack versus full-weld access |
| `FXD-WLD-001` | Weld-process evidence | Weld and access | missing-process variant |
| `FXD-DST-001` | Welded-shape unloading | Distortion and unloading | unload-trap variant |
| `FXD-MFG-001` | Geometry authority and connectivity | Real manufacturing geometry | provisional/disconnected variants |
| `FXD-TAB-001` | Tab-and-slot fit | Laser-cut construction | slot, bottoming, relief variants |
| `FXD-HOL-001` | Hole process authority | Hole process authority | laser-as-precision variant |
| `FXD-THR-001` | Threaded clamp mounting | Clamp mounting | pilot/tap variant |
| `FXD-PKY-001` | Poka-yoke evidence | Poka-yoke | reversible-riser variant |
| `FXD-CLE-001` | Cleco fit and approval | Cleco usage | product/fixture/grip/removal variants |
| `FXD-TACK-001` | Tack/location workflow | Tack or Location Fixture | tack sequence/access variant |
| `FXD-COST-001` | Lifecycle and nest classification | Disposable/reuse handling | job-revision/nest variants |
| `FXD-MNT-001` | Service evidence | Maintenance | replacement evidence variant |
| `FXD-EXP-001` | Review-only package gate | Outputs and validation | stale/provisional export variant |

The executable catalog in `RULE_CATALOG` carries title, description,
applicability, required evidence, deterministic logic, states, severity,
override policy, source reference, and test mapping for every ID.

## Current limitations

The generated B-Rep parts are deterministic manufacturing-review geometry, not
released drawings or a structural analysis. The current authoring slice uses
editable parametric plate/member solids, hollow structural-tube wall geometry,
and through-hole operations; detailed cut profiles, commercial tooling
envelopes, tube mitres, and tab contour topology remain explicitly review work
rather than claimed released geometry. Individual maintenance and replacement
evidence is validated for generated service contacts, but tool-clearance,
wear-life, and calibrated replacement intervals remain qualified-review work.
FXD does not perform thermal
simulation, robot path planning, clamp-force calculation, fixture-capacity
certification, safety approval, automated nesting, or production release.
Qualified fixture-engineering review remains mandatory. Milestones 23 through
25 still own their existing detailed manufacturing, drawing, and costing
contracts; M30 composes their boundaries rather than replacing them.
