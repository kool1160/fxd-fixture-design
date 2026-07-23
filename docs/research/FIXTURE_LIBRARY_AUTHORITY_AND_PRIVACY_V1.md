# FXD Fixture Library Authority and Privacy v1

## Purpose

Authority answers: "What may this record prove?" Privacy answers: "Where may
this record and its representations go?" They are independent and both are
required.

Every library item has exactly one authority level. Authority is immutable
within an item revision. Upgrading authority creates a new revision and makes
dependent evidence stale.

The common schema enforces these distinctions with conditional requirements,
not prose alone. Exact private and supplier CAD require source identity,
SHA-256, units, storage, read-only authority, an owned frame, licensing/usage
evidence, and exact visible classification. Supplier exact CAD additionally
requires supplier and model identity. Metadata, provisional, template,
standard, benchmark, context, and knowledge authorities are denied
manufacturing geometry outputs. A preview can never upgrade authority.

## Authority levels

### `fxd_parametric_component`

An FXD-owned, versioned feature definition that can deterministically generate
supported geometry. It may participate in exact geometry, manufacturing
outputs, BOM, and validation only after successful generation and project
validation.

It does not imply structural, process, or production approval.

### `exact_private_imported_cad`

Exact locally imported geometry controlled by the user or organization. Source
identity, SHA-256, units, revision, privacy, and storage policy are required.

It may participate in exact collision and clearance. Export and redistribution
follow owner policy. It is read-only evidence unless separately converted into
an authorized editable representation.

### `supplier_authorized_exact_cad`

Exact supplier geometry obtained under terms that authorize the intended local
use. Supplier, model, revision, source, SHA-256, and licensing notes are
required.

Authorization for local use does not automatically permit embedding, public
commit, redistribution, STEP export, or derivative publication.

### `metadata_only_commercial_component`

Supplier and model metadata without exact geometry. It may support sourcing,
recommendation, and interface questions. An optional `advisory_bom_hint` can
describe an unresolved candidate, but `deliverable_eligible` is always false
and `bom_participation` remains `excluded`.

It is excluded from exact collision, exact clearance, STEP, DXF, and any claim
that depends on physical geometry.

### `provisional_review_envelope`

Explicitly approximate review geometry. It may support conservative
broad-phase review and communicate missing evidence.

It never silently becomes exact. Exact collision, exact clearance, release,
supplier identity, and manufacturing output remain blocked or excluded.
Fixture BOM participation is excluded; a generic review placeholder, when
needed, uses the separate non-deliverable `advisory_bom_hint`.

### `user_authored_reusable_component`

A user-owned reusable definition with provenance, revision, feature history,
interfaces, and privacy controls. It may be editable through new revisions.

Project-specific validation never transfers automatically to a new placement.

### `fixture_family_template`

A starting structure with parameters, strategies, unsupported conditions,
validation requirements, and human questions.

It is not completed geometry, a validated fixture, or release evidence.

### `shop_standard`

An attributed organization, shop, machine/process, project, or engineer input
that participates through deterministic precedence.

It is not a universal rule and does not override deterministic safety or
validation boundaries.

### `process_context_asset`

An asset representing the environment needed for a process question. The asset
also declares an underlying geometry authority: exact private, exact
supplier-authorized, provisional, or metadata-only.

Its validation value cannot exceed that underlying geometry authority.

### `private_benchmark_reference`

A private annotation and disposition record that may link to private local
assets. It supports evaluation and human-acceptance research.

It cannot be published, used as universal policy, or treated as production
approval. Public release fails closed unless the structured rights contract
permits the exact metadata fields and asset identities being released.

### `public_engineering_knowledge`

Public principles, patterns, applications, failures, and abstract dispositions
with source provenance and original FXD wording.

It may support deterministic retrieval and AI recommendation, but not geometry
truth, supplier claims, standards compliance, validation passes, or release.

## Authoritative machine contract

