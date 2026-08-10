# FXD Current Control State

## State

**ACTIVE — M33.1 / ISSUE #69**

This is the concise operator-facing control surface. The matching machine-readable authority is [`docs/CONTROL_STATE.json`](docs/CONTROL_STATE.json); CI requires them to agree.

The Issue #66 reset was accepted and merged through PR #67 at `592876fefde118b5325bbb5b4949eeb1490cdf6c`. Issue #70 activates the first bounded product gate under the new Review-Control/Codex operating model.

## Active milestone

- **M33:** AI-Driven Fixture Synthesis Proof
- **Milestone issue:** #68
- **Status:** ACTIVE

## Sole active gate

- **Gate:** M33.1 — Native product reconstruction and explicit live-AI mode
- **Issue:** #69
- **Lane:** product implementation
- **Implementation PR:** none yet
- **Expected branch:** Codex creates one focused branch only after `CONTINUE`
- **Review authority:** FXD Review-Control chat
- **Builder/repair session:** Codex

## IN SCOPE

- A versioned, CAD-neutral, source-SHA-bound product/manufacturing reconstruction contract.
- Exact component, transform, body, OCP face/hole/axis/plane evidence needed by the first supported fixture family.
- Bounded classifications such as plate/sheet, tube/structural, formed, machined, purchased, or `unknown`.
- Candidate datum/contact features, weld candidates, engineer-confirmed weld intent, confidence, provenance, and unresolved ambiguity.
- Explicit `ai_design_live` and `deterministic_offline` execution modes.
- One intentional, bounded OpenAI request only when live mode is selected and triggered.
- Visible and persisted provider/model/request/provenance state.
- Live-AI failure that stops clearly with **no deterministic substitute**.
- Opt-in exactly-one-request live acceptance separate from ordinary offline CI.
- Focused tests, full repository checks, pinned OCP evidence, native UI evidence, privacy/secret checks, and exact-head review.

## OUT OF SCOPE

- Final typed fixture-strategy design contract.
- Strategy-to-OCP fixture authoring.
- AI repair cycles.
- Final fixture generation.
- Multiple fixture families.
- Universal CAD/manufacturing reconstruction.
- Private fixture-library upload or public disclosure of Chris's fixture knowledge.
- Customer/employer CAD in public tests, prompts, logs, screenshots, or CI.
- Claude/Anthropic integration or audit.
- M33.2 or later work.
- Production approval, release, billing, SaaS, or deployment.

## Protected boundaries

- Source CAD remains byte-immutable and source-SHA-bound.
- Unsupported meaning remains `unknown`; material ambiguity asks a focused question or blocks.
- Live mode is explicit and never inferred from environment variables alone.
- The OpenAI model is explicitly configured; FXD never guesses or silently switches it.
- Missing key/model, timeout, provider failure, malformed/quarantined response, or cancellation cannot produce a fake AI success.
- Secrets and unrestricted provider content never enter persistence or public evidence.
- Offline tests cannot claim live-provider proof.
- Software evidence cannot approve fixture practicality or production use.
- M32 / Issue #57 / PR #54 remains superseded and cannot be resumed as current work.

## Required evidence

- **A — repository/deterministic:** focused tests, full suite, `bash scripts/ci.sh`, `git diff --check`, governance/secret checks.
- **B — real geometry:** pinned OCP reconstruction evidence and source immutability.
- **C — native UI:** unmistakable LIVE / FAILED-NO-FALLBACK / OFFLINE states.
- **E — live provider:** one intentional OpenAI request, explicit model/provider, request count, timeout/retry evidence, safe provenance, no fallback.

Profile E requires an intentional live request. Offline CI does not satisfy it.

## Held and superseded

- M32 / Issue #57 — SUPERSEDED
- PR #54 — closed unmerged; branch and evidence preserved for selective salvage
- Issue #59 — closed as superseded
- Issue #63 — closed as superseded
- `docs/MILESTONE_STATE.json` — frozen historical evidence only

## Next valid action

**CONTINUE**

Codex must read Issue #69 and repository truth, implement the smallest complete M33.1 vertical slice on one focused draft PR, run the required evidence, and stop `AWAITING_REVIEW`. It must not begin M33.2, merge, advance, or reinterpret the gate.
