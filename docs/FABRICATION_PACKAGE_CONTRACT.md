# FXD fabrication-package export contract

Milestone 8 adds a deterministic, vendor-neutral review package for an
eligible complete fixture concept. The package contains:

- `fixture.step`: ISO-10303-21-shaped proof output containing explicit FXD
  AABB boxes; it is not kernel-authored B-Rep STEP;
- `profiles.dxf`: millimetre XY envelope polylines for the current proof layer;
- `bom.json`: reconciled generated-feature and generic-tooling quantities;
- `setup.md`: locating, clamping, units, and required review actions;
- `validation.json`: concept and optional access findings;
- `manifest.json`: concept identity, source hash, revision, artifact list, and
  `production_approval: false`.

Invalid concepts cannot be exported. Provisional concepts may be exported for
engineering review, but every package is marked `engineering_review_required`
and explicitly does not certify, validate, or approve production use. The
current proof layer cannot preserve curved topology, manufacturing tolerances,
bend deductions, or real tooling geometry; a future kernel/export milestone
must replace these representations before fabrication-ready CAD claims are
appropriate.
