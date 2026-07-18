# Manufacturing Orientation Contract

## Purpose

`fxd_geometry.manufacturing_orientation` records a deterministic manufacturing
coordinate system separately from immutable customer STEP coordinates. It gives
the workbench familiar Front, Top, Right, selected-planar-face, custom-plane,
and source-orientation choices without rotating, rewriting, or relabeling the
source model.

## Evidence and acceptance

An orientation stores the source SHA-256, source coordinate system, selected
exact fixture-down face, optional exact operator/front face, their plane origin
and normal evidence, normal flip, source-to-manufacturing 4x4 transform, inverse
transform, method, explanation, and evidence. The ordinary guided path projects
the front-face normal into the bottom plane, assigns it to manufacturing +Y,
assigns the accepted bottom normal to manufacturing +Z, and derives the
right-handed +X axis. Parallel bottom/front definitions fail clearly. The
matrices are validated as inverses. An orientation proposal is not accepted
merely because it can be constructed. The engineer must explicitly accept it
for its current source SHA-256 before analysis is enabled.

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

STEP import opens a dedicated three-step Orientation page before Process or
assembly analysis. The engineer clicks a planar fixture-down face and then a
planar operator/front face directly in the persistent VTK viewport. Bottom and
front use distinct review-only highlights; the preview shows the build plane,
manufacturing XYZ triad, operator/front direction, gravity/build-down, and
load/unload directions. A largest/stablest planar-face recommendation is phrased
as a question and never accepted silently. Normal mode shows no raw face IDs or
matrices. Existing reference-plane, exact-axis, flip, quarter/custom rotation,
transform, inverse, face, plane, and raw-evidence controls remain available only
inside **Advanced orientation settings**. An **Edit orientation** command returns
to the guided page later.

The persistent VTK viewport retains the real OCP-imported source actors. Its
overlays are not source CAD, proof geometry, or manufacturing geometry, and they
never receive `REAL OCP` source authority. Native worker cell picking maps a
clicked tessellation triangle back to the exact OCP face identity. Render-window
size is synchronized with the embedded child window, and resize rendering is
coalesced to avoid stale repaint smearing.

## Limits

This contract does not provide mass properties, thermal simulation, robot path
planning, collision-free welding, production approval, or a universal best
fixture orientation. Qualified engineering review remains mandatory.
