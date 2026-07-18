# FXD Project Record

## 2026-07-17 - Milestone 27 unified workbench implementation

Milestone 27 replaces the launch path's Tk shell with a PySide6 `QMainWindow`
and embeds one persistent native VTK render child in the central viewport. Docked
engineering explorer, properties, and findings panels expose only available
source and project evidence. The renderer preserves immutable STEP identity,
validated zero-based tessellation, source colors where XCAF mapping exists,
and fail-closed behavior for metadata-only input. Camera movement reuses the
same polydata and actors.

PySide6 is pinned as a desktop dependency with its LGPLv3/commercial packaging
boundary recorded. The legacy Tk module remains temporarily available for
compatibility but is no longer the launcher target. Milestone 27 remains
Pending until Windows screenshots, user visual acceptance, Kernel acceptance,
independent review, and merge. No production approval is claimed.

## 2026-07-15 — Milestone 20 safe internal phase

Milestone 20 adds versioned `fxd-neutral-project-v2` persistence with legacy
v1 loading, atomic saves, adjacent autosave recovery, structured local JSONL
diagnostics, and isolated user preferences. The application can now invoke
the existing fail-closed fabrication-package gate and export engineering-
review artifacts when deterministic validation permits it. A neutral synthetic
performance proof measured 0.727 ms against a 1000 ms budget, and release
manifest/signing procedures are documented without embedding keys.

The milestone remains Pending: `bash scripts/ci-contract.sh` passes (99 tests,
4 real-kernel tests skipped), but `bash scripts/ci.sh` could not install the
pinned OCP dependency because this environment cannot resolve PyPI. Real-kernel
large-assembly performance evidence and authorized release signing remain
pending. No production approval or certification claim is made.

## 2026-07-16 - Milestone 22 deterministic placement proof layer

Milestone 22 adds explicit datum-candidate ranking and editable placement
contracts for primary, secondary, and tertiary datum contacts, round and
diamond pins, stops, supports, and clamps. Placement validation composes the
existing six-DOF locating solver, access findings, vendor-neutral tooling
selection, weld intent, and Milestone 21 structural members. It reports
overconstraint, duplicate directions, missing or invalid geometry evidence,
unsupported mounts, blocked access, insufficient clamp capacity, and retained
alternative arrangements without allowing preference scores to override
deterministic validity.

Placement plans preserve source SHA-256 identity, millimetre units, evidence,
assumptions, confidence, deterministic JSON, validation digests, and optional
project save/load round trips. The implementation is a proof layer only: it
does not author final B-Rep tooling, simulate force or thermal behavior, plan
robot motion, certify safety, or approve production fixtures.

Evidence: 10 focused placement tests, 121 full tests, compileall, backlog and
schema validation, secret scan, and real OCP kernel proof passed. Bash is not
available on this Windows host, so `bash scripts/ci.sh` could not be run.

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

## 2026-07-13 — Milestone 8 complete

Milestone 8 adds a deterministic fabrication review package for eligible
fixture concepts. The package includes a source-bound manifest, explicit
millimetre STEP-shaped AABB geometry, XY DXF envelope profiles, reconciled BOM
quantities including generic purchased clamp metadata, setup instructions,
and concept/access validation findings. Invalid concepts are rejected. Every
artifact carries revision and review status, and the package explicitly does
not claim certification, validation, or production approval.

The current proof layer cannot author true B-Rep STEP, bend-aware profiles,
tolerance stacks, or real tooling geometry; those remain unresolved before
direct fabrication use.

Evidence: `python -m unittest discover -s tests -v` passes 31 tests,
`python scripts/export_proof.py` writes six deterministic synthetic artifacts,
and `bash scripts/ci.sh` passes. No kernel, vendor connector, dependency,
customer geometry, or proprietary rule pack was added.

## 2026-07-13 — Milestone 9 complete

