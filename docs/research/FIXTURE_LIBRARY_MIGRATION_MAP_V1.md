# FXD Fixture Library Migration Map v1

## Status and protected boundary

This document describes a possible future mapping from PR #54's
`fxd-fixture-knowledge-v1` to the extended fixture-library architecture.

It does not modify PR #54, its branch, its runtime code, its knowledge files,
its deterministic retrieval, Milestone 32, or the milestone registry. It does
not authorize migration.

## Current PR #54 model inspected

The read-only inspection used the exact PR #54 head
`6b28a972b61983b11ee7ccd077036e9a6a0a88a0`.

Current public schemas:

- `fxd-fixture-knowledge-v1`;
- `fxd-fixture-knowledge-sources-v1`.

Current record types:

- `engineering_principle`;
- `fixture_pattern`;
- `component_application`;
- `human_acceptance`;
- `human_rejection`.

Current seed counts:

- 8 engineering principles;
- 6 fixture patterns;
- 6 component applications;
- 1 abstract human acceptance;
- 1 abstract human rejection.

Current source fields:

- identity;
- publisher;
- title;
- URL;
- source type;
- reuse classification;
- licensing note;
- accessed date.

Current knowledge fields include applicability and strategy dimensions for
fixture family, assembly and material form, process, production volume,
handling, build orientation, construction, component family, datum, constrained
and floating degrees of freedom, support, locate, stop, foolproofing, clamp,
reaction, base, station repetition, weld access, loading and unloading,
distortion/heat/spatter, cleaning, maintenance, changeover, failure modes,
selection criteria, assumptions, confidence, sources, related records, human
disposition, downstream dependencies, and station count.

## Current deterministic retrieval

PR #54 ranks precedent locally with fixed integer weights:

| Query field | Current weight |
|---|---:|
| fixture family | 12 |
| assembly form | 5 |
| material form | 5 |
| process | 8 |
| production volume | 3 |
| handling mode | 5 |
| build orientation | 3 |
| construction method | 5 |
| station-count range | 6 |

It records positive and negative score components, matches, conflicts,
assumptions, failure modes, sources, non-applicable records, and unresolved
questions. Results sort by descending score and stable identity. Human
rejections are constraint-only and cannot become positive design strategies.

There are no embeddings, vector database, runtime source visits, or provider
dependency in this model.

## Record-type mapping

| PR #54 record | Extended category | Extended authority | Migration behavior |
|---|---|---|---|
| `engineering_principle` | `public_engineering_knowledge` | `public_engineering_knowledge` | preserve identity, title, summary, applicability, limitations, sources, and strategy fields |
| `fixture_pattern` | `public_engineering_knowledge` | `public_engineering_knowledge` | preserve identity and strategy fields; optionally link future family templates without converting the pattern into a template |
| `component_application` | `public_engineering_knowledge` | `public_engineering_knowledge` | preserve as an application pattern; do not convert it automatically into exact or parametric library geometry |
| `human_acceptance` | `public_engineering_knowledge` | `public_engineering_knowledge` | preserve abstract disposition and source; do not turn acceptance into validation or release |
| `human_rejection` | `public_engineering_knowledge` | `public_engineering_knowledge` | preserve as constraint-only precedent and link to failure-mode records where appropriate |

## Source mapping

| PR #54 source field | Extended source field |
|---|---|
| `identity` | `source_id` |
| `publisher` | `publisher` |
| `title` | `title` |
| `url` | `canonical_url` when public |
| `accessed` | `date_accessed` |
| `source_type` | `source_category` |
| `reuse_classification` | `reuse_classification` |
| `licensing_note` | `licensing_note` |
| implicit record summary | explicit `original_fxd_paraphrase` |
| implicit record applicability | explicit source `applicability` |
| not present | explicit source `limitations` |

Human-review sources with no public URL remain valid provenance in a future
private or controlled source schema. The public source schema in this research
package intentionally requires HTTPS because its corpus contains official
public web sources only.

## Field mapping

Current applicability and strategy fields can move under a future
`engineering_details` object without loss. A migration should preserve the
original v1 record payload or digest so retrieval and audit can reproduce the
old result.

Suggested mapping:

