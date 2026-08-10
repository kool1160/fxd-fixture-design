# FXD Current Control State

## State

**AWAITING_REVIEW — GOVERNANCE RESET; PRODUCT IMPLEMENTATION HELD**

This file is the concise operator-facing control surface. The matching machine-readable projection is [`docs/CONTROL_STATE.json`](docs/CONTROL_STATE.json); CI requires them to agree.

GitHub Issue #66 is the active governance authority for the reset. The frozen pre-reset `docs/MILESTONE_STATE.json` remains historical evidence only and cannot select current work.

## Active gate

- **Issue:** #66 — Governance reset: AI-driven fixture synthesis and LaserX-style project control
- **Lane:** product direction / architecture / governance
- **Implementation PR:** #67 — draft governance reset
- **Expected branch:** `governance/ai-driven-fxd-reset`
- **Review authority:** FXD Review-Control chat
- **Builder/repair session:** Codex, only after `CONTINUE`

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
- Repair deterministic governance/state validation exposed by PR #67 without broadening into product runtime work.

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
- `docs/CONTROL_STATE.json` and this file agree and pass deterministic validation.
- No active instruction or executable workflow authorizes the advisory-AI/deterministic-template product path.
- The autonomous Foreman workflow and automatic selector fail closed.
- The next bounded product gate has measurable acceptance criteria.
- The old milestone registry is preserved byte-for-byte as historical evidence rather than silently rewritten.
- Review-Control can issue one `CONTINUE`; Codex can repair one bounded pass and stop `AWAITING_REVIEW`.

## Next valid action

**Check PR #67's exact head and CI.** If repository-control validation fails, write bounded findings and issue `CONTINUE` for Codex to repair the same PR. Do not begin product implementation before this governance head is accepted.