Milestone 9 adds attributable, copy-on-write correction records and a local
knowledge store. Records capture proposed generated-feature metadata,
corrections, rejection or acceptance decisions, outcomes, scope, confidence,
and evidence without serializing coordinates, topology, source bytes, or source
references. A sanitized training view removes source and concept identifiers.
Private records are stored under ignored `.fxd/knowledge/`; public code does
not contain customer corrections, shop rules, or proprietary geometry.
Universal scope is gated to explicit `rule_candidate` entries, so preferences
and isolated lessons cannot silently become rules. Records remain historical
engineering evidence and do not validate or approve production fixtures.

Evidence: `python -m unittest discover -s tests -v` passes 36 tests,
`python scripts/knowledge_proof.py` demonstrates source-free training output,
and `bash scripts/ci.sh` passes. No kernel, connector, dependency, customer
geometry, or proprietary rule pack was added.

## 2026-07-13 — Milestone 10 complete

Milestone 10 adds an optional CAD connector boundary while preserving the
standalone neutral workflow. `NeutralStepConnector` delegates to the immutable
STEP `ProductModel`; connector failures cannot mutate source bytes. A
read-only SOLIDWORKS Connected/Makers probe reports conservative
`unsupported`, `not_detected`, or `unknown` states and never invokes COM or a
vendor SDK. Future vendor-document mutation is explicitly approval-gated.

No SOLIDWORKS SDK, binary, customer geometry, or vendor catalog was added.
Actual SOLIDWORKS compatibility, API access, and redistribution rights remain
unresolved until an approved Windows/vendor review is available.

Evidence: `python -m unittest discover -s tests -v` passes 40 tests,
`python scripts/connector_proof.py` passes, and `bash scripts/ci.sh` passes.

## 2026-07-14 — Milestone 11 kernel boundary assessed

The safe internal phase adds a CAD-neutral `RealKernel` contract, explicit
backend discovery, and a hard failure for missing or unreviewed B-Rep
backends. The AABB implementation is documented and tested as a test double
only. No kernel dependency was installed because this checkout has no OCCT
runtime and no reviewed binding/version or redistribution record.

Milestone 11 remains blocked. Real STEP topology, Boolean, distance,
clearance, hierarchy, and deterministic round-trip evidence require approval
of an exact kernel/binding and a runtime containing it.

Evidence: `python -m unittest discover -s tests -v`,
`tests/test_kernel_boundary.py`, and `docs/GEOMETRY_KERNEL_BOUNDARY.md`.

## 2026-07-14 — Milestone 12 deterministic locating solver

FXD now exposes a CAD-neutral `LocatingStrategy` made from explicit contact
points, normals, product references, and distinct locator roles. The solver
forms rigid-body constraint rows and deterministically reports rank across six
translational/rotational degrees of freedom, underconstraint, redundant
locators, invalid references, and clamp exclusion. Tolerance, repeatability,
and datum assumptions remain structured evidence. Concept generation accepts
the strategy and gates invalid locating concepts out of recommendation.

Evidence: `python scripts/constraint_proof.py`,
`tests/test_constraints.py`, and the focused concept regression tests. The
required `bash scripts/ci.sh` command was attempted but could not install the
pre-existing pinned kernel dependency because this environment had no PyPI DNS
or network access; no code failure was reached. Full-rank analysis is not a
production approval or a substitute for kernel contact, force, tolerance,
access, or manufacturing validation.

## 2026-07-14 — Milestone 13 weld-fixture engineering rules

FXD now stores explicit weld process, direction, sequence, heat-input,
distortion, tack, release, and assumption metadata. A deterministic,
configurable evaluator reports missing process evidence, heat-input threshold
conflicts, missing tack/release intent, fixture features associated with weld
zones, and clamp-force directions that reinforce expected distortion. Findings
and recommendations retain rule identity, evidence, assumptions, and
confidence. Conflicts remain warnings rather than being averaged into a score;
caller-supplied thresholds and directions are not universal shop policy.

The implementation remains CAD-neutral and uses synthetic reference evidence.
It does not simulate thermal distortion, force adequacy, spatter, weld quality,
robot motion, or production safety, and it does not include private shop rules.

