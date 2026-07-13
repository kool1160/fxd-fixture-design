# FXD tooling library contract

Milestone 7 adds `ToolingItem`, `ToolingLibrary`, and `ToolingSelection` as
vendor-neutral contracts for clamps, pins, rests, and future tooling classes.
Each item contains an explicit millimetre envelope, stroke, force, mounting
metadata, access metadata, source, license, attribution, preference, and a
custom-geometry marker.

`generic_tooling_library()` contains synthetic metadata only. A private shop
library may be passed to `ToolingLibrary` at runtime, but custom geometry must
identify a non-public source and is never bundled by FXD. Selection requires
minimum stroke and force and deterministically prefers adequate standard items
before custom items. No selection proves contact stability, force adequacy,
tolerance stack, weld access, or production readiness; those remain validation
and human-approval responsibilities.
