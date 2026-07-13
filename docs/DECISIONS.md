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
