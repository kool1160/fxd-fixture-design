# FXD Engineering Constitution

## 1. Source geometry is immutable

Imported customer/product geometry is evidence, not a destructive editing workspace. Store reconstruction, annotations, fixture features, derived geometry, and corrections separately. Preserve source bytes, identity, units, hierarchy, and transforms.

## 2. Use a CAD-neutral domain model

The engineering core may not depend on SOLIDWORKS, Inventor, Fusion, or another vendor object model. Connectors translate through the neutral FXD contracts.

## 3. Reconstruct product meaning before designing around it

A valid B-Rep is not automatically a sufficient manufacturing model. When fixture strategy depends on component, feature, hole, plane, axis, bend, contact, or weld meaning, FXD must derive or obtain that meaning with traceable confidence. Material ambiguity blocks synthesis or asks the engineer; it is never silently guessed.

## 4. AI owns fixture strategy in AI Design mode

When the operator selects live AI Design, the configured OpenAI model must author the strict typed fixture strategy that drives downstream build planning. AI is not merely an explainer attached after deterministic templates generate the fixture.

The strategy must contain the material locating, supporting, clamping, reaction, base/construction, loading/unloading, access, assumptions, alternatives, and precedent decisions required by the supported gate.

## 5. Deterministic systems own executable engineering truth

Language models may reason, interpret, propose, and repair. They are not the sole authority for source identity, dimensions, units, topology, constraints, collision, clearances, access, persistence, quantities, or safety/release claims.

Only validated typed commands may reach the geometry engine. OCP authors the B-Rep. Deterministic failures remain authoritative.

## 6. Live AI may not fail invisibly

AI Design and deterministic/offline mode are separate explicit modes.

When AI Design is selected, missing configuration, timeout, provider failure, quarantine, cancellation, or malformed output must stop clearly. FXD may not quietly substitute deterministic fixture generation and present it as AI-designed.

Provider, model, request state, whether a live request occurred, and strategy provenance must be visible and persisted without exposing secrets.

## 7. Every generated feature must be traceable

A support, stop, pin, clamp mount, reaction support, relief, rail, riser, station, or base feature must identify:

- the source product/reconstruction evidence that caused it;
- the AI strategy decision or manual command;
- the compiled rule/command that authored it;
- parameters and units;
- cited precedents;
- assumptions, warnings, and validation findings;
- repair lineage and later user edits.

## 8. Units and tolerances are explicit

Use one documented internal unit system, initially millimeters and radians unless the kernel requires another representation. Never infer units silently. Separate nominal geometry, manufacturing allowance, contact clearance, process tolerance, and inspection intent.

## 9. Fixture design is constraint design

Represent the intended removal of translational and rotational degrees of freedom. Detect underconstraint, redundant or contradictory restraint, tolerance binding, and intentional float. Clamping direction and reaction must be evaluated relative to locating/support geometry.

## 10. Access and removability are first-class

A geometrically valid fixture is invalid when the product, operator, torch, clamp, robot, cable, finished assembly, cleaning tool, or service action cannot enter or leave the required space. Loading, welding/tacking, unloading, maintenance, and changeover sequences must be represented honestly.

## 11. Prefer manufacturable simplicity

Favor standard purchased components, laser-cut plates, formed parts, tube/plate structures, tab-and-slot construction, replaceable wear points, understandable adjustment, and shop-buildable geometry over unnecessary machining or visually impressive complexity.

## 12. Fixture precedents must contain reasoning

An opaque part/fixture STEP pair is not sufficient durable knowledge. Accepted precedents must connect product features and manufacturing intent to fixture responses, reasons, constraints, access/sequence, parameters, corrections, and failure history.

Private precedents and proprietary shop heuristics remain separately controlled.

## 13. Bounded repair, not open-ended agent loops

Deterministic failures may be returned to AI only through a structured repair contract with frozen accepted decisions, legal commands, and explicit cost/turn/retry limits. Repeated failure becomes `BLOCKED`; it does not justify unlimited retries or weakened validation.

## 14. Human approval is mandatory

FXD produces fixture designs, real geometry, evidence, and warnings. It does not certify a fixture, approve a weld process, guarantee distortion, certify clamp force/structure, or authorize production. Qualified human engineering review remains mandatory.

The decisive product question is:

> Would an experienced fixture engineer actually build and use this?

Software that cannot earn that answer has not passed the product gate.

## 15. Validation requires representative geometry and real failure layers

Use synthetic and legally shareable golden models covering assemblies, transforms, thin sheet, plates, tubes, holes, inaccessible welds, trapped products, tolerance variation, ambiguous reconstruction, invalid AI strategies, and deliberately poor fixtures.

Test pure logic, OCP B-Rep, persistence, native UI/VTK behavior, and live-provider integration at the layer where each can fail. Offline tests do not prove a live AI request.

## 16. AI output is bounded untrusted data

Natural-language intent compiles into restricted versioned contracts. Validate schema, identities, source/reconstruction versions, units, parameters, commands, and provenance before authoring. Provider output never executes arbitrary code or receives unrestricted tools.

## 17. Privacy is local-first

Do not upload customer/employer CAD, private fixture geometry, proprietary corrections, file paths, secrets, or hidden project dumps to external services by default. AI use must disclose exactly what structured information leaves the machine.

## 18. Dependency licensing and paid services are architecture concerns

Record license, redistribution obligations, binary requirements, commercial implications, provider terms, and cost boundaries for every geometry, CAD, UI, AI, and export dependency. Availability is not commercial permission.

## 19. Proprietary knowledge stays separated

Public code may define interfaces, synthetic fixtures, generic rules, and legally shareable precedent metadata. Confidential shop knowledge, patent-sensitive methods, customer corrections, real fixture libraries, and commercial rule packs live in ignored or separately controlled storage.

## 20. One active gate and one independent review path

Development follows `docs/OPERATOR_PROTOCOL.md`: one active gate, one implementation PR, Review-Control as planning/review authority, Codex as bounded builder, and exact-head evidence. Claude/Anthropic is not a standard implementation, review, audit, or fallback route.

## 21. One health command

`scripts/ci.sh` remains the authoritative repository-health command. Every accepted gate keeps it working and extends it only when the new risk requires deterministic coverage.

## 22. Prove the core product before expanding scope

Before multiple fixture families, multi-station optimization, broad native CAD, SaaS, billing, learned universal rules, or model routing, FXD must pass one representative AI-driven fixture synthesis proof with live provenance, real authoring, deterministic validation, bounded repair, and qualified practicality acceptance.