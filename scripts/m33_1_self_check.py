"""Offline M33.1 reconstruction/mode/persistence proof using synthetic OCP data."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxd_geometry import (  # noqa: E402
    AnnotationRole, ExecutionMode, GeometryReference, InteractiveWorkflow,
    OcpKernel, ProcessSetup, TopologyCounts, Vec3, execute_design_mode, face_annotation,
    load_step_for_workbench, orientation_from_faces,
    product_from_workbench_document,
)
from fxd_geometry.project import FxdProject  # noqa: E402


def synthetic_workflow():
    kernel = OcpKernel()
    source = kernel.export_step(kernel.make_box((0, 0, 0), (120, 80, 8)))
    document = load_step_for_workbench(source, source_name="m33-1-self-check.step")
    product = product_from_workbench_document(document)
    component = product.components[0]
    kernel_component = document.assembly.components[0]
    bottom = kernel_component.faces[0]
    front = next(face for face in kernel_component.faces if abs(sum(
        left * right for left, right in zip(bottom.normal, face.normal)
    )) < 0.1)
    bottom_ref = GeometryReference(
        component.identity, component.bodies[0].identity, bottom.reference,
    )
    front_ref = GeometryReference(
        component.identity, component.bodies[0].identity, front.reference,
    )
    orientation = orientation_from_faces(
        document, bottom_ref, front_ref, accepted=True,
    )
    setup = ProcessSetup(
        "m33-1-self-check", fixture_type="Full weld fixture",
        manufacturing_process="MIG welding", operation_mode="Manual",
        production_quantity=10, volume_category="Low",
        fixture_lifecycle="Store and reuse",
        manufacturing_orientation=orientation,
        manufacturing_build_direction=Vec3(0, 0, 1),
        manufacturing_loading_direction=Vec3(1, 0, 0),
        manufacturing_unloading_direction=Vec3(-1, 0, 0),
    )
    weld = face_annotation(
        document, front_ref, AnnotationRole.WELD_JOINT,
        notes="Legally shareable synthetic weld intent.",
    )
    workflow = InteractiveWorkflow(
        document.source_sha256, setup, geometry_annotations=(weld,),
    )
    return source, document, workflow


def main() -> int:
    source, document, workflow = synthetic_workflow()
    outcome = execute_design_mode(
        document, workflow, ExecutionMode.DETERMINISTIC_OFFLINE,
    )
    reconstruction = outcome.project.product_reconstruction
    execution = outcome.project.ai_execution
    assert document.source_bytes == source
    assert reconstruction is not None and not reconstruction.blocked
    assert reconstruction.reconstruction_identity == reconstruction.expected_identity()
    assert len(reconstruction.bodies) == 1
    assert reconstruction.bodies[0].topology == TopologyCounts(1, 1, 6, 12)
    assert set(reconstruction.bodies[0].face_identities) == {
        item.identity for item in reconstruction.faces
    }
    assert execution is not None
    assert execution.mode == ExecutionMode.DETERMINISTIC_OFFLINE
    assert execution.request_count == 0 and not execution.request_attempted
    assert not execution.fallback_used
    with tempfile.TemporaryDirectory() as directory:
        restored = FxdProject.load(
            outcome.project.save(Path(directory) / "m33-1-self-check.fxd.json")
        )
    assert restored.product_reconstruction.to_dict() == reconstruction.to_dict()
    assert restored.ai_execution.to_dict() == execution.to_dict()
    print(json.dumps({
        "schema": "fxd-m33-1-self-check-v1",
        "source_sha256": document.source_sha256,
        "reconstruction_identity": reconstruction.reconstruction_identity,
        "component_count": len(reconstruction.components),
        "body_count": len(reconstruction.bodies),
        "face_count": len(reconstruction.faces),
        "plane_count": len(reconstruction.planes),
        "confirmed_weld_count": len(reconstruction.confirmed_weld_intent),
        "blocking_questions": reconstruction.blocker_count,
        "mode": execution.mode.value,
        "request_count": execution.request_count,
        "fallback_used": execution.fallback_used,
        "persistence": "passed",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
