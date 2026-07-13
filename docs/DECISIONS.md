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
