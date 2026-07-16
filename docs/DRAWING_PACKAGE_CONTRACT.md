# Drawing Package Contract

Milestone 24 drawings are a deterministic review representation of one
validated Milestone 23 `ManufacturingAssembly`. The package preserves the
source SHA-256, concept identity, manufacturing evidence digest, stable
component identities, part numbers, revisions, BOM entries, hole metadata,
dimensions, STEP/DXF links, assumptions, and validation evidence.

`fxd_geometry.drawings` owns typed sheets, views, dimensions, annotations,
hole-table rows, BOM entries, revision blocks, findings, and a small
timestamp-free PDF renderer. Views are derived from authoritative component
bounds and metadata; the renderer does not replace B-Rep geometry or invent
datums, tolerances, fits, weld procedures, or approval.

Assembly, exploded, fabricated-component, purchased-reference, and
evidence-backed detail sheets are generated in stable order. Missing or
contradictory identities, exports, title blocks, validation evidence, or
approval-boundary text fail closed. The existing manufacturing export package
can include `fixture-drawings.pdf`, `drawing-manifest.json`, and
`drawing-bom.json` only after the assembly, fixture validation, and drawing
provenance gates pass.

The PDF visibly states `ENGINEERING REVIEW REQUIRED` and `NOT RELEASED FOR
PRODUCTION`. All outputs remain engineering-review-only. No structural,
safety, weld-procedure, vendor, or production certification is implied.
Milestone 25 cost and volume optimization and Milestone 26 pilot work remain
outside this contract.