Evidence: `python -m unittest tests.test_weld_rules` passes. The repository's
full suite remains environment-blocked by the pre-existing missing pinned OCP
runtime (`cadquery-ocp==7.9.3.1.1`) in kernel tests.

## 2026-07-14 — Milestone 14 safe internal phase

Generated fixture features now carry explicit, public-safe manufacturing
metadata for method, material, thickness, fit, clearance, allowance,
interface, and operations. The CAD-neutral manufacturing boundary now authors
kernel solids with explicit slot, relief, and pin-hole Boolean operations,
checks that each result contains a solid, and exports deterministic STEP plus
supported prismatic/cylindrical DXF profiles. Neutral fabrication-package
export accepts those kernel-authored artifacts while retaining the proof path
when no real geometry is supplied.

Milestone 14 remains blocked. The pinned `cadquery-ocp==7.9.3.1.1` runtime is
not installed and network access cannot install it, so true kernel geometry,
interference/manufacturability checks, and STEP/DXF acceptance evidence could
not run. Free-form kernel-edge DXF profiles, tolerance-aware fit validation,
and validated purchased-tooling interfaces remain unresolved. No status
change to Complete is supported.

Evidence: focused fixture, concept, export, and manufacturing contract tests
pass; `python -m compileall -q fxd_geometry tests` passes;
`bash scripts/ci.sh` is blocked while installing the pinned OCP dependency;
the repository-wide suite reaches 57 tests and has four pre-existing OCP
runtime errors.

## 2026-07-14 — Milestone 15 implementation evidence

Milestone 15 adds a versioned `validate_fixture_concept` release gate that
integrates concept findings, geometry collision/clearance evidence, locating
adequacy, access and unload findings, weld-rule findings, clamp/tooling review,
tolerance/repeatability gaps, and optional real-kernel manufacturing-solid
clearance checks. Results are `valid`, `provisional`, or `invalid`; invalid
results are rejected by fabrication-package export. Findings retain subsystem,
evidence, assumptions, and a deterministic evidence digest. The synthetic
regression deliberately reports a clamp/product collision and remains invalid,
which demonstrates that known unsafe geometry blocks release.

Focused validation/export tests and the synthetic proof pass. Full CI is not
currently reproducible in this environment because network/DNS access prevents
installation of the already-pinned `cadquery-ocp==7.9.3.1.1` runtime; the
existing real-kernel tests therefore remain unverified here. Milestone status
remains Pending until that environment verification is completed.

## 2026-07-14 — Milestone 17 implementation evidence

The CAD-neutral kernel boundary now exposes review geometry primitives for the
visual application: real-kernel triangle tessellation linked to face records,
stable edge inspection records, interference checks, and section operations.
These records are display and selection evidence only; they do not replace
B-Rep validation or imply production approval. The pinned OCP runtime is not
available locally, so real-kernel acceptance and release claims remain pending
GitHub Actions evidence.

## 2026-07-14 — Milestone 18 complete

The project workflow now exposes a restricted edit contract for supported
parameter changes (including locator type, pin diameter, support height, clamp
choice, baseplate thickness, fit, and clearance) plus move, resize, replace,
suppress, restore, and compare operations. Edits are copy-on-write revisions;
they regenerate the deterministic concept model, recompute validation evidence,
and revoke the revision-bound engineering-review approval. Project persistence
stores the edit log and revision evidence, while unsupported free-form edits
fail explicitly. Source STEP bytes, source hashes, annotations, and vendor
connectors remain untouched.

Evidence: `python -m unittest discover -s tests` passes 88 tests with four
environment-skipped real-kernel tests; `bash scripts/ci-contract.sh` passes.
OCP is unavailable in this environment, so no new real-kernel acceptance claim
is made. The workflow remains engineering-review-only and does not certify or
approve production fixtures.

## 2026-07-15 — Milestone 19 complete

The neutral workflow layer adds editable, ordered weld, tack, clamp, and
release sequence plans; traceable heat, distortion, spatter, and restricted-
contact zones; shared torch, hand, operator, robot, cobot, and unload envelope
references; deterministic envelope and trapped-part conflicts; and variant
comparison that preserves blocked gates. Findings retain rule, geometry, and
evidence links in a review visual model. No thermal, force, spatter, or robot
kinematic simulation is claimed, and the workflow remains engineering-review-
only.

