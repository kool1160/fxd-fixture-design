# FXD Operator Protocol

## Purpose

Make FXD simple to operate without turning Chris into a human message bus or allowing agents to invent work.

> **Review-Control decides and reviews. GitHub remembers. ChatGPT Codex Remote implements one bounded gate. Pull requests hold the evidence.**

One repository. One active gate. One implementation PR.

Current state is stored in `docs/CONTROL_STATE.json` and projected concisely in `CURRENT.md`. They must agree before any work begins.

## Roles

### FXD Review-Control chat

Review-Control is the sole planning, scope, status, and independent-review authority for normal FXD execution. It owns fresh repository inspection, product/architecture decisions inside owner-approved direction, durable scope, exact-head review, bounded GitHub findings, routine merge/next-gate activation when every guardrail passes, and owner escalation for genuine owner-only decisions.

It does not perform normal product implementation. It may perform narrow governance/control repairs when needed to restore safe project operation.

### ChatGPT Codex Remote implementation session

ChatGPT Codex Remote owns implementation of the one active gate, repair of blocking findings on the same branch/PR, deterministic tests/evidence, updating the same implementation PR, and stopping when the bounded pass is complete.

Codex does not choose new scope, create a future milestone, merge, advance, deploy, approve its own work, or keep searching for useful work after completion.

### Product runtime AI

The OpenAI model used inside FXD is a product component, not the project orchestrator. It may author a typed fixture strategy and bounded repairs under the accepted architecture. It cannot change repository scope, bypass deterministic validation, approve a fixture, or control GitHub.

## Permanent API and cost boundary

This boundary is fail-closed and applies even when FXD is not otherwise held.

- Normal FXD implementation, repair, and coding work uses **ChatGPT Codex Remote under the user's ChatGPT agentic allowance**.
- Repository GitHub Actions must not invoke `openai/codex-action` for implementation, repair, review, or orchestration.
- Repository GitHub Actions must not receive, expose, or forward `OPENAI_API_KEY` for development/orchestration.
- Repository `OPENAI_API_KEY` use is reserved for explicit **FXD product-runtime live-AI evidence/use** only.
- Product-runtime API use requires a reviewed exact head, explicit Review-Control authorization, an explicit model/provider, the active request budget, and fail-closed provenance.
- A development convenience, automation idea, or desire to remove owner clicks never authorizes paid API orchestration.
- CI must reject any reintroduction of a paid development dispatcher or workflow API-key route.

The retired `.github/workflows/m33-1-codex-continue.yml` is historical evidence only and must remain inert/read-only/fail-closed.

## HOLD state

If `docs/CONTROL_STATE.json` has `state: HELD` or `product_implementation_held: true`:

- `CONTINUE` is illegal;
- Codex product implementation/repair is prohibited;
- Profile E and other product-runtime paid requests are prohibited unless the owner explicitly changes the hold;
- PR merge and gate advancement are prohibited;
- Review-Control may inspect GitHub and perform narrow governance/cost-safety repairs only;
- resumption requires explicit owner instruction followed by a coherent control-state update.

Legal Review-Control output while held is:

```text
HOLD
Reason: <one sentence>
```

## Normal operating loop after resume

```text
Review-Control locks one active gate
              ↓
          CONTINUE
              ↓
ChatGPT Codex Remote implements or repairs one bounded pass
              ↓
       AWAITING_REVIEW
              ↓
Review-Control checks exact head and evidence
       ↙                ↘
   CONTINUE       OWNER_DECISION / BLOCKED / COMPLETE
```

The owner should not need to copy detailed implementation prompts between chats. Codex reads the repository.

## Review-Control output

Normal successful output after resume:

```text
CONTINUE
Gate: <issue / bounded objective>
PR: none | #__
Reason: <one sentence>
```

A real owner decision:

```text
OWNER_DECISION
Question: <one concise product/risk/authority question>
Why it matters: <one sentence>
```

