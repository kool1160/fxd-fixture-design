# FXD access-analysis contract

Milestone 6 adds a dependency-free proof-layer contract for weld, operator,
robot, and unload access. `WeldAccessRequest` binds an explicit manual or
robot envelope to a stable annotation weld-joint identity. `AccessEnvelope`
also supports operator and unload envelopes so process assumptions are visible
instead of inferred.

Envelopes use explicit millimetre AABBs, optional approach direction and reach,
and a `process_data_complete` flag. The evaluator intersects envelopes with
generated fixture features and returns traceable findings. Blocked approaches
and unload paths are errors for concept validation; missing or incomplete
process data is a warning. No warning or error is a certification, production
approval, weld-quality result, or robot-motion result.

The AABB proof layer cannot establish free-form B-Rep clearance, torch angle,
operator ergonomics, robot reachability, singularity avoidance, or weld
sequence quality. Those require representative geometry and future validated
kernel or simulation adapters.
