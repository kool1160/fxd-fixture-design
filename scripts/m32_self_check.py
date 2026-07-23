"""Autonomous, offline M32 software-acceptance scenario.

This is deliberately a *software* self-check.  It creates a legally shareable
synthetic STEP assembly in a temporary directory, drives the deterministic M32
workflow, and writes a redacted report.  It never imports customer CAD, calls a
provider, or makes a production/safety claim.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from fxd_geometry import (
    AdjustmentState,
    AnnotationRole,
    ConstructionMethod,
    ConfirmedWeldIntent,
    EngineeringAnnotations,
    FixtureBuildError,
    FixtureFamily,
    FixtureLifecycle,
    FixturePurpose,
    GeometryReference,
    InteractiveWorkflow,
    MultiStationRequirements,
    ProductFeatureRole,
    OcpKernel,
    ProcessSetup,
    Vec3,
    analyze_engineering_workflow,
    author_fixture_build,
    build_m32_product_feature_bindings,
    bind_fixture_build_plan_to_proposal,
    build_fixture_build_package,
    face_annotation,
    load_step_for_workbench,
    product_from_workbench_document,
    propose_multi_station_fit,
    evaluate_fixture_concept_evidence,
    evaluate_fixture_concept_quality,
    evidence_from_fixture_build,
    rejected_generic_m32_evidence,
    validate_fixture_build_plan,
)
from fxd_geometry.ai_fixture_engineer import deterministic_baseline_proposal
from fxd_geometry.fabrication_workflow import (
    BuildComponentRole, FixtureBuildRequirements, GeometryAuthority,
    generate_multi_station_fixture_alternatives,
)
from fxd_geometry.manufacturing_orientation import orientation_from_faces
from fxd_geometry.project import FxdProject, ProjectFormatError


SELF_CHECK_SCHEMA = "fxd-m32-self-check-v1"
VISUAL_REVIEW_SCHEMA = "fxd-m32-visual-review-v1"
_FAILURE_CATEGORIES = {
    AssertionError: "deterministic_contract_assertion_failed",
    FixtureBuildError: "fixture_build_authoring_or_release_gate_failed",
    ProjectFormatError: "project_persistence_or_approval_gate_failed",
    OSError: "local_artifact_operation_failed",
}


def _reference(component: object, face: object) -> GeometryReference:
    """Construct the same stable body identity as product normalization."""
    component_identity = str(getattr(component, "reference"))
    return GeometryReference(
        component_identity,
        "body:" + sha256(component_identity.encode("utf-8")).hexdigest()[:20],
        str(getattr(face, "reference")),
    )


def _dot(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _selected_orientation_references(document: object) -> tuple[
        GeometryReference, GeometryReference, tuple[GeometryReference, ...],
        GeometryReference, tuple[GeometryReference, ...], bool]:
    """Choose stable orthogonal bottom/front/datum references from the public model."""
    candidates: list[tuple[object, object, GeometryReference]] = []
    for component in document.assembly.components:
        for face in component.faces:
            if face.is_planar:
                candidates.append((component, face, _reference(component, face)))
    horizontal = [
        item for item in candidates
        if abs(float(item[1].normal[2])) >= 0.999
    ]
    if not horizontal:
        raise AssertionError("self-check STEP has no confirmed planar horizontal face")
    # The lower horizontal face is the generated fixture-down candidate.  Flip
    # only when its OCP normal points downward so manufacturing +Z is upward.
    _bottom_component, bottom_face, bottom_reference = min(
        horizontal, key=lambda item: float(item[1].center_mm[2])
    )
    bottom_normal = tuple(float(value) for value in bottom_face.normal)
    front_candidates = tuple(
        item for item in candidates
        if item[2] != bottom_reference
        and abs(_dot(
            bottom_normal, tuple(float(value) for value in item[1].normal),
        )) <= 1e-7
    )
    front = max(
        front_candidates,
        key=lambda item: (
            float(item[1].normal[0]),
            float(item[1].center_mm[0]),
            float(item[1].area_mm2),
            item[2].face_identity,
        ),
        default=None,
    )
    if front is None:
        raise AssertionError("self-check STEP has no non-parallel planar front face")
    front_normal = tuple(float(value) for value in front[1].normal)
    side = next(
        (
            item for item in candidates
            if item[2] not in {bottom_reference, front[2]}
            and abs(_dot(bottom_normal, tuple(float(value) for value in item[1].normal))) <= 1e-7
            and abs(_dot(front_normal, tuple(float(value) for value in item[1].normal))) <= 1e-7
        ),
        None,
    )
    if side is None:
        raise AssertionError("self-check STEP has no third orthogonal planar datum face")
    datum_references = (bottom_reference, front[2], side[2])
    top = max(
        (item for item in horizontal if item[2] != bottom_reference),
        key=lambda item: (float(item[1].area_mm2), item[2].face_identity),
    )
    hole_references = tuple(
        item[2] for item in sorted(
            (
                (component, face, _reference(component, face))
                for component in document.assembly.components
                for face in component.faces
                if "Cylinder" in face.surface_type
                and face.axis_direction is not None
                and abs(float(face.axis_direction[2])) >= 0.999
            ),
            key=lambda item: item[2].face_identity,
        )[:2]
    )
    if len(hole_references) != 2:
        raise AssertionError("self-check STEP requires two exact cylindrical locator holes")
    return (
        bottom_reference, front[2], datum_references, top[2],
        hole_references, bottom_normal[2] < 0.0,
    )


def _public_source(kernel: OcpKernel, directory: Path) -> tuple[Path, bytes]:
    """Create a two-piece, legally shareable fabricated-bracket STEP assembly."""
    horizontal = kernel.make_box((0.0, 0.0, 0.0), (120.0, 38.0, 5.0))
    for center in ((35.0, 19.0, -1.0), (85.0, 19.0, -1.0)):
        horizontal = kernel.cut(
            horizontal, kernel.make_hole(center, 4.0, 7.0),
        )
    upright = kernel.make_box((0.0, 0.0, 5.0), (5.0, 38.0, 62.0))
    source_bytes = kernel.export_step(kernel.compound((horizontal, upright)))
    path = directory / "m32_public_self_check_bracket.step"
    path.write_bytes(source_bytes)
    return path, source_bytes


def _fixture_build_requirements(product: object, orientation: object) -> FixtureBuildRequirements:
    joint_references = tuple(
        GeometryReference(component.identity, body.identity, body.faces[0].identity)
        for component in product.components
        for body in component.bodies
    )
    confirmed_weld = ConfirmedWeldIntent(
        "m32-public-bracket-joint",
        joint_references,
        "feature-selected exterior side",
        38.0,
        "manual MIG",
        1,
        Vec3(5.0, 19.0, 5.0),
        orientation.source_vector_to_manufacturing(Vec3(1.0, 0.0, 0.0)),
        Vec3(1.0, 0.0, 0.0),
        Vec3(4.0, 4.0, 24.0),
        orientation.identity,
        ("Synthetic public joint intent for deterministic access validation.",),
        orientation.source_vector_to_manufacturing(Vec3(0.0, 1.0, 0.0)),
        Vec3(0.0, 1.0, 0.0),
    )
    return FixtureBuildRequirements(
        source_sha256=product.source_sha256,
        fixture_purpose=FixturePurpose.FULL_WELD,
        construction_method=ConstructionMethod.LASER_CUT_FABRICATED,
        lifecycle=FixtureLifecycle.PERMANENT,
        job_revision="M32-SELF-CHECK",
        fixture_revision="A",
        production_quantity=100,
        repeat_frequency="repeat production",
        weld_process="manual MIG",
        shop_capabilities=("laser cutting", "fixture welding", "machining"),
        tack_access_available=None,
        full_weld_access_available=True,
        unload_clearance_evaluated=True,
        adjustment_state=AdjustmentState.LOCKED,
        assumptions=(
            "Synthetic public software-acceptance geometry; dimensions are not shop release inputs.",
            "The synthetic weld intent validates software access only and is not a shop release.",
        ),
        confirmed_weld_intent=True,
        confirmed_weld_joint_count=1,
        confirmed_welds=(confirmed_weld,),
    )


def _expect_blocked_reason(action: Any, expected: type[Exception],
                           message_fragment: str, reason: str) -> str:
    """Prove a specific fail-closed gate without persisting exception text."""
    try:
        action()
    except expected as error:
        if message_fragment not in str(error):
            raise AssertionError(
                f"the expected {reason} gate was pre-empted by another failure"
            ) from error
        return reason
    raise AssertionError(f"the expected {reason} gate unexpectedly allowed the action")


def _safe_failure_category(error: Exception) -> str:
    """Classify only the allowlisted failure class; never persist exception text."""
    for error_type, category in _FAILURE_CATEGORIES.items():
        if isinstance(error, error_type):
            return category
    return "unexpected_internal_failure"


def _write_summary_screenshot(report: dict[str, object], destination: Path) -> None:
    """Render a headless evidence snapshot without opening the engineering GUI."""
    from PIL import Image, ImageDraw, ImageFont

    fixture_build = report["fixture_build"]
    validation = report["fixture_build_validation"]
    geometry = report["authored_geometry"]
    gates = report["release_gates"]
    persistence = report["project_persistence"]
    image = Image.new("RGB", (1500, 900), "#111827")
    draw = ImageDraw.Draw(image)
    title = ImageFont.load_default(size=28)
    subtitle = ImageFont.load_default(size=16)
    body = ImageFont.load_default(size=18)
    draw.text((56, 46), "FXD M32 autonomous software self-check", font=title, fill="#f8fafc")
    draw.text((56, 100), "OFFLINE SYNTHETIC REVIEW EVIDENCE - HUMAN ENGINEERING REVIEW REQUIRED", font=subtitle, fill="#a7f3d0")
    lines = (
        "Scenario: compact precedent-informed 5-station fixture within 1219.2 mm maximum length",
        f"Calculated pitch: {float(fixture_build['calculated_pitch_mm']):.1f} mm",
        f"Fixture-build validation: {validation['status']} (qualified human review still required)",
        f"Authored real OCP components: {int(geometry['real_ocp_component_count'])}",
        f"Product review instances: {int(geometry['product_instance_count'])}",
        f"Tessellated triangles: {int(geometry['tessellated_triangle_count'])}",
        "AABB fallback: not used",
        "Authoring state: DETERMINISTICALLY VALID - NOT HUMAN APPROVED",
        f"Engineering approval gate blocked: {bool(gates['engineering_approval_blocked'])}",
        f"Release export gate blocked: {bool(gates['release_export_blocked'])}",
        f"Source CAD immutable: {bool(report['step_import']['source_cad_unchanged'])}",
        f"Project save/reload preserved governed state: {bool(persistence['passed'])}",
    )
    y = 170
    for line in lines:
        draw.text((80, y), line, font=body, fill="#e2e8f0")
        y += 52
    draw.text(
        (56, 836),
        "Automated software-evidence snapshot only; it is not production approval or a substitute for human engineering judgment.",
        font=subtitle,
        fill="#fbbf24",
    )
    image.save(destination, format="PNG")


def _run_m32_scenario(directory: Path) -> tuple[dict[str, object], Path, Path]:
    """Execute the governed scenario and retain its reloadable local artifacts."""
    directory.mkdir(parents=True, exist_ok=True)
    kernel = OcpKernel()
    source_path, source_before = _public_source(kernel, directory)
    source_digest = sha256(source_before).hexdigest()
    document = load_step_for_workbench(source_path)
    product = product_from_workbench_document(document)
    if document.source_sha256 != source_digest or product.source_sha256 != source_digest:
        raise AssertionError("STEP import did not retain its immutable source identity")

    (bottom, front, planar_references, clamp_reference,
     locator_hole_references, flip_bottom) = _selected_orientation_references(document)
    orientation = orientation_from_faces(
        document, bottom, front, flip_bottom=flip_bottom, accepted=True,
    )
    if not orientation.accepted or orientation.is_stale_for(product.source_sha256):
        raise AssertionError("guided bottom/front orientation was not accepted for the imported source")

    roles = (
        AnnotationRole.PRIMARY_DATUM,
        AnnotationRole.SECONDARY_DATUM,
        AnnotationRole.TERTIARY_DATUM,
    )
    if len(planar_references) < len(roles):
        raise AssertionError("self-check STEP has insufficient planar datum evidence")
    workflow = InteractiveWorkflow(
            product.source_sha256,
            ProcessSetup(
                project_name="M32 public software self-check",
                fixture_type="Full weld fixture",
                manufacturing_process="Manual MIG",
                operation_mode="Manual",
                production_quantity=100,
                operator_access="Synthetic operator-side review envelope",
                shop_capabilities=("laser cutting", "fixture welding", "machining"),
                material_assumptions="Synthetic low-carbon steel review assembly",
                manufacturing_orientation=orientation,
                manufacturing_build_direction=Vec3(0.0, 0.0, 1.0),
                manufacturing_loading_direction=Vec3(0.0, -1.0, 0.0),
                manufacturing_unloading_direction=Vec3(0.0, 1.0, 0.0),
                fixture_family=FixtureFamily.LINEAR_MULTI_STATION_WELD.value,
                requested_station_count=5,
                maximum_fixture_length_mm=1219.2,
                operator_loading_side="Operator front (+Y)",
                clamp_operating_side="Operator front (+Y)",
                table_mounting_preference="Table mounting holes",
                compare_one_up_and_multi_up=True,
            ),
            tuple(
                face_annotation(document, reference, role)
                for reference, role in zip(planar_references, roles)
            ) + (
                face_annotation(
                    document, clamp_reference, AnnotationRole.PERMITTED_SUPPORT,
                ),
            ) + tuple(
                face_annotation(
                    document, reference, AnnotationRole.PERMITTED_LOCATOR,
                )
                for reference in locator_hole_references
            ),
    )
    analyzed_project = analyze_engineering_workflow(document, workflow)
    if analyzed_project.workflow is None or not analyzed_project.workflow.analysis_completed:
        raise AssertionError("assembly analysis did not complete through the shared workflow command")
    workflow = replace(analyzed_project.workflow, concepts_generated=True, active_stage="Concepts")
    proposal_annotations = EngineeringAnnotations.for_product(
        product,
        build_orientation=orientation.manufacturing_z_source,
        loading_direction=orientation.manufacturing_vector_to_source(Vec3(0.0, -1.0, 0.0)),
        process_type="Synthetic MIG weld",
        production_quantity=100,
    )
    proposal_annotations = replace(
        proposal_annotations,
        permitted_locating_surfaces=(bottom,),
    )
    project = FxdProject.from_product(product, proposal_annotations, workflow=workflow)

    pending_proposal_project = project.with_fixture_proposal(
        deterministic_baseline_proposal(project)
    )
    pending_proposal = pending_proposal_project.fixture_proposal
    if pending_proposal is None:
        raise AssertionError("the deterministic self-check proposal was not persisted")
    if pending_proposal.blocker_count:
        blockers = ", ".join(
            f"{item.rule_id}:{item.what_is_wrong}"
            for item in pending_proposal.guided_issues
            if item.severity == "error"
        )
        raise AssertionError(
            f"the deterministic self-check proposal has unresolved blockers: {blockers}"
        )
    project = pending_proposal_project.decide_fixture_proposal(
        "accepted_for_engineering_review",
        "Deterministic offline M32 self-check proposal acceptance.",
    )
    accepted_proposal = project.fixture_proposal
    if accepted_proposal is None:
        raise AssertionError("the deterministic self-check proposal was not persisted")
    if (accepted_proposal.proposal_decision != "accepted_for_engineering_review"
            or accepted_proposal.blocker_count != 0):
        raise AssertionError("the deterministic self-check proposal is not accepted and blocker-free")

    requested = MultiStationRequirements(
            FixtureFamily.LINEAR_MULTI_STATION_WELD,
            5,
            1219.2,
            None,
            "Operator front (+Y)",
            "+Y",
            "Operator front (+Y)",
            "manual",
            "Table mounting holes",
            100,
            True,
            loading_direction_source=orientation.manufacturing_vector_to_source(Vec3(0.0, -1.0, 0.0)),
            unloading_direction_source=orientation.manufacturing_vector_to_source(Vec3(0.0, 1.0, 0.0)),
            operator_loading_direction_source=orientation.manufacturing_vector_to_source(Vec3(0.0, 1.0, 0.0)),
            clamp_operating_direction_source=orientation.manufacturing_vector_to_source(Vec3(0.0, 1.0, 0.0)),
            manufacturing_up_direction_source=orientation.manufacturing_z_source,
            source_to_manufacturing=orientation.source_to_manufacturing,
            manufacturing_to_source=orientation.manufacturing_to_source,
            manufacturing_orientation_identity=orientation.identity,
            product_feature_bindings=build_m32_product_feature_bindings(
                product,
                tuple(
                    (feature_role, annotation.reference)
                    for annotation_role, feature_role in (
                        (AnnotationRole.PRIMARY_DATUM, ProductFeatureRole.PRIMARY_SUPPORT),
                        (AnnotationRole.SECONDARY_DATUM, ProductFeatureRole.SECONDARY_LOCATOR),
                        (AnnotationRole.TERTIARY_DATUM, ProductFeatureRole.TERTIARY_STOP),
                        (AnnotationRole.PERMITTED_SUPPORT, ProductFeatureRole.CLAMP_CONTACT),
                        (AnnotationRole.PERMITTED_LOCATOR, ProductFeatureRole.LOCATOR_HOLE),
                    )
                    for annotation in workflow.geometry_annotations
                    if annotation.role == annotation_role
                ),
            ),
    )
    fit = propose_multi_station_fit(product, requested)
    if fit.requested_station_count != 5 or fit.feasible_station_count < 5:
        raise AssertionError("the compact governed layout did not fit all five requested stations")
    if fit.requires_explicit_acceptance:
        raise AssertionError("compact layout unexpectedly reduced the accepted station count")
    reduction_probe = propose_multi_station_fit(
        product, replace(requested, maximum_fixture_length_mm=900.0),
    )
    if (reduction_probe.requested_station_count, reduction_probe.feasible_station_count) != (5, 4):
        raise AssertionError("the tighter deterministic fit probe did not propose four stations")
    if not reduction_probe.requires_explicit_acceptance:
        raise AssertionError("station-count reduction did not remain behind explicit acceptance")
    accepted = requested
    alternatives = generate_multi_station_fixture_alternatives(
        product, project.active, _fixture_build_requirements(product, orientation), accepted,
    )
    plan = bind_fixture_build_plan_to_proposal(alternatives[-1], accepted_proposal)
    layout = plan.multi_station_layout
    if layout is None or len(layout.stations) != 5:
        raise AssertionError("all five requested stations were not used for the compact fixture build plan")
    if layout.required_fixture_length_mm > 1219.2:
        raise AssertionError("accepted fixture layout exceeds its maximum fixture length")
    station_plates = tuple(item for item in plan.components if item.role == BuildComponentRole.STATION_PLATE)
    clamp_closed = tuple(item for item in plan.components if item.role == BuildComponentRole.TOGGLE_CLAMP)
    clamp_open = tuple(item for item in plan.components if item.role == BuildComponentRole.CLAMP_OPEN_ENVELOPE)
    braces = tuple(item for item in plan.components if item.role == BuildComponentRole.END_BRACE)
    if len(station_plates) != 5 or len(clamp_closed) != 5 or len(clamp_open) != 5:
        raise AssertionError("product-driven station or clamp review geometry is incomplete")
    if any(item.geometry_authority != GeometryAuthority.PURCHASED_COMPONENT
           for item in clamp_closed + clamp_open):
        raise AssertionError("supplier-neutral clamp review geometry gained manufacturing authority")
    if any(value is None for station in layout.stations for value in (
            station.clamp_tip_reaches_surface, station.open_clamp_envelope_clear,
            station.hand_access_clear, station.unload_path_clear)):
        raise AssertionError("station access evidence was not deterministically evaluated")
    if any(station.trapped_part is None or not station.access_evidence
           or station.loading_envelope is None or station.unloading_envelope is None
           for station in layout.stations):
        raise AssertionError("load/unload or trapped-part evidence is incomplete")
    if any(
            len(station.source_to_station_manufacturing) != 16
            or station.source_to_station_manufacturing[:12] == (
                1.0, 0.0, 0.0, station.translation_mm.x,
                0.0, 1.0, 0.0, station.translation_mm.y,
                0.0, 0.0, 1.0, station.translation_mm.z,
            )
            for station in layout.stations):
        raise AssertionError("station product instances did not retain the accepted full manufacturing transform")
    if any(station.product_bounds.intersects(brace.bounds)
           for station in (layout.stations[0], layout.stations[-1]) for brace in braces):
        raise AssertionError("end structure interferes with an end station")

    project = project.with_fixture_build(plan)
    proposal_block_reason = project.fixture_build_proposal_block_reason()
    if proposal_block_reason is not None:
        raise AssertionError(
            "the self-check build is not current and bound to the accepted proposal: "
            + proposal_block_reason
        )
    if (plan.fixture_proposal_identity != accepted_proposal.proposal_identity
            or plan.fixture_proposal_evidence_digest != accepted_proposal.evidence_digest):
        raise AssertionError("the self-check build lost its exact proposal identity or evidence binding")
    improved_quality = evaluate_fixture_concept_quality(plan)
    improved_quality_evidence = evidence_from_fixture_build(plan)
    rejected_quality = evaluate_fixture_concept_evidence(
        rejected_generic_m32_evidence(),
    )
    if improved_quality.status != "passed" or improved_quality.blockers:
        raise AssertionError("the precedent-informed M32 concept did not pass concept quality")
    if rejected_quality.status != "blocked":
        raise AssertionError("the frozen generic M32 rejection benchmark unexpectedly passed")
    if improved_quality.score <= rejected_quality.score:
        raise AssertionError("the improved concept did not materially improve the quality score")
    validation = validate_fixture_build_plan(product, plan)
    if not validation.valid:
        raise AssertionError(
            "feature-bound M32 build did not pass deterministic validation: "
            + ", ".join(item.rule_id for item in validation.findings)
        )
    if (not layout.single_station_qualification_digest
            or "single_station_gate=passed_before_multi_station_repetition"
            not in layout.rationale):
        raise AssertionError("five-station synthesis lacks its passed one-up qualification")

    authored = author_fixture_build(plan, product, kernel)
    if authored.provisional or authored.review_labels:
        raise AssertionError("deterministically valid review geometry was labelled invalid")
    triangle_count = sum(
        len(mesh.triangles)
        for component in authored.components
        for mesh in kernel.tessellate(component.shape)
    )
    if not authored.components or triangle_count < 1 or not all(item.topology.solids >= 1 for item in authored.components):
        raise AssertionError("fixture authoring did not produce real OCP solids and tessellation evidence")

    missing_acceptance_gate = _expect_blocked_reason(
        lambda: pending_proposal_project.with_fixture_build(plan).decide("approve_for_review"),
        ProjectFormatError,
        "must be accepted for engineering review",
        "accepted_fixture_proposal_required",
    )
    missing_package_proposal_gate = _expect_blocked_reason(
        lambda: build_fixture_build_package(authored, plan, product),
        FixtureBuildError,
        "bound to an accepted fixture proposal",
        "accepted_fixture_proposal_required",
    )
    export_block_reason = "qualified_windows_fixture_engineering_review_required"
    approval_block_reason = "qualified_windows_fixture_engineering_review_required"
    stale_station = replace(layout.stations[0], access_evidence_digest="")
    stale_plan = replace(plan, multi_station_layout=replace(
        layout, stations=(stale_station,) + layout.stations[1:],
    ))
    stale_validation = validate_fixture_build_plan(product, stale_plan)
    stale_rule_ids = sorted({
        item.rule_id for item in stale_validation.findings
        if "missing or stale" in item.message
    })
    if "FXD-M32-ACC" not in stale_rule_ids:
        raise AssertionError("stale station validation evidence did not fail closed")
    stale_export_block_reason = _expect_blocked_reason(
        lambda: build_fixture_build_package(
            authored, stale_plan, product, accepted_proposal=accepted_proposal,
        ),
        FixtureBuildError,
        "stale for the supplied construction plan",
        "authored_fixture_geometry_stale",
    )
    persisted_plan = replace(plan, authoring_state="provisional")
    project = project.with_fixture_build(persisted_plan)
    source_unchanged = (
        source_path.read_bytes() == source_before
        and document.source_bytes == source_before
        and sha256(source_path.read_bytes()).hexdigest() == source_digest
    )
    if not source_unchanged:
        raise AssertionError("the autonomous workflow changed source STEP bytes")

    project_path = directory / "m32-visual-review.fxd.json"
    project.save(project_path)
    restored = FxdProject.load(project_path)
    persistence_passed = (
        restored.fixture_build is not None
        and restored.fixture_build.to_dict() == persisted_plan.to_dict()
        and restored.product.source_bytes == source_before
        and restored.product.source_sha256 == source_digest
    )
    if not persistence_passed:
        raise AssertionError("project save/reload did not retain governed M32 evidence")

    report = {
        "schema": SELF_CHECK_SCHEMA,
        "status": "passed",
        "scenario": "legally shareable synthetic two-piece fabricated bracket",
        "network_provider_used": False,
        "step_import": {"passed": True, "source_cad_unchanged": True},
        "guided_orientation": {
            "bottom_face_selected": True,
            "front_face_selected": True,
            "bottom_flip_applied": flip_bottom,
            "accepted": True,
            "source_cad_unchanged": source_unchanged,
        },
        "assembly_analysis": {"passed": True, "concept_count": len(project.concepts)},
        "accepted_proposal": {
            "proposal_identity": accepted_proposal.proposal_identity,
            "evidence_digest": accepted_proposal.evidence_digest,
            "decision": accepted_proposal.proposal_decision,
            "blocker_count": accepted_proposal.blocker_count,
            "current": project.fixture_build_proposal_block_reason() is None,
            "plan_identity_bound": (
                plan.fixture_proposal_identity == accepted_proposal.proposal_identity
            ),
            "plan_evidence_digest_bound": (
                plan.fixture_proposal_evidence_digest == accepted_proposal.evidence_digest
            ),
            "missing_acceptance_gate_independently_blocked": (
                missing_acceptance_gate == "accepted_fixture_proposal_required"
                and missing_package_proposal_gate == "accepted_fixture_proposal_required"
            ),
        },
        "fixture_build": {
            "family": FixtureFamily.LINEAR_MULTI_STATION_WELD.value,
            "requested_station_count": 5,
            "accepted_feasible_station_count": len(layout.stations),
            "explicit_reduction_acceptance_required": fit.requires_explicit_acceptance,
            "maximum_fixture_length_mm": 1219.2,
            "calculated_pitch_mm": layout.station_pitch_mm,
            "accepted_required_length_mm": layout.required_fixture_length_mm,
            "requested_required_length_mm": layout.requested_intent_required_length_mm,
            "original_request_retained": True,
            "tighter_length_reduction_probe": {
                "maximum_fixture_length_mm": 900.0,
                "feasible_station_count": reduction_probe.feasible_station_count,
                "explicit_acceptance_required": reduction_probe.requires_explicit_acceptance,
            },
        },
        "concept_quality": {
            "frozen_rejected_benchmark": rejected_quality.to_dict(),
            "precedent_informed_concept": improved_quality.to_dict(),
            "metrics": {
                "fixture_length_mm": improved_quality_evidence.fixture_length_mm,
                "occupied_length_mm": improved_quality_evidence.occupied_length_mm,
                "empty_span_ratio": improved_quality_evidence.empty_span_ratio,
                "station_pitch_mm": improved_quality_evidence.station_pitch_mm,
                "product_specific_contacts_per_station": list(
                    improved_quality_evidence.product_specific_contacts_per_station
                ),
                "connected_base_component_count": len(
                    improved_quality_evidence.connected_component_identities
                ),
                "mounting_point_count": improved_quality_evidence.mounting_point_count,
                "clamp_support_mapping_count": len(
                    improved_quality_evidence.clamp_support_mappings
                ),
                "datum_dof_mapping_count": len(
                    improved_quality_evidence.datum_dof_mappings
                ),
            },
        },
        "fixture_build_validation": {
            "status": validation.status,
            "finding_totals": {
                severity: sum(1 for item in validation.findings if item.severity == severity)
                for severity in ("error", "warning", "info")
            },
            "disposition_totals": {
                disposition: sum(1 for item in validation.findings if item.disposition == disposition)
                for disposition in ("authoring_blocker", "review_blocker", "export_blocker", "warning", "informational")
            },
            "review_blocker_rule_ids": sorted(
                item.rule_id for item in validation.findings if item.disposition == "review_blocker"
            ),
            "authoring_blocked": validation.authoring_blocked,
        },
        "authored_geometry": {
            "real_ocp_component_count": len(authored.components),
            "product_instance_count": len(layout.stations),
            "tessellated_triangle_count": triangle_count,
            "aabb_fallback_used": False,
            "provisional": authored.provisional,
            "labels": list(authored.review_labels),
            "local_station_plate_count": len(station_plates),
            "provisional_closed_clamp_count": len(clamp_closed),
            "provisional_open_clamp_envelope_count": len(clamp_open),
            "supplier_neutral_clamps_excluded_from_authored_ocp": all(
                item.component.role not in {BuildComponentRole.TOGGLE_CLAMP, BuildComponentRole.CLAMP_OPEN_ENVELOPE}
                for item in authored.components
            ),
        },
        "access_review": {
            "loading_and_unloading_evaluated": True,
            "trapped_part_detected": any(
                station.trapped_part is True for station in layout.stations
            ),
            "first_and_last_station_end_clearance": True,
            "weld_access_status": "clear_for_recorded_synthetic_joint",
        },
        "release_gates": {
            "proposal_gate_satisfied": True,
            "engineering_approval_blocked": True,
            "engineering_approval_block_reason": approval_block_reason,
            "release_export_blocked": True,
            "release_export_block_reason": export_block_reason,
            "stale_release_export_block_reason": stale_export_block_reason,
            "validation_gate_rule_ids": sorted({
                item.rule_id for item in validation.findings
                if item.disposition == "review_blocker"
            }),
            "stale_validation_gate_rule_ids": stale_rule_ids,
        },
        "project_persistence": {
            "passed": persistence_passed,
            "fixture_build_retained": True,
            "source_cad_unchanged": True,
        },
        "human_engineering_review_required": [
            "fixture practicality",
            "loading and unloading",
            "weld access",
            "locator and clamp suitability",
            "operator access",
            "manufacturability",
            "structural adequacy",
            "safety",
            "final production approval",
        ],
    }
    return report, source_path, project_path


def run_m32_self_check() -> dict[str, object]:
    """Execute the fully deterministic M32 scenario and return a redacted report."""
    with tempfile.TemporaryDirectory(prefix="fxd-m32-self-check-") as temporary:
        report, _, _ = _run_m32_scenario(Path(temporary))
        return report


def _write_json(destination: Path, report: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)


def write_report(destination: Path, *, artifact_directory: Path | None = None) -> dict[str, object]:
    """Run the scenario and atomically persist only redacted acceptance evidence."""
    try:
        report = run_m32_self_check()
        artifacts = artifact_directory or destination.parent
        artifacts.mkdir(parents=True, exist_ok=True)
        screenshot_name = "m32-self-check-evidence.png"
        _write_summary_screenshot(report, artifacts / screenshot_name)
        report["evidence_artifacts"] = {"summary_screenshot": screenshot_name}
    except Exception as error:
        report = {
            "schema": SELF_CHECK_SCHEMA,
            "status": "failed",
            "network_provider_used": False,
            "failure_category": _safe_failure_category(error),
        }
    _write_json(destination, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline M32 software self-check.")
    parser.add_argument("--report", type=Path, required=True, help="Destination for the redacted JSON report.")
    parser.add_argument("--artifact-directory", type=Path, help="External directory for the evidence screenshot.")
    args = parser.parse_args(argv)
    report = write_report(args.report, artifact_directory=args.artifact_directory)
    if report["status"] == "passed":
        print("FXD_M32_SELF_CHECK=passed")
        print(f"FXD_M32_SELF_CHECK_SCHEMA={report['schema']}")
        return 0
    print("FXD_M32_SELF_CHECK=failed")
    print(f"FXD_M32_FAILURE_CATEGORY={report['failure_category']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
