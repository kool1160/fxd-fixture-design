# FXD Product Direction

## Product identity

FXD is an intelligent industrial fixture-design platform. It begins with weld fixturing for fabricated assemblies and is intended to expand later to gauges, nests, inspection tooling, assembly fixtures, and other workholding.

The defining workflow is:

> Give FXD the product assembly, manufacturing intent, and approved fixture precedents; receive a practical, editable fixture strategy authored into real geometry, deterministically challenged, and presented for qualified engineering approval.

## The product problem

Existing fixture automation commonly produces contour-matched skeletons, generic cradles, or mathematically valid geometry that ignores how a real fixture is loaded, located, clamped, welded, maintained, and removed.

FXD must reason about the manufacturing job, not just surround a finished solid.

A successful fixture is not one that passes software checks. It is one a qualified fixture engineer would actually build and use after review.

## Current product reset

Issue #66 supersedes the prior Milestone 32 direction.

The closed M32 implementation proved substantial OCP, VTK, geometry, persistence, validation, fixture-library, and export capability. It did not prove the product because AI remained advisory while deterministic templates generated the fixture, and repeated human reviews rejected practical fixture quality.

The branch and evidence remain available for selective salvage. The old product flow is not the continuing authority.

## Product differentiators

FXD must:

- reconstruct or derive enough native product meaning to distinguish components, features, transforms, holes, planes, axes, contacts, and weld intent;
- understand assemblies rather than treating the weldment as one anonymous body;
- use AI to author the fixture strategy—not merely explain a deterministic result;
- separate locating from clamping;
- reason about six degrees of freedom and intentional float;
- select supports, locators, stops, pins, clamp targets, and reaction paths from exact product evidence;
- consider torch, operator, robot, loading, unloading, cleaning, and maintenance access;
- prefer standard and laser-cut/fabricated construction before unnecessary machining;
- use private structured precedents that explain why a fixture was designed as it was;
- produce alternatives and visible tradeoffs instead of one opaque answer;
- expose assumptions and let the engineer correct them;
- preserve deterministic validation and qualified human approval.

## Accepted authority split

### AI designs the strategy

In explicit live AI Design mode, the configured OpenAI model returns a strict typed fixture strategy covering the material design choices required by the supported fixture family.

It may interpret geometry and intent, retrieve approved precedents, choose/rank strategies, propose typed repairs, and explain tradeoffs.

### Deterministic systems execute and police it

The geometry engine compiles only allowlisted typed commands, authors real OCP geometry, and runs deterministic checks for source identity, units, topology, locating, collision, access, manufacturability, persistence, and export.

A failed deterministic check cannot be overridden by AI confidence.

### The engineer approves reality

FXD does not certify structure, clamp force, weld process, distortion, ergonomics, safety, or production release. Qualified engineering approval remains mandatory.

## No silent fallback

AI Design and deterministic/offline mode are different product modes.

When AI Design is selected:

- the provider and model are explicit;
- the application proves whether a live request occurred;
- provenance and request state are visible;
- provider failure, missing configuration, timeout, quarantine, or cancellation stops clearly;
- FXD may not quietly substitute a deterministic fixture and present it as AI-designed.

Offline mode remains valuable for analysis, validation, tests, and manually specified plans, but it must be labeled honestly.

## Product reconstruction

Before fixture strategy, FXD must create a trustworthy source-SHA-bound native product model sufficient for the active fixture family.

Where evidence supports it, the model should identify:

- components and transforms;
- plate, sheet, tube, formed, machined, and purchased-part roles;
- planes, axes, holes, edges, bends, profiles, and contacts;
- candidate datums and permitted/forbidden contacts;
- weld candidates and engineer-confirmed weld intent;
- critical characteristics;
- uncertainty and missing intent.

When ambiguity materially changes fixture design, FXD asks a focused question or blocks. It does not design confidently around unknown meaning.

## Fixture precedents

Chris's fixture library is a high-value private product asset, but geometry alone is not enough.

FXD must convert accepted examples and corrections into structured relationships:

```text
product feature / intent
→ fixture response
→ reason
→ parameters / units
→ constraint or intentional float
→ access and sequence
→ correction / failure history
```

Private geometry and proprietary shop knowledge remain local and separately controlled. Public repository content is limited to contracts, synthetic examples, and legally shareable generic knowledge.

## First proof boundary

Before broad scope, FXD must prove one representative fixture from end to end:

1. trustworthy product reconstruction;
2. one intentional live OpenAI strategy request using an explicitly selected high-capability model;
3. typed supports, locators, clamps/reactions, base/construction, loading/unloading, and access intent;
4. real OCP authoring driven by that strategy;
5. deterministic validation;
6. at most one bounded AI repair cycle;
7. persistence and visible provenance;
8. qualified human review answering: **Would I actually build and use this?**

A fixture that is merely geometrically valid fails this proof.

## Initial fixture scope

The first proof targets one deliberately bounded weld-fixture family for a representative fabricated assembly. It does not promise universal fixturing.

Multiple fixture families, multi-station optimization, robot simulation, broad learned rules, or commercialization infrastructure do not begin until the first proof passes.

## Integrated CAD direction

FXD ultimately needs a fixture-focused native CAD workspace sufficient to inspect, correct, and finish routine fixture work without forcing every ordinary edit into another CAD package.

That workspace should support a bounded set of fixture-native operations—plates, blocks, tubes, supports, stops, pins, clamp mounts, holes, slots, tabs, notches, reliefs, markings, transforms, patterns, replacement, persistence, and synchronized outputs.

It must not distract from the first AI-driven synthesis proof. Issue #62 remains a product decision for later governed planning.

## CAD-neutral boundary

FXD remains standalone and CAD-neutral. STEP is the first neutral input/output. Future SOLIDWORKS, Inventor, Fusion, Creo, Onshape, CATIA, NX, and other connectors are thin adapters around the same product and fixture contracts.

CAD-neutral means vendor-independent, not CAD-disconnected.

## Commercial direction

FXD may become commercial software. Do not add billing, public accounts, SaaS infrastructure, or broad cloud storage until the local engineering product proves value.

The base product should remain useful without unbounded paid AI usage. Live AI use must be explicit, budgeted, attributable, and replaceable behind a stable provider interface.

## Permanent non-goals

FXD does not initially promise:

- universal fixturing for every geometry or process;
- certified thermal-distortion prediction;
- structural or clamp-force certification;
- weld-process or safety approval;
- automatic production release;
- complete robot offline programming;
- replacement of every general-purpose CAD capability;
- unattended modification of customer CAD;
- supplier scraping or unauthorized CAD redistribution;
- hidden provider use or silent AI fallback.