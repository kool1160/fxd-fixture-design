# Unified Local Engineering Workbench

FXD's desktop shell is a PySide6 `QMainWindow` with one native VTK render child
embedded into the central Qt host. A supervised local renderer worker isolates
VTK's native OpenGL lifecycle from Qt and its undecorated HWND is parented into
the central viewport; it is not a second user-facing application window. The
engineering explorer is docked on the left,
properties and deterministic findings are docked on the right, and the center
contains the persistent VTK scene. Normal operation does not open a detached
viewer window.

Install the pinned desktop runtime in the existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-desktop.txt
```

For Windows Explorer, double-click `launch-fxd.bat` in the repository root.
It resolves the repository root itself, uses `.venv\Scripts\python.exe`, and
keeps its console open if launch validation fails. Drag a `.step` or `.stp`
file onto the batch file to open it immediately through the normal FXD OCP
import path.

To create a desktop shortcut, right-click `launch-fxd.bat`, choose **Show more
options** if necessary, then choose **Send to > Desktop (create shortcut)**.

The PowerShell launcher remains available from the repository root:

```powershell
.\scripts\launch-fxd.ps1
```

Load a STEP file immediately:

```powershell
.\scripts\launch-fxd.ps1 -StepPath "C:\path\assembly.step"
```

## Navigation

- Left-drag: orbit
- Middle-drag: pan
- Mouse wheel or right-drag: zoom
- `F`: fit all geometry
- View menu: front, back, left, right, top, bottom, and isometric

Opaque shaded surfaces are the default. Wireframe and transparency are
explicit review modes. Imported XCAF component colors are used where they map
to source components; otherwise FXD uses a neutral material. Tessellation and
actors are created once per import and are not rebuilt during camera movement.
Existing FXD project layer visibility remains editable from **View > Project
layers** and is preserved by project save/load. Layers without mapped render
actors retain their project state without fabricating display geometry.

## Evidence and diagnostics

The properties panel reports source name, immutable SHA-256, component, face,
triangle, actor, and point counts plus the render backend and native/fallback
state. A visible render benchmark is available from the renderer diagnostics
action. Its FPS result is meaningful only while the embedded viewport is
mapped on the local display.

Ordinary vendor STEP files are read through the hardened OCP adapter. Files
with no transferable B-Rep roots fail closed. FXD never substitutes proof
boxes, bounds, or generated geometry for a failed source import, and
provisional project evidence is never labeled as real OCP source geometry.

## Boundaries

- Customer STEP bytes and their SHA-256 identity remain unchanged.
- The viewer does not infer or approve fixture engineering.
- Deterministic validation remains authoritative over display or AI output.
- All output remains engineering-review-only until qualified human approval.
- Headless CI uses Qt's offscreen platform and dependency injection; the real
  Windows embedded viewport still requires independent visual review.
- The native renderer worker re-reads the immutable STEP source to avoid sharing
  OCP or OpenGL objects across UI-process boundaries, so initial load performs
  two validated imports. Camera movement never reimports or retessellates.

Milestone 27 was independently visually accepted and merged in PR #49.

## Interactive engineering workflow

The Fixture Engineering Workflow dock organizes Product, Process, Datums and
intent, Concepts, Tooling, and Edit and revisions. A real OCP assembly can be
normalized into the CAD-neutral product model using only immutable source
bytes, stable component and face identities, normals, areas, and tessellation
vertices. Annotations remain separate from source CAD.

`Analyze Assembly` runs the existing placement, concept, access, weld, and
validation contracts on a bounded background thread. Unknown process inputs
and missing access envelopes remain visible findings. `Generate Fixture
Concepts` exposes deterministic alternatives and comparison evidence for
validity, relative cost, loading and unloading, repeatability, feature counts,
operator/weld/automation access, manufacturability, maintainability, unresolved
assumptions, and ranking rationale. Relative evidence is not a quotation.
Generated AABB feature evidence is shown only as translucent wireframe
provisional review geometry; it is never labeled `REAL OCP`, final B-Rep, or
released fabrication geometry.

### Manufacturing orientation

STEP import opens **Orientation** immediately. In the normal workflow, click the
planar face that sits on the fixture, confirm or flip its side, then click the
planar face that points toward the operator/front. FXD derives manufacturing
right (+X), operator/front (+Y), and up (+Z), rejects parallel face pairs, and
shows distinct bottom/front highlights plus the build plane, XYZ triad,
operator side, gravity, load, and unload directions. The support-face
recommendation asks for confirmation and is never silently accepted. Normal
mode does not expose face IDs, source axes, rotations, or matrices.

**Advanced orientation settings** retains the existing source reference-plane,
exact-axis, normal-flip, quarter/custom rotation, transform, inverse, face,
plane, and raw-evidence controls. **Edit orientation** returns to the guided
page from the Engineering menu or toolbar. An engineer must explicitly accept
the current source-SHA-linked orientation before deterministic analysis can
run. Any source or selected-face change clears downstream analysis, concepts,
approval, authored fixture geometry, and export evidence without rotating or
rewriting source CAD.

See `docs/MANUFACTURING_ORIENTATION_CONTRACT.md` for persistence, transform,
validation, and limitation details.

### AI Fixture Engineer proposal

After orientation acceptance, the workbench opens **Proposal** and presents the
prominent **Generate Fixture Proposal** action. Missing essential intent is
shown as a short interview with a reason and visible recommended answer for each
question. FXD never applies those answers silently. The proposal view labels AI,
offline fallback, timeout/failure, cancellation, and stale states separately.

Normal review lists recommendation category, title, engineer decision, and
deterministic status without raw face IDs or matrices. Selecting a
recommendation highlights its mapped source face or generated fixture feature
and explains the engineering reason, confidence, assumptions, checks, and
unresolved risk. Accept, reject, suppress, edit, regenerate, and overall review
decisions are audited. Provider, engine, contract, SHA, orientation, and proposal
identities remain under **Technical proposal details**.

The Validation tab summarizes blocking issues and warnings in plain language.
**Fix this** navigates to the mapped workflow section and evidence; **More
details** exposes rule and technical evidence. A failed or stale workflow stage
opens its related guided findings. The first-run proposal guide can be dismissed,
disabled, and reopened from **Help > Fixture proposal guide**.

Projects persist this evidence in schema v5. Source or orientation mismatch
makes the proposal stale and blocks approval/export while leaving the old review
visible. See `docs/AI_FIXTURE_PROPOSAL_CONTRACT.md`.

Supported parameter, move, resize, replacement, suppression/restore, and saved
revision restoration operations create deterministic project revisions, revoke
prior review approval, regenerate concepts, and rerun validation. Private local
tooling records can retain supplied manufacturer, part number, revision,
directions, stroke, reach, force, and explicit verified/unverified state after
the selected CAD passes the real OCP import path. Project schema v5
persists process setup, exact annotations, tooling verification state, finding
reviews, proposal provenance and audit history, active concept, visibility,
revisions, and timing evidence. V1 through v4 projects remain readable. Invalid
concepts and stale or blocked proposals remain blocked from review export;
provisional output retains the engineering-review-only boundary.

Milestone 30 was squash-merged through PR #52 at `edf65bb`. Milestone 31 remains
Pending until hosted validation, independent review, user Windows visual
acceptance, engineering acceptance, and merge.
