# FXD engineering-annotation contract

Milestone 3 adds `EngineeringAnnotations`, a CAD-neutral document bound to the
SHA-256 identity of one immutable `ProductModel`. It stores engineering intent
separately from imported source geometry:

- build orientation and loading direction as explicit vectors
- process type and positive production quantity
- critical characteristics with references, nominal values, units, and tolerance
- permitted locating surfaces and forbidden contact areas
- weld-joint references and process notes
- shop constraints and editable, visible assumptions

`GeometryReference` identifies a component and may narrow to a body, face, or
edge. Saving and loading validates every reference against the source model and
rejects a different source hash. JSON is deterministic and local; it contains
annotation data, not source CAD bytes or generated fixture geometry.

This contract records intent only. It does not claim constraint satisfaction,
collision/access validation, manufacturability, certification, or production
approval.
