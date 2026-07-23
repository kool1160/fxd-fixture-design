# FXD correction and reusable-knowledge contract

Milestone 9 adds `CorrectionRecord` and `KnowledgeStore` for local capture of
engineer decisions. A record is attributable (`author`, time, and record id),
bound to a source digest and concept identity for audit, and records the
proposed feature metadata, correction, decision, rationale, outcome, scope,
confidence, and evidence.

`ProposedFeature` intentionally contains no bounds, coordinates, topology,
component names, source bytes, or CAD payload. It stores only generated-feature
kind, rule, parameters, units, assumptions, and warnings. The training view
removes source and concept identifiers as well. This makes it suitable for
future retrieval or learning without silently exporting source geometry.

The project-scoped correction store contains only its contract and synthetic
tests in the public repository. Local records belong at
`.fxd/knowledge/corrections.json`, which is ignored. Private shop rules,
customer corrections, and confidential evidence must remain in separately
controlled storage. `universal` scope is rejected unless the entry is
explicitly a `rule_candidate`; accepted history still requires engineering
review before it becomes a rule.

Milestone 32 adds a separate public precedent library under
`data/fixture_knowledge`. It contains versioned official-source metadata,
original FXD paraphrases, abstract fixture patterns, and abstract human review
evidence deliberately safe for a public repository. It contains no private
correction records, supplier CAD, catalogs, images, customer geometry, employer
data, or hidden shop rules. Public precedent is retrieved by deterministic
weighted field matching; it can guide a baseline or provider-neutral proposal
but cannot become a universal rule or override deterministic validation.

The record captures engineering history and does not certify a fixture,
validate geometry, approve production, or turn a preference into a universal
rule.
