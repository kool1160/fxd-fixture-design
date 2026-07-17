# PySide6 / Qt Desktop Application Shell

## Window hierarchy

Use the existing `QMainWindow` as the single authoritative desktop workbench.

1. **Compact branded application bar** — 32–36 px. Flat FXD icon, project title, project revision, persistent `SOURCE CAD · READ-ONLY` identity badge, renderer/worker health indicator, optional user/workstation identity.
2. **Desktop menu bar** — native or custom-dark `QMenuBar`, 24–28 px. File, Edit, View, Project, Engineering, Validation, Tools, Window, Help.
3. **Grouped engineering toolbar** — 36–42 px. Icon-first desktop controls with concise labels on high-value actions only.
4. **Left workflow rail** — 42–52 px compact numbered/status icons.
5. **Engineering explorer** — 230–340 px, dockable/resizable, usually left. Contains project/workflow/object trees with filters.
6. **Persistent VTK viewport** — center and visual priority. No replacement widget, no web canvas, no re-created renderer during ordinary panel changes.
7. **Contextual inspector** — 300–440 px, dockable/resizable, usually right. Tabs for Properties, Evidence, Findings, Validation, History.
8. **Bottom engineering status strip** — 22–28 px. Selection identity, units, coordinate system, renderer status, worker status, autosave, validation summary.
9. **Resizable splitters and docks** — preserve user layout through `QSettings` and project/user preference scope.

## Recommended sizes

| Window | Left rail | Explorer | Inspector | Toolbar | Viewport target |
|---|---:|---:|---:|---:|---:|
| 1366×768 | 44 | 240–260 | 300–320 | 38 | at least 730×500 |
| 1920×1080 | 48 | 280–320 | 340–380 | 40 | about 1180×820 |
| 2560×1440 | 48 | 320–360 | 380–440 | 40 | about 1680×1160 |

## Non-maximized behavior

- Recommended minimum: 1180×720.
- At 1180–1365 px wide: collapse workflow labels to icons; inspector defaults to 300 px; hide low-priority toolbar labels; retain all functionality through menus.
- Below 1180 px: do not silently compress the viewport. Collapse either Explorer or Inspector to an edge tab and show a one-time layout notice.
- Explorer and Inspector widths should not expand indefinitely on large displays; place surplus width in the viewport.

## Dock and splitter behavior

- Explorer and Inspector are `QDockWidget` or splitter-managed persistent panels.
- User can collapse, float, move, and restore panels where supported by the existing architecture.
- Splitter handles: 5–7 px effective hit area, 1 px visual divider, high-contrast hover cue.
- Double-click splitter handle restores recommended size.
- `View > Reset Workbench Layout` restores the default without deleting project data.

## Viewport priority rules

- Minimum viewport before panels collapse: 680×440.
- No centered dashboard cards over an active project.
- Findings selection may open a compact overlay label or temporary callout, but not a permanent card covering geometry.
- Large forms open in the Inspector or a modeless dock unless the task must block workflow.

## Layout persistence

Persist window geometry, dock state, splitter sizes, visible columns, last-used view mode, and panel tabs using `QSettings`. Store engineering decisions in the project, not in UI settings.
