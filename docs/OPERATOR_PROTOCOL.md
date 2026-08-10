# FXD Operator Protocol

## Purpose

Make FXD simple to operate without turning Chris into a human message bus or allowing agents to invent work.

> **Review-Control decides and reviews. GitHub remembers. Codex implements one bounded gate. Pull requests hold the evidence.**

One repository. One active gate. One implementation PR.

## Roles

### FXD Review-Control chat

The Review-Control chat is the sole planning, scope, status, and independent-review authority for normal FXD project execution.

It owns:

- reading current GitHub truth before planning or review;
- product and architecture decisions within owner-approved direction;
- durable scope in the active issue and `CURRENT.md`;
- exact-head pull-request review;
- writing bounded review findings to GitHub;
- routine merge and next-gate activation only when already authorized and every guardrail passes;
- owner escalation for genuine product ambiguity, destructive/high-risk action, production authority, paid services, secrets, or qualified fixture judgment.

It does not perform normal product implementation.

### Codex implementation session

Codex owns:

- implementation of the one active gate;
- repair of blocking findings on the same branch and PR;
- deterministic tests and evidence;
- updating the same implementation PR;
- stopping when the bounded pass is complete.

Codex does not choose new scope, create a future milestone, merge, advance, deploy, approve its own work, or keep searching for useful work after completion.

### Product runtime AI

The OpenAI model used inside FXD is a product component, not the project orchestrator.

It may author a typed fixture strategy and bounded repairs. It cannot change repository scope, bypass deterministic validation, approve a fixture, or control GitHub.

## Normal operating loop

```text
Review-Control locks one active gate
              ↓
          CONTINUE
              ↓
Codex implements or repairs one bounded pass
              ↓
       AWAITING_REVIEW
              ↓
Review-Control checks exact head and evidence
       ↙                ↘
   CONTINUE       OWNER_DECISION / BLOCKED / COMPLETE
```

The owner should not need to copy detailed implementation prompts between chats. Codex reads the repository.

## Review-Control output

Normal successful output:

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

Codex reads `AGENTS.md`, `CURRENT.md`, this protocol, Product Direction, Engineering Constitution, Architecture, the active issue, the active PR, exact review findings, and required checks. Then it follows this order:

1. If FXD is held, the active gate is missing, or repository truth conflicts, stop `BLOCKED`.
2. If the active PR has unresolved blocking findings, repair only those findings on the same PR.
3. If required CI is failing, diagnose and repair only the failure inside the active gate.
4. If the PR is green and no blocker remains, refresh exact-head evidence and stop `AWAITING_REVIEW`.
5. If no implementation PR exists, build the smallest complete vertical slice allowed by the active issue, open one focused draft PR, and stop `AWAITING_REVIEW`.
6. If a needed change is outside scope, add or recommend backlog work and stop. Do not silently broaden the gate.

`CONTINUE` never means:

- keep finding useful things to do;
- reopen superseded M32 work;
- start a second implementation PR;
- redesign unrelated architecture;
- add speculative infrastructure;
- weaken deterministic checks;
- silently switch AI mode to deterministic fallback;
- merge, deploy, publish, delete branches, or approve production tooling.

## Exact-head review

After `AWAITING_REVIEW`, Review-Control must inspect the exact pushed SHA fresh. Builder summaries and green CI are evidence, not proof.

The review order is:

1. **Scope:** every changed file maps to the active gate.
2. **Architecture:** AI, OCP authoring, deterministic validation, persistence, UI, and provider boundaries remain correct.
3. **Deterministic evidence:** required checks actually ran against the reviewed head.
4. **Runtime proof:** browser/native/OCP/VTK/live-provider behavior is proven at the layer where it can fail.
5. **Security/privacy/licensing:** secrets, private geometry, permissions, provider use, and dependencies remain bounded.
6. **Product outcome:** the gate proves the intended engineering result, not merely that code exists.
7. **Human boundary:** software does not claim qualified fixture approval.

Any new commit invalidates the prior review.

## Scope-drift firewall

- New feature discovered during implementation → backlog.
- Nice-to-have cleanup outside acceptance criteria → backlog.
- “While we’re here” refactor → backlog.
- Future infrastructure with no current consumer → backlog.
- New provider/service/dependency that materially changes architecture → `OWNER_DECISION`.
- A blocker may justify a narrow repair. It does not authorize a redesign.

## AI audit rule

Claude / Anthropic is not part of FXD's standard implementation, audit, review, fallback, or tie-break process.

The acceptance order is:

1. deterministic evidence;
2. independent Review-Control judgment using an approved OpenAI path when model review is useful;
3. qualified human fixture-engineering judgment for physical practicality and release.

## Merge and advancement

Review-Control may perform routine merge and activate the next already-approved gate only when:

- the reviewed exact head has not changed;
- required checks are green;
- no unresolved blocking thread remains;
- scope and acceptance criteria are satisfied;
- rollback and remaining risks are recorded;
- no owner-only boundary is crossed.

Codex never merges or advances itself.

## Permanent product boundary

FXD remains assistive engineering software. It may design and author reviewable fixture geometry, but it does not certify structure, clamp force, weld process, safety, or production release. Qualified human approval remains mandatory.