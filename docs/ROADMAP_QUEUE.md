<!-- FXD-MILESTONE-STATE: docs/MILESTONE_STATE.json -->
# FXD Forward Milestone Queue

This is a derived roadmap. Current sequence and status come only from `docs/MILESTONE_STATE.json`, under `docs/MILESTONE_CONTRACT.md`. It preserves the governing principle: **AI proposes. Engineering validates.** Source CAD remains immutable, deterministic engineering remains authoritative, and no generated fixture is approved for production without qualified human review.

## Queue

1. Milestone 19 — Deepen weld-fixture and automation workflow
2. Milestone 20 — Harden project reliability and application operations
3. Milestone 21 — Generate complete fixture structures
4. Milestone 22 — Optimize locator, support, and clamp placement
5. Milestone 23 — Produce manufacturing-ready fixture geometry
6. Milestone 24 — Generate fixture drawings and documentation
7. Milestone 25 — Optimize cost, volume, and manufacturability
8. Milestone 26 — Complete end-to-end engineering pilots
9. Milestone 27 - Unified engineering workbench
10. Milestone 28 - Interactive fixture engineering workflow
11. Milestone 29 - Implement the desktop UI and branding system
12. Milestone 30 - Real manufacturing geometry and tack/location fixtures
13. Milestone 31 - AI Fixture Engineer and guided validation
14. Milestone 32 - Multi-station weld fixture synthesis

## Milestone 21 — Generate complete fixture structures

**Status:** Complete

Implemented and merged in PR #43. The structural layer remains an editable,
traceable engineering-review proof layer; it does not claim structural adequacy
or production approval.

Generate coherent fixture assemblies around imported customer products instead of isolated fixture primitives.

Acceptance criteria:

- FXD selects an explainable baseplate or welded-frame strategy from product size, loading, access, process, quantity, and shop constraints
- base structure, risers, supports, stops, locator mounts, clamp towers, brackets, and structural members form one connected buildable fixture concept
- load paths, stability, practical plate thickness, tubing/member sizing assumptions, and base support are explicit
- unsupported or physically disconnected fixture features fail closed
- the generated fixture surrounds the imported assembly without requiring a pre-existing fixture model
- alternate structural concepts can be compared for cost, access, loading, and repeatability
- all generated structure remains editable, traceable, review-only, and separate from source CAD

**Recommended level:** Sol

## Milestone 22 — Optimize locator, support, and clamp placement

**Status:** Complete

Implemented and merged in PR #44 at `85ce6c0`. Placement evidence remains
engineering-review-only and deterministic validation continues to override
preference scoring.

Implementation is complete and under independent PR review. Kernel-derived surface
evidence, final B-Rep tooling geometry, and qualified human approval remain
required for production use.

Build the serious engineering placement engine that turns locating, distortion, access, tooling, and production intent into practical fixture arrangements.

Acceptance criteria:

- datum candidates are ranked using real product surfaces, normals, critical characteristics, stability, accessibility, and distortion intent
- round-pin, diamond-pin, rest, stop, support, and clamp roles are placed and validated explicitly
- support placement addresses sag, weld shrink, distortion, and load transfer without overconstraint
- clamp selection accounts for direction, stroke, force, reach, mounting, weld access, operator access, and release sequence
- standard vendor-neutral tooling is preferred before custom geometry where practical
- placement alternatives are generated when collision, access, constraint, or manufacturability gates fail
- every proposed placement cites rules, geometry references, assumptions, evidence, and confidence
- deterministic validation overrides AI ranking

**Recommended level:** Sol

## Milestone 23 — Produce manufacturing-ready fixture geometry

**Status:** Complete

Implemented and merged in PR #45 at `85b76a8`. Manufacturing geometry and
exports remain subject to qualified engineering review and release controls.

Convert an approved fixture concept into real buildable fabricated and machined component geometry.

Acceptance criteria:

- laser-cut plates, tabs, slots, reliefs, risers, gussets, tubing/frame members, pin holes, clamp mounts, shim packs, wear items, and machined locator blocks are authored as real B-Rep geometry
- fabricated and purchased components have stable identities, part numbers, material, thickness, quantity, finish, and manufacturing intent
- tabs, slots, fasteners, hole fits, weld access, tool access, tolerance stack, and assembly sequence are validated
- each fabricated component can produce deterministic STEP and appropriate DXF output
- purchased-component mounting geometry reconciles with library metadata
- malformed, disconnected, conflicting, or non-manufacturable geometry fails closed
- exports remain engineering-review-only until human approval

