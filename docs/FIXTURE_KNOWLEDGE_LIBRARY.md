# FXD public fixture knowledge library

## Purpose and authority

`fxd-fixture-knowledge-v1` is a small, public, CAD-neutral precedent library.
It helps the supported M32 fixture family retrieve explainable strategies
without network access. It is evidence and design precedent, not production
approval, a certified rule pack, a replacement CAD kernel, or permission to
copy supplier geometry.

This library is separate from the ignored private correction store described
in `docs/KNOWLEDGE_CONTRACT.md`. Public records contain only official-source
metadata, original FXD paraphrases, abstract patterns, and abstract human
dispositions. Private shop practices and project corrections never enter it.

## Record contract

Each record has a stable identity, schema version, legal record type,
applicability fields, engineering strategy fields, failure modes, selection
criteria, assumptions, confidence, source identities, related records, human
disposition, downstream dependencies, and an optional station-count range.
Supported record types are:

- `engineering_principle`
- `fixture_pattern`
- `component_application`
- `human_acceptance`
- `human_rejection`

The contract can represent fixture and product family, assembly and material
form, process, production volume, handling mode, build orientation,
construction, component families, datum hierarchy, constrained and floating
degrees of freedom, support, locate, stop, foolproof, clamp, reaction, base,
station repetition, weld access, load/unload, heat/spatter, cleaning,
maintenance, changeover, and downstream evidence.

Validation rejects unknown schemas, record types, source identities, related
record identities, duplicate or unstable identities, malformed station ranges,
and missing provenance.

## Seed corpus

The initial corpus contains:

- 8 engineering principles;
- 6 fixture patterns;
- 6 component applications;
- 1 abstract accepted M32 repair direction;
- 1 abstract rejected M32 pattern.

The accepted direction is compact, continuously mounted, product-bound,
role-explicit, clamp-to-support mapped, loadable, weld-reviewable, and
shop-buildable. The rejected pattern records only abstract failure features:
isolated generic stations, excessive empty rail, generic blocks, weak contact
and reaction evidence, unclear handling rhythm, and weak structural intent.
No review image, private dimension, or user fixture geometry is retained.

## Deterministic retrieval

`retrieve_precedent` applies fixed integer weights to fixture family, assembly
form, material form, process, volume, handling mode, build orientation,
construction method, and station count. It reports every positive or negative
score component, matching field, conflict, assumption, failure mode, source
identity, non-applicable record, and unresolved question. Results are ordered
by descending score and then stable record identity.

Human-rejection records are returned only as constraints. They can never be
selected as a positive design strategy. There are no embeddings, vector
database, runtime URLs, provider dependency, or new package dependency.

## Engineering boundary

Retrieved precedent may inform deterministic synthesis or a compact
provider-neutral proposal. It may not silently become final geometry, invent a
vendor claim, authorize purchased tooling geometry, override a blocker, approve
weld process or structure, or release a fixture. Qualified human engineering
review remains mandatory.
