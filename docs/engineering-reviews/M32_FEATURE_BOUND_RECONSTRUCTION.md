# M32 Feature-Bound Reconstruction Record

Status: implementation evidence for renewed qualified Windows fixture-engineering review
Milestone: 32
Issue: #57
Implementation PR: #54
Supported family: `linear_multi_station_weld_fixture`

This record does not approve, certify, or release the fixture. PR #54 must
remain draft, open, unmerged, and without auto-merge until Chris completes
another qualified Windows fixture-engineering review.

## Inputs reconciled

- the runtime `fxd-fixture-knowledge-v1` corpus;
- the merged extended fixture-library research package from PR #64, used as
  non-runtime research guidance under its authority and privacy contract;
- all ten public NIST AP242 STEP reference parts merged by PR #65;
- the first Windows rejection: template-driven stations, unproved handling,
  crowded ends, impractical clamps, unproved weld access, a tall wall-like
  structure, weak construction intent, and unclear semantics;
- the second Windows rejection: isolated generic stations, excessive rail and
  empty span, primitive contacts, weak base coherence, unclear station rhythm,
  and an unconvincing support/locator/stop/clamp/reaction strategy.

No private review image, proprietary fixture heuristic, employer data, or
confidential shop standard is reproduced here.

## Reconstruction contract

M32 no longer selects arbitrary sorted faces or percentage-of-bounding-box
contact locations. The supported workflow requires current imported OCP
evidence for:

- one planar primary support face with three non-collinear on-face mesh points;
- one planar secondary locator face;
- one planar tertiary stop face;
- one planar clamp-contact face;
- either zero locator holes or exactly two cylindrical locator holes with
  exact axes and radii.

Bindings include immutable source references, surface type, area, center,
normal, face bounds, on-face mesh points, and a mesh SHA-256. They are
recomputed before synthesis; stale or modified evidence is an authoring
blocker.

The benchmark station uses three fixed primary rests, a distinct projected
clamp reaction rest, one round pin, one relieved pin, clearance side and
loading guides, a feature-targeted clamp envelope, local station plate mounts,
and a connected paired-rail base. Pin radii equal imported hole radii minus
the explicit diametral clearance. Loading and unloading use a two-stage path:
axial lift off the exact pin pair followed by translation through the recorded
operator corridor.

## Single-station gate

A repeated fixture receives no authoring authority unless a one-up station
first passes:

1. exact feature and component-placement validation;
2. fixture concept-quality validation;
3. clamp reach, open state, hand, loading, unloading, trapped-part, and
   recorded weld-access validation;
4. deterministic plate, hole, parent-path, and manufacturability validation.

The passed result is persisted as
`fxd-m32-single-station-qualification-v1` evidence with a SHA-256 digest.
Failed one-up work may remain inspectable as a diagnostic plan, but repeated
OCP fixture authoring is blocked.

## Public reference evidence

Regression coverage imports all ten NIST AP242 files and confirms deterministic
face identities, positive face areas, planar evidence, and cylindrical
axis/radius evidence. The public synthetic M32 bracket includes two actual
through-holes and exercises the same workbench normalization, binding,
one-up qualification, five-up repetition, OCP authoring, tessellation, and
project persistence path.

## Remaining human boundary

The result remains provisional fixture-engineering work. A qualified reviewer
must still assess real clamp selection and force, distortion response,
ergonomics, guarding and pinch points, structural capacity, maintenance,
shop-specific mounting and tolerances, weld process details, and production
release suitability.
