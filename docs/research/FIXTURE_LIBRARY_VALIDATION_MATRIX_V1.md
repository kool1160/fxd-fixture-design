# FXD Fixture Library Validation Participation Matrix v1

## Status

Research matrix only. It defines deterministic semantics for future planning
and does not implement or authorize production release.

## Participation values

- `required`: evidence from this record is mandatory for the operation when the
  record is in scope.
- `permitted`: the record may participate when available and applicable.
- `provisional only`: the record may support conservative review, but cannot
  supply an exact pass.
- `excluded`: the record must not participate.
- `blocks when missing`: the operation cannot complete when required evidence
  or representation is unavailable.
- `human confirmation required`: software evidence is insufficient; a qualified
  person must confirm the stated scope.

`human confirmation required` never means that human preference can override a
deterministic blocker.

## Authority matrix: review, recommendation, and deterministic authority

| Authority | Visual review | AI recommendation | Deterministic validation | Manufacturing release |
|---|---|---|---|---|
| `fxd_parametric_component` | permitted after representation generation | permitted with item and revision citation | required for every declared participating pack | human confirmation required |
| `exact_private_imported_cad` | permitted with private/source label | permitted only within privacy policy | required for selected geometry packs | human confirmation required |
| `supplier_authorized_exact_cad` | permitted subject to supplier terms | permitted with supplier, model, revision, and license boundary | required for selected geometry packs | human confirmation required |
| `metadata_only_commercial_component` | permitted as a metadata card; no exact shape | permitted as an unresolved candidate | excluded from geometry validation; permitted for metadata completeness | blocks when missing if exact selection is required |
| `provisional_review_envelope` | permitted only with persistent provisional label | permitted only as a provisional candidate | provisional only | excluded |
| `user_authored_reusable_component` | permitted with author and revision | permitted with project-specific revalidation warning | required when placed | human confirmation required |
| `fixture_family_template` | permitted as a starting structure | permitted as bounded starting precedent | excluded until instantiated into project evidence | excluded |
| `shop_standard` | permitted as attributed decision context | permitted as a scoped preference | permitted only as deterministic input provenance | human confirmation required |
| `process_context_asset` | required when selected by the process pack | permitted with underlying geometry-authority label | required when selected, limited by underlying authority | human confirmation required |
| `private_benchmark_reference` | permitted only in controlled private review | permitted only in private evaluation under policy | excluded from project validation truth | excluded |
| `public_engineering_knowledge` | permitted as rationale | permitted as cited advisory precedent | excluded from geometry truth; permitted as rule-selection provenance | excluded |

## Authority matrix: geometry and access

| Authority | Broad-phase collision | Exact collision | Clearance | Loading/unloading | Weld/tool access | Operator access | Maintenance access |
|---|---|---|---|---|---|---|---|
| `fxd_parametric_component` | required | required after successful generation | required | permitted | permitted | permitted | permitted |
| `exact_private_imported_cad` | required | required | required | permitted | permitted | permitted | permitted |
| `supplier_authorized_exact_cad` | required | required | required | permitted | permitted | permitted | permitted |
| `metadata_only_commercial_component` | excluded | excluded | excluded | excluded | excluded | excluded | excluded |
| `provisional_review_envelope` | provisional only | excluded | provisional only | provisional only | provisional only | provisional only | provisional only |
| `user_authored_reusable_component` | required when placed | required when exact geometry is current | required when placed | permitted | permitted | permitted | required when service is relevant |
| `fixture_family_template` | excluded | excluded | excluded | human confirmation required | human confirmation required | human confirmation required | human confirmation required |
| `shop_standard` | excluded | excluded | permitted as an input, never as geometry | permitted as an input | permitted as an input | permitted as an input | permitted as an input |
| `process_context_asset` | required when selected by a validation pack | blocks when missing if the pack requires exact geometry | blocks when missing if the pack requires exact geometry | required when selected | required when selected | required when selected | required when selected |
| `private_benchmark_reference` | excluded | excluded | excluded | permitted as evaluation criteria | permitted as evaluation criteria | permitted as evaluation criteria | permitted as evaluation criteria |
| `public_engineering_knowledge` | excluded | excluded | excluded | permitted as advisory precedent | permitted as advisory precedent | permitted as advisory precedent | permitted as advisory precedent |