Evidence: `bash scripts/ci-contract.sh` passes with 94 tests and four skipped
real-kernel tests. `bash scripts/ci.sh` was attempted but could not install the
pinned `cadquery-ocp==7.9.3.1.1` because this environment cannot resolve
PyPI; real-kernel acceptance remains an authoritative GitHub Actions concern.

## 2026-07-17 - Milestone 27 complete

The unified PySide6 workbench was independently visually accepted, passed
hosted Kernel acceptance, and was squash-merged through PR #49 at `7a8076a`.
One main window contains the supervised native VTK viewport, engineering
explorer, properties, findings, project operations, and renderer diagnostics.
Real OCP source evidence, immutable SHA-256 identity, XCAF colors, zero-based
tessellation, and fail-closed imports remain authoritative.

## 2026-07-17 - Milestone 28 complete

The unified workbench now orchestrates explicit process setup, exact OCP face
annotations, deterministic placement and concept generation, gated concept
comparison, provisional fixture review visualization, operational findings,
private tooling metadata, supported edits, revision creation, revalidation,
and schema-v3 persistence. The implementation composes existing engineering
contracts and does not add supplier scraping, paid AI, source-CAD mutation, or
automatic production approval.

The comparison surface includes both loading and unloading, relative cost and
repeatability evidence, feature and tooling counts, access disciplines,
manufacturability, maintainability, unresolved assumptions, and deterministic
ranking rationale. The workbench exposes existing move, resize, replace,
suppress/restore, parameter, and saved-revision operations. Private tooling
metadata remains local and can only be marked verified when its traceability
fields are present and its selected STEP geometry imports through real OCP.

Milestone 28 passed Windows visual acceptance and hosted Kernel validation,
received independent review, and was squash-merged through PR #50 at
`1313922`. Provisional AABB review actors remain visually and semantically
separate from real source and final manufacturing geometry.

## 2026-07-17 - Milestone 29 local implementation evidence

The approved FXD UI & Branding Kit v1.1 is integrated through a presentation-
only `fxd_ui` package. Shared tokens, palette, QSS, application and toolbar
icons, source-CAD identity, semantic status chips, workflow navigation,
approval gates, desktop menus, compact status evidence, and `QSettings` layout
persistence now brand the existing PySide6 workbench. The persistent VTK
viewport, OCP import, project schema, interactive workflow, validation gates,
and source geometry contracts were not replaced.

Branding source `FXD_UI_Branding_Kit_v1.1.zip` was read at 7,386,642 bytes with
SHA-256 `D73627B0760B59FCD9521A120824258F27EFCDB1B7FF5FA33F7CD37FDC06AF76`.
All 148 manifest payload entries matched before a curated 68-file production
payload subset plus the source manifest was imported. Reference-only HTML,
mockups, social artwork, duplicate
raster previews, fonts, supplier data, and customer CAD were excluded.

Local evidence: Python 3.12.10, OCP 7.9.3.1, PySide6 6.8.3, and VTK 9.6.2;
30 focused branding/workbench tests and 201 full-suite tests pass with zero
failures, errors, or skips; compile, schema, backlog, launcher, secret-scan,
kernel-proof, and `scripts/ci.sh` checks pass. A live Windows review loaded a
four-component OCP STEP compound with 24 faces and 48 triangles, displayed its
real geometry, exercised orbit, pan, zoom, fit, standard view, wireframe, and
transparency, and closed cleanly. Its source SHA-256 remained
`D33C0464216D0F38124CBB64D0E64D8183C52A15A1D62BEC18B72899A3E33AAA`.

Milestone 29 was independently visually accepted and squash-merged through
PR #51 at `4b6691a`. No production approval or physical prove-out is claimed.

## 2026-07-17 - Milestone 30 local implementation evidence

