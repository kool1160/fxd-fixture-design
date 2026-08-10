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

## Current reset

Issue #66 governs the current product and governance reset.

- Issue #57 and PR #54 are closed as superseded.
- Preserve their branch/evidence for selective salvage.
- Do not continue the advisory-AI/deterministic-template architecture.
- Do not begin product runtime implementation until PR #67 is accepted and `docs/CONTROL_STATE.json` activates one bounded next gate.

## Product architecture rules

### AI authors fixture strategy

In live AI Design mode, the configured OpenAI model must produce a strict typed fixture strategy that actually drives downstream build planning and geometry authoring.

The strategy must cover the material engineering choices required by the gate: datum hierarchy, supports, locators/stops/pins, clamps and reaction paths, base/construction, loading/unloading, weld/access intent, alternatives, assumptions, and cited precedents.

### Deterministic systems enforce truth

OCP and deterministic logic own:

- source identity and geometry references;
- typed-command validation;
- units, dimensions, topology, locating, collision, clearance, access, and manufacturability;
- persistence, stale-state, BOM, STEP, DXF, and export gates;
- structured failure evidence.

AI may repair a failed strategy only through an allowlisted bounded repair contract. It may never override a deterministic failure.

### No silent AI fallback

When AI Design is selected:

- provider and model must be explicitly configured;
- the UI must show provider, model, request state, and whether a live request occurred;
- missing configuration, provider failure, timeout, cancellation, quarantine, or malformed output stops the AI path clearly;
- deterministic/offline mode is a separate explicit mode;
- no deterministic fixture may be quietly substituted and presented as AI-designed.

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
6. Run focused and full deterministic checks plus risk-appropriate native/live-provider evidence.
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
Gate: <issue / objective>
PR: #__
Head: <full SHA>
CI: green | failing | running
Work: <one sentence>
Blocker: none | <one sentence>
```

or:

```text
BLOCKED
Gate: <issue / objective>
Reason: <one sentence>
```

Builder confidence is never acceptance evidence.