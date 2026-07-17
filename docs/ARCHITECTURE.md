# FXD Architecture

## Architectural shape

```text
CAD files / CAD connector
          |
          v
  Import and translation
          |
          v
Normalized Product Model  <---- Engineering annotations
          |
          v
Geometry + Constraint Engine
          |
          +---- Fixture rule packs
          +---- Access and collision analysis
          +---- Standard tooling libraries
          |
          v
Fixture Concept Model
          |
          +---- AI planner / explainer / ranker
          +---- Deterministic validators
          |
          v
Editable UI + neutral exports + CAD connectors
```

## Major boundaries

### Product model

Represents source assemblies, components, instances, transforms, bodies, faces, edges, units, metadata, and stable geometric references. It never contains generated fixture geometry as though it were part of the customer product.

### Engineering annotations

Represent build orientation, critical characteristics, welds, forbidden regions, permissible contacts, load direction, process envelopes, quantity, tolerance intent, and shop constraints.

### Fixture concept model

Represents base structures, locators, supports, clamps, purchased components, generated parts, assembly sequence, assumptions, warnings, scores, and traceability.

### Geometry and constraint engine

Owns topology queries, spatial indexing, contact calculations, collision, clearance, Boolean operations, approach envelopes, degrees-of-freedom reasoning, and deterministic concept checks.

### AI layer

Consumes compact structured context. It proposes restricted commands, asks for missing engineering intent, compares valid concepts, and explains tradeoffs. It does not directly mutate kernel geometry or silently override failed checks.

### Interactive workflow orchestration

`fxd_geometry.interactive_workflow` is a CAD-neutral application contract. It
records process setup, exact OCP-derived face annotations, private tooling
metadata state, finding review state, and operation timings. It translates
those inputs into the existing annotations, placement, concepts, project, and
validation APIs. It does not own geometry rules and may not convert unknown
evidence into a pass. The PySide6 shell invokes this boundary; it does not
duplicate engineering policy.

### Desktop presentation system

`fxd_ui` owns the approved FXD desktop tokens, application palette, QSS,
production icons, and reusable semantic Qt widgets. It consumes stable domain
identities and validation results but owns no geometry, engineering rules,
approval policy, project revisions, or persistence. `fxd_qt_app.py` composes
that presentation layer with the existing persistent VTK viewport and
CAD-neutral interactive workflow. A theme or layout change therefore cannot
turn provisional evidence into authoritative source geometry or bypass a
deterministic gate.

### Connectors

Thin adapters import or export data through STEP and vendor APIs. The standalone application must work without a vendor connector.

## Technology selection criteria

The geometry stack must be evaluated for:

- STEP assembly import and export
- stable topology access and transforms
- Boolean robustness
- distance, interference, and section operations
- 2D profile and DXF generation
- Windows distribution
- headless testing
- commercial redistribution
- performance on industrial assemblies
- language bindings and long-term maintenance

Milestone 1 must produce runnable evidence before the stack is considered selected.