**Recommended level:** Sol

## Milestone 24 — Generate fixture drawings and documentation

**Status:** Complete

Implemented and merged in PR #46 at `e3aaf19`. Generated documentation is a
review package and is not automatic production release.

Generate a reviewable fixture drawing package from validated fixture manufacturing geometry.

Acceptance criteria:

- fixture assembly drawing, exploded views, section views, detail views, and fabricated-part drawings are generated from the same authoritative geometry
- baseplate dimensions, hole tables, locator coordinates, clamp callouts, purchased-component references, weld symbols, fits, tolerances, and fabrication notes are included where applicable
- BOM, part numbers, revision information, assumptions, validation findings, and approval boundaries reconcile across every artifact
- PDF output is deterministic and linked to STEP and DXF deliverables
- ambiguous annotation placement, missing dimensions, unsupported symbols, and incomplete manufacturing evidence are surfaced for engineer correction rather than hidden
- drawing generation never claims production approval automatically

**Recommended level:** Sol

## Milestone 25 — Optimize cost, volume, and manufacturability

**Status:** Complete

Implemented and merged in PR #47. Cost, volume, and manufacturability
comparisons remain engineering-review evidence and do not claim production
approval.

Compare fixture strategies against production volume, loading time, tooling cost, fabrication effort, machining effort, repeatability, maintenance, and automation requirements.

Acceptance criteria:

- cost models separate purchased tooling, material, laser cutting, machining, welding, assembly, setup, maintenance, and engineering assumptions
- low-volume, medium-volume, and high-volume fixture strategies can be compared without pretending uncertain estimates are exact
- manual, cobot, and robotic variants include loading time, access, safety, changeover, and expected maintenance considerations
- standard components, replaceable wear items, modularity, and custom tooling tradeoffs are explainable
- manufacturability and shop-capability conflicts are reported before ranking
- the system explains why one concept is preferred for a stated production quantity
- human engineering and commercial review remain mandatory

**Recommended level:** Sol

## Milestone 26 — Complete end-to-end engineering pilots

**Status:** Complete

Milestone 26 was implemented, independently visually reviewed, accepted by
Kernel acceptance, and squash-merged in PR #48. The accepted viewer limitation
was a detached native VTK window alongside the Tk controls; Milestone 27 owns
its replacement with one embedded viewport.

Prove the complete FXD workflow on legally shareable representative fabricated assemblies and measure engineering usefulness honestly.

Acceptance criteria:

- pilots include sheet-metal, structural-tube, mixed plate-and-tube, manual-welding, and robot/cobot scenarios
- each pilot runs through STEP import, intent capture, fixture generation, engineer edits, deterministic validation, manufacturing geometry, drawings, BOM, and neutral exports
- qualified fixture engineers score loading, unloading, stability, locating, clamping, weld access, automation access, manufacturability, maintainability, safety, and drawing usefulness
- failures, corrections, rejected concepts, and accepted outcomes are recorded without exposing confidential source CAD
- runtime, memory, interaction, regeneration, export, and drawing-package performance are measured
- production release is prohibited without explicit qualified human approval
- pilot evidence determines the next product-hardening and commercialization queue

**Recommended level:** Sol

## Milestone 27 - Unified engineering workbench

**Status:** Complete

Independently visually accepted, accepted by hosted Kernel validation, and
squash-merged in PR #49 at `7a8076a`.

Unify the local engineering application around an embedded accelerated VTK
viewport and a professional desktop shell without changing deterministic
engineering authority.

Acceptance criteria:

- one PySide6 main window embeds the persistent VTK viewport with no detached viewer
- source colors, immutable STEP identity, validated zero-based tessellation, and fail-closed imports are preserved
- CAD navigation, standard views, shaded/wireframe/transparency modes, and renderer diagnostics remain available
- actual assembly components populate an engineering explorer without fabricated results
- source identity, geometry counts, selection identity, findings, validation, and evidence status are visible
- project open/save, autosave recovery, review export, layers, and review decisions remain governed by existing contracts
- headless CI and local Windows visual evidence both pass
- the application remains engineering-review-only and never substitutes generated geometry for source CAD

**Recommended level:** Sol

## Milestone 28 - Interactive fixture engineering workflow

**Status:** Complete

