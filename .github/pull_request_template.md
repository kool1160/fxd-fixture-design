## Classification

- [ ] Product milestone implementation
- [ ] Separate product milestone closeout
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

For implementation PRs: the milestone remains Active after this PR merges; a separate closeout PR is required.

For closeout PRs: link all implementation merges, evidence profiles, explicit human approvals, unresolved risks, and the governing issue before changing the registry.
