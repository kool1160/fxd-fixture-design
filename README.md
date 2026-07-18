# FXD — Intelligent Fixturing Design

FXD is an AI-assisted industrial fixture-design platform for manufacturing and fabrication.

The first product focus is practical weld fixturing for sheet-metal, formed-part, plate, tube, and mixed fabricated assemblies. FXD is intended to help an engineer move from a customer assembly to an editable, manufacturable fixture concept—not merely generate a contour-matched skeleton or cradle.

## Product mission

> Import the assembly, describe the process and critical requirements, and produce fixture concepts that understand how the product is located, clamped, loaded, welded, accessed, and removed.

The long-term platform may support welding, robotic/cobot workholding, assembly, inspection, bonding, and other industrial fixture classes.

## Core principles

- CAD-neutral core with STEP as the first interchange format
- deterministic geometry and manufacturing rules for critical decisions
- AI for interpretation, planning, explanation, and concept ranking
- editable outputs rather than opaque generated geometry
- traceable design decisions and explicit assumptions
- human engineering approval before any production release
- practical manufacturing over impressive-looking but unusable geometry

## Initial target workflow

1. Import a fabricated assembly.
2. Identify components, interfaces, candidate datums, and accessible geometry.
3. Capture critical dimensions, weld locations, loading direction, process, quantity, and shop constraints.
4. Generate multiple fixture concepts optimized for cost, loading speed, or repeatability.
5. Validate locating, clamping, weld access, load/unload clearance, and manufacturability.
6. Export an editable fixture assembly, DXFs, STEP files, BOM, and setup information.

## Development model

FXD uses a milestone-driven AI Foreman workflow. The Foreman selects one backlog outcome, executes all safe implementation work, validates the repository, and opens a pull request for review. Specialist roles are defined in `docs/AGENT_ROSTER.md`.

Read these first:

1. `AGENTS.md`
2. `docs/PRODUCT_DIRECTION.md`
3. `docs/ENGINEERING_CONSTITUTION.md`
4. `BACKLOG.md`

Foreman setup is documented in `docs/FOREMAN_SETUP.md`.

## Project status

FXD is in early research and prototyping. It does not yet generate production-approved fixtures.

## Local workbench

On Windows, double-click `launch-fxd.bat` in the repository root. It uses the
repository `.venv` and does not require a PowerShell execution-policy change.
Drag a `.step` or `.stp` file onto the launcher to open it directly in FXD.

To add FXD to the desktop, right-click `launch-fxd.bat`, choose **Show more
options** if necessary, then choose **Send to > Desktop (create shortcut)**.
You can drag a STEP file onto that shortcut as well.

The PowerShell launcher remains available for command-line use:

```powershell
.\scripts\launch-fxd.ps1
```

Use **Import STEP** to load a model through the real OCP kernel into the
embedded persistent VTK viewport. The workbench is engineering-review-only
and never mutates customer source CAD.

## Baseline checks

Run `bash scripts/ci.sh` for repository health. The Milestone 1 synthetic
geometry proof is `python scripts/geometry_proof.py`; the access proof is
`python scripts/access_proof.py`. Their limitations and
candidate-kernel evaluation are recorded in `docs/GEOMETRY_STACK_SPIKE.md`.

## Rights

No open-source license is granted. Copyright © 2026 Christopher Hilton. All rights reserved. See `NOTICE.md`.
