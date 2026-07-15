# FXD weld-fixture workflow contract

Milestone 19 composes the existing weld-rule, access, and deterministic
validation contracts into an editable engineer-review workflow. `SequencePlan`
and `WorkflowStep` keep weld, tack, clamp, release, and loading operations
ordered, addressable, and visually traceable. `ReviewZone` records generic
heat, distortion, spatter, and restricted-contact intent without publishing
shop-specific limits.

`WorkflowEnvelope` is a shared neutral reference for torch, hand, operator,
robot, cobot, load, and unload approaches. Envelope intersections are
deterministic review findings linked to both the responsible workflow envelope
and the collided fixture geometry. They are not robot motion planning, thermal
simulation, or weld-quality validation. Missing process data remains a warning.

Every `WorkflowReport` is bound to the current versioned `ValidationResult`, its
immutable source hash, status, and evidence digest. `compare_workflow_variants`
requires distinct manual and robot/cobot reports for the same source product.
A variant with invalid or provisional authoritative validation cannot be
reported as passing all deterministic gates. All results remain
engineering-review-only and source CAD is immutable.
