# FXD Milestone Contract

## Purpose and authority

This contract governs FXD product-milestone sequence, selection, evidence, and completion. `docs/MILESTONE_STATE.json` is the sole machine-readable projection of current milestone status. The active milestone GitHub issue owns the approved scope and acceptance criteria; linked pull requests provide implementation and validation evidence.

The authority order is:

1. `docs/ENGINEERING_CONSTITUTION.md`
2. `docs/PRODUCT_DIRECTION.md`
3. accepted architecture and decision records
4. `docs/ENGINEERING_TEAM.md`
5. this contract
6. `docs/MILESTONE_STATE.json`
7. the active milestone GitHub issue
8. linked implementation pull requests and their evidence
9. the separate milestone closeout pull request
10. derived roadmaps, handoffs, project records, workbench guides, and binder snapshots

This contract cannot weaken immutable source CAD, CAD-neutral design, deterministic engineering authority, traceability, explicit units and tolerances, mandatory human approval, local-first privacy, dependency licensing review, fail-closed behavior, or `bash scripts/ci.sh` as the one repository health command.

## Legal statuses

Only these values are authoritative:

- `Planned`: approved in sequence but not selected for implementation.
- `Active`: the sole product milestone currently authorized for implementation.
- `Blocked`: authorized work cannot proceed until a recorded blocker is resolved.
- `Waiting`: work is awaiting a named external result or approval and is not being advanced.
- `Paused`: work was intentionally suspended by a recorded decision.
- `Complete`: all applicable evidence and completion gates passed and the controlling merge evidence is recorded.
- `Superseded`: a recorded sequence decision replaced the milestone with an identified successor or disposition.
- `Cancelled`: a recorded decision removed the milestone without replacement.

`Pending`, `In progress`, `Mostly complete`, `Current / Pending`, `Implemented`, `Complete under review`, and `Functionally complete` are not legal milestone statuses. They may appear only in clearly marked historical prose that preserves what was reported at the time.

## Product lane and sequence

Exactly one product milestone must be `Active`, except when the product lane is formally paused. A formally paused lane has zero Active milestones, `product_lane.paused` set to `true`, no `active_milestone`, and a recorded decision and pause reason.

Milestones follow their registered sequence positions. An Active milestone's predecessor must be `Complete` or formally `Superseded`. A later milestone cannot pass a predecessor that is `Blocked`, `Waiting`, or `Paused`. Work must not be selected merely because a derived Markdown backlog is stale.

After Milestone 32 is closed out, the product lane is to become formally paused with zero Active milestones. This contract neither creates nor implies Milestone 33. Any future milestone requires a separate proposal, explicit human approval, a sequence-revision decision, and a registry change.

## Issue-first implementation

Before product implementation begins, the milestone must have one open authoritative GitHub issue containing scope, exclusions, protected engineering boundaries, evidence profiles, acceptance criteria, and completion conditions. The registry must link that issue. Implementation pull requests must link the milestone issue and stay inside its scope.

Large milestones may use child issues. Child issues must name their parent milestone, inherit its protected boundaries, cover disjoint reviewable outcomes, and never own or change product-milestone status. Closing a child issue does not complete the milestone.

An implementation pull request may deliver code, tests, documentation, or acceptance evidence, but its merge does not make a post-governance milestone `Complete`. The milestone remains Active through implementation merge until a separate closeout pull request reconciles every required evidence profile, unresolved risk, issue state, and merge evidence.

## Maintenance lane

Maintenance is separate from the product lane. Maintenance work requires a dedicated maintenance issue, may proceed alongside the Active product milestone when it does not compete for milestone authority, and must not change milestone status or absorb milestone scope. A maintenance pull request must identify its maintenance issue, classification, dependencies, licensing impact, and applicable verification.

PR #55 is a blocked documentation-maintenance candidate governed by Issue #58. It is not product milestone work and cannot own milestone status. Its dependency/licensing, byte-determinism, and unsupported-bookmark findings remain blocking until resolved in that maintenance lane.

## Evidence profiles