`scripts/validate_fixture_library_research.py` contains the single
`AUTHORITY_RULES` table used by semantic validation. JSON Schema mirrors the
locally expressible constraints, but does not define a competing authority
table.

| Authority | Source evidence | Geometry, frames, interfaces, material, and states | BOM and fixture output | Separate equipment |
|---|---|---|---|---|
| `fxd_parametric_component` | no imported source file; traced parametric definition | exact generated definition, owned frame, material intent, and typed interfaces permitted | manufactured participation requires deterministic validation and human release | prohibited |
| `exact_private_imported_cad` | private authorized identity, SHA-256, usage evidence, storage, units, and revision | exact imported geometry and owned frame; no competing parametric definition | owner policy, validation, and human release govern BOM/output | may source a separately authorized equipment record |
| `supplier_authorized_exact_cad` | supplier, model, supplier-authorized source, SHA-256, license evidence, storage, units, and revision | exact imported geometry and owned frame; no competing parametric definition | supplier terms, validation, and human release govern BOM/output | may source a separately authorized equipment record |
| `metadata_only_commercial_component` | metadata only; source-file geometry prohibited | all geometry-bearing fields prohibited | deliverable BOM and manufacturing output excluded; advisory hint only | prohibited |
| `provisional_review_envelope` | source-file geometry prohibited | visibly provisional representation only; exact features and manufacturing interfaces prohibited | deliverable BOM and manufacturing output excluded; advisory hint only | prohibited |
| `user_authored_reusable_component` | author and exactly one parametric or user-authored exact source form | owned frame and mounting interface required; revisioned function/material evidence permitted | validation and human release required | prohibited unless a separate context-delivery record exists |
| `fixture_family_template` | no source-file geometry | no geometry-bearing fields | BOM, STEP, DXF, drawings, and release excluded | prohibited |
| `shop_standard` | attributed standard provenance, not CAD | no geometry-bearing fields | deliverable BOM and manufacturing geometry excluded | prohibited |
| `process_context_asset` | dedicated context record names any governed geometry source | collision, envelope, and access authority derive from the source | fixture BOM, STEP, DXF, and release excluded | dedicated schema alone can authorize a separate manifest |
| `private_benchmark_reference` | opaque benchmark metadata only | public record carries no geometry-bearing fields | BOM and manufacturing output excluded | prohibited |
| `public_engineering_knowledge` | public source identity and original FXD paraphrase only | all geometry-bearing fields prohibited | BOM and manufacturing output excluded | prohibited |

Changing a label never carries geometry or output rights across rows. Any
authority transition creates a new immutable revision and revalidation.

## Privacy classifications

### `public`

Safe for public repository use after source, licensing, and disclosure review.

### `synthetic_public`

Invented data designed for public testing. It must not encode a real private
fixture, path, dimension set, screenshot, or supplier-controlled asset.

### `private_local`

User-controlled local content. It is excluded from public repositories and
provider payloads by default.

### `supplier_restricted`

Supplier-controlled content governed by source terms. The record must state
whether local use, embedding, preview generation, export, and redistribution
are permitted.

### `organization_confidential`

Employer or organization material subject to organization policy. It cannot be
published without explicit authorization.

## Storage-policy decisions

| Policy | Permitted use | Required behavior |
|---|---|---|
| `embedded` | portable project copy | record source, digest, privacy, and right to embed |
| `linked` | separately controlled asset | retain link identity and expected digest; block when missing |
| `metadata_only` | sourcing and unresolved engineering | never invent exact geometry |
| `not_applicable` | public knowledge or non-file record | no hidden file dependency |

## Editable authority

- `editable`: project-local supported edits are allowed.
- `read_only`: geometry and source evidence cannot be modified.
- `editable_new_revision_only`: edits create a new immutable library revision.
- `not_applicable`: the record has no editable geometry.

