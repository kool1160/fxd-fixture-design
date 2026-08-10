# AI-Driven Fixture Synthesis Architecture

## Decision

FXD's defining product loop is no longer “deterministic fixture generator plus advisory AI.”

The accepted architecture is:

```text
Product CAD / assembly intent / private precedents
                    ↓
      Native product reconstruction and evidence
                    ↓
     Typed AI Fixture Strategy (live OpenAI mode)
                    ↓
 Restricted strategy-to-geometry command compiler
                    ↓
           Real OCP fixture authoring
                    ↓
     Deterministic engineering validation
          ↓ pass                 ↓ fail
  human review/export     structured repair findings
                                  ↓
                     one bounded AI repair cycle
                                  ↓
                       re-author and revalidate
```

AI owns design reasoning. Deterministic systems own executable geometry, validation truth, and release blocking.

## 1. Native product reconstruction

Fixture synthesis must not begin from an anonymous body when manufacturing meaning is required.

The product-understanding layer must produce a versioned, source-SHA-bound native model containing, where evidence supports it:

- assembly components and instances;
- transforms and units;
- plate, sheet, tube, formed, machined, and purchased-part classifications;
- planes, axes, holes, edges, bends, profiles, contacts, and candidate datums;
- weld candidates and engineer-confirmed weld intent;
- critical characteristics and permitted/forbidden contact regions;
- stable source references and uncertainty.

The reconstruction may combine deterministic recognition and AI classification, but unsupported meaning remains explicit. Ambiguity that materially changes fixture strategy blocks synthesis and asks the engineer a focused question.

Source CAD remains byte-immutable.

## 2. Fixture precedent model

A fixture STEP file is not sufficient precedent because it records the result without the reasoning.

FXD precedents must encode relationships between product evidence and fixture responses. A precedent may contain:

```text
product feature / intent
→ fixture response
→ reason
→ parameters and units
→ constraints and intentional float
→ loading/unloading sequence
→ weld/access keep-outs
→ accepted corrections
→ known failure modes
```

Required relationship categories include:

- primary, secondary, and tertiary location;
- support placement and clamp reaction;
- round versus relieved pin strategy;
- clamp target, direction, opening, reach, and mounting;
- base, rail, riser, station, tab/slot, and purchased-tooling strategy;
- loading, unloading, tack/weld, cleaning, maintenance, and changeover;
- manufacturing process, quantity, tolerance intent, and lifecycle.

Private fixture geometry, corrections, and shop heuristics remain local/private. The public repository contains contracts, synthetic examples, and legally shareable generic evidence only.

## 3. Typed AI Fixture Strategy

The live model must return a strict versioned contract—provisionally `fxd-fixture-strategy-v1`—that actually drives downstream authoring.

At minimum the strategy must identify:

- immutable product source and reconstruction identity;
- fixture purpose and supported family;
- manufacturing orientation;
- datum hierarchy and controlled/floating degrees of freedom;
- support locations and referenced product evidence;
- locator/stop/pin selections and references;
- clamp targets, force directions, reaction supports, open/release paths, and tooling requirements;
- base and construction strategy;
- loading and unloading sequence;
- weld/tack and operator/robot access keep-outs;
- alternatives considered;
- assumptions, unresolved questions, confidence, and cited precedents;
- explicit parameters with units and legal ranges;
- required deterministic checks.

Provider prose alone cannot author geometry. Every material design decision must compile into an allowlisted typed command referencing governed identities.

## 4. Strategy compiler and OCP authoring

A deterministic compiler translates the accepted strategy into a fixture build plan and restricted OCP-authoring commands.

It must:

- resolve only current governed product/precedent identities;
- reject unknown or stale references;
- validate units and parameter ranges;
- preserve traceability from each authored feature back to AI strategy, product evidence, precedent, and later repair;
- author only supported fixture primitives and purchased-tooling envelopes;
- never let provider output execute arbitrary Python, shell, CAD, network, or filesystem operations.

The OCP kernel authors the real B-Rep. AI never directly mutates kernel objects.

## 5. Deterministic validation

After authoring, deterministic validation remains authoritative for:

- source identity and topology;
- units, dimensions, and tolerances;
- 3-2-1 / constraint behavior and intentional float;
- support and clamp reaction paths;
- collision, clearance, access, trapped-part, and load/unload checks;
- feature containment and manufacturing authority;
- persistence, stale-state, export, BOM, STEP, and DXF reconciliation;
- prohibited or unsupported operations.

A failed deterministic check cannot be overridden by model confidence, a reviewer preference, or a passing provider response.

## 6. Bounded AI repair

Validation failures are normalized into a structured repair package containing:

- failed rule and severity;
- affected authored and product identities;
- measured evidence;
- permitted repair commands;
- frozen successful decisions that must not change;
- remaining budget.

The default first proof permits at most one AI repair cycle. Repair must update the same strategy lineage and cannot expand fixture family or gate scope.

Repeated failure ends `BLOCKED`; it does not trigger an open-ended agent loop.

## 7. Explicit provider modes

FXD has two visibly separate modes:

### AI Design — live

- requires explicit provider and model configuration;
- makes an intentional live request;
- displays provider, model, request ID/state, timestamp, strategy identity, and token/cost data when available;
- fails closed on missing configuration, timeout, provider failure, quarantine, cancellation, or malformed response;
- never silently substitutes deterministic fixture generation.

### Deterministic / offline analysis

- is explicitly selected and labeled;
- may analyze, validate, author known manually specified plans, and exercise tests;
- must not claim an AI-designed fixture.

The UI must make these states impossible to confuse.

## 8. Model policy

The first synthesis proof uses an explicitly configured high-capability OpenAI model. Model identity is operator-selected configuration, recorded in proposal provenance, and never guessed or silently changed by FXD.

Lower-cost models may later support bounded classification or explanation only after evidence shows they meet the task. No Claude/Anthropic product or review fallback is part of the accepted architecture.

## 9. Acceptance proof

Before multiple fixture families, SaaS, billing, broad CAD editing, or learned global rules, FXD must prove one representative fixture:

1. reconstruct the product sufficiently for fixturing;
2. make one visible live AI strategy request;
3. author real fixture geometry from that strategy;
4. reject at least one seeded invalid strategy or repair finding deterministically;
5. complete no more than one bounded AI repair;
6. persist and reload complete provenance;
7. reconcile STEP/DXF/BOM/review output where applicable;
8. receive qualified human judgment: **Would I actually build and use this?**

A geometrically valid but practically poor fixture fails the proof.

## 10. Salvage boundary

The closed M32 branch contains valuable OCP, VTK, geometry, validation, persistence, fixture-library, and export work. Those components may be selectively reused after review.

The old flow—deterministically generate first, then attach an AI proposal identity—is not reusable as the product authority.