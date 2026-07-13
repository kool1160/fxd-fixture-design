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

The public repository contains only the contract and synthetic tests. Local
records belong at `.fxd/knowledge/corrections.json`, which is ignored. Private
shop rules, customer corrections, and confidential evidence must remain in
separately controlled storage. `universal` scope is rejected unless the entry
is explicitly a `rule_candidate`; accepted history still requires engineering
review before it becomes a rule.

The record captures engineering history and does not certify a fixture,
validate geometry, approve production, or turn a preference into a universal
rule.
