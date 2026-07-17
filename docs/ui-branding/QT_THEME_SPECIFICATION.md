# Qt Theme Specification

## Palette

Set an application-level dark `QPalette` consistent with tokens, then apply `fxd.qss` for widget-specific styling. Palette roles should map Window→Carbon, Base→Panel/Input, AlternateBase→Graphite, Text→Steel, Disabled Text→muted 46%, Button→Raised, Highlight→FXD Blue, HighlightedText→White, ToolTipBase→Raised, ToolTipText→Steel.

Avoid per-widget palettes unless required by VTK integration or platform-specific rendering. Centralize theme loading and support a future system/high-contrast theme without changing domain widgets.

## Disabled contrast

Disabled controls must remain legible and explainable. Use 42–48% opacity for icon/text, a darker border, and visible nearby reason text. Do not rely only on a disabled tooltip for critical gates.

## Focus

All keyboard-focusable widgets receive a 2 px FXD Blue focus outline. For controls whose QSS border change would shift layout, reserve 2 px in the resting state or draw a custom focus primitive.

## Selection

Active selection uses blue-tinted fill plus a leading blue bar. Inactive-window selection uses muted blue-gray. Synchronize tree/table selection with VTK selection without rebuilding the renderer.

## Splitters and docks

Splitters have a 6 px hit region and 1 px visual line. Hover uses FXD Blue. Docks use compact title bars, persistent state, accessible close/float controls, and no oversized headers.

## Widget guidance

- Menus: compact 6 px vertical item padding, shortcuts aligned right, separators only between functional groups.
- Dialogs: 520–760 px typical width; resize where evidence tables or geometry previews exist.
- Trees: 24 px rows, status icon + label + optional count; preserve accessible model roles.
- Tables: meaningful headers, stable column widths, optional row striping, sortable/filterable where relevant.
- Tabs: text labels, 2 px active blue indicator, no rounded browser-tab styling.
- Inputs: 28–32 px height, visible units, numeric bounds and precision tied to engineering contracts.
- Tooltips: action + shortcut + state; delay around 450–650 ms; never sole instruction.
- Progress: use for import/analysis/validation tasks; show phase and cancel only when safely supported.
- Scrollbars: 12 px visual width with 28 px minimum thumb; wheel behavior follows platform conventions.

## VTK boundary

Do not apply a QWidget background over the VTK render window. Theme only the host frame, layer legend, view cube, and transient overlays. Preserve persistent renderer/camera/interactor objects.
