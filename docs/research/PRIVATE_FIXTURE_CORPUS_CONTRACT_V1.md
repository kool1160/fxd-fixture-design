# FXD Private Fixture Corpus Contract v1

## Purpose

Chris's self-created practice fixtures may form a private engineering reference
and benchmark corpus. The corpus can support architecture research, generator
evaluation, fixture-CAD language design, failure analysis, and human acceptance
criteria.

It is not a public dataset, a universal template library, a training-rights
claim, production approval, or permission to publish the assets.

## Public/private split

The public repository may contain:

- `private_benchmark_case_v1.schema.json`;
- synthetic benchmark examples;
- the annotation contract;
- privacy and release procedures; and
- abstract, non-identifying findings explicitly approved for publication.

The public repository must never contain:

- private STEP, IGES, STL, or native CAD;
- screenshots or rendered images;
- local or network paths;
- private dimensions or tolerance sets;
- customer, employer, or supplier identifiers;
- proprietary shop rules or confidential standards;
- asset-derived fingerprints that reveal the design;
- copied design notes; or
- automatic training or production-safety claims.

## Private storage

Private assets live in a separately controlled local store. The public project
may know only opaque private asset identities when running locally. Those
identities are empty in public synthetic examples.

The private store should provide:

- owner and authorship;
- asset identity and immutable revision;
- source SHA-256;
- units;
- privacy classification;
- local storage policy;
- linked benchmark identities;
- access and audit history;
- selected-release disposition.

This contract does not select a database, cloud service, or file layout.

## Case annotation

Every benchmark case supports:

- fixture class;
- product and material forms;
- manufacturing process;
- production quantity and confidence;
- source-part construction;
- build orientation;
- datum hierarchy;
- constrained and intentionally floating degrees of freedom;
- supports;
- locators;
- stops;
- clamps;
- force-reaction mappings;
- base and structural strategy;
- loading sequence;
- clamping sequence;
- tack, weld, assembly, machining, or inspection sequence;
- unloading sequence;
- weld, tool, operator, robot, and inspection access;
- process-context assets;
- manufacturability;
- wear and replaceable components;
- successful principles;
- compromises;
- failure modes;
- improvements FXD should propose;
- human acceptance criteria;
- human disposition;
- authorship;
- provenance;
- privacy;
- selected public-release permission; and
- linked private asset identities.

Annotations describe evidence and judgment. They must distinguish observation,
interpretation, preference, rule candidate, and unresolved question.

## Curation workflow

1. Verify that Chris owns or is authorized to use the asset.
2. Assign a private opaque asset identity and digest.
3. Classify fixture family, process, and intended benchmark coverage.
4. Create the structured case annotation without copying sensitive notes into
   public storage.
5. Record engineering strengths, compromises, failures, and proposed FXD
   improvements separately.
6. Obtain a human disposition.
7. Run privacy and proprietary-knowledge review.
8. Keep the asset private unless one case is explicitly selected for release.

## Coverage strategy

A curated private set should span:

- weld fixtures;
- tack and location fixtures;
- assembly fixtures;
- gauges and profile checks;
- inspection tooling;
- nests;
- rework fixtures;
- machining and workholding;
- laser-cut and tab-and-slot construction;
- tube and frame construction;
- commercial clamps and private tooling;
- loading and unloading constraints;
- process-context examples;
- accepted, compromised, and rejected concepts.

Coverage is more valuable than volume. Hundreds of similar examples must not
outvote a missing process or failure class.

## Benchmark use

Allowed private uses:

- compare generated strategy to annotated experienced-engineer work;
- test whether FXD finds known failure modes;
- evaluate loading, access, role separation, serviceability, and output
  coherence;
- identify missing template parameters;
- measure agreement with stated human criteria;
- challenge deterministic and AI recommendation boundaries.

Prohibited uses:

- claim production safety or certification;
- infer a universal rule from frequency alone;
- publish the corpus;
- send private geometry or annotations to a provider without explicit approval;
- train or fine-tune a model without a separate rights, privacy, and governance
  decision;
- use appearance similarity as the only quality measure.

## Human disposition

Supported dispositions:

- accepted reference;
- accepted with conditions;
- rejected reference;
- not yet reviewed; and
- synthetic example only.

Acceptance means the example is useful benchmark evidence under its recorded
conditions. It is not a declaration that the fixture was safe, certified,
released, or appropriate for another product.

## Selected public release

Selected release is a protected action. Before release:

1. Chris explicitly selects the asset and scope;
2. authorship and third-party rights are verified;
3. customer, employer, supplier, and shop-confidential information is removed;
4. patent-sensitive content is reviewed;
5. geometry, images, dimensions, notes, and metadata are reviewed separately;
6. a synthetic or redacted derivative is preferred where it answers the
   research question;
7. exact release files and license are approved explicitly.

The boolean in the schema records permission status; it does not grant
permission by itself.

## Evaluation controls

Benchmark comparisons should report:

- case and generator revision;
- input and context completeness;
- deterministic passes and blockers;
- generated-to-reference similarities and differences;
- specialist disagreements;
- human acceptance questions;
- unresolved risks;
- whether private assets remained local.

One scalar similarity score is insufficient. A generated fixture may look
similar while failing access, restraint, manufacture, or release.

## Retention and deletion

Retention policy belongs to the private store owner. Removing a private asset
must leave public history untouched and mark private benchmark links missing.
The public schema and synthetic examples remain usable without any private
asset.

## Synthetic examples

The four public examples are invented:

- flat-base weld fixture;
- profile-check fixture;
- machining workholding setup; and
- combined build-and-check tooling.

They validate the contract and illustrate annotation quality. They do not
encode a real fixture or recommended dimensions.
