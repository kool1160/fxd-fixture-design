# FXD structural concept contract

Milestone 21 composes the existing primitive fixture features into a complete
proof-layer structural assembly. `StructuralAssembly` records a deterministic
baseplate or welded-frame strategy, base supports, risers, brackets, locator
mounts, clamp towers, frame rails, parent/child connectivity, load paths, sizing
assumptions, and traceable findings.

Strategy selection uses explicit product spans, loading direction, process,
production quantity, caller-supplied access requirements, and shop constraints.
Thresholds are public `StructuralParameters`; they are review heuristics, not
universal shop policy. A caller may explicitly override the strategy.

Connectivity and load-path checks are AABB proof-layer evidence. They reject
unknown parents, disconnected members, cycles, missing roots, unsupported
features, and missing load paths. They do not prove force adequacy, stiffness,
weld quality, fatigue life, operator safety, or production approval.

The structural assembly remains separate from immutable source CAD and is
regenerated from editable fixture concepts. Real B-Rep component authoring,
serious placement optimization, drawings, detailed costing, and released
manufacturing geometry remain later milestone work.
