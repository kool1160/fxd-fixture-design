# FXD Development Orchestration Setup

## Status

**The former autonomous “FXD Foreman” and paid GitHub Codex dispatcher are retired. FXD M33.1 is currently HELD — COST CONTROL.**

Do not run a workflow that selects a milestone, plans, implements, reviews, and publishes inside one agent context. Do not create a GitHub/API-backed Codex implementation route. Both conflict with the accepted Review-Control/ChatGPT Codex Remote separation and can create stale, duplicate, or paid work outside the owner-approved path.

## Accepted operating model

Read [`docs/OPERATOR_PROTOCOL.md`](OPERATOR_PROTOCOL.md).

- The **FXD Review-Control chat** reads GitHub truth, owns scope, writes durable decisions/findings, and independently reviews exact PR heads.
- **ChatGPT Codex Remote** is the normal implementation/repair surface after a legal `CONTINUE`; it uses the user's ChatGPT agentic allowance and stops `AWAITING_REVIEW`.
- GitHub holds the active issue, scope, branch, PR, findings, CI, and evidence.
- GitHub Actions do not run paid Codex/provider development orchestration and do not receive repository OpenAI API credentials for implementation or repair.
- Chris is escalated only for genuine product ambiguity, destructive/high-risk action, paid services, secrets, production authority, or qualified fixture judgment.
- Claude/Anthropic is not a standard implementation, review, audit, or fallback route.

## Current control state

Read repository-root `CURRENT.md` and `docs/CONTROL_STATE.json` before any action.

The Issue #66 reset is accepted. Issue #70 activated M33.1, but explicit owner direction now holds that gate for cost control:

- **M33.1 / Issue #69 — Native product reconstruction and explicit live-AI mode**
- **State:** HELD — COST CONTROL
- **Implementation PR:** #79, draft and preserved
- **Branch:** `agent/m33-1-native-product-reconstruction`
- no Codex implementation/repair pass is authorized while the hold is active;
- no Profile E/product-runtime paid request is authorized while held;
- PR #79 must not merge or advance to M33.2 while held;
- superseded Issue #57 / PR #54 remains closed and may be used only as reviewed salvage evidence.

Resumption requires explicit owner instruction followed by Review-Control synchronizing `docs/CONTROL_STATE.json`, `CURRENT.md`, Issue #69, and PR state before issuing `CONTINUE`.

## Codex entry point after resume

The standing implementation prompt is:

```text
.github/codex/prompts/run-milestone.md
```

Despite the historical filename, it defines the bounded `Continue FXD` contract. It does not authorize milestone selection, override a hold, or create a paid repository dispatcher. ChatGPT Codex Remote reads repository truth directly.

## Repository preflight

Before any future `CONTINUE`, Review-Control must verify:

- repository identity and current default-branch SHA;
- `docs/CONTROL_STATE.json`, `CURRENT.md`, Issue #69, and PR #79 agree;
- `product_implementation_held` is false after explicit owner resume;
- the existing implementation PR/branch is the sole M33.1 implementation surface;
- exact review findings and required CI are known;
- no held, superseded, or future lane is being targeted;
- no GitHub workflow has reintroduced a paid Codex/provider development route.

Ambiguity blocks before model execution.

## OpenAI product configuration

The OpenAI API used by the **FXD product runtime** is separate from ChatGPT Codex Remote development orchestration.

M33.1 eventually requires explicit process configuration for a separately authorized live acceptance:

```text
OPENAI_API_KEY
FXD_OPENAI_MODEL
FXD_AI_PROVIDER=openai
```

These values are product-runtime configuration only. They must not be forwarded into GitHub Actions or repository development automation. Do not commit keys. Use a dedicated OpenAI project with conservative limits and alerts.

The model name is explicitly configured; FXD must not guess, auto-route, or silently switch it. Live AI Design must display provider/model/request provenance and fail closed when configuration or provider execution fails. Deterministic/offline mode remains separately selectable and labeled. Exactly-one-request live acceptance is opt-in, separate from ordinary CI, and prohibited while the current cost-control hold remains active.

## Public repository warning

Do not place customer CAD, employer files, real fixture libraries, proprietary rule packs, private corrections, patent-sensitive details, API keys, file paths, or vendor-restricted binaries in repository prompts, tests, screenshots, logs, or artifacts.
