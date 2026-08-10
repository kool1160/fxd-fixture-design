# M33.1 Native Reconstruction and Explicit AI Mode

This document describes the bounded implementation for Issue #69. It does not
authorize M33.2, the final fixture-strategy contract, strategy-to-OCP authoring,
AI repair, production release, or additional fixture families.

## Native reconstruction

`fxd_geometry.product_reconstruction` defines
`fxd-native-product-reconstruction-v1`. The contract is source-SHA-bound and
stores separately from immutable STEP bytes:

- exact OCP component, transform, body, face, plane, cylindrical-axis, and
  candidate-hole evidence where the kernel supports it;
- bounded component classifications with confidence and provenance;
- candidate datum/contact features;
- separately typed weld candidates and engineer-confirmed weld intent;
- focused blocking questions for material ambiguity.

A cylindrical face is not silently called a hole. A planar or dimensional
pattern is not silently called a purchased, formed, tube, or machined part.
Unsupported meaning remains `unknown`. The reconstruction identity is the
SHA-256-derived identity of its canonical evidence payload. Loading a project
checks both that identity and the immutable source SHA.

Project format v6 persists the reconstruction and safely migrates v1-v5
projects with no invented reconstruction evidence. Old projects remain
readable with reconstruction absent until current OCP evidence is created.

## Explicit modes and provenance

`fxd_geometry.ai_execution` defines two explicit modes:

- `ai_design_live`
- `deterministic_offline`

Environment variables configure a provider; they do not select a mode. The
PySide6 workbench requires a visible mode selection and shows one unmistakable
banner:

```text
AI DESIGN — LIVE — <provider> / <model>
AI DESIGN — FAILED — NO FALLBACK USED
DETERMINISTIC / OFFLINE — NO LIVE AI REQUEST
```

`fxd-ai-design-execution-v1` persists provider/model identity, request
attempted state, exact request count, status, timestamp, prompt/response
contract versions, proposal identity when applicable, sanitized failure
category, timeout, retry count, usage availability, and token counts when the
API reports them. It never persists credentials, raw prompts, raw provider
output, STEP bytes, private paths, or unrestricted error content.

Live mode permits exactly one request, zero automatic retries, and a timeout no
greater than 60 seconds. Missing configuration, reconstruction ambiguity,
timeout, provider failure, cancellation, malformed output, or contract
quarantine produces no deterministic substitute. Offline mode may run the
legacy deterministic analysis/proposal path but is labeled as offline and
cannot claim an AI-authored result.

The reused `fxd-fixture-proposal-v1` response is only the bounded M33.1 live
request proof payload. This gate does not introduce or impersonate the future
`fxd-fixture-strategy-v1` contract.

## Evidence commands

Ordinary deterministic evidence:

```powershell
py -3.12 -m unittest tests.test_m33_product_reconstruction tests.test_m33_ai_execution tests.test_m33_live_acceptance
py -3.12 scripts/m33_1_self_check.py
bash scripts/ci.sh
git diff --check
```

Native Windows PySide6/VTK/OCP evidence, separate from CI and using no paid
request:

```powershell
py -3.12 scripts/m33_1_native_ui_check.py
```

Intentional live OpenAI acceptance is separate from ordinary CI. It refuses a
dirty or unexpected repository/branch and prints only bounded provenance:

```powershell
$env:FXD_M33_1_LIVE_ACCEPTANCE = "1"
$env:FXD_OPENAI_MODEL = "<explicit high-capability model>"
py -3.12 scripts/m33_1_live_acceptance.py
```

`OPENAI_API_KEY` must already be configured in the process environment. One
run has one request budget. A failed run is evidence of failure; it does not
authorize an automatic retry or deterministic fallback.

All results remain engineering-review evidence. They do not certify fixture
practicality, structure, clamp force, weld process, safety, or production use.
