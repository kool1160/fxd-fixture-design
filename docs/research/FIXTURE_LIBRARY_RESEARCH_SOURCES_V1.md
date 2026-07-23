# FXD Fixture Library Research Sources v1

## Method and reuse boundary

Research was limited to official publisher, regulator, project, product, schema,
and standards pages accessed on 2026-07-23. The repository stores only
publisher, title, canonical URL, access date, category, original FXD
paraphrase, applicability, limitations, reuse classification, and licensing
note.

No site was scraped. No catalog, CAD, image, product table, exact vendor
dimension, performance claim, copied article, or substantial source text was
downloaded or committed.

The machine-readable source records are in
`data/research/fixture_library_reference_v1/fixture_library_reference_v1.json`.

## Official engineering and product sources

### Carr Lane Manufacturing

- Title: [Workpiece Fixture Design Principles](https://www.carrlane.com/engineering-resources/fixture-design-principles)
- Category: official manufacturer engineering page
- Original FXD paraphrase: deliberate locating and clamping roles, avoidance of
  redundant location, and verifiable loading are useful fixture-design
  concerns.
- Applicability: datum, locating, clamping, foolproofing, and loading records.
- Limitations: not a universal shop rule or project-specific approval.
- Reuse: `metadata_and_original_fxd_paraphrase`.
- Licensing: no handbook, page text, figures, tables, calculations, or product
  data copied.

### DEMMELER

- Title: [3D welding tables](https://www.demmeler.com/products-shop/original-3d-clamping-systems/3d-welding-tables/)
- Category: official product documentation
- Original FXD paraphrase: table and grid choices should be explicit mounting
  interfaces rather than assumed universal standards.
- Applicability: table-grid and modular mounting taxonomy.
- Limitations: no dimensions, capacities, hole patterns, images, or CAD.
- Reuse: `metadata_and_original_fxd_paraphrase`.
- Licensing: metadata and original FXD interpretation only.

### DESTACO

- Title: [Welding applications](https://www.destaco.com/en/applications/welding)
- Category: official product documentation
- Original FXD paraphrase: commercial clamp use requires explicit motion,
  contact, mounting, and access interfaces; exactness requires authorized CAD.
- Applicability: commercial clamps and provisional states.
- Limitations: no force, cycle, performance, geometry, or suitability claim.
- Reuse: `metadata_and_original_fxd_paraphrase`.
- Licensing: no catalog, image, specification, or CAD copied.

### Fixtureworks

- Title: [Standard fixturing components](https://www.fixtureworks.com/store/pc/standard-fixturing-components-v69.htm)
- Category: official product documentation
- Original FXD paraphrase: supports, locators, stops, and workholding elements
  benefit from separate functional and service roles.
- Applicability: component taxonomy and replaceability.
- Limitations: no exact products, dimensions, materials, claims, or CAD.
- Reuse: `metadata_and_original_fxd_paraphrase`.
- Licensing: category metadata and original FXD interpretation only.

### Jergens

- Title: [Fixturing components](https://www.jergensinc.com/en/categories/fixturing-components)
- Category: official product documentation
- Original FXD paraphrase: mounting, locating, support, and replacement duties
  should remain independently represented.
- Applicability: typed interfaces and replacement compatibility.
- Limitations: no product selection or specification imported.
- Reuse: `metadata_and_original_fxd_paraphrase`.
- Licensing: metadata and original FXD paraphrase only.

### Strong Hand Tools

- Title: [MAX table overview](https://www.stronghandtools.com/pages/max-table-overview)
- Category: official product documentation
- Original FXD paraphrase: a modular base is a project context and interface
  choice whose provenance should remain visible.
- Applicability: mounting and reusable placement concepts.
- Limitations: no dimensions, capacities, photos, claims, or CAD.
- Reuse: `metadata_and_original_fxd_paraphrase`.
- Licensing: product-family metadata and original FXD interpretation only.

## Official regulatory guidance

### OSHA welding

- Title: [Welding, Cutting, and Brazing - Overview](https://www.osha.gov/welding-cutting-brazing)
- Category: official regulatory guidance
- Original FXD paraphrase: geometric torch access covers only one part of
  welding context and cannot be represented as procedure or safety approval.
- Applicability: boundary for welding access records.
- Limitations: no legal conclusion or copied regulatory text.
- Reuse: `regulatory_metadata_and_original_fxd_paraphrase`.
- Licensing: metadata and original FXD wording; current authority remains with
  OSHA and qualified reviewers.

### OSHA machine guarding

- Title: [Machine Guarding - Overview](https://www.osha.gov/machine-guarding/)
- Category: official regulatory guidance
- Original FXD paraphrase: guarding and hazardous motion remain separate safety
  responsibilities even when FXD can show geometric conflicts.
- Applicability: guarding, keep-out, service, and operator context.
- Limitations: no machine-specific safeguard or compliance design.
- Reuse: `regulatory_metadata_and_original_fxd_paraphrase`.
- Licensing: metadata and original FXD paraphrase only.

### OSHA robotics

- Title: [Robotics - Overview](https://www.osha.gov/robotics)
- Category: official regulatory guidance
- Original FXD paraphrase: setup and maintenance states matter in addition to a
  nominal process pose.
- Applicability: movement-state and maintenance-envelope architecture.
- Limitations: no robot programming, safety assessment, or certification.
- Reuse: `regulatory_metadata_and_original_fxd_paraphrase`.
- Licensing: metadata and original FXD paraphrase only.

## Official Open CASCADE documentation

### OCAF application framework

- Title: [Application Framework](https://dev.opencascade.org/about/application_framework)
- Category: official open-source project documentation
- Original FXD paraphrase: a document-oriented data model can manage
  dependencies, recomputation, and undo without making transient shapes the
  sole identity.
- Applicability: future persistence and stable semantic identity evaluation.
- Limitations: no OCAF selection or topology guarantee is authorized.
- Reuse: `open_source_documentation_metadata_and_original_fxd_paraphrase`.
- Licensing: documentation metadata and original FXD paraphrase only; future
  adoption requires separate license review.

### XDE

- Title: [Extended Data Exchange user guide](https://dev.opencascade.org/doc/overview/html/occt_user_guides__xde.html)
- Category: official open-source project documentation
- Original FXD paraphrase: shapes, assemblies, and attached properties can be
  organized in a shared document structure.
- Applicability: multi-asset provenance and assembly identity evaluation.
- Limitations: no runtime adoption or migration is authorized.
- Reuse: `open_source_documentation_metadata_and_original_fxd_paraphrase`.
- Licensing: documentation metadata and original FXD paraphrase only.

## Official schema specification

### JSON Schema

- Title: [Draft 2020-12](https://json-schema.org/draft/2020-12)
- Category: official schema specification
- Original FXD paraphrase: the dialect provides a versioned vocabulary for
  structural constraints and reusable definitions.
- Applicability: dialect for the eight research schemas.
- Limitations: schema conformance does not prove engineering validity.
- Reuse: `specification_metadata_and_schema_uri`.
- Licensing: public schema URI and metadata only; specification text is not
  copied.

## Official interaction reference

### RoboDK

- Title: [Reference Frame](https://robodk.com/doc/en/Interface-Reference-Frame.html)
- Category: official product documentation
- Original FXD paraphrase: visible reference-frame hierarchy is a useful
  interaction analogy for dependent process-context objects.
- Applicability: product-direction interaction reference under Issues #61/#62.
- Limitations: RoboDK is not a dependency, implementation source, robot
  programming target, or product to copy.
- Reuse: `interaction_reference_only`.
- Licensing: documentation metadata and high-level original observation only;
  no UI, images, code, or workflow text copied.

## Standards metadata watch items

These records contain citation metadata only. No normative text, rules, symbols,
examples, or requirements are reproduced or implemented.

### ISO 5459:2024

- Title: [Datums and datum systems](https://www.iso.org/standard/87855.html)
- Applicability: future licensed datum terminology and requirements review.
- Limitation: not an implemented rule source.
- Reuse: `standards_metadata_only_no_normative_text`.
- Licensing: copyrighted ISO content remains excluded.

### ISO 1101:2017

- Title: [Geometrical tolerancing](https://www.iso.org/standard/66777.html)
- Applicability: future licensed inspection and geometrical specification
  review.
- Limitation: not an implemented inspection requirement.
- Reuse: `standards_metadata_only_no_normative_text`.
- Licensing: copyrighted ISO content remains excluded.

### ISO 10218-2:2025

- Title: [Industrial robot applications and robot cells](https://www.iso.org/standard/73934.html)
- Applicability: future licensed robot-context and safety-boundary review.
- Limitation: not an implemented robot safety rule.
- Reuse: `standards_metadata_only_no_normative_text`.
- Licensing: copyrighted ISO content remains excluded.

## Source conclusions

The sources support architecture-level distinctions:

- locating, support, stop, and clamp roles should be explicit;
- purchased tooling needs separate metadata, envelope, and exact authorities;
- modular bases require typed mounting interfaces;
- process context needs state and safety boundaries;
- persistent CAD data benefits from semantic identity above transient shape;
- schemas can validate structure but not engineering truth;
- interaction references are analogies, not implementation licenses;
- standards require separately licensed and qualified future review.

They do not supply exact vendor data, universal dimensions, proprietary
heuristics, certified rules, or production approval.
