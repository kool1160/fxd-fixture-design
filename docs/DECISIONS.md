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
