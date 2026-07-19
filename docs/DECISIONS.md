# FXD Decision Log

Record durable product and engineering decisions here.

## Decision template

### YYYY-MM-DD — Decision title

**Decision:**

**Context:**

**Alternatives considered:**

**Reasoning:**

**Risks and tradeoffs:**

**Supporting evidence:**

**Revisit trigger:**

---

## Initial decisions

### 2026-07-13 — Keep the core CAD-neutral

**Decision:** FXD will use a neutral product model and thin CAD connectors rather than placing core fixture logic inside one CAD platform.

**Reasoning:** This preserves portability, reduces vendor lock-in, and allows the same engineering engine to serve multiple manufacturing environments.

### 2026-07-13 — AI proposes; deterministic engineering validates

**Decision:** AI may interpret intent, propose concepts, rank alternatives, and explain decisions. Geometry, mathematics, constraints, and engineering rules remain authoritative for validation.

### 2026-07-13 — Keep engineering annotations separate from source geometry

**Decision:** Engineering intent is stored in a versioned local JSON document
bound to the imported product's source hash. Annotation references identify
stable product geometry but never embed generated fixture geometry or mutate the
immutable `ProductModel`.

**Reasoning:** This preserves source identity, makes assumptions editable and
visible, and gives later deterministic fixture generation a traceable input.

**Risks and tradeoffs:** The current synthetic model exposes identity-based
topology only; full CAD topology stability and richer annotation editing remain
future work.

**Supporting evidence:** `docs/ANNOTATION_CONTRACT.md` and the 8 passing tests in
`tests/test_annotations.py`.

### 2026-07-13 — Rank fixture concepts with deterministic evidence

**Decision:** Complete fixture concepts are generated as explicit alternatives
for minimum cost, fast loading, and high repeatability. Ranking uses bounded,
explainable score components and deterministic constraint findings before any
future AI explanation or preference ranking.

**Reasoning:** Engineers need tradeoffs and visible warnings, not one opaque
answer. The proof layer can expose translation intent and traceability while
honestly flagging rotational and force-validation limits.

**Risks and tradeoffs:** The current score is a prioritization heuristic, not
an engineering fitness or safety score. AABB geometry cannot prove contact
normals, rotational restraint, clamp force, weld access, or tolerance stacks.

**Supporting evidence:** `docs/FIXTURE_CONCEPT_CONTRACT.md`,
`scripts/concept_proof.py`, and the complete-concept tests.

### 2026-07-13 — Keep tooling libraries vendor-neutral and separable

**Decision:** Tooling libraries use neutral metadata contracts and deterministic
selection. Generic public proof items are separate from caller-supplied private
shop libraries; vendor catalog content is not bundled.

**Reasoning:** FXD needs standard-component preference without coupling the
core to a vendor catalog, SDK, or restricted geometry. Selection can expose
mounting, access, stroke, and force requirements while leaving adequacy to
deterministic validation and human approval.

**Risks and tradeoffs:** Generic envelopes do not prove real clamp force,
contact stability, tolerance stack, or access. Real catalog integration needs
separate licensing and attribution review.

**Supporting evidence:** `docs/TOOLING_LIBRARY_CONTRACT.md`,
`scripts/tooling_proof.py`, and `tests/test_tooling.py`.

### 2026-07-13 — Export review packages without production claims

**Decision:** Export deterministic STEP-shaped, DXF, BOM, setup, manifest, and
validation artifacts from eligible concepts, while marking every package
`engineering_review_required` and `production_approval: false`.

**Context:** The current core has dependency-free AABB proof geometry and no
licensed B-Rep kernel. It can prove deterministic envelopes and quantities,
but not fabrication-ready topology, bend deductions, tolerance stacks, or
physical tooling adequacy.

**Reasoning:** A reviewable package provides runnable milestone evidence while
keeping CAD-neutral boundaries and the human approval requirement explicit.

**Risks and tradeoffs:** The STEP and DXF artifacts are proof-layer outputs,
not suitable for direct fabrication. A reviewed kernel/export implementation
is required before that limitation can be removed.

**Supporting evidence:** `docs/FABRICATION_PACKAGE_CONTRACT.md`,
`scripts/export_proof.py`, and `tests/test_export.py`.

### 2026-07-13 — Keep CAD connectors optional and approval-gated

**Decision:** CAD connectors translate through the immutable neutral product
model. The repository ships only a dependency-free STEP connector and a
read-only SOLIDWORKS host probe; vendor-document mutation is unavailable until
explicit human approval.

