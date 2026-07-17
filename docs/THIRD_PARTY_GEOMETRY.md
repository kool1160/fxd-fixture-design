# Third-party geometry runtime

FXD pins `cadquery-ocp==7.9.3.1.1` in `requirements-kernel.txt`.

## OCP binding

- Distribution: `cadquery-ocp`
- Pinned release: `7.9.3.1.1`
- Purpose: thin Python bindings for Open CASCADE Technology
- Binding license: Apache License 2.0
- Supported Python range published by the package: Python 3.10 through 3.14
- Published wheels include Windows x86-64, Linux x86-64/AArch64, and macOS x86-64/ARM64

## Open CASCADE Technology runtime

The OCP wheels contain the underlying OCCT runtime. OCCT is distributed under
GNU LGPL 2.1 with the Open CASCADE exception. Packaging work must retain the
applicable copyright notices, license text, exception text, and the user's
ability to replace or relink covered dynamic libraries as required by the
license terms.

## FXD policy

- OCP objects remain inside `fxd_geometry.kernel.OcpKernel`.
- Vendor/kernel objects must not leak into annotations, fixture rules, AI
  prompts, saved neutral projects, or CAD connectors.
- The pinned version may change only through a reviewed dependency update with
  real geometry regression tests.
- Source CAD remains immutable.
- AABB geometry remains an explicitly named test double and cannot satisfy a
  real-kernel release gate.
- Production packaging must include a generated third-party notice and copies
  of the applicable Apache-2.0 and OCCT LGPL-exception license materials.

This record approves engineering development use of the pinned runtime. A
separate packaging review is still required before distributing an installer.

## PySide6 desktop runtime

FXD pins `PySide6==6.8.3` in `requirements-desktop.txt` for the local Windows
application shell and native VTK child-window host.

- Distribution: `PySide6`, including Shiboken, Essentials, and Addons wheels
- Purpose: Qt 6 desktop widgets and the native VTK integration boundary
- License options published by Qt: LGPLv3, GPLv3, or commercial Qt licensing
- FXD development use: LGPLv3-compatible dynamic-library use

An installer or commercial distribution requires a separate packaging and
legal review. It must preserve applicable notices and license text and must
not prevent replacement of covered dynamic libraries. This repository does
not accept a commercial Qt agreement or redistribute Qt binaries by adding
the development dependency.
