# FXD Current Control State

## State

**GOVERNANCE RESET — PRODUCT IMPLEMENTATION HELD**

This file is the concise operator-facing control surface. GitHub Issue #66 is the active governance authority for the reset. Historical milestone records remain evidence, but they do not authorize continuing the superseded M32 implementation.

## Active gate

- **Issue:** #66 — Governance reset: AI-driven fixture synthesis and LaserX-style project control
- **Lane:** product direction / architecture / governance
- **Implementation PR:** none until the governance-reset PR is opened
- **Review authority:** FXD Review-Control chat
- **Builder:** Codex, only after `CONTINUE`

## Held and superseded

- Issue #57 — closed as superseded
- PR #54 — closed unmerged; branch and evidence preserved for salvage
- Issue #59 — closed as superseded
- Issue #63 — closed as superseded

Do not reopen or continue these items unless Issue #66 or a later accepted decision explicitly authorizes it.

## In scope

- Replace the old Foreman operating model with a LaserX-style Review-Control ↔ Codex loop.
- Make AI the typed fixture-strategy author.
- Keep OCP/deterministic systems responsible for authoring, validation, and failure evidence.
- Prohibit silent live-AI fallback.
- Define product reconstruction and structured fixture-precedent requirements.
- Define the milestone transition that supersedes M32 without calling it complete.
- Define one bounded AI-driven fixture-synthesis proof before broader work.

## Out of scope

- Product runtime implementation in this governance gate.
- Merging or deleting PR #54.
- Production fixture approval or release.
- Multiple fixture families.
- Full general-purpose CAD.
- Customer or employer CAD in public automation.
- Supplier scraping or unauthorized CAD redistribution.

## Success evidence

- `AGENTS.md`, Product Direction, Architecture, Engineering Constitution, milestone governance, operator protocol, and Codex prompt all agree.
- No active instruction still authorizes the advisory-AI/deterministic-template product path.
- The next bounded product gate has measurable acceptance criteria.
- Review-Control can issue one `CONTINUE`; Codex can implement one bounded pass and stop `AWAITING_REVIEW`.

## Next valid action

Open and independently review the governance-reset pull request. Do not begin product implementation before that exact head is accepted.