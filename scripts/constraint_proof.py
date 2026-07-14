"""Runnable synthetic proof for deterministic locating analysis."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import (GeometryReference, LocatorContact, LocatingStrategy,
                          Vec3, analyze_locating_strategy, import_step)

product = import_step(Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic_assembly.step")
reference = GeometryReference("BRACKET_A", "BRACKET_BODY")
contacts = (
    LocatorContact("rest-a", "rest", reference, Vec3(0, 0, 0), Vec3(0, 0, 1)),
    LocatorContact("rest-b", "rest", reference, Vec3(20, 0, 0), Vec3(0, 0, 1)),
    LocatorContact("rest-c", "rest", reference, Vec3(0, 20, 0), Vec3(0, 0, 1)),
    LocatorContact("stop-a", "stop", reference, Vec3(0, 0, 0), Vec3(1, 0, 0)),
    LocatorContact("stop-b", "stop", reference, Vec3(0, 20, 0), Vec3(1, 0, 0)),
    LocatorContact("side", "diamond_pin", reference, Vec3(0, 0, 0), Vec3(0, 1, 0)),
)
analysis = analyze_locating_strategy(product, LocatingStrategy(
    contacts, tolerance_mm=0.1, repeatability_mm=0.05,
    datum_assumptions=("primary plane is the three rest contacts",)))
assert analysis.rank == 6 and analysis.strategy_valid
print("FXD constraint proof passed: explicit contacts, rank=6, tolerance and datum assumptions preserved")
