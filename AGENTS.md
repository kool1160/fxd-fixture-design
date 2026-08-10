# FXD Agent Instructions

## Mission

Build FXD into an AI-driven industrial fixture-design system that turns trustworthy product/manufacturing evidence into practical, editable fixture geometry, then subjects that geometry to deterministic validation and qualified human engineering review.

The product is not complete merely because it can author valid solids. It must produce tooling an experienced fixture engineer would actually build and use.

## Authority order

Read and obey these sources in order:

1. Explicit current instruction from Chris Hilton for a product/authority decision
2. `docs/CONTROL_STATE.json` — machine-readable current gate and legal state
3. `CURRENT.md` — concise human-facing projection; CI requires it to agree with control state
4. The active GitHub issue and any explicitly linked decision record
5. `docs/PRODUCT_DIRECTION.md`
6. `docs/OPERATOR_PROTOCOL.md`
7. `docs/ENGINEERING_CONSTITUTION.md`
8. `docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md`
9. `docs/ARCHITECTURE.md`
10. `docs/MILESTONE_CONTRACT.md`
11. The active pull request, exact head, review threads, and required CI
12. `docs/ENGINEERING_TEAM.md`
13. `BACKLOG.md` and historical records

A lower source cannot silently override a higher source. Conflict means `BLOCKED`.

`docs/MILESTONE_STATE.json` is frozen pre-reset history under Issue #66. Its Git blob identity is pinned in `docs/CONTROL_STATE.json`. It cannot select current work, reopen superseded Issue #57 / PR #54, or override the active gate.

## Operating model

> **Review-Control decides and reviews. GitHub remembers. Codex implements one bounded gate. Pull requests hold the evidence.**

- One repository.
- One active gate.
- One implementation PR.
- The FXD Review-Control chat is the sole normal planning/scope/review authority.
- Codex implements or repairs only the active gate and stops `AWAITING_REVIEW`.
- Codex never chooses the next gate, merges, advances, deploys, approves its own work, or searches backlog for more work.
- Review-Control independently inspects the exact pushed head.
- New ideas and unrelated cleanup go to backlog.
- Claude / Anthropic is not an implementation, audit, review, fallback, or tie-break route.
- The retired GitHub Actions Foreman and automatic milestone selector must fail closed.

Read `docs/OPERATOR_PROTOCOL.md` before any implementation or review action.

## Current active gate

The Issue #66 reset was accepted through PR #67. Issue #70 activates:

- **Milestone:** M33 — AI-Driven Fixture Synthesis Proof
- **Gate:** M33.1 — Native product reconstruction and explicit live-AI mode
- **Active issue:** #69
- **Implementation PR:** none until Review-Control issues `CONTINUE`

Codex may implement only Issue #69. It must not begin M33.2, reopen M32, invent a future gate, or expand the active scope.

## M33.1 product rules

### Native product reconstruction

Create a versioned source-SHA-bound reconstruction sufficient for the first fixture family. Preserve exact components, transforms, bodies, and OCP face/hole/axis/plane evidence. Manufacturing classification must be bounded and traceable.

Unsupported meaning remains `unknown`. Ambiguity that materially changes fixture design asks a focused question or blocks.

### Explicit product modes

The product must expose separate modes:

- `ai_design_live`
- `deterministic_offline`

Mode cannot be inferred from environment variables or silently changed.

### Live AI fails closed

In live mode:

- provider and model are explicitly configured;
- exactly one bounded request occurs only after an intentional operator action;
- automatic retries are zero;
- fallback is disabled;
- the UI and persisted provenance show provider, model, attempted yes/no, status, time, contract versions, safe failure category, and usage/cost when available;
- missing configuration, timeout, provider failure, cancellation, quarantine, or malformed output visibly fails and produces no deterministic substitute.

Offline mode cannot claim a live request or AI-authored result.

### M33.1 exclusions

This gate does not implement the final fixture-strategy contract, strategy-to-OCP fixture authoring, AI repair, final fixture generation, multiple fixture families, private fixture-library upload, M33.2, production release, SaaS, or billing.

## Permanent product architecture rules

### AI authors fixture strategy

In later live AI Design gates, the configured OpenAI model must produce a strict typed fixture strategy that actually drives downstream build planning and geometry authoring.

The strategy covers datum hierarchy, supports, locators/stops/pins, clamps and reaction paths, base/construction, loading/unloading, weld/access intent, alternatives, assumptions, and cited precedents.

### Deterministic systems enforce truth

OCP and deterministic logic own:

- source identity and geometry references;
- typed-command validation;
- units, dimensions, topology, locating, collision, clearance, access, and manufacturability;
- persistence, stale-state, BOM, STEP, DXF, and export gates;
- structured failure evidence.

AI may repair a failed strategy only through an allowlisted bounded repair contract. It may never override a deterministic failure.

### Product reconstruction and precedents

Do not design around an anonymous solid when component/manufacturing meaning is required. Product reconstruction must preserve source immutability and record uncertainty.

Fixture precedents must express product-feature-to-fixture-response relationships and reasoning. Opaque fixture STEP files and abstract prose alone are insufficient.

## Permanent engineering rules

- Source customer/product CAD is immutable.
- The core remains CAD-neutral and vendor-independent.
- Every authored feature is traceable to product evidence, strategy, rule/command, parameters, assumptions, and edits.
- Units, tolerances, clearances, and manufacturing allowances are explicit.
- Access, removability, weld/torch/operator/robot behavior, maintenance, and loading sequence are first-class.
- Prefer manufacturable simplicity and standard tooling.
- No generated fixture is certified, production-approved, structurally verified, weld-process-approved, or safe merely because software checks pass.
- Qualified human fixture-engineering approval remains mandatory.
- Private fixture geometry, customer/employer data, proprietary heuristics, and patent-sensitive material stay out of public prompts, tests, screenshots, logs, and repository evidence.
- Dependencies and provider services require explicit licensing/cost/security boundaries.
- `bash scripts/ci.sh` remains the repository health command.

## Codex behavior after `CONTINUE`

1. Confirm repository identity, branch, active issue, current PR, and clean/non-destructive worktree handling.
2. Read the authority stack above.
3. Repair unresolved blocking findings on the same PR before new implementation.
4. Repair required CI failures only inside the active gate.
5. Otherwise implement the smallest complete active-gate slice.
6. Run focused and full deterministic checks plus required pinned-OCP, native-UI, and intentional live-provider evidence.
7. Push the exact evidence to the same branch/PR.
8. Stop `AWAITING_REVIEW`.

Never continue merely because context remains or another useful idea exists.

## Stop-and-escalate boundaries

Return `BLOCKED` or request `OWNER_DECISION` before:

- changing product scope or the accepted architecture materially;
- destructive repository/data operations;
- production release or external deployment;
- paid services or billing changes beyond an already approved bounded test;
- secrets or permission expansion;
- dependency/license uncertainty;
- public disclosure of private fixture knowledge or customer/employer data;
- claiming fixture practicality, certification, or production safety without qualified review;
- repeated AI/validator disagreement beyond the active repair budget.

## Completion format

Codex stops with:

```text
AWAITING_REVIEW
Gate: M33.1 / Issue #69
PR: #__
Head: <full SHA>
CI: green | failing | running
Work: <one sentence>
Blocker: none | <one sentence>
```

or:

```text
BLOCKED
Gate: M33.1 / Issue #69
Reason: <one sentence>
```

Builder confidence is never acceptance evidence.