Every milestone issue and registry entry names the applicable profiles. Required profiles are cumulative; selecting one does not waive the deterministic repository baseline.

- **A — repository and deterministic core:** focused tests, full deterministic suite, compile checks, `git diff --check`, repository governance validation, secret scan, and `bash scripts/ci.sh`.
- **B — real geometry/manufacturing evidence:** pinned real-kernel execution, topology and persistence proof, immutable source evidence, and fail-closed manufacturing/export checks appropriate to the change.
- **C — Windows desktop/visual acceptance:** native Windows workbench execution, real VTK/OCP interaction where applicable, visual-state evidence, and exact remaining manual acceptance items.
- **D — engineering acceptance:** qualified human review of fixture practicality, access, manufacturability, safety boundaries, assumptions, limitations, and production-release exclusions.
- **E — AI/provider boundary:** provider-neutral contract checks, deterministic fallback and validation authority, sanitized failure handling, credential isolation, and paid/live requests only with explicit authorization.
- **F — documentation-only work:** source-to-publication traceability, deterministic generation where applicable, dependency and licensing review, link/preflight checks, and proof that documentation cannot alter product status.

## Completion gates

A milestone may become `Complete` only when:

1. its issue scope and acceptance criteria are satisfied;
2. every required evidence profile has reviewable results;
3. implementation pull requests are merged and their commits are in repository history;
4. deterministic validation passes without weakening protected boundaries;
5. material risks, assumptions, specialist disagreements, and limitations are recorded;
6. required human engineering and visual acceptance is explicit;
7. no approval, release, export, or safety claim exceeds the evidence;
8. a separate closeout pull request reconciles the registry and derived documents; and
9. the closeout pull request is explicitly approved and merged.

The implementation PR and closeout PR must remain separate for milestones governed by this contract. The closeout PR changes governance state; it does not conceal implementation changes.

## Sequence changes and interruptions

Changing order, inserting, superseding, cancelling, or replacing a milestone requires an explicit human-approved decision recorded in the registry, an incremented `sequence_revision`, valid predecessor relationships, and updated issue links. A `Superseded` record names its replacement or explicit disposition. A `Cancelled` record names the cancellation decision. Silent renumbering and milestone skipping are prohibited.

An emergency may interrupt Active work only for a security, data-loss, legal/licensing, safety, or repository-integrity condition. The interruption must have a dedicated issue and human decision, set the affected milestone to `Blocked`, `Waiting`, or `Paused` as appropriate, preserve its evidence, and identify the exact resumption condition. An emergency does not silently activate another product milestone.

## Legacy reconciliation

Milestones 1 through 31 predate this contract and are reconciled as legacy `Complete` using real merged implementation evidence. Missing historical issues or separate closeout pull requests are recorded as process gaps; none are invented retroactively.

Milestone 20 is controlled by PR #40 and merge commit `5f90765b96140f0cb3103f3ac5e04a79f82ab604`. Older dated Markdown that still reported it as Pending remains historical and is followed by a reconciliation note.

Milestone 31 is controlled by PR #53 and merge commit `ac1e7a1799ef9be674f6ab5739e48d178fa2f1dc`. Its implementation handoff reported that approval remained required; later user acceptance and merge supplied the controlling completion evidence. The earlier handoff remains historical rather than being rewritten.

## Human escalation

Human approval is required for sequence changes, a future product-lane activation, milestone closeout, protected-boundary changes, paid services, dependency-license uncertainty, public disclosure of sensitive engineering material, production-release claims, and the stop-and-ask boundaries in `AGENTS.md` and the Engineering Constitution. AI output and automated validation cannot grant engineering approval.

## Derived documents and binders

`BACKLOG.md`, `docs/ROADMAP_QUEUE.md`, `docs/STRATEGY_HANDOFF.md`, project records, workbench guides, and binders are derived context. They must point to the registry for current status and cannot compete with it. Historical binders and dated records must be visibly labeled non-authoritative snapshots. They may preserve period-accurate wording, including now-illegal status phrases, only inside that historical boundary.
