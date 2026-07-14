# Milestone 16 implementation evidence

The first local engineer-facing visual boundary is implemented in
`fxd_geometry.visual`. `scripts/visual_app.py` launches a dependency-free
browser review surface and accepts an optional legally shareable STEP path;
the default proof uses `tests/fixtures/synthetic_assembly.step`.

The scene contract carries product and fixture AABB evidence, stable source or
rule references, generation rules, parameters, assumptions, warnings,
validation findings, visibility layers, and explicit valid/provisional/invalid
and approval states. Pointer rotation, layer toggles, and feature suppression
or replacement operate on immutable project state. `save_project` and
`load_project` persist source STEP evidence and separate feature overrides.

Evidence: `python -m unittest tests.test_visual -v` (4 passing tests).
`bash scripts/ci.sh` was attempted but remains environment-blocked while
installing the already-pinned `cadquery-ocp==7.9.3.1.1` package because PyPI
DNS/network access is unavailable. The visual layer does not replace the real
kernel and does not claim production approval.
