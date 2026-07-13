"""Run the Milestone 5 deterministic concept-generation proof."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import EngineeringAnnotations, Vec3, generate_fixture_concepts, import_step


def main() -> None:
    product = import_step(Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic_assembly.step")
    annotations = EngineeringAnnotations.for_product(
        product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
        process_type="manual MIG", production_quantity=1)
    result = generate_fixture_concepts(product, annotations)
    for concept in result.ranked:
        print(concept.identity, "score=", concept.score.total,
              "features=", len(concept.fixture.features),
              "findings=", ",".join(item.code for item in concept.fixture.findings))


if __name__ == "__main__":
    main()
