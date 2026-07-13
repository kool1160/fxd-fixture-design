# FXD Engineering Constitution

## 1. Source geometry is immutable

Imported product geometry is evidence, not a workspace for destructive edits. Store annotations, fixture features, derived geometry, and user corrections separately. Preserve source identity and transforms.

## 2. Use a CAD-neutral domain model

The engineering core may not depend on SOLIDWORKS, Inventor, or another vendor object model. Connectors translate between vendor APIs and the neutral FXD model.

## 3. Deterministic systems own engineering truth

Language models may interpret and propose. They may not be the sole authority for dimensions, topology, constraints, collision, clearances, units, quantities, or safety claims.

## 4. Every generated feature must be traceable

A support, stop, pin, clamp mount, relief, or baseplate feature must identify:

- the input geometry or annotation that caused it
- the rule or command that generated it
- its parameters and units
- assumptions and warnings
- later user edits

## 5. Units and tolerances are explicit

Use one documented internal unit system, initially millimeters and radians unless the chosen kernel requires another representation. Never infer units silently. Separate nominal geometry, manufacturing allowance, contact clearance, and process tolerance.

## 6. Fixture design is constraint design

Represent the intended removal of translational and rotational degrees of freedom. Detect likely underconstraint, redundant constraint, contradictory contact, and intentional float. Clamping direction should be evaluated relative to locating geometry.

## 7. Access and removability are first-class

A geometrically valid fixture is invalid if the product, operator, torch, clamp, robot, or finished assembly cannot access or leave the required space. Load sequence and unload path must be represented explicitly as the product matures.

## 8. Prefer manufacturable simplicity

Favor standard purchased components, laser-cut plates, formed parts, tab-and-slot construction, replaceable wear points, and understandable adjustment over unnecessary custom machining or mathematically clever geometry.

## 9. Human approval is mandatory

FXD produces engineering proposals and evidence. It does not certify a fixture, approve a weld process, guarantee distortion, or authorize production. Release states and warnings must be honest.

## 10. Validation requires representative geometry

Use synthetic and legally shareable golden models covering repeated parts, nested transforms, thin sheet, tubes, holes, inaccessible welds, trapped products, tolerance variation, and deliberately invalid fixtures. Tests must include numeric tolerances appropriate to the kernel.

## 11. AI output must be bounded

Natural-language requests must compile into a restricted command model. Validate commands before execution. Destructive or high-impact actions require preview and approval.

## 12. Privacy is local-first

Do not upload customer or employer CAD to external services by default. Cloud or AI use must disclose exactly what geometry, metadata, images, or derived information leaves the machine.

## 13. Dependency licensing is an architecture concern

Record the license, redistribution obligations, binary requirements, and commercial implications of every geometry, CAD, UI, AI, and export dependency. Do not assume that a package being downloadable makes it commercially safe.

## 14. Proprietary knowledge stays separated

Public code may define interfaces and generic rules. Confidential shop knowledge, patent-sensitive methods, customer corrections, and commercial rule packs must live in ignored or separately controlled storage.

## 15. One health command

`scripts/ci.sh` must remain the authoritative repository-health command. Every milestone keeps it working and extends it when new technologies are introduced.
