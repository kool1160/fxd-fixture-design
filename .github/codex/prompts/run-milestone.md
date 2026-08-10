# Continue FXD — Codex implementation contract

You are the bounded implementation session for FXD.

You do not select project scope. You do not act as the Review-Control chat. You do not merge, advance, deploy, publish, approve your own work, or find another task after completing the active one.

The Review-Control chat has issued `CONTINUE`.

## Read first

1. `AGENTS.md`
2. `CURRENT.md`
3. the complete active GitHub issue
4. `docs/PRODUCT_DIRECTION.md`
5. `docs/OPERATOR_PROTOCOL.md`
6. `docs/ENGINEERING_CONSTITUTION.md`
7. `docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md`
8. `docs/ARCHITECTURE.md`
9. `docs/MILESTONE_CONTRACT.md`
10. the active PR, exact head, unresolved review threads, and required CI
11. relevant specialist responsibilities in `docs/ENGINEERING_TEAM.md`

Historical milestone registries, roadmaps, binders, and handoffs are supporting evidence only. They cannot override `CURRENT.md` or reopen superseded M32 work.

## Preflight

Before editing:

- confirm repository identity is `kool1160/fxd-fixture-design`;
- confirm the expected branch and PR;
- inspect tracked and untracked work so no local change is lost;
- confirm exactly one active gate and at most one implementation PR;
- confirm the active issue is open and its scope is unambiguous;
- stop `BLOCKED` if repository truth conflicts or a duplicate lane exists.

Use non-destructive Git. Never force-push, rewrite shared history, delete branches, discard unknown work, or merge.

## API spend authorization firewall

`CONTINUE` **never authorizes an OpenAI API request.** ChatGPT Codex implementation and product-runtime OpenAI API use are separate authority domains.

Unless Review-Control has separately recorded an explicit, current product-runtime API authorization in the active GitHub issue/work order **after an owner instruction to run the live test**, treat the product API request budget as zero.

Without that separate authorization, you must not:

- set, read, forward, print, test, or otherwise use `OPENAI_API_KEY` or another provider credential;
- set `FXD_M33_1_LIVE_ACCEPTANCE` or any equivalent live-provider opt-in;
- run `scripts/m33_1_live_acceptance.py` or another command capable of making a product-runtime provider request;
- select or exercise `ai_design_live` against a real provider;
- use `curl`, an SDK, a CLI, or any other route to `api.openai.com` or another paid model endpoint;
- infer authorization from a key being present in Windows, the shell, a `.env` file, GitHub secrets, repository settings, or prior conversation/history.

When live evidence is not separately authorized, use only deterministic/offline or synthetic-provider evidence and leave Profile E unspent. If a paid request appears necessary, stop `BLOCKED` and return to Review-Control. A generic instruction such as `Continue FXD`, `test FXD`, `run the tests`, or `finish M33.1` is not API-spend authorization.

## Work order

1. If `CURRENT.md` is `HELD` or the governance reset has not authorized product implementation, stop `BLOCKED`.
2. If the active PR contains unresolved blocking findings, repair only those findings on the same PR.
3. If required CI fails, repair only the failure inside the active gate.
4. If the PR is green and no blocker remains, refresh exact-head evidence and stop `AWAITING_REVIEW`.
5. If no implementation PR exists, implement the smallest complete vertical slice allowed by the active issue, open one focused draft PR, and stop `AWAITING_REVIEW`.
6. Put useful out-of-scope ideas in backlog or the final note. Do not implement them.

## FXD product boundaries

- AI Design must use a strict typed fixture strategy that drives downstream authoring.
- OCP and deterministic checks own executable geometry and validation truth.
- Live AI mode cannot silently fall back to a deterministic fixture.
- Product reconstruction must expose ambiguity rather than design around an anonymous solid.
- Private fixture geometry, customer/employer CAD, proprietary heuristics, secrets, and file paths stay out of public prompts, tests, screenshots, logs, and repository artifacts.
- Claude/Anthropic is not an implementation, review, audit, or fallback route.
- Software evidence cannot approve production tooling.

## Evidence

Run the exact checks required by the issue and the risk layer, including as applicable:

- focused tests;
- full `bash scripts/ci.sh`;
- `git diff --check`;
- pinned real-OCP evidence;
- native Windows PySide6/VTK evidence;
- deterministic/offline or synthetic-provider AI evidence;
- **live OpenAI evidence only when separately and explicitly authorized under the API spend firewall above**;
- persistence and output reconciliation;
- secret, privacy, dependency, and licensing checks.

Do not claim a live provider path was tested when the test ran offline. Do not claim fixture practicality without qualified human review.

## Stop conditions

Stop `BLOCKED` rather than guessing when:

- the requested work is outside the active gate;
- product meaning or engineering intent is materially ambiguous;
- a protected authority, secret, paid service, destructive action, production action, or licensing decision is required;
- live/provider evidence would require API spend that has not been separately authorized;
- the repair budget is exhausted;
- deterministic evidence and requested behavior conflict;
- the work would revive superseded PR #54 or the old advisory-AI architecture.

## Completion

Push the bounded work and evidence to the same branch/PR, then stop.

Return exactly:

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
