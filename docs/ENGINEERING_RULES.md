# FXD Engineering Rules

This document records deterministic fixture-engineering rules that FXD may enforce or validate.

Rules added here must include:

- the rule
- why it exists
- applicable geometry or process conditions
- exceptions
- validation method
- source or engineering justification

Initial principles:

- locate before clamping
- clamp toward established locators
- avoid unnecessary overconstraint
- preserve loading, welding, maintenance, and unloading access
- keep assumptions explicit
- never treat AI preference as an engineering rule without validation

Milestone 13 public rule contracts:

- A weld joint may carry process, weld direction, sequence, heat-input units,
  expected distortion direction, tack intent, release sequence, and explicit
  assumptions. Missing values remain visible evidence gaps.
- A caller may provide heat-input review thresholds and clamp-force directions;
  these are configurable review inputs, not universal shop policy.
- A support or clamp associated with a weld reference receives a deterministic
  heat, spatter, and access review finding. This reference-level proof is not a
  thermal, force, or weld-quality simulation.
- A clamp force that points with an annotated distortion direction produces a
  restraint-conflict warning. Opposing direction produces a review
  recommendation, not a safety or adequacy claim.
- Every finding and recommendation records its rule, evidence, assumptions,
  and confidence. Conflicting rules remain separate warnings.
