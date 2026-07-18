# FXD Milestone Records 26-30

This addendum begins Volume 2 of the FXD professional project binder. Milestones 26-29 are verified complete from merged repository evidence. Milestone 30 is the current pending milestone and is not recorded as complete.

## Milestone 26 - Complete the local engineering workbench

**Status:** Complete  
**Controlling evidence:** PR #48, merged to `main` at `c8f831d938480dc80c0930653cf61d16b8037fcd`.

FXD repaired the real-STEP display path after the OCCT one-based triangle-index failure and established persistent real-geometry viewing. Valid triangle indices are converted to zero-based Python indices before display meshes are constructed. The workbench added persistent VTK PolyData/Actor rendering, camera controls, fit-all, standard views, orbit, diagnostic counts, and source-color preservation where XCAF provides color evidence.

The exact source STEP bytes and SHA-256 remain immutable. When the native Windows VTK/Tk bridge is unavailable, FXD uses its existing real-geometry CPU fallback rather than substituting proof boxes, synthetic shapes, or bounding envelopes.

**Validation evidence:** 5 focused tests and 154 full-suite tests passed with no failures, errors, or skips. Real-kernel proof, backlog validation, compilation, and diff checks passed. Controlled real assemblies were exercised without source mutation.

**Protected boundary:** Render benchmarks are not claims about visible GUI frame rate. This remains engineering-review software and does not approve production fixtures.

## Milestone 27 - Unify the FXD engineering workbench

**Status:** Complete  
**Controlling evidence:** PR #49, merged to `main` at `7a8076af6d07454628422eb3e40528e32db801b0`.

FXD replaced the launched Tk shell with a unified PySide6 engineering workbench while retaining the Milestone 26 compatibility layer. One persistent native VTK viewport is embedded through a supervised local worker to avoid the observed PySide6/VTK same-process Windows render crash.

The workbench added the engineering tree, properties and findings panels, project layers, review decisions, renderer controls, diagnostics, benchmark actions, component selection, and actor visibility. `VtkSceneController` owns persistent actors and navigation independently of the UI framework. The worker validates the exact selected STEP path and expected SHA-256 before importing real OCP geometry.

**Validation evidence:** 15 focused tests and 164 full-suite tests passed with no failures, errors, or skips. CI contract, full CI, kernel proof, compilation, backlog, schema, and diff validation passed. Windows visual acceptance exercised real assemblies, navigation, selection, layers, and clean shutdown.

**Protected boundary:** Native child-window embedding is a Windows desktop integration and is not cross-platform GUI acceptance. Proof or placeholder geometry may never be labeled real source geometry.

## Milestone 28 - Expose the interactive fixture engineering workflow

**Status:** Complete  
**Controlling evidence:** PR #50, merged to `main` at `1313922511c1d350dcc09a7c23fe1ed4446f1231`.

FXD exposed its existing deterministic placement, fixture, access, weld, validation, editing, revision, persistence, visualization, and export contracts through the unified workbench. The interactive workflow added explicit process intent, exact OCP face annotations, private tooling metadata, deterministic concept analysis, review state, bounded background analysis, concept comparison, supported corrections, revision restoration, linked findings, save/reload, and gated review-evidence export.

Project schema v3 persists the workflow only when present and retains v1/v2 read compatibility. Generated fixture evidence is visibly labeled provisional review geometry and remains separate from authoritative real-OCP source actors.

**Validation evidence:** 34 focused tests and 190 full-suite tests passed with no failures, errors, or skips. Compilation, schema, backlog, CI contract, full CI, secret scan, kernel proof, and diff checks passed. Windows acceptance exercised a real assembly, annotations, alternatives, revisions, persistence, and viewport interaction.

**Protected boundary:** No paid runtime AI, supplier scraping, thermal simulation, robot path planning, production approval, or safety certification is claimed. Incomplete evidence keeps concepts provisional or invalid.

## Milestone 29 - Implement the desktop UI and branding system

**Status:** Complete  
**Controlling evidence:** PR #51, merged to `main` at `4b6691a68145b6e2063d29db95c54200eb331489`.

FXD integrated the approved UI and Branding Kit v1.1 into the PySide6 workbench without replacing the engineering engine, project schema, source-CAD identity, or deterministic validation gates. The milestone added centralized tokens, palette, QSS, approved app/logo/toolbar assets, reusable semantic widgets, compact source identity, workflow rail, renderer health, validation and approval gates, grouped menus and toolbars, responsive dock sizing, and QSettings layout persistence.

All 148 branding-kit manifest payloads were verified before a curated import of 68 production payload files plus the source manifest. HTML prototypes, mockups, social art, patterns and previews, duplicate raster sizes, fonts, and customer or supplier data were excluded.

**Validation evidence:** 30 focused branding/workbench tests and 201 full-suite tests passed with no failures, errors, or skips. Compilation, planning schema, backlog, launcher, secret scan, kernel proof, and full CI passed. Windows visual evidence confirmed real OCP geometry, viewport navigation, source identity, unchanged source bytes, and clean shutdown.

**Protected boundary:** Branding does not replace or weaken deterministic engineering behavior. No mockup value, live paid AI, supplier scraping, physical prove-out, or production approval is claimed.

## Milestone 30 - Generate real fixture geometry and tack/location workflows

**Status:** Current / Pending  
**Current evidence:** PR #52 is open and unmerged.

Milestone 30 is implementing deterministic, editable fixture-construction evidence for real OCP manufacturing-review geometry and first-class fixture purposes. The current implementation includes full-weld, tack/location, assembly, inspection, profile-check, go/no-go, rework, robotic/cobot, and combined build/check purposes; construction and lifecycle evidence; Cleco strategy; tab/slot and hole-process contracts; poka-yoke; BOM, nest, sequence, geometry-authority, validation, comparison, authoring, and package contracts; and project schema v4 with v1-v3 read compatibility.

The open implementation reports 16 focused tests and 224 full-suite tests passing, plus compilation, backlog, planning-schema, kernel-proof, and CI evidence. However, Milestone 30 must remain pending until hosted kernel acceptance, independent review, controlled Windows visual review with approved input, user engineering acceptance, and merge are all complete.

**Protected boundary:** Current geometry is deterministic real-OCP review geometry. Detailed released profiles, tube mitres, commercial-tool envelopes, final tab contours, drawings, shop-specific policy, structural adequacy, safety, welding procedure, process capability, and production release remain qualified engineering work.

## Volume policy

Volume 1 is closed at Milestone 25. This document and the corresponding print PDF begin Volume 2. Future completed milestones should be added to Volume 2 in documentation batches without altering Volume 1 except to correct a factual or formatting error.

## Record-control statement

Pull requests, merge commits, tests, workflow runs, backlog records, review comments, and repository source remain the controlling implementation history. Nothing in this document constitutes fixture certification, weld-process approval, structural validation, manufacturability approval, supplier quotation, safety certification, or production release.
