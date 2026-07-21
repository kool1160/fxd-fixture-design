# Milestone 32 Multi-Station Weld Fixture Synthesis

## Supported family and boundary

Milestone 32 supports exactly one deterministic fixture family:
`linear_multi_station_weld_fixture`. It is intended for small fabricated
assemblies that can be loaded consistently and repeated along a principal
fixture axis. Unsupported families fail explicitly; this is not an unconstrained
fixture or B-Rep generator.

The implementation composes the existing `FixtureBuildRequirements`,
`FixtureBuildPlan`, manufacturing-component identity, OCP authoring, BOM,
export, project-persistence, proposal, validation, and workbench contracts.
`MultiStationRequirements` supplies only the additional governed intent:
station count (one through eight), maximum length, optional preferred pitch,
loading and clamp sides, unloading direction, manual/cobot/robot mode, table
mounting preference, quantity, and one-up/multi-up comparison intent.
When comparison is selected, `generate_multi_station_fixture_alternatives`
returns the one-up and requested-count plans through the same validation and
authoring contracts; the workbench shows that comparison basis and selects the
requested-count plan for continued review.

## Deterministic layout and geometry

The layout chooses the product's longest horizontal envelope axis, then derives
equal pitch from the product span, explicit or derived clamp sweep, hand
clearance, weld clearance, and adjustment allowance. It fails closed when the
requested count cannot fit and names the smaller deterministic count that can.

Each station persists a stable `m32-station-NN` identity and a translation-only
review transform. The instance references the immutable source SHA-256 and
source component identities; it is not a copied or modified source B-Rep.

The supported generator adds a low table-mounted backbone, a deliberately low
common datum rail, and product-bounded local laser-cut station plates. Each
station plate carries its own three-point supports, locator plate, hard stop,
clamp mount, and replaceable wear/shim evidence. Compact end gussets remain
outside the first and last product envelopes. The recorded rationale explains
why the four repeated local plates share a backbone and explicitly avoids a
tall product-sized wall; it is stiffness intent, not a certified capacity
claim.

Supplier-neutral clamp geometry is purchased/provisional review evidence, not
authored manufacturing geometry. Closed clamp and open handle/sweep envelopes
are stored and displayed separately with the operating side, contact target,
and reaction-support relationship. They are excluded from authored fixture
STEP/DXF, nesting, and manufacturable BOM output unless authorized exact
tooling is supplied through a later governed boundary.

## Validation and review boundary

M32 adds deterministic checks for family, count, pitch, length, stable source
instance identity, product-instance overlap, station completeness, rail/base
span, brace connectivity, both end-station clearances, clamp-tip reach,
clamp-open envelope, hand access, loading and unloading sweeps, and trapped
parts. Station access values default to unevaluated and therefore fail closed;
the generator must write explicit directions, envelopes, results, and evidence.
Weld/torch access remains unevaluated until confirmed joint reference, side,
length, process, sequence, approach direction, and envelope evidence exist.
The existing parent-connectivity,
source-SHA, locating, clamp-reaction, access, manufacturing-authority, and
export gates remain active.

An authored component is tessellated from its actual OCP shape for the VTK
workbench. Bounds remain only an explicitly labelled debug fallback if that
tessellation fails. Product review instances use the immutable source mesh plus
their stored station transforms. The scene uses stable visual semantics for
source product, fixture structure, supports/wear items, locators/stops, clamp
mounts, closed purchased tooling, open clamp sweep, selected/finding state, and
per-station load/unload arrows. All geometry, validation, and exports remain
engineering-review-only; no structural capacity, clamp force, weld procedure,
safety, or production approval is inferred.

## Windows qualified-engineering visual review

From the clean M32 implementation branch, run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_m32_visual_review.ps1"
```

The command creates a persistent, redacted bundle outside the repository and
opens the actual FXD Qt/VTK application on the governed synthetic five-requested
to four-feasible project. The application stays open until the reviewer closes
it. The bundle retains its synthetic STEP, reloadable FXD project, reports,
initial screenshots, and qualified-engineering checklist after closure. Provider
configuration is removed only from child processes; no network provider request
is permitted. Passing software checks does not approve the fixture or replace
qualified judgment for access, practicality, clamps, weld intent,
manufacturability, structure, safety, or production release.

## Autonomous Windows software self-check

Run the complete repeatable M32 software scenario from the checked-out M32
branch with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_m32_self_check.ps1"
```

The runner requires a clean worktree and the repository `.venv`. It creates a
legally shareable synthetic STEP assembly only in a temporary directory, then
automates STEP import, exact planar bottom/front orientation acceptance,
deterministic analysis, concept generation, the explicit 5-to-4 station-fit
acceptance at a 1219.2 mm maximum length, build validation, real OCP authoring,
provisional labels, and approval/export release gates. It also runs focused M32
and Qt controller coverage, PowerShell runner regression coverage,
`compileall`, the full Python suite, and the governed offline/real-kernel CI
contracts. The scenario saves and reloads its synthetic project before
attesting source immutability, and writes a headless evidence-snapshot PNG and
redacted JSON report under `%TEMP%`. Neither artifact contains STEP bytes,
source identities, provider content, credentials, or customer data.

Every child process is forced offline, so the command cannot select an AI
provider or make a paid request. It does not launch the GUI. A passing run is
evidence that the governed software path works; it does not replace qualified
human judgment of fixture practicality, load/unload, weld access, locator and
clamp suitability, operator access, manufacturability, structure, safety, or
final production approval.