## Authority matrix: outputs and release

| Authority | BOM | STEP | DXF | Drawings | Review reports | Production release |
|---|---|---|---|---|---|---|
| `fxd_parametric_component` | required when manufactured or purchased | permitted after exact generation and validation | permitted when a supported 2D definition exists | permitted | required | human confirmation required |
| `exact_private_imported_cad` | permitted | permitted only by owner policy | excluded unless an authorized 2D definition exists | permitted as reference | required | human confirmation required |
| `supplier_authorized_exact_cad` | required when selected | permitted only when supplier terms allow | excluded | permitted subject to terms | required | human confirmation required |
| `metadata_only_commercial_component` | permitted as unresolved supplier line | excluded | excluded | permitted as metadata callout | required with missing-geometry warning | blocks when missing if exact selection is required |
| `provisional_review_envelope` | permitted only as unresolved generic line | excluded | excluded | permitted only as visibly provisional review geometry | required with provisional label | excluded |
| `user_authored_reusable_component` | required when placed | permitted after project validation | permitted for supported manufactured profiles | permitted | required | human confirmation required |
| `fixture_family_template` | excluded | excluded | excluded | excluded | permitted as planning context | excluded |
| `shop_standard` | permitted as provenance | excluded | excluded | permitted as attributed notes | required when it affects a decision | human confirmation required |
| `process_context_asset` | permitted when it is part of delivered equipment | permitted only if authority and license allow | excluded | permitted as reference | required when selected | human confirmation required |
| `private_benchmark_reference` | excluded | excluded | excluded | excluded | excluded from public reports; permitted in controlled private evaluation | excluded |
| `public_engineering_knowledge` | excluded | excluded | excluded | permitted as attributed rationale | permitted | excluded |

## Category matrix: geometry and access

Category rules are minimum behavior. If an item's authority is weaker, the
weaker authority controls.

| Category | Visual review | AI recommendation | Deterministic validation | Manufacturing release |
|---|---|---|---|---|
| FXD standard parametric primitives | permitted after generation | permitted with feature and rule citation | required when used | human confirmation required |
| Shop-standard packs | permitted as visible configuration | permitted as scoped preference | permitted only as attributed input | human confirmation required |
| Private purchased tooling | permitted at the item's geometry authority | permitted with sourcing and authority limits | required when selected; exact-required packs block on weak authority | human confirmation required |
| User-created reusable components | permitted with author and revision | permitted with project-specific warning | required when placed | human confirmation required |
| Fixture-family templates | permitted as planning structure | permitted as bounded starting point | excluded until instantiated | excluded |
| Process-context assets | required when selected | permitted with authority and state limits | required when selected | human confirmation required |
| Private benchmark references | controlled private review only | controlled private evaluation only | excluded from project truth | excluded |
| Public engineering knowledge | permitted as rationale | permitted as cited precedent | excluded from geometry truth | excluded |

| Category | Broad-phase collision | Exact collision | Clearance | Loading/unloading | Weld/tool access | Operator access | Maintenance access |
|---|---|---|---|---|---|---|---|
| FXD standard parametric primitives | required when placed | required after generation | required | permitted | permitted | permitted | required for wear or removable items |
| Shop-standard packs | excluded | excluded | permitted as a parameter source | permitted as a preference source | permitted as a preference source | permitted as a preference source | permitted as a preference source |
| Private purchased tooling | required when geometry exists | blocks when missing if exact tooling is required | blocks when missing if exact tooling is required | required when motion affects handling | required when tooling affects process access | required when tooling affects the operator | required when service affects layout |
| User-created reusable components | required when placed | required when exact geometry is current | required | required when the component affects flow | required when the component affects process | required when the component affects handling | required |
| Fixture-family templates | excluded | excluded | excluded | human confirmation required | human confirmation required | human confirmation required | human confirmation required |
| Process-context assets | required when selected by the process pack | blocks when missing if exact context is required | blocks when missing if exact context is required | required when selected | required when selected | required when selected | required when selected |
| Private benchmark references | excluded | excluded | excluded | permitted as evaluation criteria | permitted as evaluation criteria | permitted as evaluation criteria | permitted as evaluation criteria |
| Public engineering knowledge | excluded | excluded | excluded | permitted as advisory precedent | permitted as advisory precedent | permitted as advisory precedent | permitted as advisory precedent |