Milestone 30 adds the CAD-neutral fixture-build contract and review-only
construction workflow. It persists fixture purpose, construction method,
lifecycle and job revision, Cleco strategy, product-hole approval, hole-process
authority, adjustment state, authored component evidence, BOM, nest
classification, and the optional build plan in schema-v4 projects while reading
v1 through v3 projects unchanged. The contract covers full weld, tack/location,
assembly, inspection, profile check, go/no-go, rework, robotic, and combined
build-and-check purposes. Tack/location plans require tack access, release, and
unload evidence but deliberately do not require finish-weld access or claim
finish-weld distortion control.

The deterministic M30 rule catalog emits traceable findings for datum/support,
pin, clamp, access, weld/distortion, manufacturing, tabs, holes/threads,
poka-yoke, Cleco, tack, cost/lifecycle, maintenance, and export gates. A valid
plan authors OCP B-Rep plate, tube-frame, riser, gusset, locator, pin, clamp,
tab/slot, and hole geometry; individual STEP and eligible planar DXF outputs,
the BOM, hole-process table, slot-and-tab map, Cleco-hole map, poka-yoke map,
nest classification, and workflow sequences remain engineering-review-only.
Source CAD bytes and SHA-256 are read-only input evidence throughout.

Local evidence: Python 3.12.10 with OCP 7.9.3.1; 16 focused Milestone 30 and
workbench tests and 223 full-suite tests pass with zero failures, errors, or
skips. A locally generated, nonconfidential OCP STEP source was loaded in the
persistent VTK workbench, verified as real source geometry, navigated with
orbit, pan, zoom, fit, and standard views, then closed cleanly without changing
the source SHA-256. Milestone 30 remains Pending until hosted kernel acceptance,
independent review, full Windows visual acceptance, user engineering acceptance,
and merge. It does not claim released fabrication detail, thermal or robot
simulation, structural adequacy, safety certification, or production approval.

## 2026-07-18 - Milestone 31 local implementation evidence

Milestone 31 adds the provider-neutral `fxd-fixture-proposal-v1` request,
response, provenance, recommendation, validation, edit, and audit contracts. A
configured environment-only HTTP provider receives compact engineering summaries
without STEP bytes; malformed, unknown-identity, source-mismatched, orientation-
mismatched, or engineering-context-mismatched output is quarantined. When AI is unavailable, the same
workflow uses an explicitly labeled deterministic baseline. Existing
deterministic placement, concept, access, weld, validation, approval, and export
engines remain authoritative and fail closed.

The schema-v5 project record persists the proposal separately from immutable
source CAD and manufacturing orientation, remains backward compatible through
v1, and preserves engineer accept, reject, suppress, edit, regeneration, and
stale-state evidence. The Qt workbench adds the Proposal step, minimum-intent
confirmation, per-recommendation highlights and explanations, guided validation
with correction routing, and dismissible/reopenable first-run guidance.

Local evidence: Python 3.12.10, OCP 7.9.3.1, PySide6 6.8.3, and VTK 9.6.2;
17 focused AI fixture tests, 45 focused Qt/workbench tests, 14 project and export
persistence tests, 36 manufacturing-orientation/interactive/kernel tests, and
278 full-suite tests pass with zero failures, errors, or skips. `compileall`,
`git diff --check`, launcher dependency checking, and `scripts/ci.sh` pass; the
governed CI validates 20 milestones and its real OCP proof.

A locally generated, nonconfidential OCP STEP box was loaded through the native
`vtkWin32OpenGLRenderWindow`. Bottom and front planar faces were picked directly
and displayed with distinct highlights; preview, Fit View, orientation acceptance,
minimum-intent confirmation, deterministic fallback generation, recommendation
highlighting, guided issue explanation, correction routing, and post-resize
repaint were exercised. The source SHA-256 remained
`2A9EAC1BCEBD809EEC6DF40BA07D3576E6D1926AE7DA3D2AC0BC88F010CEAF94`.

Milestone 31 remains pending hosted acceptance, fresh independent review, user
Windows visual acceptance, engineering acceptance, and explicit merge authority.
No production fixture approval or physical adequacy claim is made.
