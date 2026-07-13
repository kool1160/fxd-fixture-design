# FXD complete fixture concept contract

Milestone 5 adds `generate_fixture_concepts`, which composes the immutable
product model and the Milestone 4 primitive proof into three alternatives:
`minimum_cost`, `fast_loading`, and `high_repeatability`. Each alternative
contains a locating strategy, a clamp strategy, traceable clamp-mount
features, deterministic constraint findings, and a score with its component
values and rationale.

The score is a bounded prioritization aid, not a safety or production-release
claim. Constraint analysis proves only the translation intent represented by
the proof layer. Rotational restraint, contact normals, clamp force,
tolerance stack, weld access, and unloadability still require later geometry
and engineering validation. Missing permitted locating intent is surfaced as
an underconstraint warning; AABB limitations are surfaced explicitly.

`FixtureCorrection` is copy-on-write concept metadata. Corrections never alter
the imported `ProductModel` or its source bytes. AI may eventually suggest
these corrections through a restricted command contract, but this milestone
contains no AI execution path.
