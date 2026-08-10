# FXD Milestone and Gate Contract

## Purpose

Keep FXD focused on proving a valuable fixture-design product without turning project operation into ceremony or allowing agents to invent work.

> **One product milestone. One active gate. One implementation PR.**

Development operation is governed by `docs/OPERATOR_PROTOCOL.md`.

## Authority order

1. Explicit current decision from Chris Hilton
2. `docs/CONTROL_STATE.json` — machine-readable current state
3. `CURRENT.md` — concise human projection; CI requires it to agree with control state
4. The active GitHub issue and accepted decision records
5. `docs/PRODUCT_DIRECTION.md`
6. `docs/OPERATOR_PROTOCOL.md`
7. `docs/ENGINEERING_CONSTITUTION.md`
8. `docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md`
9. `docs/ARCHITECTURE.md`
10. This contract
11. The active PR, exact head, review findings, and CI
12. Historical milestone registry, roadmaps, handoffs, records, and binders

A conflict stops work. A lower source cannot silently override a higher source.

## Accepted Issue #66 reset

Issue #66 is the accepted product and project-control reset. PR #67 merged that reset as `592876fefde118b5325bbb5b4949eeb1490cdf6c`.

The accepted transition:

- makes AI the typed fixture-strategy author in live AI Design mode;
- keeps OCP and deterministic systems responsible for executable authoring, validation, and failure evidence;
- requires qualified human engineering judgment for fixture practicality and production authority;
- retires the autonomous Foreman and automatic current-work selector;
- separates Review-Control from Codex;
- supersedes M32 / Issue #57 / PR #54 without falsely calling it Complete;
- preserves M32 history and useful technical evidence for selective salvage;
- freezes `docs/MILESTONE_STATE.json` as byte-preserved historical evidence only.

Issue #70 activated M33 / Issue #68 and M33.1 / Issue #69. Explicit owner direction now places M33.1 on **HELD — COST CONTROL** with draft PR #79 preserved as its sole implementation PR. The hold does not cancel or complete the gate; it removes implementation, paid product-runtime acceptance, merge, and advancement authority until explicit owner resume.

## Legal states

Current gate state must be one of:

- `PLANNED`
- `ACTIVE`
- `AWAITING_REVIEW`
- `REPAIR`
- `BLOCKED`
- `HELD`
- `COMPLETE`
- `SUPERSEDED`
- `CANCELLED`

Only one gate may be `ACTIVE`, `AWAITING_REVIEW`, `REPAIR`, or `HELD` as the current product gate at a time.

A milestone may contain ordered child gates, but only one child gate is current. Child gates do not create parallel product work.

## M32 disposition

Milestone 32 is **SUPERSEDED**, not Complete.

Reason:

- its architecture left AI advisory while deterministic templates generated the fixture;
- normal operation did not make live-provider use undeniable;
- acceptance paths intentionally proved offline deterministic behavior rather than the intended AI-driven product;
- repeated qualified human reviews rejected fixture practicality.

Its branch, commits, tests, documentation, and evidence remain historical/salvage assets. Superseded work may be reused only after review against the new architecture.

No completion claim may use M32 software evidence as proof that FXD can design a useful fixture.

## Active product milestone

# M33 — AI-Driven Fixture Synthesis Proof

- **Issue:** #68
- **Status:** ACTIVE
- **Current gate:** M33.1 / Issue #69 / PR #79 — **HELD — COST CONTROL**
- **Goal:** prove one representative fixture from trustworthy product reconstruction through a live AI-authored strategy, real OCP authoring, deterministic validation, at most one bounded AI repair, persistence/provenance, and qualified human practicality acceptance.

M33 is not Complete because its first gate is held and incomplete. Later gates remain planned and unauthorized until Review-Control accepts evidence and advances them after a legal resume.

## Ordered M33 gates

### M33.1 — Product reconstruction and explicit AI mode

- **Issue:** #69
- **Implementation PR:** #79
- **Branch:** `agent/m33-1-native-product-reconstruction`
- **Status:** HELD — COST CONTROL

After explicit owner resume, prove:

- source-SHA-bound native product/manufacturing reconstruction;
- material ambiguity is visible and blocks or asks a focused question;
- AI Design and deterministic/offline mode are separate explicit modes;
- provider/model/live-request state is undeniable and safely persisted;
- AI Design fails closed instead of silently falling back;
- one opt-in live acceptance path makes exactly one bounded request;
- zero automatic provider retries and zero repair requests in this gate.

While held: no Codex implementation/repair pass, no Profile E live request, no PR #79 merge, and no M33.2 advancement is authorized.

M33.1 does not authorize the final fixture-strategy schema, strategy-to-OCP authoring, fixture generation, or repair cycles.

### M33.2 — Typed fixture strategy drives OCP

**PLANNED — NOT AUTHORIZED.**

Prove:

- a live OpenAI request returns the strict strategy contract;
- the strategy contains actual datum/support/locator/clamp/reaction/base/load/access decisions;
- a deterministic compiler validates legal commands and exact identities;
- real OCP fixture geometry is authored from that strategy;
- no deterministic template independently chooses the product strategy first.

### M33.3 — Deterministic rejection and bounded repair

**PLANNED — NOT AUTHORIZED.**

Prove:

- seeded invalid strategy or authored behavior is rejected by deterministic checks;
- failures become a structured repair package;
- no more than one AI repair cycle updates the same strategy lineage;
- repeated failure ends `BLOCKED` without weakening checks or expanding scope.

