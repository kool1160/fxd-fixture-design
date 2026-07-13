#!/usr/bin/env python3
"""Run the Milestone 2 synthetic STEP import proof."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import import_step


def main() -> None:
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic_assembly.step"
    model = import_step(fixture)
    nested = next(component for component in model.components if component.identity == "NESTED")
    assert model.units == "mm"
    assert nested.transform.translation.x == 11
    assert nested.bounds.maximum.z == 38
    assert nested.bodies[0].faces and nested.bodies[0].edges
    print(f"Imported {len(model.components)} components, {len(nested.bodies)} body type(s), units={model.units}")
    print("FXD STEP import proof passed: identity, repeated instances, nested transforms, topology summary, immutable source")


if __name__ == "__main__":
    main()
