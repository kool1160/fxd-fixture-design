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

Read repository-root `CURRENT.md` before any action.

During the Issue #66 reset:

- product implementation is held;
- superseded Issue #57 / PR #54 must not be continued;
- the governance-reset branch/PR is the only active work;
- no future product gate begins until Review-Control accepts the reset and activates it durably.

## Codex entry point

The standing implementation prompt is:

```text
.github/codex/prompts/run-milestone.md
```

Despite the historical filename, it now defines the bounded `Continue FXD` contract. It does not authorize milestone selection.

## Repository preflight

Before Codex receives write authority, Review-Control must verify:

- repository identity;
- current default-branch SHA;
- `CURRENT.md` and active issue;
- open PRs and duplicate branches;
- exact active PR head and review findings;
- required CI;
- no held or superseded lane is being targeted.

Ambiguity blocks before model execution.

## OpenAI product configuration

The OpenAI API used by the FXD product is separate from Codex development orchestration.

A future accepted AI Design gate will require explicit process configuration such as:

```text
OPENAI_API_KEY
FXD_OPENAI_MODEL
FXD_AI_PROVIDER=openai
```

Do not commit keys. Use a dedicated OpenAI project with conservative limits and alerts.

AI Design must display provider/model/live-request provenance and fail closed when configuration or provider execution fails. Deterministic/offline mode remains separately selectable and labeled.

## Public repository warning

Do not place customer CAD, employer files, real fixture libraries, proprietary rule packs, private corrections, patent-sensitive details, API keys, file paths, or vendor-restricted binaries in repository prompts, tests, screenshots, logs, or artifacts.