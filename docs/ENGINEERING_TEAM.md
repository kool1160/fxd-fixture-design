# FXD Engineering Responsibilities

## Purpose

FXD uses explicit engineering responsibility boundaries so important disciplines challenge the product without creating a swarm of agents or pretending software review is professional certification.

Specialists may analyze, challenge, test, and explain. They may not bypass the Engineering Constitution, deterministic validation, the active gate, privacy/licensing rules, or qualified human approval.

## Project-control roles

### FXD Review-Control

Review-Control is the planning, scope, integration, and independent-review authority defined in `docs/OPERATOR_PROTOCOL.md`.

Owns:

- reading current GitHub truth;
- keeping one active gate and one implementation PR;
- selecting only materially relevant specialist questions;
- resolving product/architecture consistency inside approved direction;
- writing durable decisions and review findings;
- independently reviewing the exact pushed head;
- routine merge/next-gate advancement only when already authorized;
- owner escalation at genuine authority or judgment boundaries.

Must ask:

> Is this the smallest complete gate that moves FXD toward a fixture someone would actually build, and does the exact-head evidence prove it?

Review-Control does not perform normal product implementation.

### Codex implementation specialist

Codex receives `CONTINUE`, implements or repairs only the active gate, adds evidence, updates the same draft PR, and stops `AWAITING_REVIEW`.

Codex does not select scope, merge, advance, deploy, approve its own work, or start another task.

Must ask:

> Does every changed file and test map directly to the active issue and its review findings?

### Product runtime AI

The OpenAI model running inside FXD is a product component. It authors a restricted typed fixture strategy and bounded repairs under `docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md`.

It has no repository, GitHub, merge, deployment, or production-approval authority.

Must ask:

> What fixture strategy best satisfies the supplied product evidence and precedents, and which assumptions remain unresolved?

## Engineering disciplines

Review-Control applies only the disciplines materially affected by the gate. A discipline may be a read-only review lens, deterministic test owner, implementation responsibility, or qualified human acceptance role. It does not require a separate model call unless that creates real value.

### Chief Fixture Engineer

Owns overall fixture coherence: orientation, datum philosophy, supports, locating, clamping, repeatability, adjustability, loading/unloading, serviceability, and cost/volume tradeoffs.

Must ask:

> Would an experienced fixture engineer actually build and use this?

### Product Reconstruction Engineer

Owns manufacturing meaning derived from source CAD: components, transforms, plates/tubes/formed parts, holes, planes, axes, bends, contacts, weld candidates, confidence, and unresolved ambiguity.

Must ask:

> Does FXD understand what this assembly is well enough to fixture it, or is it designing around an anonymous solid?

### Geometry Engineer

Owns STEP import/export, assembly hierarchy, B-Rep topology, stable identities, exact references, Booleans, distance, collision, clearance, containment, profiles, numeric robustness, units, and OCP behavior.

Must ask:

> Does the real geometry actually support this conclusion and authored feature?

### Manufacturing Engineer

Owns sheet/plate/tube fabrication, laser cutting, forming, machining, purchased hardware, tab-and-slot construction, assembly sequence, tolerance practicality, serviceability, and cost.

Must ask:

> Can this be fabricated, assembled, maintained, and afforded in a real shop?

### Locator and Constraint Engineer

Owns degrees of freedom, datum hierarchy, supports, stops, round/relieved pins, intentional float, under/overconstraint, tolerance binding, thermal growth, and replacement strategy.

Must ask:

> Is every required degree of freedom controlled without making the product fight the fixture?

### Clamp and Tooling Engineer

Owns clamp type, target, direction, reaction path, force assumptions, stroke, reach, mounting, opening, access, part deformation, purchased tooling, spatter exposure, and maintenance.

Must ask:

> Will this hold the assembly without distorting it, blocking work, or creating a maintenance nightmare?

### Weld Process Engineer

Owns weld-joint evidence, manual/cobot/robot approach, torch and cable envelopes, tack/weld sequence, heat/distortion awareness, interference, spatter, helmet/hand access, and uncertainty.

Must ask:

> Can the weld actually be made correctly and repeatedly with this fixture in place?

### Robotics and Automation Engineer

Owns cobot/robot reach assumptions, end-of-arm tooling, approach paths, collision envelopes, loading/unloading automation, and future simulation connectors.

Must ask:

> Can the automation reach, move, work, and clear the fixture without impractical motion or collision?

### CAD and Fixture-Editing Engineer

Owns neutral file contracts, future host-CAD adapters, native fixture-editing operations, stable references through regeneration, editable outputs, and preventing vendor objects from leaking into the core.

Must ask:

> Can the engineer finish routine fixture work without corrupting source CAD or locking FXD to one vendor?

### AI Systems Engineer

Owns typed strategy/repair contracts, context design, provider integration, model provenance, explicit live/offline modes, cost and timeout limits, structured-output quarantine, and resistance to hallucinated geometry or claims.

Must ask:

> Is AI genuinely driving the authorized strategy, or is it merely decorating deterministic output—and can failure be mistaken for success?

### Knowledge and Precedent Engineer

Owns product-feature-to-fixture-response precedents, source attribution, private/public separation, accepted corrections, failure history, confidence, retrieval, and rule versus preference classification.

Must ask:

> What exactly should FXD learn from this fixture, and is the reasoning captured rather than just the final shape?

### Validation Engineer

Owns invariants, engineering-rule tests, representative synthetic geometry, live-provider boundaries, OCP/native evidence, regression cases, traceability, failure packages, and exact-head acceptance evidence.

Must ask:

> What evidence proves this at the layer where it can fail, and what could still make it wrong?

### UX and Workflow Engineer

Owns visible mode/provenance state, assumption editing, geometry selection, strategy alternatives, findings, correction routes, undo-safe behavior, persistence, and keeping complexity understandable.

Must ask:

> Can the engineer tell what AI did, challenge it, correct it, and distinguish live AI from offline fallback without guessing?

### IP, Privacy, Licensing, and Standards Guardian

Owns proprietary/public boundaries, customer/employer data protection, patent-sensitive review, dependency/provider/vendor terms, standards attribution, and commercial distribution risks.

Must ask:

> Can this information, dependency, provider request, artifact, and implementation be safely used, committed, distributed, and commercialized?

### Qualified Human Fixture Reviewer

Owns the final judgment that software cannot supply: practical locating/clamping, loading, welding, distortion response, ergonomics, maintenance, shop buildability, safety boundaries, and production suitability.

Must ask:

> Would I actually build this, use it, and accept responsibility for the remaining engineering decisions?

This role cannot be replaced by a model, test suite, CI job, or code reviewer.

## Conflict rules

- Deterministic geometry and validated engineering rules outrank AI preference.
- Qualified practicality rejection outranks passing software checks for the product gate.
- Manufacturing safety and unloadability outrank visual elegance.
- Product Reconstruction may block strategy when manufacturing meaning is insufficient.
- Geometry may reject unsupported references or authored claims.
- Locator, Clamp, Weld, Robotics, or Manufacturing responsibility may reject a concept within its evidence boundary.
- IP/Privacy/Licensing may block publication or provider transmission without blocking private local research.
- Unresolved disagreement is recorded as `BLOCKED`; it is not silently averaged away.
- No discipline can approve production release outside explicit qualified authority.

## Efficiency rule

Do not run every specialist on every gate. Review-Control names only the materially affected responsibilities and uses deterministic checks before spending additional model calls.

Claude/Anthropic is not a standard specialist, audit, fallback, or tie-break path.