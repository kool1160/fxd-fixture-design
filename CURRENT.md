# FXD Current Control State

## State

**HELD — COST CONTROL — M33.1 / ISSUE #69 / PR #79**

This is the concise operator-facing projection of [`docs/CONTROL_STATE.json`](docs/CONTROL_STATE.json). The Issue #66 reset remains accepted through PR #67. M33 / Issue #68 remains the active product milestone, but product implementation is held by explicit owner direction.

## Preserved active gate

- **Milestone:** M33 — AI-Driven Fixture Synthesis Proof
- **Gate:** M33.1 — Native product reconstruction and explicit live-AI mode
- **Issue:** #69
- **Implementation PR:** #79 — draft and held
- **Branch:** `agent/m33-1-native-product-reconstruction`
- **Held head:** `3397c96ad011aedc185e8cb46484662bd87a272e`
- **Status:** HELD — COST CONTROL

PR #79 and its evidence are preserved. The hold does not accept, merge, supersede, or discard that work.

## Development execution boundary

- **Implementation surface:** ChatGPT Codex Remote under the user's ChatGPT agentic allowance.
- **Development API requests:** 0.
- **Paid GitHub Codex dispatchers:** forbidden.
- GitHub workflows must not invoke `openai/codex-action` or pass `OPENAI_API_KEY` for implementation, repair, review, or orchestration.
- Repository `OPENAI_API_KEY` use is reserved for explicit FXD **product-runtime** live-AI evidence/use after Review-Control authorization.
- The M33.1 Profile E request remains unspent and is prohibited while this hold is active.

## M33.1 scope preserved

### IN SCOPE after resume

- Source-SHA-bound native product/manufacturing reconstruction.
- Exact component, transform, body, OCP face/hole/axis/plane evidence needed by the first supported fixture family.
- Bounded classifications with unsupported meaning retained as `unknown`.
- Explicit `ai_design_live` and `deterministic_offline` modes.
- Fail-closed live OpenAI behavior with visible, persisted provenance and no deterministic substitute.
- Focused tests, full repository checks, pinned OCP evidence, native UI evidence, privacy/secret checks, exact-head review, and one intentional Profile E request when separately authorized.

### OUT OF SCOPE

- Final typed fixture strategy.
- Strategy-to-OCP fixture authoring.
- AI repair cycles.
- Final fixture generation.
- Multiple fixture families.
- M33.2 or later work.
- Production release, SaaS, billing, or deployment.
- Claude/Anthropic implementation, review, audit, fallback, or tie-break use.

## Product-runtime budgets

- **Live requests per acceptance run:** 1
- **Automatic provider retries:** 0
- **Repair requests in M33.1:** 0
- **Maximum request timeout:** 60 seconds
- **Model policy:** explicitly configured high-capability OpenAI model; no default guess or silent switch

These are product-runtime ceilings. They do not authorize development/orchestration API spending.

## Held and superseded

- M32 / Issue #57 — SUPERSEDED
- PR #54 — closed unmerged; preserved for selective salvage
- Issue #59 — closed as superseded
- Issue #63 — closed as superseded
- `docs/MILESTONE_STATE.json` — frozen historical evidence only

## Next valid action

**HOLD**

No Codex implementation/repair pass, no paid GitHub model/API development workflow, no Profile E request, no merge of PR #79, and no M33.2 advancement until explicit owner resume. Review-Control may inspect the repository and perform cost-safety governance only.