### M33.4 — Persistence, outputs, and qualified acceptance

**PLANNED — NOT AUTHORIZED.**

Prove:

- source/reconstruction/strategy/provider/repair/geometry/validation provenance survives save/reload;
- applicable STEP/DXF/BOM/review evidence reconciles;
- qualified human review answers **Would I actually build and use this?**;
- a poor but geometrically valid fixture fails the milestone.

## M33 non-goals

- multiple fixture families;
- multi-station optimization unless a later accepted gate explicitly requires it;
- broad integrated-CAD implementation;
- SaaS, billing, accounts, or cloud project storage;
- universal learned rules;
- supplier scraping or unauthorized CAD redistribution;
- customer/employer CAD in public automation;
- Claude/Anthropic implementation or audit;
- production certification or automatic release.

## Gate creation, hold, and activation

Every active gate requires one GitHub issue containing:

- objective;
- exact in-scope outcome;
- explicit exclusions;
- protected engineering/security/privacy boundaries;
- required deterministic and runtime evidence;
- cost, turn, timeout, and repair limits where AI is used;
- completion conditions.

The issue is implementation scope. Conversation alone does not expand it.

A gate becomes active only when `docs/CONTROL_STATE.json`, `CURRENT.md`, and GitHub agree. Codex cannot activate a gate.

A gate becomes held when explicit owner/authority direction is durably projected into `docs/CONTROL_STATE.json` and `CURRENT.md`. While held, `CONTINUE` is illegal. Resumption requires explicit owner instruction and a coherent control-state update before any implementation or product-runtime paid request.

## Development/API cost boundary

Normal implementation and repair use ChatGPT Codex Remote under the user's ChatGPT agentic allowance. Repository GitHub Actions may not invoke paid Codex/provider development orchestration or receive repository OpenAI API credentials for development. Product-runtime API use is separate and requires explicit Review-Control authorization under the active gate budget. CI must fail closed if a paid repository development route is reintroduced.

## Implementation loop

Review-Control returns `CONTINUE` only after confirming:

- FXD is not held;
- control state and `CURRENT.md` agree;
- the active issue is unambiguous;
- the selected branch/PR is correct and no duplicate implementation PR exists;
- unresolved findings and CI state are known;
- the task is inside the active gate.

When a valid implementation PR already exists, ChatGPT Codex Remote repairs or implements only that same gate/PR and stops `AWAITING_REVIEW`. When no implementation PR exists in a future gate, Codex creates exactly one focused branch and one draft PR for the active gate.

Review-Control inspects the exact pushed head and returns:

- `CONTINUE` for bounded repair or the next already-approved gate when not held;
- `OWNER_DECISION` for genuine product/authority ambiguity;
- `BLOCKED` when evidence or prerequisites are missing;
- `HOLD` while owner-authorized hold state is active;
- `COMPLETE` only after accepted merged evidence.

Codex never merges, advances, or selects a new gate.

## Scope control

- New ideas go to backlog.
- Unrelated refactors go to backlog.
- Future infrastructure without a current consumer goes to backlog.
- “While we are here” does not authorize work.
- A blocker may authorize a narrow repair, not a redesign.
- Changing product direction, fixture family, provider authority, privacy posture, production behavior, or milestone goal requires an explicit owner-approved decision.
- Passing tests cannot redefine the acceptance criteria.

## Evidence profiles

Use only the profiles materially required by the gate, but deterministic repository health is always required.

- **A — repository/deterministic:** focused tests, full suite, compile/static checks, `git diff --check`, secret/governance checks, `bash scripts/ci.sh`.
- **B — geometry/manufacturing:** real pinned OCP behavior, source immutability, topology, authoring, persistence, validation, and output reconciliation.
- **C — desktop/visual:** native Windows PySide6/VTK/OCP behavior and visible AI/provenance states.
- **D — qualified engineering:** fixture practicality, loading, access, locating, clamping, manufacturability, maintenance, safety boundaries, and production exclusions.
- **E — live AI/provider:** intentional live request, provider/model identity, strict contract, failure handling, credential isolation, usage/cost evidence, and no silent fallback.
- **F — documentation/governance:** authority consistency, link/state integrity, and proof that docs do not authorize product behavior accidentally.

Offline tests do not satisfy Profile E. Green software checks do not satisfy Profile D. A hold may prohibit a profile even when that profile is eventually required for gate completion.

## Completion

A gate is Complete only when:

- the accepted exact head satisfies the issue;
- required checks and runtime evidence are present;
- blocking review findings are resolved;
- no hidden scope expansion entered the change;
- no claim exceeds the evidence;
- the PR is merged through the approved repository method;
- `docs/CONTROL_STATE.json`, `CURRENT.md`, and durable GitHub records are advanced together to the next already-approved state.

A separate three-PR closeout ceremony is not required for routine gates. Review-Control may merge and advance inside the already-approved M33 sequence when the exact-head safety check passes and no hold or owner-only boundary blocks it.

Human approval remains required for product-direction changes, destructive actions, production release, secrets/permission expansion, paid-service changes beyond an approved bounded test, and qualified fixture practicality/release judgment.

## Historical records

Milestones 1–31 and the superseded M32 materials remain historical evidence. Do not rewrite history or delete useful work.

Historical records, binders, `docs/MILESTONE_STATE.json`, backlog snapshots, and strategy handoffs cannot select current work. Current state comes only from `docs/CONTROL_STATE.json`, `CURRENT.md`, and the active issue.
