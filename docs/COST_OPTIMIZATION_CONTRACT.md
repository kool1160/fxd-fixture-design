# Cost and Optimization Contract

FXD Milestone 25 produces deterministic engineering estimates from a validated
manufacturing assembly and, when supplied, its validated drawing package.
Rates, densities, thresholds, formulas, assumptions, evidence, and findings
are persisted as structured data and are stable under equivalent input order.

The analysis fails closed when source, concept, manufacturing, drawing, or
authoritative validation identity does not reconcile. Missing prices remain
explicit configurable assumptions; they are never presented as supplier
quotations. Material mass is estimated from component bounds, density, and
quantity. Process cost is `(base hours + 0.02 * hole count + 0.03 * tab-slot
count) * quantity * rate`; totals use named engineering, programming, setup,
assembly, inspection, finishing, commissioning, maintenance, replacement, and
material assumptions.

Prototype, low-volume, medium-volume, and high-volume scenarios expose fixture
investment and amortized cost per unit. Manufacturability findings identify
review thresholds such as excessive component, machining-feature, or purchased
tooling counts. Recommendations are review-only explanations, not production
approval, safety certification, supplier pricing, or robot-cycle certification.

The contract leaves detailed optimization, supplier quotations, released
manufacturing budgets, and Milestone 26 pilot validation to later work.