**Context:** Milestone 10 requires a CAD-specific connector path without
coupling the core to SOLIDWORKS or distributing vendor-owned software.

**Alternatives considered:** Importing a SOLIDWORKS SDK or COM wrapper into the
core; probing or automating a vendor installation from public CI; keeping no
connector boundary until a vendor integration is funded.

**Reasoning:** The neutral connector preserves standalone operation and gives
future adapters a testable boundary. The conservative probe avoids treating a
host, edition, or environment variable as proof of API rights or compatibility.

**Risks and tradeoffs:** SOLIDWORKS Connected/Makers compatibility is not
proven on this Linux runner. A Windows test and license review are required
before any SDK or COM implementation.

**Supporting evidence:** `docs/CAD_CONNECTOR_CONTRACT.md`,
`scripts/connector_proof.py`, and `tests/test_connectors.py`.

**Revisit trigger:** Approved Windows access and documented vendor API and
redistribution terms.

### 2026-07-14 — Gate real-kernel use behind an explicit neutral adapter

**Decision:** Real B-Rep operations must enter FXD through the `RealKernel`
contract. Backend discovery is diagnostic only, and missing or unreviewed
backends fail explicitly; the AABB implementation remains a named test
double.

**Context:** Milestone 11 requires a real kernel, but this checkout has no
installed OCCT runtime or approved dependency record.

**Reasoning:** Silent fallback would allow AABB evidence to be mistaken for
topology, Boolean, clearance, or STEP-round-trip evidence. The boundary lets
the neutral core and tests proceed without coupling them to vendor objects.

**Risks and tradeoffs:** The milestone remains blocked until an exact kernel
and binding can be reviewed for licensing, redistribution, platform support,
and representative STEP behavior.

**Supporting evidence:** `fxd_geometry/kernel.py`,
`docs/GEOMETRY_KERNEL_BOUNDARY.md`, and `tests/test_kernel_boundary.py`.

### 2026-07-18 - Keep AI fixture proposals advisory and provider-neutral

**Decision:** AI fixture proposals use a versioned, provider-neutral JSON
contract. Provider output is quarantined until its source SHA, manufacturing
orientation, referenced identities, and schema validate. The existing
deterministic engineering engines always rerun and remain authoritative for
approval and export; provider failure produces an explicitly labeled offline
baseline instead of bypassing the workflow.

**Context:** Milestone 31 adds an AI Fixture Engineer that must remain useful
without credentials while avoiding hidden source-CAD mutation, silent intent
assumptions, or production-safety claims.

**Reasoning:** A strict boundary permits later provider choice without coupling
the CAD-neutral core to an SDK. Visible provenance, explicit engineer decisions,
and deterministic validation preserve traceability and human authority.

**Risks and tradeoffs:** HTTP cancellation is cooperative and cannot interrupt
an operating-system call already in progress. The deterministic baseline can
recommend only what current geometry and rule evidence support, and neither AI
nor baseline output proves physical fixture adequacy.

**Supporting evidence:** `docs/AI_FIXTURE_PROPOSAL_CONTRACT.md`,
`fxd_geometry/ai_fixture_engineer.py`, and
`tests/test_ai_fixture_engineer.py`.

### 2026-07-19 - Synthesize only one governed multi-station fixture family

**Decision:** M32 extends the existing `FixtureBuildPlan` with typed
multi-station layout evidence and supports only
`linear_multi_station_weld_fixture`. It uses deterministic pitch, length,
source-instance, connectivity, clamp-reach, and access checks before real OCP
authoring. Generic toggle-clamp solids are vendor-neutral review geometry, not
released supplier CAD.

**Reasoning:** The existing construction, component, export, persistence, and
validation contracts already define the authoritative fixture path. A parallel
assembly model or AI-authored free-form B-Rep would split engineering truth and
weaken traceability. Explicit source-referenced instances preserve immutable
product evidence while making repeated stations reviewable.

**Risks and tradeoffs:** Equal pitch and explicit review allowances are a first
supported archetype, not a universal fixture rule. The geometry does not prove
clamp force, structural adequacy, thermal behaviour, released vendor fit, or
physical process safety. Human fixture and weld-process review remains required.

**Supporting evidence:** `docs/M32_MULTI_STATION_WELD_FIXTURE.md`,
`fxd_geometry/fabrication_workflow.py`, and
`tests/test_multi_station_fixture.py`.
