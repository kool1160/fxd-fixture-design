# Manufacturing Component Contract

Milestone 23 adds a CAD-neutral manufacturing-component layer in
`fxd_geometry.component_geometry`. It converts an approved Milestone 21
structural concept, and the optional Milestone 22 placement plan, into
editable real-kernel solids with stable identities, manufacturing metadata,
interfaces, source references, and review-only neutral exports.

Dependencies and interfaces remain caller-supplied. FXD validates component
identity, source SHA-256, parent connectivity, holes, fits, tab-and-slot
metadata, tooling mounts, planar DXF eligibility, and real-kernel collision
evidence. Invalid or incomplete evidence blocks export; the validator never
repairs geometry or invents manufacturing intent.

The layer complements Milestone 13 weld rules, Milestone 19 workflow/access
contracts, Milestone 21 structural concepts, and Milestone 22 placement
contracts. Existing feature-level manufacturing geometry and project formats
remain readable. Component solids are regenerated deterministically from the
persisted product and concept rather than mutating or embedding customer CAD.

STEP and planar DXF files are emitted as an engineering-review package only.
The current implementation is proof-layer geometry: it does not provide final
released drawings, complete tolerance-stack calculations, structural
certification, safety approval, thermal simulation, robot path planning, or
production approval. Future work can extend the same component contracts with
reliefs, machined profiles, purchased-tool mounting patterns, drawing views,
cost models, and qualified human approval evidence.
