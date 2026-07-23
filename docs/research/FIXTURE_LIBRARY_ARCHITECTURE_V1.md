# FXD Extended Fixture Library Reference Architecture v1

## Status and boundary

This document is implementation-ready architecture research. It relates to
Issues #61 and #62, but does not close either issue, begin Milestone 33, change
Milestone 32, modify PR #54, authorize runtime implementation, or approve a
fixture for production.

The schemas and data under `docs/research` and `data/research` are research
artifacts. Production code must not import or package them. A future owner must
approve a governed milestone before any runtime adoption.

## Architectural objective

The future library is a CAD-neutral, local-first system for storing and using:

1. FXD parametric fixture primitives;
2. user and shop engineering preferences;
3. exact private or supplier-authorized tooling geometry;
4. metadata-only commercial tooling;
5. user-authored reusable components;
6. fixture-family starting structures;
7. optional process-context assets;
8. private benchmark references; and
9. public engineering knowledge.

The library is not one flat catalog. It is a set of authority-separated records
that share stable identities, revision rules, interfaces, provenance, and
participation policies.

## Reference model

```text
Library source record
        |
        v
Immutable library item revision -----> preview or exact/private asset
        |                                      |
        +---- mounting interfaces              |
        +---- functional interfaces            |
        +---- movement states                   |
        +---- validation participation          |
        +---- output participation              |
        +---- replacement classes               |
        |                                      |
        v                                      v
Pinned project instance ----------------> project-local transform
        |
        +---- validation evidence by item revision and state
        +---- output evidence by item revision
        +---- explicit migration/replacement events
```

Identity belongs to the library record and project instance, not to a transient
B-Rep shape or display actor. Geometry, preview, supplier file, and generated
feature definitions are representations attached to that identity.

## Core entities

### Library item

`fixture_library_item_v1.schema.json` is the common envelope. It supports:

- schema and item identity;
- human-readable name and category;
- exactly one authority level;
- supplier or author, model/internal number, and immutable revision;
- explicit units;
- source-file identity and SHA-256 where a file exists;
- source, licensing, and privacy notes;
- embedded, linked, metadata-only, or not-applicable storage policy;
- editable, read-only, or new-revision-only authority;
- local coordinate system;
- exact, parametric, provisional, metadata, or absent preview;
- parametric feature definition;
- typed mounting and functional interfaces;
- contact, movement, open/closed, keep-out, and maintenance states;
- material and manufacturing intent;
- BOM, export, and validation participation;
- variants, replacement classes, revision history, and deprecation;
- missing-link behavior and downstream dependencies.

The schema permits compact research knowledge records while the complete
synthetic item demonstrates the full contract. A future runtime schema may
tighten conditional requirements per category only through a new version.

### Source record

`fixture_library_source_v1.schema.json` separates provenance from engineering
content. Public source records contain only the publisher, title, canonical
URL, access date, category, original FXD paraphrase, applicability, limitations,
reuse classification, and licensing note.

No public source record grants permission to redistribute supplier CAD,
catalogs, exact dimensions, performance claims, images, or copied text.

### Fixture-family template

A template is a bounded starting structure, never a completed fixture. It
declares product and material families, process and volume range, handling,
datum opportunities, support/locate/stop/clamp strategy, base structure,
loading and unloading, access, construction, primitive and purchased-tooling
categories, context needs, parameters, known failures, unsupported conditions,
required deterministic validations, and human-review questions.

### Shop-standard pack

A shop-standard pack is attributed engineering input. It does not become a
universal rule. The merge order is:

1. FXD defaults;
2. organization standards;
3. shop standards;
4. machine or process standards;
5. project overrides;
6. explicit engineer decisions.

The effective value comes from the highest applicable precedence, but the merge
result retains every lower-level value and source. Conflicts remain visible.
Two equal-precedence records conflict until an explicit deterministic
tie-breaker or engineer decision resolves them.

### Private benchmark case

A private benchmark case is an annotation and disposition record that may link
to private local assets. It is not itself the asset and never embeds the
fixture, screenshot, path, dimension set, or proprietary rule.

### Process-context asset

A context asset is loaded only when needed to answer the engineering question.
It records geometry authority, frames, movement states, keep-out and maintenance
envelopes, functional interfaces, required validation packs, and limitations.
Robot assets are optional; they are not the foundation of the architecture.

## Storage architecture

### Public repository

Permitted:

- schemas and contracts;
- synthetic examples;
- original FXD public engineering records;
- official-source metadata and paraphrase;
- abstract non-proprietary human dispositions.

Prohibited:

