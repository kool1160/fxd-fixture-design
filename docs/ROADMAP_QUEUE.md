# FXD Forward Milestone Queue

This roadmap extends the product beyond the current Phase 3 backlog. It preserves the governing principle: **AI proposes. Engineering validates.** Source CAD remains immutable, deterministic engineering remains authoritative, and no generated fixture is approved for production without qualified human review.

## Queue

1. Milestone 19 — Deepen weld-fixture and automation workflow
2. Milestone 20 — Harden project reliability and application operations
3. Milestone 21 — Generate complete fixture structures
4. Milestone 22 — Optimize locator, support, and clamp placement
5. Milestone 23 — Produce manufacturing-ready fixture geometry
6. Milestone 24 — Generate fixture drawings and documentation
7. Milestone 25 — Optimize cost, volume, and manufacturability
8. Milestone 26 — Complete end-to-end engineering pilots

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

Implemented as a deterministic placement proof layer. Kernel-derived surface
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

**Status:** Pending

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

**Status:** Pending

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

**Status:** Pending

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

**Status:** Pending

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
