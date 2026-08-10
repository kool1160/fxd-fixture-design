# FXD Architecture

## Architectural objective

FXD is a CAD-neutral fixture-design application in which a live AI model may author a restricted engineering strategy, while deterministic systems own product evidence, executable geometry, validation, persistence, and release blocking.

The central correction from Issue #66 is architectural:

**AI must drive the fixture strategy before geometry generation. It is not merely an adviser attached to a fixture that deterministic templates already decided to build.**

## High-level system

```text
CAD / assembly intent / private approved precedents
                     |
                     v
       Import, topology, and reconstruction
                     |
                     v
      Native Product + Manufacturing Model
                     |
          +----------+-----------+
          |                      |
          v                      v
missing-intent questions   precedent retrieval
          |                      |
          +----------+-----------+
                     v
        Typed AI Fixture Strategy
          (explicit live provider mode)
                     |
                     v
 Restricted strategy/command compiler
                     |
                     v
       Real OCP fixture authoring
                     |
                     v
 Deterministic engineering validation
          |                      |
          | pass                 | structured fail
          v                      v
  human review/export       bounded AI repair
                                 |
                                 +----> recompile / re-author / revalidate
```

## Authority layers

### 1. Immutable source evidence

Owns source bytes/hash, assembly/component identities, transforms, units, B-Rep topology, and imported provenance. Source customer/product CAD is never destructively edited.

### 2. Native product reconstruction

Represents manufacturing-relevant product meaning separately from source CAD:

- components and instances;
- plate/sheet/tube/formed/machined/purchased classifications;
- holes, planes, axes, profiles, bends, contacts, and candidate datums;
- weld candidates and confirmed weld intent;
- critical characteristics;
- permitted/forbidden contacts;
- confidence and unresolved ambiguity.

Deterministic recognition and AI interpretation may contribute, but the persisted model records provenance and uncertainty. Material ambiguity blocks synthesis or asks a focused question.

### 3. Engineering intent and annotations

Stores build orientation, process, quantity, tolerances, critical characteristics, welds, loading/unloading, operator/robot sides, shop capabilities, fixture purpose, and explicit constraints. It is source-SHA and revision bound.

### 4. Fixture precedent store

Stores approved product-feature-to-fixture-response relationships, not merely fixture files.

Public contracts and synthetic/generic records live in the repository. Private fixture geometry, proprietary corrections, and shop heuristics live in local or separately controlled storage.

Precedent retrieval is evidence. It does not approve geometry.

### 5. AI strategy layer

`AiFixtureProvider` remains provider-neutral, with OpenAI as the first live adapter.

The AI layer receives compact structured context, selected precedent relationships, legal identity sets, supported command vocabulary, and explicit budgets. It returns a strict versioned fixture strategy.

It owns reasoning choices such as:

- datum hierarchy and intentional float;
- support and locator strategy;
- stops/pins;
- clamp targets, directions, reaction paths, reach/opening assumptions;
- base/construction strategy;
- loading/unloading and access intent;
- alternatives, assumptions, questions, and repair decisions.

It does not receive arbitrary execution authority and cannot mutate OCP directly.

### 6. Strategy compiler

The compiler converts the strategy into allowlisted typed build commands.

It validates:

- schema and source/reconstruction identities;
- current product and precedent references;
- units, ranges, and supported fixture family;
- command dependency and ordering;
- traceability and repair lineage;
- no arbitrary code, shell, network, or filesystem instructions.

Unsupported or stale references fail closed.

### 7. Fixture concept and build model

Represents the accepted strategy as editable engineering state:

- base/structure;
- supports, locators, stops, pins, clamps, reaction features, purchased tooling;
- generated parts and manufacturing metadata;
- load/unload/weld/access envelopes;
- alternatives, assumptions, findings, scores, and traceability;
- user edits and repair lineage.

The model is not a claim of production approval.

### 8. OCP geometry authoring

The geometry kernel authors real B-Rep only from compiled legal commands. It owns Boolean/topology operations, exact placement, containment, and neutral export geometry.

The kernel never asks the model for unstructured code and never treats model prose as executable geometry.

### 9. Deterministic validation

Owns authoritative checks for:

- source identity and current revisions;
- units, dimensions, precision, and topology;
- degrees of freedom, under/overconstraint, and intentional float;
- clamp force direction and reaction evidence;
- collision, clearance, access, loading, unloading, and trapped-part conditions;
- manufacturing authority and component containment;
- persistence and stale-state rules;
- BOM/STEP/DXF/export reconciliation;
- supported fixture-family limits.

A deterministic failure cannot be overridden by AI confidence or review preference.

### 10. Repair coordinator

Normalizes validation failures into a bounded repair contract containing failed rules, measured evidence, affected identities, frozen accepted decisions, legal repair commands, and remaining budget.

The first product proof permits at most one repair cycle. Repeated failure becomes explicit `BLOCKED` evidence.

### 11. Desktop presentation

The PySide6/VTK workbench exposes:

- native product/reconstruction evidence;
- AI versus offline mode;
- provider/model/request/provenance state;
- fixture strategy and alternatives;
- real authored geometry;
- validation findings and correction routes;
- user edits, review history, and approval/export boundaries.

The UI owns presentation, not engineering truth.

### 12. Connectors and outputs

Thin adapters import/export STEP and later vendor formats. The core remains useful without a vendor CAD host.

Outputs include editable project state and, when valid, reconciled STEP, DXF, BOM, setup, review, and traceability artifacts. Release remains human-controlled.

## Provider modes

### AI Design mode

- explicit provider and model configuration;
- one intentional live request or bounded repair request;
- visible request/provenance state;
- no silent deterministic fallback;
- provider failure stops clearly.

### Deterministic/offline mode

- explicit separate mode;
- may analyze, validate, exercise synthetic tests, and author manually specified plans;
- never claims AI-designed output.

## Security and privacy boundaries

- No API keys in source, projects, diagnostics, prompts, screenshots, tests, or CI artifacts.
- No customer/employer STEP bytes or private fixture geometry leave the machine without explicit authority.
- Provider context is compact and purpose-bounded.
- Private precedents remain local/private.
- AI output is untrusted data until strict parsing and deterministic validation.
- Paid requests are explicit, budgeted, and attributable.
- Supplier CAD is never scraped or redistributed without authorization.

## Development orchestration boundary

The product runtime AI is not the development orchestrator.

Project development follows `docs/OPERATOR_PROTOCOL.md`:

- Review-Control owns scope and independent review;
- Codex implements one active gate and stops `AWAITING_REVIEW`;
- GitHub owns durable state/evidence;
- no Claude/Anthropic audit or fallback path;
- one active gate and one implementation PR.

## First proof architecture

The next product gate is deliberately narrow. It must prove one representative fixture from product reconstruction through a live AI-authored strategy, real OCP authoring, deterministic validation, at most one repair, persistence/provenance, and qualified human practicality review.

Broader fixture families, multi-station optimization, integrated CAD expansion, SaaS, billing, and model routing remain deferred until that proof passes.

## Salvage from superseded M32

The closed M32 branch may contribute reviewed components such as OCP authoring, VTK display, exact feature evidence, validators, persistence, exports, and fixture-library contracts.

The following pattern is prohibited as the product authority:

```text
deterministic template generates fixture
→ AI returns advisory proposal
→ proposal identity is attached after generation
```

Any salvaged code must fit the accepted AI-strategy-first boundary.