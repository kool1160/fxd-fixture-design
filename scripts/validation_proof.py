#!/usr/bin/env python3
"""Run the deterministic Milestone 15 proof on synthetic assembly data."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import EngineeringAnnotations, Vec3, generate_fixture_concepts, import_step, validate_fixture_concept


product = import_step(Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic_assembly.step")
annotations = EngineeringAnnotations.for_product(
    product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
    process_type="manual MIG", production_quantity=1)
concept = generate_fixture_concepts(product, annotations).recommended
result = validate_fixture_concept(product, concept)
print(f"{result.version} {result.status} {len(result.findings)} findings {result.evidence_digest}")
for finding in result.findings:
    print(f"{finding.severity.upper():9} {finding.subsystem:14} {finding.code}: {finding.message}")
