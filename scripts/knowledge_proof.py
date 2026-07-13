"""Run the Milestone 9 sanitized correction-record proof."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import (CorrectionRecord, EngineeringAnnotations, FixtureCorrection,
                          KnowledgeStore, Vec3, generate_fixture_concepts, import_step)


def main() -> None:
    product = import_step(Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic_assembly.step")
    annotations = EngineeringAnnotations.for_product(
        product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
        process_type="manual MIG", production_quantity=1)
    concept = generate_fixture_concepts(product, annotations).recommended
    assert concept is not None
    record = CorrectionRecord.from_concept(
        "proof-record-1", "synthetic-engineer", "2026-07-13T00:00:00Z", concept,
        FixtureCorrection("clamp_force", "review", "force data missing"),
        evidence=("synthetic review finding",))
    training = KnowledgeStore().add(record).records[0].to_training_dict()
    print("record=", record.record_id, "features=", len(record.proposed_features),
          "decision=", record.decision, "training_source_digest=", "source_digest" in training)


if __name__ == "__main__":
    main()
