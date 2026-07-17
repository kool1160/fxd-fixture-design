# FXD Brand Guide — Desktop Engineering Edition

## Brand idea

FXD is a **digital fixture engineer**, not another CAD system and not an AI black box. It helps an engineer understand a fabricated assembly, develop practical fixture concepts, expose assumptions and evidence, and make qualified decisions.

## Identity

| Element | Approved use |
|---|---|
| Product name | FXD |
| Full name | Intelligent Industrial Fixture Design |
| Descriptor | Digital Fixture Engineer |
| Primary principle | AI proposes. Engineering validates. |
| Mission line | The software should think like an experienced fixture engineer. |

## Character

Engineering-first, practical, direct, calm under uncertainty, explainable, shop-floor aware, and visually controlled. The application should feel adjacent to serious CAD, simulation, inspection, and manufacturing software without imitating any vendor.

It must not feel like a consumer app, generic SaaS dashboard, game, cryptocurrency product, flashy AI demo, or web page inside a desktop shell.

## Approved palette

| Token | Hex | Role |
|---|---:|---|
| Carbon | `#0B0D10` | Main application background and viewport surround |
| Graphite | `#14181D` | Menu, toolbars, dock foundations |
| Panel | `#1A1F26` | Inspectors, trees, tabs, forms |
| Raised panel | `#222831` | Selected groups, cards, modal surfaces |
| Border | `#323A45` | Dividers, splitters, field outlines |
| Steel text | `#D6DBE0` | Primary readable text |
| Muted steel | `#8B96A3` | Secondary labels, metadata |
| FXD Blue | `#0A84D7` | Selection, deterministic evidence, linked geometry |
| FXD Orange | `#FF7A00` | Proposed fixture geometry, primary engineering action |
| Pass | `#39C98A` | Successful validation check |
| Warning | `#F4B740` | Non-blocking concern |
| Fail | `#EF6464` | Blocking failure |
| Not Evaluated | `#7D8794` | Check not run or evidence absent |
| Engineer Override | `#B78AF7` | Explicit human override with recorded reason |

Blue means reference, selection, source evidence, or deterministic information. Orange means generated fixture content, proposed change, or a deliberate engineering action. Semantic colors are reserved for states and are always paired with an icon and label.

## Logo hierarchy

- **Metallic approved lockup:** splash screen, About dialog, presentation covers, documentation, promotional artwork.
- **Flat SVG lockup:** application chrome, installer, title areas, exported reports, technical documentation.
- **Icon only:** executable icon, taskbar, compact top bar, About icon, recent-project list.
- **Monochrome assets:** laser marking, engraving, one-color print, limited-color technical documents.

Keep clear space equal to the locator-pin head diameter. Never stretch, rotate, randomly recolor, add glows, rearrange the X, or treat the orange and blue X parts as unrelated symbols.

## Typography

- UI: `Segoe UI`, 9–10 pt at 100% Windows scaling; 10–11 pt for primary forms.
- Technical values: `Consolas`, 9–10 pt.
- Section headings: Segoe UI Semibold, 10–12 pt.
- Dialog titles: Segoe UI Semibold, 12–14 pt.
- Avoid novelty or sci-fi fonts. The industrial character comes from control, spacing, geometry, and hierarchy.

## Brand promise in the UI

Every significant recommendation exposes identity, type, purpose, target geometry, Why, Evidence, Assumptions, Alternatives, deterministic checks, engineer disposition, and revision history.

## Approval language

Use precise states: Proposed, Accepted, Modified, Rejected, Locked, Deferred, Engineer Approved, Physically Proven.

Never use `Production Ready` unless qualified engineering review and required physical prove-out have actually been completed and recorded.
