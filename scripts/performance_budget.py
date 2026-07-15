#!/usr/bin/env python3
"""Measure the neutral synthetic workflow used for the Milestone 20 budget."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fxd_geometry import EngineeringAnnotations, Vec3, generate_fixture_concepts, import_step


def main() -> None:
    source = ROOT / "tests/fixtures/synthetic_assembly.step"
    started = time.perf_counter()
    product = import_step(source)
    annotations = EngineeringAnnotations.for_product(
        product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
        process_type="manual MIG", production_quantity=1)
    concepts = generate_fixture_concepts(product, annotations)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    result = {"fixture": "synthetic_assembly.step", "components": len(product.components),
              "concepts": len(concepts.concepts), "elapsed_ms": elapsed_ms,
              "budget_ms": 1000, "status": "pass" if elapsed_ms <= 1000 else "fail",
              "kernel": "neutral-proof"}
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit("neutral performance budget exceeded")


if __name__ == "__main__":
    main()
