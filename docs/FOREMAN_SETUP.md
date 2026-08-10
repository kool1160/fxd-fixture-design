# FXD Development Orchestration Setup

## Status

**The former autonomous “FXD Foreman” workflow is retired by Issue #66.**

Do not run a workflow that selects a milestone, plans, implements, reviews, and publishes inside one agent context. It conflicts with the accepted Review-Control/Codex separation and can revive stale or duplicate work.

## Accepted operating model

Read [`docs/OPERATOR_PROTOCOL.md`](OPERATOR_PROTOCOL.md).

- The **FXD Review-Control chat** reads GitHub truth, owns scope, writes durable decisions/findings, and independently reviews exact PR heads.
- **Codex** receives `CONTINUE`, implements or repairs one bounded gate on one PR, and stops `AWAITING_REVIEW`.
- GitHub holds the active issue, scope, branch, PR, findings, CI, and evidence.
- Chris is escalated only for genuine product ambiguity, destructive/high-risk action, paid services, secrets, production authority, or qualified fixture judgment.
- Claude/Anthropic is not a standard implementation, review, audit, or fallback route.

## Current control state

Read repository-root `CURRENT.md` and `docs/CONTROL_STATE.json` before any action.

The Issue #66 reset is accepted. Issue #70 activates exactly one product gate:

- **M33.1 / Issue #69 — Native product reconstruction and explicit live-AI mode**
- product implementation is authorized only for Issue #69;
- there is no implementation PR until Review-Control issues `CONTINUE` and Codex creates one focused draft PR;
- superseded Issue #57 / PR #54 remains closed and may be used only as reviewed salvage evidence;
- M33.2 and later work remain out of scope.

## Codex entry point

The standing implementation prompt is:

```text
.github/codex/prompts/run-milestone.md
```

Despite the historical filename, it defines the bounded `Continue FXD` contract. It does not authorize milestone selection.

## Repository preflight

Before Codex receives write authority, Review-Control must verify:

- repository identity and current default-branch SHA;
- `docs/CONTROL_STATE.json`, `CURRENT.md`, and Issue #69 agree;
- no existing implementation PR or duplicate branch already owns M33.1;
- exact review findings and required CI are known;
- no held, superseded, or future lane is being targeted.

Ambiguity blocks before model execution.

## OpenAI product configuration

The OpenAI API used by the FXD product is separate from Codex development orchestration.

M33.1 requires explicit process configuration for live acceptance:

```text
OPENAI_API_KEY
FXD_OPENAI_MODEL
FXD_AI_PROVIDER=openai
```

Do not commit keys. Use a dedicated OpenAI project with conservative limits and alerts.

The model name is explicitly configured; FXD must not guess, auto-route, or silently switch it. Live AI Design must display provider/model/request provenance and fail closed when configuration or provider execution fails. Deterministic/offline mode remains separately selectable and labeled. Exactly-one-request live acceptance is opt-in and separate from ordinary CI.

## Public repository warning

Do not place customer CAD, employer files, real fixture libraries, proprietary rule packs, private corrections, patent-sensitive details, API keys, file paths, or vendor-restricted binaries in repository prompts, tests, screenshots, logs, or artifacts.
