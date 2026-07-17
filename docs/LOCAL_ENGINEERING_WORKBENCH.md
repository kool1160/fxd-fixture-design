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

Launch from the repository root:

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

Milestone 27 remains Pending until local visual acceptance, CI, independent
review, and merge.
