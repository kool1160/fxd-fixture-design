# Manufacturing Orientation Contract

## Purpose

`fxd_geometry.manufacturing_orientation` records a deterministic manufacturing
coordinate system separately from immutable customer STEP coordinates. It gives
the workbench familiar Front, Top, Right, selected-planar-face, custom-plane,
and source-orientation choices without rotating, rewriting, or relabeling the
source model.

## Evidence and acceptance

An orientation stores the source SHA-256, source coordinate system, selected
exact face or reference-plane identity, plane origin and normal, normal flip,
rotation about the build normal, source-to-manufacturing 4x4 transform, inverse
transform, method, explanation, and evidence. The matrices are validated as
inverses. An orientation proposal is not accepted merely because it can be
constructed. The engineer must explicitly accept it for its current source
SHA-256 before analysis is enabled.

Changing the source, plane, face, flip, or rotation revokes downstream
analysis, concepts, fixture-build state, and cached authored geometry. A stale
orientation or an unaccepted proposal fails closed. Exact source-face
annotations remain source evidence and are not CAD edits.

## Analysis boundary

Process directions are specified in manufacturing coordinates. Interactive
workflow orchestration converts those vectors through the accepted transform at
the CAD-neutral engine boundary, so existing support, datum, clamp, access,
load, unload, and fixture calculations use the accepted manufacturing frame
without mutating source geometry or coordinates.

Auto recommendation ranks only confirmed planar-face area and available
tessellation-based stability/center-projection evidence. Weld access, clamp
access, loading, unloading, trapped-part risk, and distortion evidence remain
explicitly provisional until the applicable engineering annotations and
envelopes exist. Recommendations are never approvals and cannot turn missing
evidence into a pass.

## Workbench presentation

The persistent VTK viewport retains the real OCP-imported source actors. It
adds separate review-only actors for the selected face tessellation, translucent
build plane, manufacturing XYZ triad, gravity/build-down arrow, and load/unload
arrows. These overlays are not source CAD, proof geometry, or manufacturing
geometry, and they never receive `REAL OCP` source authority.

## Limits

This contract does not provide mass properties, thermal simulation, robot path
planning, collision-free welding, production approval, or a universal best
fixture orientation. Qualified engineering review remains mandatory.
