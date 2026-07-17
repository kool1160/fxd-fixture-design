# Source CAD Protection Pattern

Use the exact visible label:

`SOURCE CAD · READ-ONLY`

## Compact badge

Recommended height: 22–24 px. Shield/lock icon, label, source filename, and verified/unverified evidence dot. Place in the branded top application bar and repeat in the Assembly inspector header.

Example:

`[shield] SOURCE CAD · READ-ONLY  Frame_A.step  rC  SHA 8E2A…91F4`

## Details exposed

- source filename
- customer or project revision
- abbreviated SHA-256
- full SHA-256 in tooltip and Source Identity dialog
- import timestamp and status
- OCP evidence status: Verified geometry, Partial evidence, Import warning, or Unavailable
- component, solid, shell, face, edge, vertex, and triangle counts where available
- renderer representation state

## Interaction

- Clicking the badge opens a non-editable Source Identity panel.
- Copy buttons allow filename and hash copying.
- No `Save source`, overwrite, or modify action exists.
- Annotations, fixture geometry, access envelopes, and recommendations are separate layers and separate project records.
- Source geometry appearance can be changed for visualization, but the underlying CAD remains unchanged.

## Visual layer convention

- Source assembly: neutral steel/blue-gray, 100% identity preserved.
- Selected source reference: FXD Blue outline/highlight.
- Generated fixture geometry: FXD Orange family with object-specific value/lightness changes.
- Validation warning geometry: Warning hatch/outline.
- Collision/failure geometry: Fail outline and measured callout.
- Access envelopes: translucent blue/cyan with edge line.
- Annotations: label leader plus icon; never baked into source geometry.
