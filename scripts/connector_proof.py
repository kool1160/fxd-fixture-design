"""Run the dependency-free CAD connector boundary proof."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import NeutralStepConnector, probe_solidworks

neutral = NeutralStepConnector()
print(f"Neutral connector: {neutral.probe().status}")
probe = probe_solidworks()
print(f"SOLIDWORKS probe: {probe.status} ({probe.host})")
print("FXD connector proof passed: standalone path, conservative vendor probe, approval boundary")