## Category matrix: outputs and release

| Category | BOM | STEP | DXF | Drawings | Review reports | Production release |
|---|---|---|---|---|---|---|
| FXD standard parametric primitives | required when used | permitted after exact validation | permitted when manufactured as 2D stock | permitted | required | human confirmation required |
| Shop-standard packs | permitted as attributed decision provenance | excluded | excluded | permitted as attributed notes | required when applied | human confirmation required |
| Private purchased tooling | required when selected; unresolved if metadata-only | permitted only for authorized exact geometry | excluded | permitted subject to source terms | required | human confirmation required |
| User-created reusable components | required when used | permitted after validation | permitted for supported manufactured profiles | permitted | required | human confirmation required |
| Fixture-family templates | excluded | excluded | excluded | excluded | permitted as planning context | excluded |
| Process-context assets | permitted when delivered with the project equipment | permitted only when authority and license allow | excluded | permitted as reference | required when selected | human confirmation required |
| Private benchmark references | excluded | excluded | excluded | excluded | excluded from public reports; permitted in controlled private reports | excluded |
| Public engineering knowledge | excluded | excluded | excluded | permitted as rationale only | permitted | excluded |

## Exactness rules

1. Exact collision requires current exact geometry for every in-scope item.
2. A provisional envelope may produce a conflict finding, but never an exact
   clearance pass.
3. Metadata-only items are absent geometry, not zero-volume geometry.
4. A process-context asset inherits the limits of its underlying geometry
   authority.
5. Missing linked exact geometry blocks exact operations and cannot fall back
   silently to a preview.
6. A changed digest or revision makes prior exact evidence stale.

## Loading and unloading rules

The selected process pack defines required states. At minimum, a relevant
fixture or tooling item declares:

- loading state;
- locating state;
- open and closed clamp states;
- process state;
- release state;
- finished-product unload state; and
- maintenance state where service affects layout.

Missing required states produce `blocks when missing` or `provisional only`, not
a pass.

## Weld and tool access rules

Access evidence cites:

- tool or torch authority;
- reference point and approach direction;
- body and swept envelopes;
- fixture and product state;
- relevant process regions;
- missing cable, dress, hand, visibility, or safety context.

Geometric access does not approve a weld procedure, robot path, machine
operation, ergonomic condition, guarding, or safety.

## BOM rules

- exact selected purchased tooling uses exact supplier/model/revision metadata;
- metadata-only tooling uses an unresolved line and blocks when exact selection
  is required;
- provisional envelopes never create an exact supplier part;
- manufactured FXD components reconcile geometry, revision, material, and
  quantity;
- private benchmark and public knowledge records never enter BOM.

## STEP and DXF rules

STEP includes only validated FXD-authored geometry and exact imported geometry
whose policy permits export. DXF includes only supported manufactured profiles
with current feature definitions.

Reference, provisional, metadata-only, template, standard, and benchmark
records are excluded from manufacturing geometry exports.

## Drawings and reports

Drawings may show reference context only with explicit representation and
authority labels. Review reports list:

- item and revision;
- authority;
- missing links;
- provisional states;
- validation participation;
- output inclusion or exclusion;
- stale evidence;
- human confirmations required.

## Production-release boundary

No authority level or category independently grants production release.
Deterministic validation, output coherence, source and license compliance, and
qualified human review are cumulative. `human confirmation required` is the
strongest permitted value for production release in this research matrix.
