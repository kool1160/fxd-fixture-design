## Classification

- [ ] Product milestone implementation
- [ ] Product milestone closeout evidence
- [ ] Product milestone state finalization
- [ ] Maintenance
- [ ] Governance/documentation only

Authoritative issue: #

Milestone number, if applicable:

This PR does not own milestone status; current status comes from `docs/MILESTONE_STATE.json`.

## Scope

Describe the bounded outcome and explicit exclusions. For milestone implementation, identify child issues and explain why this PR does not absorb unrelated work.

## Evidence profiles

- [ ] A — repository and deterministic core
- [ ] B — real geometry/manufacturing evidence
- [ ] C — Windows desktop/visual acceptance
- [ ] D — engineering acceptance
- [ ] E — AI/provider boundary
- [ ] F — documentation-only work

Record exact commands, totals, failures, errors, skips, hosted results, and remaining human acceptance.

## Protected boundaries

- [ ] Source CAD and source coordinates remain immutable.
- [ ] CAD-neutral architecture and deterministic engineering authority remain intact.
- [ ] Traceability, units, tolerances, privacy, and human approval remain explicit.
- [ ] Approval, release, and export fail closed when evidence is incomplete.
- [ ] Dependency versions and licensing implications were reviewed, or no dependency changed.
- [ ] No confidential CAD, credentials, private engineering rules, or raw provider content entered the repository.
- [ ] `bash scripts/ci.sh` passes as the one repository health command.

## Closeout boundary

For implementation PRs: the milestone remains Active after this PR merges; a separate closeout evidence PR and later state-finalization PR are required.

For closeout evidence PRs: link all implementation merges, record reviewable results for every selected evidence profile, explicit human approvals, unresolved risks, and the governing issue. Record the known closeout PR number but keep the milestone Active because this PR cannot know its future merge SHA.

For state-finalization PRs: after the separate closeout evidence PR merges, record its locally present PR-number-bearing merge commit, the explicit closeout decision, `Complete` status, and the approved next-lane disposition. State finalization must remain distinct from implementation and closeout evidence.
