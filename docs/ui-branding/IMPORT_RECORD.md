# FXD UI & Branding Kit Import Record

## Source

- Package: `FXD UI & Branding Kit v1.1 - Desktop Engineering Edition`
- Version: `1.1.0`
- Original ZIP filename: `FXD_UI_Branding_Kit_v1.1.zip`
- Source ZIP SHA-256: `D73627B0760B59FCD9521A120824258F27EFCDB1B7FF5FA33F7CD37FDC06AF76`
- Source ZIP size: `7,386,642` bytes
- Manifest generation time: `2026-07-17T10:50:36Z`
- Manifest verification: all 148 listed payload entries matched their recorded byte
  counts and SHA-256 values before import

The original ZIP remains outside the repository and was not modified or copied
into Git.

## Imported Files

The source path and SHA-256 for all 68 imported payload files are retained in
`assets/branding/manifest/FXD_UI_Branding_Kit_v1.1_MANIFEST.json`. The regression
test in `tests/test_ui_branding.py` verifies every imported file against that
manifest.

- `assets/icons/toolbar/`: all 45 approved Qt SVG icons and `ICON_MAP.json`
- `assets/branding/app-icons/`: all 10 approved PNG sizes and `favicon.ico`
- `assets/branding/logos/`: flat color icon, flat color lockup, mono-white
  lockup, and approved dark About artwork
- `fxd_ui/theme/fxd.base.qss`: unchanged approved v1.1 QSS
- `fxd_ui/theme/fxd.tokens.json`: unchanged approved v1.1 token contract
- `docs/ui-branding/`: brand guide, application-shell specification,
  source-CAD protection specification, Qt theme specification, and
  accessibility checklist
- `assets/branding/manifest/FXD_UI_Branding_Kit_v1.1_MANIFEST.json`: source
  checksum manifest

`fxd_ui/theme/fxd.qss` is the production stylesheet derived from the approved
base QSS with FXD workbench-specific selectors appended. Python constants and
palette mapping live in `fxd_ui/theme/tokens.py` and `fxd_ui/theme/theme.py`.

## Intentional Exclusions

- HTML prototype and JavaScript: reference-only; the application remains PySide6
- mockup PNGs and index: visual specifications, not production runtime assets
- social and banner artwork: unrelated to the desktop workbench
- checkerboard and engineering-grid patterns: preview/reference material only
- duplicate raster logo sizes and previews: the selected production lockups cover
  desktop use without carrying the full handoff
- implementation prompt and Milestone 28 checklist: superseded by the governed
  Milestone 29 repository work

No font binaries, supplier CAD, customer CAD, confidential rules, or paid AI
integration were imported.
