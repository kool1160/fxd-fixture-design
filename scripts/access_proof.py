"""Runnable synthetic proof for Milestone 6 access findings."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_geometry import (Aabb, AccessEnvelope, EngineeringAnnotations,
                          GeometryReference, Vec3, WeldAccessRequest, WeldJoint,
                          evaluate_access, generate_fixture_primitives, import_step)

def main() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic_assembly.step"
    product = import_step(fixture_path)
    reference = GeometryReference("BRACKET_A", "BRACKET_BODY")
    annotations = EngineeringAnnotations.for_product(
        product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
        process_type="manual MIG", production_quantity=1)
    annotations = EngineeringAnnotations(**{
        **annotations.__dict__, "weld_joints": (WeldJoint("weld-1", (reference,), "manual MIG"),)
    })
    fixture = generate_fixture_primitives(product, annotations)
    analysis = evaluate_access(
        product, fixture, annotations,
        weld_requests=(WeldAccessRequest(
            "manual-weld", "weld-1",
            AccessEnvelope("manual-envelope", "manual", Aabb(Vec3(-1, -1, -1), Vec3(60, 60, 60))),
        ),),
        envelopes=(AccessEnvelope(
            "unload", "unload", Aabb(Vec3(200, 200, 200), Vec3(210, 210, 210)),
            process_data_complete=True),),
    )
    print("access findings:")
    for finding in analysis.findings:
        print(f"- {finding.severity}: {finding.code}: {finding.message}")
    print(f"blocked={analysis.blocked}; units={analysis.units}")


if __name__ == "__main__":
    main()