- current record identity -> extended item identity;
- current schema version -> migration provenance;
- current record type -> extended `record_type`;
- current title and summary -> same semantic fields;
- fixture/product/process applicability -> `applicability` plus structured
  engineering details;
- failure modes -> linked failure-mode identities and original strings;
- source IDs -> extended source IDs;
- related record IDs -> downstream or knowledge relationships;
- human disposition -> explicit disposition metadata;
- station-count range -> structured applicability;
- current evidence digest -> migration source digest.

## Retrieval compatibility

A future extended system should not change M32 retrieval implicitly. Safe
options are:

1. retain the v1 loader and retrieval unchanged for v1 projects;
2. migrate records to the extended store but run a compatibility retrieval
   profile with the exact current weights and stable tie-breaking;
3. compare old and new results before allowing a project migration.

Any new weighting, taxonomy expansion, filter, interface match, or source
confidence rule is a new retrieval profile. It must not reuse the old profile
identity.

Human rejection remains constraint-only in every compatibility profile.

## Public engineering knowledge mapping

The current public layer maps cleanly to the extended
`public_engineering_knowledge` authority. It does not map to:

- exact geometry;
- parametric component authority;
- shop-standard authority;
- private benchmark authority;
- supplier authorization;
- fixture-family template authority.

Those authorities require new records and evidence.

## Fixture pattern mapping

Current fixture patterns remain abstract precedent. A future fixture-family
template may cite them, but the template must independently define:

- supported conditions;
- parameters;
- required validations;
- unsupported conditions;
- human-review questions; and
- starting-structure boundary.

No current pattern becomes completed fixture geometry.

## Component application mapping

Current component applications describe when and why a role is useful. Future
parametric or commercial component items are separate records with:

- geometry or metadata authority;
- source file and digest where applicable;
- interfaces;
- states;
- variants;
- output participation;
- replacement rules.

An application record may cite those items, but cannot confer their authority.

## Human acceptance and rejection mapping

Current human acceptance and rejection are abstract public precedent. They may
map to:

- public knowledge disposition;
- failure-mode links;
- benchmark annotation criteria;
- retrieval constraints.

They do not map to:

- production approval;
- deterministic pass;
- private asset ownership;
- universal rule;
- supplier authorization.

## Gaps in `fxd-fixture-knowledge-v1`

The current schema intentionally lacks:

- library categories beyond public precedent;
- exact-one extended authority classification;
- file identity and SHA-256;
- privacy classification;
- linked versus embedded policy;
- editable versus read-only authority;
- local frames;
- preview authority;
- parametric feature definitions;
- mounting and functional interfaces;
- movement and open/closed states;
- keep-out and maintenance envelopes;
- material/manufacturing intent;
- BOM and output participation;
- validation participation matrix;
- variants;
- replacement compatibility;
- immutable revision history and deprecation;
- missing-link behavior;
- downstream project-instance dependencies;
- shop-standard precedence;
- private benchmark contract;
- process-context asset schema;
- template unsupported-condition and human-question contracts.

These are expected gaps, not defects in the M32 schema.

## Proposed future migration phases

### Phase 0: no change

Keep PR #54 runtime and data unchanged. Land research only after review.

### Phase 1: owner-approved schema proposal

Define production schemas and exact project integration under a future governed
milestone. Resolve scene ownership, stable topology, private storage, and
licensing first.

### Phase 2: read-only import adapter

Load v1 public knowledge into an extended read model while preserving original
payload and digest. No project mutation or write-back.

### Phase 3: compatibility retrieval proof

Prove old queries return the same selected identities, order, score components,
conflicts, rejection constraints, and unresolved questions.

### Phase 4: explicit project migration

Allow an engineer to create a new project revision that pins the extended
records. Never rewrite existing projects.

### Phase 5: expanded categories

Add parametric components, private tooling, templates, context, shop packs, and
benchmarks only after their own validation and privacy evidence exists.

## Migration acceptance evidence

A future migration should prove:

- all 22 current record identities and all source identities survive;
- current evidence digest remains reproducible or is linked to a documented
  migration digest;
- compatibility retrieval results are exact;
- human rejection is still constraint-only;
- no private record enters public data;
- no source text or supplier asset is added;
- v1 projects remain readable without silent rewrite;
- the extended runtime is not required for M32 acceptance;
- PR #54 history and branch remain untouched.
