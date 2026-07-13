#!/usr/bin/env python3
"""Run the synthetic fabrication-package export proof."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import (EngineeringAnnotations, Vec3, build_fabrication_package,
                          generate_fixture_concepts, import_step, write_fabrication_package)


product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
annotations = EngineeringAnnotations.for_product(
    product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
    process_type="MIG", production_quantity=1)
concept = generate_fixture_concepts(product, annotations).recommended
package = build_fabrication_package(concept, "A")
output = Path("/tmp/fxd-fabrication-package-proof")
paths = write_fabrication_package(package, output)
print(f"wrote {len(paths)} deterministic review artifacts to {output}")
print("status=engineering_review_required production_approval=false")