- private fixtures or customer/employer geometry;
- local paths or identifying private metadata;
- supplier CAD or catalog copies;
- exact vendor dimensions or claims;
- proprietary shop standards;
- unreleased inventions or patent-sensitive rules.

### Private local library

A future private store may contain exact imported CAD, user-authored components,
shop packs, and benchmark links. It must be separately controlled, ignored by
the public repository, local-first by default, and capable of enforcing
supplier and organization restrictions.

### Embedded versus linked

- `embedded` preserves project portability but duplicates controlled content
  and must respect license and privacy.
- `linked` preserves a separately managed source but can become missing.
- `metadata_only` never provides exact geometry.
- exact private or supplier-controlled geometry defaults to linked unless the
  owner and license explicitly permit embedding.

The project records the selected policy, source identity, expected SHA-256, and
last resolved evidence. A linked file that disappears does not erase the item
or placement; it blocks geometry-dependent actions.

## Stable project references

A project instance pins:

- item identity and immutable revision;
- representation identity and digest;
- local-to-project transform;
- mounting and functional interface identities;
- selected variant;
- movement state set;
- privacy and storage decision;
- downstream evidence digests.

Project references do not silently float to the newest library revision.

## Revision, replacement, and migration

### Immutable revisions

Editing a library definition creates a new revision. The old revision remains
addressable while any project depends on it. Deprecation changes selection
guidance, not historical project content.

### Linked updates

If a linked file changes SHA-256 under the same external path, FXD treats it as
an unresolved revision change. Exact geometry is unavailable for authoritative
use until the engineer links the changed file to a new library revision or
restores the expected source.

### Replacement

Replacement has three independent checks:

1. mounting-interface compatibility;
2. functional-interface compatibility; and
3. authority and validation compatibility.

A matching mount may preserve placement. It does not preserve validation.
Changed contact, motion, keep-out, authority, material, or output participation
makes dependent evidence stale.

### Missing links and relinking

When a link is missing, FXD retains identity, transform, interface records, and
last-known preview if policy permits. Exact collision, clearance, STEP, drawing,
and release actions block. Relinking requires the expected digest or an
explicit new-revision migration.

### No silent project rewrite

No library update, deprecation, supplier revision, source relink, or improved
template may rewrite an existing project silently. Migration is a visible
project revision with before/after identities, compatibility results,
invalidated evidence, and engineer disposition.

## Validation architecture

Validation participation is a declared property, not inferred from category
names. The authority and category matrices in
`FIXTURE_LIBRARY_VALIDATION_MATRIX_V1.md` define the minimum behavior.

Important rules:

- metadata cannot participate in exact geometry checks;
- provisional envelopes may support conservative review but never exact proof;
- missing required exact geometry blocks dependent validation;
- output and validation evidence cite item revision and state;
- AI recommendations cite retrieved record identities and cannot upgrade
  authority;
- human confirmation remains required wherever the matrix says so;
- production release remains an external qualified-human boundary.

## Output architecture

### BOM

An item may be included as an exact purchased identity, a generic unresolved
line, a manufactured FXD component, or excluded. Metadata-only commercial
records may create an explicitly unresolved BOM line but not an exact part
claim.

### STEP

Only exact authorized imported geometry and validated FXD-authored geometry may
participate. A project must respect supplier export restrictions. Provisional
and metadata-only records are excluded.

### DXF

Only validated 2D-manufacturing definitions derived from FXD-authored or
authorized editable components may participate. Purchased tooling and
provisional context assets are excluded.

### Drawings and review reports

Review reports may show metadata and provisional status with visible labels.
Drawings distinguish exact, manufactured, reference-only, and omitted content.

### Coherence

STEP, DXF, BOM, drawing, marking, and review manifests must share one project
revision and item-revision set. Any omission, supplier restriction, or
provisional representation is explicit.

## Relationship to the current public knowledge layer

PR #54's `fxd-fixture-knowledge-v1` remains an M32-specific public precedent
runtime. This research package does not import it, modify it, or replace it.
The later migration described in `FIXTURE_LIBRARY_MIGRATION_MAP_V1.md` treats
those records as `public_engineering_knowledge` sources within the extended
system while preserving their stable identities, source references, human
dispositions, and deterministic retrieval evidence.

## Specialist review

### Manufacturing Engineer

Question: Can categories express real stock, process, assembly, service, and
volume choices without universalizing one shop?

Result: shop packs are precedence-aware inputs; templates prefer standard and
fabricated construction but require project-specific manufacturability.

### Fixture and Tooling Engineer

Question: Can an experienced engineer distinguish a reusable component, a
starting template, and a validated project fixture?

Result: authority, category, template boundary, interfaces, and project pinning
remain distinct.

