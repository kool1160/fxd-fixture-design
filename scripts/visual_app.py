#!/usr/bin/env python3
"""Launch the local FXD engineering review application on synthetic evidence."""
from pathlib import Path
import sys
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fxd_geometry import (EngineeringAnnotations, Vec3, VisualProject,
    generate_fixture_concepts, import_step, serve, validate_fixture_concept)

parser = argparse.ArgumentParser(description="Launch the local FXD engineering review application")
parser.add_argument("step", nargs="?", help="legally shareable neutral STEP input")
args = parser.parse_args()
fixture = Path(args.step) if args.step else Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic_assembly.step"
product = import_step(fixture)
annotations = EngineeringAnnotations.for_product(product, build_orientation=Vec3(0, 0, 1),
    loading_direction=Vec3(1, 0, 0), process_type="manual MIG", production_quantity=1)
concept = generate_fixture_concepts(product, annotations).recommended
validation = validate_fixture_concept(product, concept)
server = serve(VisualProject(product, concept, validation))
print(f"FXD review application: http://{server.server_address[0]}:{server.server_address[1]}")
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.server_close()