Implemented, independently reviewed, accepted by hosted Kernel validation, and
squash-merged in PR #50 at `1313922`.

Expose the existing deterministic product, annotation, placement, concept,
tooling, validation, edit, revision, and export systems through the unified
desktop workbench.

Acceptance criteria:

- engineers can capture explicit process intent and unknowns without changing source CAD
- exact supported OCP faces can receive traceable engineering annotation roles
- deterministic assembly analysis exposes datum, locating, support, clamp, weld, access, and missing-evidence results
- supported fixture concepts can be generated, compared, selected, visualized, edited, regenerated, and revalidated
- invalid concepts are never recommended and provisional review geometry is never represented as released manufacturing geometry
- findings can be filtered, linked, and marked reviewed without changing authoritative validation state
- customer-owned tooling metadata remains private and visibly verified or unverified; no supplier scraping or redistribution is added
- the complete workflow, revision history, validation evidence, visibility, and review boundary survive save and reload
- local Windows visual review, hosted Kernel acceptance, independent review, and merge are required before completion

**Recommended level:** Sol

## Milestone 29 - Implement the desktop UI and branding system

**Status:** Complete

Independently visually accepted and squash-merged in PR #51 at
`4b6691a`. The UI system preserves deterministic engineering authority and
does not own fixture policy or project persistence.

Apply the approved FXD UI & Branding Kit v1.1 to the unified PySide6 workbench
without replacing engineering architecture or weakening evidence boundaries.

Acceptance criteria:

- the approved shared palette, typography, application icon, logos, Qt icons,
  and QSS are centralized and checksum traceable
- the workbench presents compact product identity, source-CAD read-only
  evidence, renderer health, workflow state, engineering status, findings, and
  approval gates without illustrative domain values
- the VTK viewport remains persistent and visually dominant at supported desktop
  sizes
- invalid, provisional, stale, incomplete, and engineer-modified states remain
  explicit through icon, text, and semantic color
- layout state is user-persistent but engineering decisions remain in the project
- source STEP bytes, SHA-256 identity, project schema, deterministic validation,
  renderer performance, and clean shutdown remain unchanged
- accessibility, focused Qt regressions, full repository validation, local
  Windows visual review, independent review, CI, and merge are required before
  completion

**Recommended level:** Sol

## Milestone 30 - Real manufacturing geometry and tack/location fixtures

**Status:** Complete

Squash-merged through PR #52 at `edf65bb`. The accepted implementation adds
typed fixture-build, lifecycle, tack/location, Cleco, authored OCP component,
BOM, nest, and guided two-face orientation evidence without weakening review
or source-CAD boundaries.

Extend the existing fixture architecture with editable, deterministic
construction evidence for real OCP manufacturing geometry, laser-cut and
tube-frame concepts, tack/location workflows, Cleco strategies, lifecycle and
job-revision choices, manufacturing BOM and nest classification, and review
only export packages. Completion still requires independent review, hosted
kernel acceptance, Windows visual review, user engineering acceptance, and
merge.

**Recommended level:** Sol

## Milestone 31 - AI Fixture Engineer and guided validation

**Status:** Complete

Reconciled by Issue #56 from merged PR #53 at `ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc`. The implementation handoff's earlier approval-required wording remains historical; later acceptance and merge are controlling evidence.

Add one provider-neutral, versioned, editable fixture proposal after accepted
manufacturing orientation. Ask only for missing essential intent, use the
existing deterministic engines for the offline baseline and authoritative
validation, provide plain-language correction routing, persist proposal
provenance and engineer decisions, and fail approval/export closed for stale or
blocked proposals. The UI must remain review-oriented and must not expose raw
identities or matrices in normal mode.

Acceptance still requires focused and full automated validation, real OCP and
Windows viewer acceptance, independent Codex review, and user engineering
visual acceptance. No production approval, autonomous iteration, learned global
rules, supplier scraping, or paid-service enablement is included.

**Recommended level:** Sol

## Milestone 32 - Multi-station weld fixture synthesis

**Status:** Active

Issue #57 is the authoritative scope. Draft PR #54 is the implementation PR. Evidence profiles A, B, C, D, and E are required. The milestone remains Active through implementation merge and its separate closeout evidence PR. A distinct state-finalization PR must then record the closeout merge SHA and formally pause the approved product lane with zero Active milestones; no Milestone 33 is created or implied.

**Recommended level:** Sol