Exact imported CAD remains read-only evidence. A derived editable FXD component
is a new item with traceable provenance, not a mutation of the import.

## Public-source reuse policy

The public source register permits only:

- publisher;
- title;
- canonical URL;
- access date;
- source category;
- original FXD paraphrase;
- applicability;
- limitations;
- reuse classification; and
- licensing note.

The research package excludes images, catalogs, product tables, exact vendor
dimensions, supplier performance claims, CAD, copied articles, and substantial
source text.

ISO records are citation metadata only. No normative ISO content is reproduced
or implemented. Future standards-dependent behavior requires licensed access,
qualified review, and owner approval.

## Private-data flow

Private geometry and annotations stay local by default. A future provider
boundary must disclose exactly which structured fields leave the machine and
must exclude source CAD, paths, screenshots, exact private dimensions, and
proprietary rules unless separately authorized.

Deterministic retrieval over private records should run locally. Retrieval logs
must not expose private titles, paths, or geometry in public telemetry.

## Rights, consent, revocation, and retention

Every private benchmark records:

- rights holder or grantor and authorship identities;
- rights basis;
- permitted use, asset, and metadata-field scope;
- approval timestamp, audited release-decision timestamp and state, and
  optional expiry;
- revocation state, timestamp, and reason;
- deletion and backup disposition;
- export and public-release permission;
- audit-record identity and retention class;
- controlled-storage and access-control assumptions; and
- encryption expectation.

`public_release_permission` defaults conceptually to false: absence, unknown
rights, pending review, expiry, or revocation cannot be interpreted as consent.
A selected public release must be a field-by-field and asset-by-asset subset of
the recorded permission. Revocation blocks further export and release, records
the audit disposition, and drives deletion/backup handling in the future
private store. Public history may retain only already-authorized public
material and non-sensitive audit evidence as applicable law and policy allow.

Release validation is reproducible and does not read the machine clock. The
recorded decision timestamp must be at or after approval, strictly before an
expiry when present, and before any revocation. Only explicitly release-capable
rights bases can approve selected public release. Unknown, pending, denied,
incomplete, expired, or revoked rights fail closed.

The public validator recursively rejects likely Windows paths, Unix home or
private paths, UNC paths, `file://` references, CAD/native-model filenames,
image filenames, and obvious customer/employer asset-path strings in every
public research JSON value. Only `canonical_url` fields in validated public
source records receive the URL exemption. HTTPS strings in provenance, notes,
benchmarks, and other fields remain subject to CAD, archive, image,
customer/employer, private-network, private-storage, local, UNC, and `file://`
checks.
This scanning is defense in depth; a future private implementation still
requires separately controlled local storage, access control, encryption
policy, backup boundaries, export controls, and qualified rights review before
authorization.

## Authority transitions

Allowed transitions always create a new revision:

- metadata-only to provisional envelope;
- provisional envelope to exact private import;
- provisional envelope to supplier-authorized exact;
- private reusable component to selected public synthetic derivative, only
  after owner approval and independent disclosure review.

Forbidden transitions:

- preview appearance to exact authority;
- file extension to supplier authorization;
- human acceptance to production approval;
- private benchmark prevalence to universal rule;
- AI confidence to deterministic validation;
- source URL availability to redistribution permission.

## Deprecation and withdrawal

Deprecation discourages new selection but does not rewrite projects.
Withdrawal blocks new selection and may block continued use if the reason is a
license, safety, or data-integrity issue. Existing projects retain the pinned
identity and show the new status visibly.

## Publication checklist

Before any public commit or selected public release:

1. confirm item and representation privacy;
2. confirm source and licensing notes;
3. scan for CAD, images, binary assets, local paths, private dimensions, and
   proprietary identifiers;
4. ensure every paraphrase is original FXD wording;
5. verify no standards text or supplier claim is copied;
6. confirm owner approval for any selected private derivative;
7. confirm no production, certification, or safety claim is created.
