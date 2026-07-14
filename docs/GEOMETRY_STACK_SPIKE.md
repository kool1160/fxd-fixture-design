# Geometry-stack spike — Milestone 1

## Decision

The baseline does not add a CAD kernel dependency yet. The neutral core is
proved with a small dependency-free AABB test double in `fxd_geometry/`; the
new `fxd_geometry.kernel` boundary makes that status explicit. A future kernel
adapter must implement the same domain boundary without leaking
vendor objects into the product model. This keeps the repository runnable in
CI while deferring a commercial redistribution decision until STEP fixtures
and kernel behavior can be evaluated with representative, legally shareable
geometry.

The likely production candidate is Open CASCADE Technology (OCCT) behind a
thin adapter. It is the strongest candidate for STEP, B-rep topology,
transforms, Boolean operations, distance/interference, and neutral export.
The proof is intentionally not evidence that OCCT is installed or selected.
Milestone 11 remains pending until a concrete wrapper is approved, installed,
and exercised against real B-Rep fixtures.

## Candidate comparison

| Candidate | STEP / B-rep | Boolean and clearance | Distribution and risk | Result |
| --- | --- | --- | --- | --- |
| OCCT, accessed through a reviewed binding | Strong; mature STEP and topology APIs | Strong geometric kernel | LGPL-2.1 with OCCT exception; binding and binary obligations must be reviewed per release | Candidate for Milestone 2 evaluation |
| CadQuery or build123d | Useful high-level modeling; depends on OCCT | Good for scripted solids; topology exposure is mediated | Apache-2.0 project, but OCCT and binding obligations remain; adds a modeling layer | Not the core boundary |
| trimesh | Mesh import/export and analysis | Useful mesh checks; not a STEP B-rep kernel | MIT; STEP/B-rep fidelity and robust Boolean coverage are insufficient for the initial core | Test utility only |
| Commercial CAD SDK | Potentially strong | Potentially strong | Vendor terms, redistribution, and deployment restrictions require approval | Excluded from baseline |

Licensing notes are a screening record, not legal advice. Before adding OCCT
or a binding, record exact versions, licenses, transitive dependencies,
redistribution obligations, platform binaries, and commercial implications.
No candidate dependency is installed by this milestone.

## Runnable evidence and limits

Run `python scripts/geometry_proof.py` for a synthetic transform,
intersection, clearance, and neutral JSON export proof. Run
`python -m unittest discover -s tests -v` for regression evidence.

The AABB proof does not cover curved surfaces, exact topology identity,
rotations, STEP parsing, robust Boolean solids, or manufacturing tolerances.
Those are explicit Milestone 2 inputs and must not be represented as solved by
this baseline.
