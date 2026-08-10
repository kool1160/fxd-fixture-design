<!-- FXD-MILESTONE-STATE: docs/MILESTONE_STATE.json -->
# FXD — Intelligent Fixture Design

FXD is an AI-driven industrial fixture-design platform for manufacturing and fabrication.

The first product focus is practical weld fixturing for sheet-metal, plate, tube, formed-part, and mixed fabricated assemblies. The intended outcome is not a contour-matched cradle or a geometrically valid demo. FXD must produce practical, editable fixture geometry that a qualified fixture engineer would actually build and use after review.

## Product mission

> Import or reconstruct the assembly, describe the manufacturing job, use AI to author the fixture strategy, compile that strategy into real OCP geometry, challenge it deterministically, and present the result for qualified engineering approval.

## Current status

**Governance and architecture reset active under Issue #66. Product implementation is held.**

The previous Issue #57 / PR #54 path is closed as superseded. It proved substantial OCP, VTK, geometry, validation, persistence, fixture-library, and export capability, but it did not prove FXD's product value: AI remained advisory while deterministic templates generated the fixture, and repeated human reviews rejected fixture practicality.

The closed branch and evidence are preserved for selective salvage. They are not authorization to continue the old flow.

Read [`CURRENT.md`](CURRENT.md) for the exact active scope and next valid action.

The pre-reset machine registry remains at [`docs/MILESTONE_STATE.json`](docs/MILESTONE_STATE.json) for historical and deterministic migration evidence. During Issue #66 it cannot override `CURRENT.md` or reopen closed work.

## Accepted product architecture

```text
Product CAD + manufacturing intent + approved precedents
                          ↓
       native product reconstruction and evidence
                          ↓
        typed live-AI fixture strategy
                          ↓
      restricted deterministic command compiler
                          ↓
              real OCP fixture authoring
                          ↓
       deterministic engineering validation
               ↓ pass              ↓ fail
       human review/export    bounded AI repair
```

AI reasons about fixture strategy. Deterministic systems own executable geometry, validation truth, and release blocking. Human engineering judgment owns practicality and production authority.

See [`docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md`](docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md).

## Core principles

- Source product CAD remains immutable and traceable.
- The engineering core remains CAD-neutral and vendor-independent.
- Product meaning is reconstructed before designing around anonymous geometry.
- Live AI Design produces the typed fixture strategy that actually drives authoring.
- OCP and deterministic checks own geometry, locating, collision, access, units, persistence, and export truth.
- AI failures cannot be hidden by a silent deterministic fallback.
- Every feature is traceable to source evidence, AI/manual strategy, commands, parameters, precedents, repairs, and edits.
- Fixture examples become structured product-feature-to-fixture-response precedents, not opaque STEP files alone.
- Qualified human fixture-engineering approval remains mandatory.
- The first proof is one representative fixture, not a universal platform demo.

## Development model

FXD now uses the same simple project-control shape proven in LaserX Design Studio:

> **Review-Control decides and reviews. GitHub remembers. Codex implements one bounded gate. Pull requests hold the evidence.**

Normal loop:

```text
Review-Control -> CONTINUE
Codex -> AWAITING_REVIEW
Review-Control -> CONTINUE | OWNER_DECISION | BLOCKED | COMPLETE
```

One repository. One active gate. One implementation PR. Codex does not choose scope, merge, advance, deploy, or approve its own work. Claude/Anthropic is not part of the standard implementation or audit path.

Read [`docs/OPERATOR_PROTOCOL.md`](docs/OPERATOR_PROTOCOL.md) and [`AGENTS.md`](AGENTS.md) before working.

## Read order

1. `AGENTS.md`
2. `CURRENT.md`
3. active GitHub issue
4. `docs/PRODUCT_DIRECTION.md`
5. `docs/OPERATOR_PROTOCOL.md`
6. `docs/ENGINEERING_CONSTITUTION.md`
7. `docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md`
8. `docs/ARCHITECTURE.md`
9. `docs/MILESTONE_CONTRACT.md`
10. active PR, exact head, review threads, and CI

Historical milestone registries, roadmaps, binders, and handoffs remain evidence and context. They do not override current control state.

## First new product proof

The next product gate must prove one representative fixture:

1. trustworthy native product reconstruction;
2. one intentional live OpenAI strategy request with visible provider/model provenance;
3. typed supports, locators, clamps/reactions, base/construction, loading/unloading, and access intent;
4. real OCP geometry authored from the AI strategy;
5. deterministic validation;
6. no more than one bounded AI repair cycle;
7. persistence and coherent review/manufacturing outputs;
8. qualified human judgment: **Would I actually build and use this?**

A fixture that is merely geometrically valid fails.

## Local workbench

On Windows, `launch-fxd.bat` starts the current engineering workbench using the repository `.venv`. Dragging a `.step` or `.stp` file onto the launcher opens that file.

The current launcher and application behavior predate the Issue #66 reset. Until the new AI-mode gate is implemented, do not assume normal launch proves that a live AI provider was configured or used. Provider provenance must become explicit in the next product gate.

## Repository health

Run:

```text
bash scripts/ci.sh
```

Passing checks prove only the behavior they actually exercise. Offline tests do not prove live-provider use, and software checks do not approve fixture practicality or production release.

## Rights

No open-source license is granted. Copyright © 2026 Christopher Hilton. All rights reserved. See `NOTICE.md`.