Other legal outputs:

```text
HOLD
Reason: <one sentence>
```

```text
BLOCKED
Reason: <one sentence>
```

```text
COMPLETE
Evidence: <accepted merge / validated outcome>
```

## Codex output

Codex always stops with one of:

```text
AWAITING_REVIEW
Gate: <issue / objective>
PR: #__
Head: <full SHA>
CI: green | failing | running
Work: <one sentence>
Blocker: none | <one sentence>
```

```text
BLOCKED
Gate: <issue / objective>
Reason: <one sentence>
```

## What `CONTINUE` means

Codex reads `AGENTS.md`, `docs/CONTROL_STATE.json`, `CURRENT.md`, this protocol, Product Direction, Engineering Constitution, Architecture, the active issue, the active PR, exact review findings, and required checks. Then it follows this order:

1. If FXD is held, control state and `CURRENT.md` disagree, the active gate is missing, or repository truth conflicts, stop `BLOCKED`.
2. If the active PR has unresolved blocking findings, repair only those findings on the same PR.
3. If required CI is failing, diagnose and repair only the failure inside the active gate.
4. If the PR is green and no blocker remains, refresh exact-head evidence and stop `AWAITING_REVIEW`.
5. If no implementation PR exists, build the smallest complete vertical slice allowed by the active issue, open one focused draft PR, and stop `AWAITING_REVIEW`.
6. If a needed change is outside scope, add or recommend backlog work and stop.

`CONTINUE` never means keep finding useful work; reopen M32; use the frozen milestone registry to select work; start a second implementation PR; redesign unrelated architecture; add speculative infrastructure; weaken deterministic checks; silently switch AI mode; create a paid GitHub/API coding route; merge/deploy/publish/delete branches; or approve production tooling.

## Exact-head review

After `AWAITING_REVIEW`, Review-Control must inspect the exact pushed SHA fresh. Builder summaries and green CI are evidence, not proof.

Review order:

1. **State:** control state, `CURRENT.md`, issue, branch, and PR agree.
2. **Scope:** every changed file maps to the active gate.
3. **Architecture:** AI, OCP authoring, deterministic validation, persistence, UI, and provider boundaries remain correct.
4. **Deterministic evidence:** required checks actually ran against the reviewed head.
5. **Runtime proof:** native/OCP/VTK/live-provider behavior is proven at the layer where it can fail.
6. **Security/privacy/licensing/cost:** secrets, private geometry, permissions, provider use, dependencies, and API spending remain bounded.
7. **Product outcome:** the gate proves the intended engineering result, not merely that code exists.
8. **Human boundary:** software does not claim qualified fixture approval.

Any new commit invalidates the prior review.

## Scope-drift firewall

New feature, nice-to-have cleanup, while-we-are-here refactor, or future infrastructure with no current consumer goes to backlog. A new provider/service/dependency that materially changes architecture requires `OWNER_DECISION`. A blocker may justify a narrow repair; it does not authorize redesign.

## AI audit rule

Claude / Anthropic is not part of FXD's standard implementation, audit, review, fallback, or tie-break process.

Acceptance order:

1. deterministic evidence;
2. independent Review-Control judgment using an approved OpenAI path when model review is useful;
3. qualified human fixture-engineering judgment for physical practicality and release.

## Merge and advancement

Review-Control may perform routine merge and activate the next already-approved gate only when the reviewed exact head has not changed, required checks are green, no blocking thread remains, acceptance criteria are satisfied, rollback/remaining risks are recorded, no owner-only boundary is crossed, and `docs/CONTROL_STATE.json`, `CURRENT.md`, and GitHub can advance coherently.

Codex never merges or advances itself.

## Permanent product boundary

FXD remains assistive engineering software. It may design and author reviewable fixture geometry, but it does not certify structure, clamp force, weld process, safety, or production release. Qualified human approval remains mandatory.
