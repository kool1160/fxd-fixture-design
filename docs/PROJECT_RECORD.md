# FXD Project Record

## 2026-07-13 — Project founded

FXD was defined as intelligent industrial fixture-design software, beginning with weld fixtures for sheet-metal and fabricated products.

Key founding decisions:

- The product is not a contour-skeleton generator.
- It must understand components, locating, clamping, access, loading, welding, and removal.
- The core will be CAD-neutral and standalone.
- STEP will be the first interchange format.
- CAD connectors will remain optional adapters.
- AI will interpret, plan, rank, and explain; deterministic systems will own engineering geometry and validation.
- Initial concepts will target laser-cut and standard-component weld fixtures on flat bases.
- Multiple concepts should expose cost, loading-speed, and repeatability tradeoffs.
- The repository is publicly visible but no open-source license is granted.
- Proprietary fixture rules and invention-sensitive material must remain outside public source control.

The first technical milestone is a runnable geometry-stack evaluation, not a large UI or speculative full architecture.

## 2026-07-13 — Milestone 1 complete

Milestone 1 is complete. The repository now has a dependency-free synthetic
geometry proof covering placement, intersection, clearance, explicit
millimetre units, and deterministic neutral serialization. A stack spike
records OCCT as the likely STEP/B-rep candidate for evaluation behind a
CAD-neutral adapter, with CadQuery/build123d and trimesh assessed as
non-core alternatives. No kernel dependency was added before representative
STEP evidence and exact redistribution obligations can be reviewed.

Evidence: `python -m unittest discover -s tests -v`,
`python scripts/geometry_proof.py`, and `bash scripts/ci.sh` all pass.

## 2026-07-13 — Milestone 2 complete

Milestone 2 adds an immutable, CAD-neutral normalized product model and a
dependency-free reader for the documented synthetic STEP evidence contract.
The proof covers repeated components, nested translation transforms, explicit
millimetre units, body/face/edge summaries, source SHA-256 identity, and clear
malformed/unsupported-input failures. No CAD kernel or vendor connector was
added. Full ISO 10303 parsing and OCCT adapter evaluation remain future work.

The initial Foreman publication omitted the synthetic `.step` fixture because
CAD files are intentionally ignored. PR #3 corrects that packaging issue with a
single-path `.gitignore` exception and commits only the synthetic, non-customer
test fixture.

Evidence: `python -m unittest discover -s tests -v`,
`python scripts/step_import_proof.py`, `python scripts/geometry_proof.py`, and
`bash scripts/ci.sh` are the required validation commands.

## 2026-07-13 — Milestone 3 complete

Milestone 3 adds a separate, CAD-neutral engineering-annotation document. It
captures build orientation, loading direction, process, quantity, critical
characteristics, permitted and forbidden contacts, weld joints, shop
constraints, and editable assumptions. Stable component/body/face/edge
references are validated against the imported model and the source SHA-256
prevents annotations from being applied to another source. Local deterministic
JSON save/load preserves the annotation document without copying or mutating
source geometry.

Evidence: `python -m unittest discover -s tests -v` passes 8 tests. The
annotation contract deliberately does not perform fixture constraint, access,
collision, or production-safety validation; those belong to later milestones.

## 2026-07-13 — Milestone 4 complete

Milestone 4 adds a dependency-free, CAD-neutral fixture primitive proof. It
generates an editable `FixtureConcept` containing a parameterized flat
baseplate, one support pad per physical body, a loading-direction hard stop,
round-pin envelope, and relieved-locator envelope. Every feature records its
source references, deterministic rule, units, parameters, assumptions, and
warnings. Product geometry remains immutable and separate.

The proof reports missing locating intent, annotated forbidden contacts,
insufficient unload margin, and obvious overlap findings. It deliberately
does not claim B-Rep accuracy, physical force adequacy, tolerance-stack
validation, weld/robot access, certification, or production approval.

Evidence: `python -m unittest discover -s tests -v` passes 11 tests, `python
scripts/fixture_proof.py` generates 7 features with explicit millimetre units,
and `bash scripts/ci.sh` passes. No kernel, vendor connector, or dependency
was added.

## 2026-07-13 — Milestone 5 complete

Milestone 5 adds three deterministic complete-fixture alternatives optimized
for minimum cost, fast loading, and high repeatability. Each alternative
combines the primitive proof with traceable clamp mounts, documents locating
and clamping strategies, reports underconstraint and proof-layer rotational
validation warnings, and exposes bounded score components plus rationale.
Engineer corrections are copy-on-write concept metadata and do not mutate the
immutable source model. AI ranking or explanation is not part of the execution
path; deterministic findings remain authoritative.

Evidence: `python -m unittest discover -s tests -v` passes 16 tests, `python
scripts/concept_proof.py` prints all ranked concepts, and `bash scripts/ci.sh`
passes. No kernel, vendor connector, dependency, customer geometry, or
production-safety claim was added.

## 2026-07-13 — Milestone 7 complete

Milestone 7 adds vendor-neutral `ToolingItem`, `ToolingLibrary`, and
`ToolingSelection` contracts for clamps, pins, rests, and future tooling. The
contracts expose explicit millimetre envelopes, stroke, force, mounting,
access, source, license, attribution, and custom-geometry metadata. Selection
is deterministic and prefers adequate standard items before custom shop items.
The public generic library contains synthetic metadata only; custom libraries
remain runtime-supplied and separate. Selection does not claim force adequacy,
contact stability, tolerance validation, or production approval.

Evidence: `python -m unittest discover -s tests -v` passes 27 tests,
`python scripts/tooling_proof.py` prints the selected generic clamp and its
review warnings, and `bash scripts/ci.sh` passes. No vendor SDK, dependency,
catalog content, customer geometry, or proprietary rule pack was added.

## 2026-07-13 — Milestone 6 complete

Milestone 6 adds a CAD-neutral access proof for weld approaches and explicit
manual, robot, operator, and unload envelopes. Envelopes use millimetre AABBs,
stable weld-joint identities, optional approach metadata, and a visible
process-data completeness flag. Deterministic intersections with generated
fixture features report blocked weld approaches, access conflicts, and blocked
unload paths. Missing or incomplete process data remains a warning; no result
claims weld quality, robot reachability, certification, or production approval.

Evidence: `python -m unittest discover -s tests -v` passes 21 tests,
`python scripts/access_proof.py` reports a blocked manual weld approach and a
clear synthetic unload envelope, and `bash scripts/ci.sh` passes. No kernel,
vendor connector, dependency, customer geometry, or proprietary rule pack was
added.
