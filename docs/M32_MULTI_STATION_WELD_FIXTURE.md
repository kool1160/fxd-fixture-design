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

The supported generator adds a connected baseplate with table holes and real
through-slot operations, an upright datum rail, rail tab-and-slot evidence,
end braces, repeated three-rest support stations, locator plates with actual
adjustment-slot cuts, hard stops, clamp brackets, vendor-neutral toggle-clamp
review solids, and replaceable shim/wear evidence. The generic clamp is an
authored review representation only, never released supplier CAD.

## Validation and review boundary

M32 adds deterministic checks for family, count, pitch, length, stable source
instance identity, product-instance overlap, station completeness, rail/base
span, brace connectivity, clamp-tip reach, clamp-open envelope, hand access,
weld access, unloading, and trapped parts. The existing parent-connectivity,
source-SHA, locating, clamp-reaction, access, manufacturing-authority, and
export gates remain active.

An authored component is tessellated from its actual OCP shape for the VTK
workbench. Bounds remain only an explicitly labelled debug fallback if that
tessellation fails. Product review instances use the immutable source mesh plus
their stored station transforms. All geometry, validation, and exports remain
engineering-review-only; no structural capacity, clamp force, weld procedure,
safety, or production approval is inferred.
