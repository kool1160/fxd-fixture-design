# FXD Current Control State

## State

**AWAITING_REVIEW — GOVERNANCE REPAIR; PRODUCT IMPLEMENTATION HELD**

This file is the concise operator-facing control surface. The matching machine-readable projection is [`docs/CONTROL_STATE.json`](docs/CONTROL_STATE.json); CI requires them to agree.

Issue #66 and merged PR #67 establish the accepted AI-driven product reset. Issue #74 / PR #72 is the sole active repair gate. The frozen pre-reset `docs/MILESTONE_STATE.json` remains historical evidence only and cannot select current work.

## Accepted reset

- **Decision issue:** #66
- **Merged reset PR:** #67
- **Merge commit:** `592876fefde118b5325bbb5b4949eeb1490cdf6c`

## Active gate

- **Issue:** #74 — Post-merge repair: close Issue 66 governance findings and restore current state
- **Lane:** governance repair
- **Implementation PR:** #72 — ready for exact-head review
- **Expected branch:** `governance/issue66-post-merge-repair`
- **Expected PR state:** open and ready for review
- **Review authority:** FXD Review-Control chat
- **Builder/repair session:** Codex, only after `CONTINUE`

## Repair delivered

- Automatic historical-milestone selection remains retired when `docs/OPERATOR_PROTOCOL.md` is absent but durable `docs/CONTROL_STATE.json` remains.
- The frozen historical registry path is required to remain exactly `docs/MILESTONE_STATE.json` before validating its pinned blob.
- Focused regressions cover both boundaries.
- Machine and human current state are synchronized to Issue #74 / PR #72.
- No one-time write-enabled repair tooling remains.

## Held and superseded

- Issue #57 — closed as superseded
- PR #54 — closed unmerged; branch and evidence preserved for salvage
- Issue #59 — closed as superseded
- Issue #63 — closed as superseded

Do not reopen or continue these items unless Issue #66 or a later accepted decision explicitly authorizes it.

## Planned but blocked

- **M33:** Issue #68 — AI-Driven Fixture Synthesis Proof
- **M33.1:** Issue #69 — Native product reconstruction and explicit live-AI mode

M33.1 remains blocked until this repair merges and a separate current-state transition activates it.

## Out of scope

- FXD runtime implementation.
- M33.1 implementation.
- Provider requests.
- Fixture-generation behavior.
- Private fixture data.
- Reopening M32.
- Production fixture approval or release.

## Acceptance evidence required

- `docs/CONTROL_STATE.json`, this file, Issue #74, branch, and PR #72 agree.
- Both original PR #67 findings have exact code and regression evidence.
- Full repository checks and pinned OCP acceptance pass on the reviewed exact head.
- No unresolved blocking review thread remains.
- Product implementation remains held through merge.

## Next valid action

**Review PR #72's exact head and CI.** Merge only after both findings are independently resolved and exact-head evidence is green. Then create a separate governed transition that activates M33.1; do not begin product implementation from this repair PR.
