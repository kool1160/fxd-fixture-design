"""Run the Milestone 4 deterministic primitive-generation proof."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import EngineeringAnnotations, Vec3, generate_fixture_primitives, import_step


def main() -> None:
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic_assembly.step"
    product = import_step(fixture)
    annotations = EngineeringAnnotations.for_product(
        product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
        process_type="manual MIG", production_quantity=1,
    )
    concept = generate_fixture_primitives(product, annotations)
    print("features:", ", ".join(feature.identity for feature in concept.features))
    print("units:", concept.units)
    print("findings:", ", ".join(f"{item.severity}:{item.code}" for item in concept.findings))


if __name__ == "__main__":
    main()
