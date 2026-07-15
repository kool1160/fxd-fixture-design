# FXD weld-fixture workflow contract

Milestone 19 composes the existing weld-rule and access contracts into an
editable engineer-review workflow. `SequencePlan` and `WorkflowStep` keep weld,
tack, clamp, and release operations ordered, addressable, and visually
traceable. `ReviewZone` records generic heat, distortion, spatter, and
restricted-contact intent without publishing shop-specific limits.

`WorkflowEnvelope` is a shared neutral reference for torch, hand, operator,
robot, cobot, and unload approaches. Envelope intersections are deterministic
review findings; they are not robot motion planning, thermal simulation, or
weld-quality validation. Missing process data remains a warning.

`compare_workflow_variants` compares reports by deterministic findings. It does
not permit a manual or automated variant to bypass a blocked geometry gate.
All results remain engineering-review-only and source CAD is immutable.
