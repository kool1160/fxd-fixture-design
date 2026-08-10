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

> **Review-Control decides and reviews. GitHub remembers. ChatGPT Codex Remote implements one bounded gate. Pull requests hold the evidence.**

- One repository.
- One active gate.
- One implementation PR.
- The FXD Review-Control chat is the sole normal planning/scope/review authority.
- ChatGPT Codex Remote implements or repairs only the active gate and stops `AWAITING_REVIEW`.
- Codex never chooses the next gate, merges, advances, deploys, approves its own work, or searches backlog for more work.
- Review-Control independently inspects the exact pushed head.
- New ideas and unrelated cleanup go to backlog.
- Claude / Anthropic is not an implementation, audit, review, fallback, or tie-break route.
- The retired GitHub Actions Foreman, automatic milestone selector, and paid GitHub Codex dispatcher must fail closed.

Read `docs/OPERATOR_PROTOCOL.md` before any implementation or review action.

## Current gate — HELD

The Issue #66 reset was accepted through PR #67. Issue #70 activated M33.1, and PR #79 is the one preserved implementation PR:

- **Milestone:** M33 — AI-Driven Fixture Synthesis Proof
- **Gate:** M33.1 — Native product reconstruction and explicit live-AI mode
- **Active issue:** #69
- **Implementation PR:** #79
- **Branch:** `agent/m33-1-native-product-reconstruction`
- **State:** `HELD — COST CONTROL`

While `product_implementation_held` is true, Codex must not modify product code, run a repair pass, make a product live-AI request, merge, or advance. It stops `BLOCKED` and waits for explicit owner resume recorded by Review-Control.

## Permanent development/API cost boundary

- Normal FXD implementation and repair work uses **ChatGPT Codex Remote under the user's ChatGPT agentic allowance**.
- GitHub Actions and repository automation must **never** invoke `openai/codex-action` for FXD implementation, repair, review, or orchestration.
- GitHub Actions and repository automation must **never** receive or forward `OPENAI_API_KEY` for development/orchestration.
- Repository `OPENAI_API_KEY` use is reserved for explicit **FXD product-runtime** live-AI evidence/use, such as a separately authorized Profile E acceptance run on an exact reviewed head.
- Product-runtime API use requires explicit Review-Control authorization, explicit provider/model selection, the gate's request budget, and fail-closed provenance.
- CI must fail if a paid development dispatcher or repository workflow API-key route is reintroduced.

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

OCP and deterministic logic own source identity and geometry references; typed-command validation; units, dimensions, topology, locating, collision, clearance, access, and manufacturability; persistence, stale-state, BOM, STEP, DXF, and export gates; and structured failure evidence.

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

## Codex behavior after a future `CONTINUE`

A `CONTINUE` is legal only after Review-Control records `product_implementation_held: false`.

1. Confirm repository identity, branch, active issue, current PR, and clean/non-destructive worktree handling.
2. Read the authority stack above.
3. Repair unresolved blocking findings on the same PR before new implementation.
4. Repair required CI failures only inside the active gate.
5. Otherwise implement the smallest complete active-gate slice.
6. Run the evidence required for that bounded pass.
7. Push exact evidence to the same branch/PR.
8. Stop `AWAITING_REVIEW`.

Never continue merely because context remains or another useful idea exists.

## Stop-and-escalate boundaries

Return `BLOCKED` or request `OWNER_DECISION` before changing product scope or accepted architecture materially; destructive repository/data operations; production release; paid services or billing; secrets or permission expansion; dependency/license uncertainty; public disclosure of private data; claims of fixture practicality/certification without qualified review; or repeated AI/validator disagreement beyond budget.

## Completion format

Codex stops with:

```text
AWAITING_REVIEW
Gate: M33.1 / Issue #69
PR: #79
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
