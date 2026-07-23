# FXD Fixture Library Stable Interfaces v1

## Purpose

Stable interfaces let a library component be mounted, replaced, validated, and
explained without treating transient B-Rep topology or a preview envelope as
its identity.

An interface identity is stable within one immutable item revision. Geometry
may realize the interface, but the interface record owns its engineering role.

## Frame rules

Every interface uses or references the reusable
`owned_coordinate_frame_v1.schema.json` contract with:

- explicit origin;
- orthonormal X, Y, and Z directions;
- declared units;
- stable frame identity; and
- owner identity;
- handedness;
- frame purpose; and
- relationship to the library item's local coordinate system.

The semantic validator rejects missing or duplicate axes, non-finite values,
zero vectors, non-normalized vectors, non-orthogonal bases, declared
left/right-handedness that disagrees with the basis, missing owners, and frame
units that disagree with the owner.

Project placement composes:

```text
interface local frame
  -> item local frame
  -> project instance transform
  -> project manufacturing or scene frame
```

Transforms never change the underlying item revision.

## Mounting interfaces

`mounting_interface_v1.schema.json` supports the following typed records.

### `face_mount`

Defines a mating face or plane, normal direction, contact region identity,
fastener or weld intent, and clearance/tolerance intent.

### `hole_pattern`

Defines stable hole identities, axes, relative locations in the interface
frame, fastener intent, and which features are round, clearance, tapped, or
otherwise classified by a governed shop or project input.

No universal fit or fastener is inferred.

### `slot_pattern`

Defines stable slot identities, centerlines or axes, adjustment direction,
usable range, lock intent, and clearance source.

### `pin_and_bushing`

Defines pin and bushing identities, insertion axis, round or relieved role,
replacement intent, and datum responsibility.

### `rail_mount`

Defines a parent rail frame, attachment regions, allowed position or pattern
parameters, and lock or fastening intent.

### `weld_mount`

Defines intended mating regions, assembly direction, weld-access dependency,
fit-up intent, and the fact that weld design and approval remain external.

### `table_grid_mount`

Defines the table-frame relationship and selected grid-feature identities.
Supplier or shop grid dimensions are referenced from the applicable exact
asset or standard pack; they are not universalized.

### `custom_datum_frame`

Defines a project-specific mounting frame when no standard type is adequate.
It requires an explanation and human confirmation.

## Required mounting fields

Every mounting interface captures:

- interface identity and type;
- frame identity;
- origin and axes;
- tagged `hole`, `slot`, `pin`, `bushing`, `rail`, `planar_face`,
  `weld_mount`, `table_grid_mount`, or `custom_datum_frame` features;
- each feature's stable identity, owning-interface reference, local position,
  normalized axis, applicable dimensions, adjustment range, tolerance or
  clearance intent, mating role, datum responsibility, and allowed replacement
  class;
- fastener intent;
- mating authority;
- tolerance or clearance classification and values where known;
- whether human confirmation is required; and
- allowed replacement classes.

## Functional interfaces

`functional_interface_v1.schema.json` supports:

- clamp contact;
- locator contact;
- support contact;
- stop contact;
- torch tip;
- robot TCP;
- probe point;
- sensor field;
- load direction;
- unload direction; and
- maintenance access.

Every functional interface captures:

- stable identity;
- role;
- frame;
- direction;
- a tagged point, axis, plane, bounded region, contact patch, envelope,
  tool-center point, or sensor field representation;
- movement state;
- permissible-contact status; and
- dependent validation packs.

## Contact interfaces

Clamp, locator, support, and stop interfaces remain distinct. A combined
physical component may expose more than one interface, but each interface has a
separate role and validation participation.

Contact geometry may be:

- a point;
- an axis;
- a plane; or
- a bounded region; or
- a contact patch.

The interface records permissible contact as required, permitted, forbidden,
not applicable, or human confirmation required.

## Tool and process interfaces

### Torch tip

Records the process reference point and approach direction. Body, cable, gas
cup, or other envelopes remain separate state geometry.

### Robot TCP

Records a tool-center frame for context alignment. It does not grant kinematic,
path, accuracy, singularity, or safety authority.

### Probe point

Records the measurement reference point and approach. Measurement uncertainty,
calibration, and inspection acceptance remain external evidence.

### Sensor field

Records an axis, region, or field used for presence or process review. Exact
field performance requires authorized supplier evidence and application
validation.

### Load and unload directions

Record intended handling vectors or regions per state. They are evidence inputs
to collision and trapped-part checks, not complete motion planning.

### Maintenance access

Records service regions, removal directions, and required states. A component
that can be installed but not serviced is not fully compatible.

## Interface compatibility

Compatibility is evaluated in layers:

1. same interface schema and type;
2. compatible frame convention;
3. compatible feature identities and count;
4. compatible fastener or mating intent;
5. compatible tolerance and clearance intent;
6. compatible functional roles and directions;
7. compatible movement states;
8. compatible geometry authority;
9. compatible validation and output participation.

Compatibility results:

- `compatible`;
- `placement_compatible_validation_stale`;
- `conditionally_compatible_human_confirmation`;
- `incompatible`; or
- `unknown_missing_evidence`.

## Replacement preserving placement

Placement may be preserved only when the selected mounting interface is
compatible. Even then:

- functional-interface changes make role evidence stale;
- contact changes make constraint and clamp evidence stale;
- movement changes make collision and access evidence stale;
- authority changes make operation permissions stale;
- source or revision changes make output evidence stale.

The project creates an explicit replacement event. It never swaps silently.
Placement compatibility is a separate result from functional equivalence.
Preserving a transform only means the mounting contract can be aligned; it
cannot preserve contact, force-reaction, motion, access, or release evidence.

## Regeneration and stable references

For FXD parametric components, feature definitions should generate interface
frames and feature identities deterministically. A regenerated B-Rep face may
change kernel topology identity while the semantic interface identity remains.

If regeneration cannot re-establish an interface unambiguously:

- the interface becomes unresolved;
- dependent placements and validation become stale;
- the project blocks exact output;
- the engineer must repair or select the interface explicitly.

This architecture does not claim a general solution to the topological naming
problem.

## Missing and degraded representations

An interface record may remain visible when exact geometry is missing. It can
support explanation and relinking but not exact geometry operations.

A provisional replacement interface never inherits exact status from the
missing source. The UI must show degraded authority and blocked operations.

## Movement-state closure

State identities are unique within the owning item or context asset. Every
functional interface and envelope state reference resolves to that owner.
Items that claim open/closed behavior must name both an open and closed state;
fixed items must not carry hidden open/closed references. Contact references
resolve to existing functional interfaces. These closure rules are semantic
validator requirements, not UI conventions.

## Interface review questions

- Does the interface identify engineering function rather than only shape?
- Are frame and direction unambiguous?
- Are units and tolerance intent explicit?
- Does the mating authority match the actual source?
- Are movement and maintenance states complete?
- Will replacement preserve only what the evidence supports?
- Which validations become stale if this interface changes?
- Can the engineer repair a broken interface without rewriting source CAD?
