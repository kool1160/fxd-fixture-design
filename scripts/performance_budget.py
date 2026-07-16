#!/usr/bin/env python3
"""Measure a legally shareable large synthetic assembly against Milestone 20 budgets."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fxd_geometry import EngineeringAnnotations, Vec3, generate_fixture_concepts, import_step


INSTANCE_COUNT = 250
IMPORT_AND_CONCEPT_BUDGET_MS = 5000


def large_synthetic_step(instance_count: int = INSTANCE_COUNT) -> str:
    """Build public synthetic STEP-shaped evidence with repeated placed components."""
    if instance_count < 100:
        raise ValueError("large-assembly evidence requires at least 100 instances")
    lines = [
        "ISO-10303-21;", "HEADER;",
        "FILE_DESCRIPTION(('FXD large synthetic assembly'),'2;1');", "ENDSEC;", "DATA;",
        "#1=PRODUCT('ROOT','Root assembly','','');",
        "#2=PRODUCT('BRACKET','Repeated bracket','','');",
        "#3=SI_UNIT(.MILLI.,.METRE.);",
        "#4=FXD_BODY('BRACKET_BODY','BRACKET',0,0,0,10,20,5);",
        "#5=FXD_FACE('BRACKET_BODY','TOP_FACE');",
        "#6=FXD_EDGE('BRACKET_BODY','EDGE_A');",
        "#7=FXD_INSTANCE('ROOT_I','ROOT','',0,0,0);",
    ]
    for index in range(instance_count):
        x = (index % 25) * 25
        y = (index // 25) * 30
        lines.append(
            f"#{8 + index}=FXD_INSTANCE('BRACKET_{index:03d}','BRACKET','ROOT_I',{x},{y},0);"
        )
    lines.extend(("ENDSEC;", "END-ISO-10303-21;"))
    return "\n".join(lines) + "\n"


def measure() -> dict[str, object]:
    source = large_synthetic_step()
    started = time.perf_counter()
    product = import_step(source, source_name="large_synthetic_assembly.step")
    annotations = EngineeringAnnotations.for_product(
        product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
        process_type="manual MIG", production_quantity=100)
    concepts = generate_fixture_concepts(product, annotations)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    status = "pass" if elapsed_ms <= IMPORT_AND_CONCEPT_BUDGET_MS else "fail"
    return {
        "fixture": "generated legally shareable large_synthetic_assembly.step",
        "components": len(product.components),
        "expected_instances": INSTANCE_COUNT,
        "concepts": len(concepts.concepts),
        "elapsed_ms": elapsed_ms,
        "budget_ms": IMPORT_AND_CONCEPT_BUDGET_MS,
        "status": status,
        "kernel": "neutral-proof",
    }


def main() -> None:
    result = measure()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["components"] < INSTANCE_COUNT:
        raise SystemExit("large synthetic assembly did not preserve all component instances")
    if result["status"] != "pass":
        raise SystemExit("large-assembly performance budget exceeded")


if __name__ == "__main__":
    main()
