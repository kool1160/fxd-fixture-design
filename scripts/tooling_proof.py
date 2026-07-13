from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import generic_tooling_library


selection = generic_tooling_library().select("clamp", minimum_stroke=10, minimum_force=500)
assert selection is not None
print(selection.item.identity)
print(selection.item.units, selection.item.stroke, selection.item.force)
for warning in selection.warnings:
    print(f"WARNING: {warning}")
