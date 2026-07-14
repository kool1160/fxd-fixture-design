# FXD deterministic validation pipeline contract

Milestone 15 adds `validate_fixture_concept`, a versioned release gate over
the existing neutral concept, constraint, access, weld, tooling, tolerance,
manufacturing, and geometry contracts.

The result is `valid`, `provisional`, or `invalid`. Errors block recommendation
and export when the result is supplied to the fabrication-package exporter.
Warnings identify missing evidence and keep the result provisional. Scores and
AI explanations cannot change this status.

Product/fixture AABB checks are explicit proof-layer evidence. When reviewed
kernel-authored manufacturing solids and a `RealKernel` are supplied, pairwise
solid clearances are also checked through the kernel boundary. Missing kernel
evidence remains visible; it is never silently replaced by a production claim.

The evidence digest makes a result reproducible and allows downstream packages
to identify the exact validation findings used for review. The pipeline does
not certify a fixture, validate weld quality, prove robot motion, or approve
production use.