### Locator and Constraint Engineer

Question: Do functional interfaces carry datum role, direction, contact
geometry, state, and dependent constraint checks?

Result: locator, support, stop, and clamp contacts are typed and cannot be
inferred from a preview.

### Clamp and Tooling Engineer

Question: Can commercial tooling remain useful before exact authorized CAD?

Result: metadata and provisional envelopes support recommendation and review,
but exact collision, export, and release remain blocked.

### Weld Process Engineer

Question: Does a torch envelope falsely imply weld procedure or safety
approval?

Result: process-access participation is state-specific and review-only; safety
and procedure approval remain external.

### Inspection and Quality Engineer

Question: Are build and inspection roles separated, and are standards claims
bounded?

Result: inspection templates separate datum and check roles. ISO sources are
metadata-only watch items; no normative content is implemented.

### Geometry Engineer

Question: Can identities survive representation and B-Rep regeneration?

Result: item, revision, project instance, frame, and typed-interface identities
are independent of transient topology. Stable subshape references remain a
future implementation risk.

### AI Systems Engineer

Question: Can retrieval guide decisions without becoming engineering truth?

Result: authority and participation are deterministic fields; AI cannot change
them and must cite source records and unresolved evidence.

### Validation Engineer

Question: Does replacement make the correct evidence stale?

Result: mount, function, authority, geometry, movement, and output changes are
independent invalidation triggers.

### UX and Workflow Engineer

Question: Can the engineer see why an item is exact, provisional, missing,
deprecated, or stale?

Result: status must be visible at item, representation, project instance,
validation, and output levels; no background update rewrites projects.

### IP and Standards Guardian

Question: Can the public package be safely distributed?

Result: it contains schemas, synthetic records, metadata, and original
paraphrase only. Private and supplier-controlled assets remain excluded.

## Recorded disagreements

1. Exact geometry versus conservative envelopes: validation benefits from exact
   geometry, while IP and sourcing constraints often permit only metadata.
   Resolution: keep both useful but unequal; exact-required checks block.
2. Embedded portability versus controlled linked assets: portability favors
   embedding, while licensing and privacy favor linking. Resolution: policy is
   explicit per item; restricted exact assets default to linked.
3. Reuse versus project specificity: reusable modules reduce effort, while
   locator and process validity are project-specific. Resolution: reuse
   interfaces and starting intent, never validation approval.
4. Flexible shop standards versus deterministic results: shops need overrides,
   while hidden overrides destroy explainability. Resolution: deterministic
   precedence with full provenance and visible conflicts.
5. Build-and-check integration versus inspection independence: combined tooling
   may improve flow but can bias results. Resolution: roles and fixture states
   remain explicit, with qualified quality review required.

## Assumptions

- Internal geometry units remain millimeters unless a future governed decision
  changes the kernel boundary.
- Library identity storage is local-first.
- Item revisions are immutable and content-addressable.
- A future project scene will provide stable project-instance identities and
  transforms, but this package does not define or implement that scene graph.
- Public knowledge records can be migrated without importing copyrighted source
  text.
- Human engineering approval remains mandatory for production use.

## Risks

- stable topology references across arbitrary B-Rep edits remain unresolved;
- supplier license terms may restrict embedding, export, or preview generation;
- broad provisional envelopes can create false conflicts while narrow ones can
  create false clearance;
- shop-standard conflicts can be numerous and hard to present;
- interface compatibility can be declared incorrectly without geometry checks;
- private-corpus annotations could leak proprietary knowledge through overly
  specific prose;
- standards metadata can become outdated and cannot replace licensed review.

## Unresolved architecture questions

1. Which future project/scene contract owns library instances and transforms?
2. Will a future implementation use the current JSON project model, OCAF, or a
   layered hybrid for parametric dependencies and undo?
3. What stable subshape strategy is acceptable for regenerated fixture-native
   features?
4. Which exact item fields become required per category in schema v2?
5. How are large private libraries indexed without leaking metadata or requiring
   cloud storage?
6. How are supplier-license policies represented and enforced at export time?
7. What qualified process packs are first: weld, inspection, assembly, or
   machining?
8. What human role may approve a private benchmark for selected public release?
9. How are compatible replacement classes certified and versioned?
10. What UX proves stale, missing, provisional, and exact authority without
    overwhelming normal engineering work?

## Validation evidence

`scripts/validate_fixture_library_research.py` validates the bounded Draft
2020-12 vocabulary used by the eight schemas, every reference instance,
cross-file source identities, minimum corpus counts, privacy invariants, and
forbidden binary/CAD extensions using only the Python standard library.
