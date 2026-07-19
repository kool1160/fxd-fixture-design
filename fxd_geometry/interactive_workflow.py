"""Serializable orchestration for the interactive fixture-engineering workflow.

This module does not introduce a second engineering engine. It translates
explicit workbench inputs and real OCP face evidence into the existing
annotation, placement, concept, project, and validation contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import math
from pathlib import Path
from time import perf_counter

from .aabb import Aabb, Transform, Vec3
from .annotations import (
    Assumption, CriticalCharacteristic, EngineeringAnnotations, GeometryReference,
    WeldJoint,
)
from .manufacturing_orientation import ManufacturingOrientation, ManufacturingOrientationError
from .placement import DatumCandidate, PlacementPlan, generate_placement_plan
from .product_model import Body, Component, Face, ProductModel
from .project import FxdProject
from .workbench import WorkbenchDocument


WORKFLOW_SCHEMA = "fxd-interactive-workflow-v2"
_LEGACY_WORKFLOW_SCHEMA = "fxd-interactive-workflow-v1"


class InteractiveWorkflowError(ValueError):
    """Raised when interactive engineering evidence is incomplete or malformed."""


class AnnotationRole(str, Enum):
    PRIMARY_DATUM = "primary_datum_candidate"
    SECONDARY_DATUM = "secondary_datum_candidate"
    TERTIARY_DATUM = "tertiary_datum_candidate"
    PERMITTED_LOCATOR = "permitted_locator_surface"
    PERMITTED_SUPPORT = "permitted_support_surface"
    FORBIDDEN_CONTACT = "forbidden_contact_surface"
    CRITICAL_FEATURE = "critical_feature"
    WELD_JOINT = "weld_joint_reference"
    HEAT_SENSITIVE = "heat_sensitive_zone"
    SPATTER_SENSITIVE = "spatter_sensitive_zone"
    LOADING_OBSTRUCTION = "loading_obstruction"
    KEEP_OUT = "keep_out_region"


@dataclass(frozen=True)
class ProcessSetup:
    """Engineer-supplied process intent; ``None`` means explicitly unknown."""

    project_name: str
    fixture_type: str | None = None
    manufacturing_process: str | None = None
    operation_mode: str | None = None
    production_quantity: int | None = None
    volume_category: str | None = None
    build_orientation: Vec3 | None = None
    loading_direction: Vec3 | None = None
    unloading_direction: Vec3 | None = None
    operator_access: str | None = None
    automation_assumptions: str | None = None
    shop_capabilities: tuple[str, ...] = ()
    material_assumptions: str | None = None
    preferred_base_strategy: str | None = None
    required_repeatability_mm: float | None = None
    required_clearance_mm: float | None = None
    tooling_preferences: tuple[str, ...] = ()
    fixture_purpose: str | None = None
    construction_method: str | None = None
    fixture_lifecycle: str | None = None
    repeat_frequency: str | None = None
    job_revision: str | None = None
    cleco_strategy: str | None = None
    manufacturing_orientation: ManufacturingOrientation | None = None
    manufacturing_build_direction: Vec3 | None = None
    manufacturing_loading_direction: Vec3 | None = None
    manufacturing_unloading_direction: Vec3 | None = None
    fixture_family: str | None = None
    requested_station_count: int | None = None
    maximum_fixture_length_mm: float | None = None
    preferred_station_pitch_mm: float | None = None
    operator_loading_side: str | None = None
    clamp_operating_side: str | None = None
    table_mounting_preference: str | None = None
    compare_one_up_and_multi_up: bool = False

    def __post_init__(self) -> None:
        if not self.project_name.strip():
            raise InteractiveWorkflowError("project name is required")
        if self.production_quantity is not None and self.production_quantity < 1:
            raise InteractiveWorkflowError("production quantity must be positive")
        if self.requested_station_count is not None and not 1 <= self.requested_station_count <= 8:
            raise InteractiveWorkflowError("requested station count must be between 1 and 8")
        for value, name in (
            (self.required_repeatability_mm, "required repeatability"),
            (self.required_clearance_mm, "required clearance"),
            (self.maximum_fixture_length_mm, "maximum fixture length"),
            (self.preferred_station_pitch_mm, "preferred station pitch"),
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise InteractiveWorkflowError(f"{name} must be finite and non-negative")
        for value, name in (
            (self.build_orientation, "build orientation"),
            (self.loading_direction, "loading direction"),
            (self.unloading_direction, "unloading direction"),
            (self.manufacturing_build_direction, "manufacturing build direction"),
            (self.manufacturing_loading_direction, "manufacturing loading direction"),
            (self.manufacturing_unloading_direction, "manufacturing unloading direction"),
        ):
            if value is not None and value == Vec3(0.0, 0.0, 0.0):
                raise InteractiveWorkflowError(f"{name} must not be zero")

    def to_dict(self) -> dict[str, object]:
        vector = lambda value: value.__dict__ if value is not None else None
        return {
            "project_name": self.project_name,
            "fixture_type": self.fixture_type,
            "manufacturing_process": self.manufacturing_process,
            "operation_mode": self.operation_mode,
            "production_quantity": self.production_quantity,
            "volume_category": self.volume_category,
            "build_orientation": vector(self.build_orientation),
            "loading_direction": vector(self.loading_direction),
            "unloading_direction": vector(self.unloading_direction),
            "operator_access": self.operator_access,
            "automation_assumptions": self.automation_assumptions,
            "shop_capabilities": list(self.shop_capabilities),
            "material_assumptions": self.material_assumptions,
            "preferred_base_strategy": self.preferred_base_strategy,
            "required_repeatability_mm": self.required_repeatability_mm,
            "required_clearance_mm": self.required_clearance_mm,
            "tooling_preferences": list(self.tooling_preferences),
            "fixture_purpose": self.fixture_purpose,
            "construction_method": self.construction_method,
            "fixture_lifecycle": self.fixture_lifecycle,
            "repeat_frequency": self.repeat_frequency,
            "job_revision": self.job_revision,
            "cleco_strategy": self.cleco_strategy,
            "manufacturing_orientation": (
                self.manufacturing_orientation.to_dict() if self.manufacturing_orientation else None
            ),
            "manufacturing_build_direction": vector(self.manufacturing_build_direction),
            "manufacturing_loading_direction": vector(self.manufacturing_loading_direction),
            "manufacturing_unloading_direction": vector(self.manufacturing_unloading_direction),
            "fixture_family": self.fixture_family,
            "requested_station_count": self.requested_station_count,
            "maximum_fixture_length_mm": self.maximum_fixture_length_mm,
            "preferred_station_pitch_mm": self.preferred_station_pitch_mm,
            "operator_loading_side": self.operator_loading_side,
            "clamp_operating_side": self.clamp_operating_side,
            "table_mounting_preference": self.table_mounting_preference,
            "compare_one_up_and_multi_up": self.compare_one_up_and_multi_up,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ProcessSetup":
        def vector(name: str) -> Vec3 | None:
            value = data.get(name)
            return Vec3(**value) if isinstance(value, dict) else None
        return cls(
            project_name=str(data["project_name"]),
            fixture_type=data.get("fixture_type"),
            manufacturing_process=data.get("manufacturing_process"),
            operation_mode=data.get("operation_mode"),
            production_quantity=data.get("production_quantity"),
            volume_category=data.get("volume_category"),
            build_orientation=vector("build_orientation"),
            loading_direction=vector("loading_direction"),
            unloading_direction=vector("unloading_direction"),
            operator_access=data.get("operator_access"),
            automation_assumptions=data.get("automation_assumptions"),
            shop_capabilities=tuple(data.get("shop_capabilities", ())),
            material_assumptions=data.get("material_assumptions"),
            preferred_base_strategy=data.get("preferred_base_strategy"),
            required_repeatability_mm=data.get("required_repeatability_mm"),
            required_clearance_mm=data.get("required_clearance_mm"),
            tooling_preferences=tuple(data.get("tooling_preferences", ())),
            fixture_purpose=data.get("fixture_purpose"),
            construction_method=data.get("construction_method"),
            fixture_lifecycle=data.get("fixture_lifecycle"),
            repeat_frequency=data.get("repeat_frequency"),
            job_revision=data.get("job_revision"),
            cleco_strategy=data.get("cleco_strategy"),
            manufacturing_orientation=(
                ManufacturingOrientation.from_dict(data["manufacturing_orientation"])
                if isinstance(data.get("manufacturing_orientation"), dict) else None
            ),
            manufacturing_build_direction=vector("manufacturing_build_direction"),
            manufacturing_loading_direction=vector("manufacturing_loading_direction"),
            manufacturing_unloading_direction=vector("manufacturing_unloading_direction"),
            fixture_family=data.get("fixture_family"),
            requested_station_count=data.get("requested_station_count"),
            maximum_fixture_length_mm=data.get("maximum_fixture_length_mm"),
            preferred_station_pitch_mm=data.get("preferred_station_pitch_mm"),
            operator_loading_side=data.get("operator_loading_side"),
            clamp_operating_side=data.get("clamp_operating_side"),
            table_mounting_preference=data.get("table_mounting_preference"),
            compare_one_up_and_multi_up=bool(data.get("compare_one_up_and_multi_up", False)),
        )


@dataclass(frozen=True)
class GeometryAnnotation:
    identity: str
    role: AnnotationRole
    reference: GeometryReference
    position_mm: Vec3
    normal: Vec3
    surface_area_mm2: float
    exact_reference: bool
    notes: str = ""
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise InteractiveWorkflowError("geometry annotation identity is required")
        if not isinstance(self.role, AnnotationRole):
            raise InteractiveWorkflowError("geometry annotation role is unsupported")
        if not self.reference.face_identity:
            raise InteractiveWorkflowError("interactive geometry annotations require a stable face reference")
        if not self.exact_reference:
            raise InteractiveWorkflowError("inexact face identity cannot be stored as an exact annotation")
        if self.normal == Vec3(0.0, 0.0, 0.0) or self.surface_area_mm2 <= 0:
            raise InteractiveWorkflowError("face normal and positive area evidence are required")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "role": self.role.value,
            "reference": self.reference.__dict__,
            "position_mm": self.position_mm.__dict__, "normal": self.normal.__dict__,
            "surface_area_mm2": self.surface_area_mm2,
            "exact_reference": self.exact_reference, "notes": self.notes,
            "evidence": list(self.evidence), "assumptions": list(self.assumptions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GeometryAnnotation":
        return cls(
            str(data["identity"]), AnnotationRole(data["role"]),
            GeometryReference(**data["reference"]), Vec3(**data["position_mm"]),
            Vec3(**data["normal"]), float(data["surface_area_mm2"]),
            bool(data["exact_reference"]), str(data.get("notes", "")),
            tuple(data.get("evidence", ())), tuple(data.get("assumptions", ())),
        )


@dataclass(frozen=True)
class CustomerToolingRecord:
    identity: str
    kind: str
    manufacturer: str | None = None
    part_number: str | None = None
    revision: str | None = None
    source_path: str | None = None
    source_sha256: str | None = None
    mounting_direction: Vec3 | None = None
    working_direction: Vec3 | None = None
    stroke_mm: float | None = None
    reach_mm: float | None = None
    force_n: float | None = None
    verified: bool = False

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.kind.strip():
            raise InteractiveWorkflowError("tooling identity and kind are required")
        if self.verified and not all((self.manufacturer, self.part_number, self.source_sha256)):
            raise InteractiveWorkflowError("verified tooling requires manufacturer, part number, and source hash")
        for value in (self.stroke_mm, self.reach_mm, self.force_n):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise InteractiveWorkflowError("tooling dimensions and force must be non-negative")

    def to_dict(self) -> dict[str, object]:
        result = dict(self.__dict__)
        for name in ("mounting_direction", "working_direction"):
            value = result[name]
            result[name] = value.__dict__ if value is not None else None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CustomerToolingRecord":
        values = dict(data)
        for name in ("mounting_direction", "working_direction"):
            if isinstance(values.get(name), dict):
                values[name] = Vec3(**values[name])
        return cls(**values)


@dataclass(frozen=True)
class OperationTiming:
    operation: str
    elapsed_ms: float


@dataclass(frozen=True)
class InteractiveWorkflow:
    source_sha256: str
    setup: ProcessSetup
    geometry_annotations: tuple[GeometryAnnotation, ...] = ()
    customer_tooling: tuple[CustomerToolingRecord, ...] = ()
    reviewed_findings: tuple[str, ...] = ()
    analysis_completed: bool = False
    concepts_generated: bool = False
    active_stage: str = "Product"
    timings: tuple[OperationTiming, ...] = ()
    schema_version: str = WORKFLOW_SCHEMA

    def __post_init__(self) -> None:
        if len(self.source_sha256) != 64:
            raise InteractiveWorkflowError("workflow source SHA-256 is malformed")
        if len({item.identity for item in self.geometry_annotations}) != len(self.geometry_annotations):
            raise InteractiveWorkflowError("geometry annotation identities must be unique")
        if len({item.identity for item in self.customer_tooling}) != len(self.customer_tooling):
            raise InteractiveWorkflowError("customer tooling identities must be unique")
        if self.schema_version not in {WORKFLOW_SCHEMA, _LEGACY_WORKFLOW_SCHEMA}:
            raise InteractiveWorkflowError("unsupported interactive workflow schema")
        if (self.setup.manufacturing_orientation is not None
                and self.setup.manufacturing_orientation.source_sha256 != self.source_sha256):
            raise InteractiveWorkflowError("manufacturing orientation does not match workflow source SHA-256")

    def with_annotation(self, annotation: GeometryAnnotation) -> "InteractiveWorkflow":
        remaining = tuple(item for item in self.geometry_annotations if item.identity != annotation.identity)
        return replace(self, geometry_annotations=remaining + (annotation,),
                       analysis_completed=False, concepts_generated=False,
                       active_stage="Datums and intent", timings=())

    def with_manufacturing_orientation(self, orientation: ManufacturingOrientation) -> "InteractiveWorkflow":
        """Replace manufacturing-frame evidence and invalidate all dependent analysis."""
        if orientation.source_sha256 != self.source_sha256:
            raise InteractiveWorkflowError("manufacturing orientation belongs to a different source STEP")
        setup = replace(self.setup, manufacturing_orientation=orientation)
        return replace(self, setup=setup, analysis_completed=False, concepts_generated=False,
                       active_stage="Orientation", timings=())

    def with_tooling(self, tooling: CustomerToolingRecord) -> "InteractiveWorkflow":
        remaining = tuple(item for item in self.customer_tooling if item.identity != tooling.identity)
        return replace(self, customer_tooling=remaining + (tooling,))

    def mark_finding_reviewed(self, finding_id: str) -> "InteractiveWorkflow":
        return replace(self, reviewed_findings=tuple(sorted(set(self.reviewed_findings) | {finding_id})))

    def validate_references(self, product: ProductModel) -> None:
        if product.source_sha256 != self.source_sha256:
            raise InteractiveWorkflowError("workflow belongs to a different source geometry")
        components = {item.identity: item for item in product.components}
        for annotation in self.geometry_annotations:
            component = components.get(annotation.reference.component_identity)
            if component is None:
                raise InteractiveWorkflowError("workflow contains an unknown component reference")
            bodies = {item.identity: item for item in component.bodies}
            body = bodies.get(annotation.reference.body_identity or "")
            if body is None or annotation.reference.face_identity not in {item.identity for item in body.faces}:
                raise InteractiveWorkflowError("workflow contains an unknown face reference")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "source_sha256": self.source_sha256,
            "setup": self.setup.to_dict(),
            "geometry_annotations": [item.to_dict() for item in sorted(
                self.geometry_annotations, key=lambda value: value.identity
            )],
            "customer_tooling": [item.to_dict() for item in sorted(
                self.customer_tooling, key=lambda value: value.identity
            )],
            "reviewed_findings": sorted(self.reviewed_findings),
            "analysis_completed": self.analysis_completed,
            "concepts_generated": self.concepts_generated,
            "active_stage": self.active_stage,
            "timings": [item.__dict__ for item in self.timings],
        }

    def identity_dict(self) -> dict[str, object]:
        """Return deterministic engineering state without observational timings."""
        result = self.to_dict()
        result.pop("timings")
        return result

    def has_accepted_manufacturing_orientation(self) -> bool:
        """Return whether derived interactive evidence belongs to an accepted current frame."""
        orientation = self.setup.manufacturing_orientation
        if orientation is None:
            return False
        try:
            orientation.require_accepted_for(self.source_sha256)
        except ManufacturingOrientationError:
            return False
        return True

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "InteractiveWorkflow":
        source_sha256 = str(data["source_sha256"])
        setup = ProcessSetup.from_dict(data["setup"])
        candidate = cls(
            source_sha256, setup,
            tuple(GeometryAnnotation.from_dict(item) for item in data.get("geometry_annotations", ())),
            tuple(CustomerToolingRecord.from_dict(item) for item in data.get("customer_tooling", ())),
            tuple(data.get("reviewed_findings", ())), bool(data.get("analysis_completed", False)),
            bool(data.get("concepts_generated", False)), str(data.get("active_stage", "Product")),
            tuple(OperationTiming(**item) for item in data.get("timings", ())),
            str(data.get("schema_version", "")),
        )
        if candidate.has_accepted_manufacturing_orientation():
            return candidate
        # Legacy source-coordinate analysis is readable history, not current
        # manufacturing-frame evidence. Revalidation requires acceptance.
        return replace(candidate, analysis_completed=False, concepts_generated=False,
                       active_stage="Orientation", timings=())


@dataclass(frozen=True)
class ConceptComparison:
    concept_identity: str
    objective: str
    validation_status: str
    recommended: bool
    preference_score: float
    cost_evidence: str
    loading_evidence: str
    unloading_evidence: str
    repeatability_evidence: str
    fixture_feature_count: int
    fabricated_component_count: int
    purchased_tooling_count: int
    operator_access_evidence: str
    weld_access_evidence: str
    automation_access_evidence: str
    manufacturability_evidence: str
    maintainability_evidence: str
    unresolved_assumptions: int
    rationale: tuple[str, ...]


def _bounds(points: tuple[tuple[float, float, float], ...]) -> Aabb:
    if not points:
        raise InteractiveWorkflowError("real OCP face evidence contains no tessellation vertices")
    return Aabb(
        Vec3(*(min(point[index] for point in points) for index in range(3))),
        Vec3(*(max(point[index] for point in points) for index in range(3))),
    )


def product_from_workbench_document(document: WorkbenchDocument) -> ProductModel:
    """Create a neutral product only from real OCP identities and vertices."""
    mesh_by_face = {mesh.face_reference: mesh for mesh in document.meshes}
    components: list[Component] = []
    if document.assembly.components:
        for kernel_component in document.assembly.components:
            face_ids = tuple(face.reference for face in kernel_component.faces)
            meshes = tuple(mesh_by_face[item] for item in face_ids if item in mesh_by_face)
            if not meshes:
                raise InteractiveWorkflowError(
                    f"component {kernel_component.reference} has no mapped real OCP tessellation evidence"
                )
            points = tuple(point for mesh in meshes for point in mesh.vertices_mm)
            body_token = sha256(kernel_component.reference.encode()).hexdigest()[:20]
            body = Body("body:" + body_token, _bounds(points), tuple(Face(item) for item in face_ids))
            components.append(Component(
                kernel_component.reference, kernel_component.name,
                kernel_component.parent_reference, Transform(), (body,),
                kernel_component.reference,
            ))
    else:
        points = tuple(point for mesh in document.meshes for point in mesh.vertices_mm)
        body = Body("body:source", _bounds(points),
                    tuple(Face(mesh.face_reference) for mesh in document.meshes))
        components.append(Component(
            "source:geometry", document.source_name, None, Transform(), (body,),
            "source:geometry",
        ))
    return ProductModel(
        "mm", tuple(components), document.source_name, document.source_sha256,
        document.source_bytes,
    )


def face_annotation(document: WorkbenchDocument, reference: GeometryReference,
                    role: AnnotationRole, *, notes: str = "") -> GeometryAnnotation:
    """Bind a role to exact OCP face evidence or fail without inference."""
    if not reference.face_identity:
        raise InteractiveWorkflowError("select a face before assigning an engineering role")
    face = next((face for component in document.assembly.components
                 if component.reference == reference.component_identity
                 for face in component.faces if face.reference == reference.face_identity), None)
    if face is None and reference.component_identity == "source:geometry":
        mesh = next((item for item in document.meshes
                     if item.face_reference == reference.face_identity), None)
        if mesh is not None:
            points = mesh.vertices_mm
            center = tuple(sum(point[index] for point in points) / len(points) for index in range(3))
            # Unstructured STEP lacks XCAF face normals. Exact identity remains
            # selectable, but datum candidacy cannot be manufactured from a
            # guessed normal.
            raise InteractiveWorkflowError(
                f"face {reference.face_identity} lacks XCAF normal evidence; annotation was not created"
            )
    if face is None:
        raise InteractiveWorkflowError("selected face is not mapped to the imported OCP assembly")
    token = sha256(f"{role.value}:{reference.component_identity}:{reference.face_identity}".encode()).hexdigest()[:16]
    return GeometryAnnotation(
        "annotation-" + token, role, reference, Vec3(*face.center_mm), Vec3(*face.normal),
        face.area_mm2, True, notes,
        (f"ocp_face={face.reference}", f"area_mm2={face.area_mm2}", f"normal={face.normal}"),
        ("Face identity is stable for this immutable source SHA-256 and importer version.",),
    )


def _engineering_annotations(product: ProductModel,
                             workflow: InteractiveWorkflow) -> EngineeringAnnotations:
    setup = workflow.setup
    orientation = setup.manufacturing_orientation
    if orientation is None:
        raise InteractiveWorkflowError("analysis requires an accepted manufacturing orientation")
    try:
        orientation.require_accepted_for(product.source_sha256)
    except ManufacturingOrientationError as exc:
        raise InteractiveWorkflowError(str(exc)) from exc
    manufacturing_build = setup.manufacturing_build_direction or Vec3(0.0, 0.0, 1.0)
    manufacturing_load = setup.manufacturing_loading_direction or Vec3(1.0, 0.0, 0.0)
    manufacturing_unload = setup.manufacturing_unloading_direction or Vec3(-1.0, 0.0, 0.0)
    build_orientation = orientation.manufacturing_vector_to_source(manufacturing_build)
    loading_direction = orientation.manufacturing_vector_to_source(manufacturing_load)
    unloading_direction = orientation.manufacturing_vector_to_source(manufacturing_unload)
    missing = [name for name, value in (
        ("manufacturing process", setup.manufacturing_process),
        ("operation mode", setup.operation_mode),
        ("production quantity", setup.production_quantity),
        ("manufacturing build direction", manufacturing_build),
        ("manufacturing loading direction", manufacturing_load),
    ) if value is None]
    if missing:
        raise InteractiveWorkflowError("analysis requires explicit " + ", ".join(missing))
    permitted_roles = {
        AnnotationRole.PRIMARY_DATUM, AnnotationRole.SECONDARY_DATUM,
        AnnotationRole.TERTIARY_DATUM, AnnotationRole.PERMITTED_LOCATOR,
        AnnotationRole.PERMITTED_SUPPORT,
    }
    permitted = tuple(item.reference for item in workflow.geometry_annotations
                      if item.role in permitted_roles)
    forbidden = tuple(item.reference for item in workflow.geometry_annotations
                      if item.role in {AnnotationRole.FORBIDDEN_CONTACT, AnnotationRole.KEEP_OUT,
                                       AnnotationRole.HEAT_SENSITIVE, AnnotationRole.SPATTER_SENSITIVE})
    critical = tuple(CriticalCharacteristic(
        item.identity, (item.reference,), notes=item.notes,
    ) for item in workflow.geometry_annotations if item.role == AnnotationRole.CRITICAL_FEATURE)
    welds = tuple(WeldJoint(
        item.identity, (item.reference,), setup.manufacturing_process, item.notes,
        assumptions=item.assumptions,
    ) for item in workflow.geometry_annotations if item.role == AnnotationRole.WELD_JOINT)
    assumptions = [
        Assumption("fixture_type", setup.fixture_type or "unknown", "Engineer process setup."),
        Assumption("operation_mode", setup.operation_mode or "unknown", "Engineer process setup."),
        Assumption("unloading_direction", repr(unloading_direction),
                   "Manufacturing unload axis converted through the accepted orientation."),
        Assumption("manufacturing_orientation", orientation.identity,
                   "Accepted manufacturing coordinate system drives deterministic analysis."),
        Assumption("manufacturing_build_axis", repr(manufacturing_build),
                   "Converted to source coordinates only at the CAD-neutral engine boundary."),
        Assumption("manufacturing_loading_axis", repr(manufacturing_load),
                   "Converted to source coordinates only at the CAD-neutral engine boundary."),
        Assumption("operator_access", setup.operator_access or "unknown", "Engineer process setup."),
        Assumption("automation", setup.automation_assumptions or "unknown", "Engineer process setup."),
        Assumption("material_process", setup.material_assumptions or "unknown", "Engineer process setup."),
        Assumption("preferred_base", setup.preferred_base_strategy or "unknown", "Engineer preference, not validation."),
    ]
    if setup.required_repeatability_mm is not None:
        assumptions.append(Assumption("required_repeatability_mm", str(setup.required_repeatability_mm),
                                      "Engineer-supplied requirement."))
    if setup.required_clearance_mm is not None:
        assumptions.append(Assumption("required_clearance_mm", str(setup.required_clearance_mm),
                                      "Engineer-supplied requirement."))
    return EngineeringAnnotations(
        product.source_sha256, product.source_name, build_orientation,
        loading_direction,
        f"{setup.operation_mode} {setup.manufacturing_process}", setup.production_quantity,
        critical, permitted, forbidden, welds, setup.shop_capabilities,
        tuple(assumptions),
    )


def _datum_candidates(workflow: InteractiveWorkflow) -> tuple[DatumCandidate, ...]:
    roles = {
        AnnotationRole.PRIMARY_DATUM: (1.0, 1.0),
        AnnotationRole.SECONDARY_DATUM: (0.95, 0.9),
        AnnotationRole.TERTIARY_DATUM: (0.9, 0.8),
        AnnotationRole.PERMITTED_LOCATOR: (0.75, 0.6),
        AnnotationRole.PERMITTED_SUPPORT: (0.7, 0.5),
    }
    source = tuple(item for item in workflow.geometry_annotations if item.role in roles)
    largest = max((item.surface_area_mm2 for item in source), default=1.0)
    return tuple(DatumCandidate(
        "datum-" + item.identity, item.reference, item.position_mm, item.normal,
        item.surface_area_mm2, roles[item.role][0],
        0.6 if workflow.setup.operator_access else 0.4,
        roles[item.role][1],
        0.8 if item.role not in {AnnotationRole.HEAT_SENSITIVE, AnnotationRole.SPATTER_SENSITIVE} else 0.2,
        item.evidence + (f"normalized_area={item.surface_area_mm2 / largest:.6f}",),
        item.assumptions + (("Operator accessibility remains provisional.",)
                            if not workflow.setup.operator_access else ()),
        0.9 if item.exact_reference else 0.0,
    ) for item in source)


def analyze_engineering_workflow(document: WorkbenchDocument,
                                 workflow: InteractiveWorkflow) -> FxdProject:
    """Run the existing deterministic engines from explicit workbench evidence."""
    if workflow.source_sha256 != document.source_sha256:
        raise InteractiveWorkflowError("workflow does not match the immutable source STEP")
    total_started = perf_counter()
    normalize_started = perf_counter()
    product = product_from_workbench_document(document)
    workflow.validate_references(product)
    normalize_ms = (perf_counter() - normalize_started) * 1000.0
    annotations = _engineering_annotations(product, workflow)
    placement_started = perf_counter()
    placement: PlacementPlan = generate_placement_plan(product, annotations, _datum_candidates(workflow))
    placement_ms = (perf_counter() - placement_started) * 1000.0
    concept_started = perf_counter()
    state = replace(workflow, analysis_completed=True, active_stage="Validation")
    project = FxdProject.from_product(product, annotations, placement=placement, workflow=state)
    concept_ms = (perf_counter() - concept_started) * 1000.0
    validation_started = perf_counter()
    _ = tuple(project.validation_for(concept) for concept in project.concepts)
    validation_ms = (perf_counter() - validation_started) * 1000.0
    analysis_operations = {
        "normalize_real_ocp_evidence", "placement_analysis", "concept_generation",
        "validation", "total_analysis",
    }
    retained_timings = tuple(
        item for item in state.timings if item.operation not in analysis_operations
    )
    timings = retained_timings + (
        OperationTiming("normalize_real_ocp_evidence", round(normalize_ms, 3)),
        OperationTiming("placement_analysis", round(placement_ms, 3)),
        OperationTiming("concept_generation", round(concept_ms, 3)),
        OperationTiming("validation", round(validation_ms, 3)),
        OperationTiming("total_analysis", round((perf_counter() - total_started) * 1000.0, 3)),
    )
    timed = replace(project, workflow=replace(state, timings=timings))
    return timed._record_revision(project.revision_id)


def compare_concepts(project: FxdProject) -> tuple[ConceptComparison, ...]:
    """Compare existing concepts without allowing scores to outrank validity."""
    validations = {item.identity: project.validation_for(item)
                   for item in project.concepts}
    eligible = [item for item in project.concepts if validations[item.identity].status != "invalid"]
    recommended = max(eligible, key=lambda item: (item.score.total, item.identity), default=None)
    rows = []
    for concept in project.concepts:
        validation = validations[concept.identity]
        breakdown = dict(concept.score.breakdown)
        findings = validation.findings
        access_findings = tuple(item for item in findings if item.subsystem == "access")
        access = "provisional" if access_findings else "supported by supplied envelopes"
        weld_access = (
            "provisional: missing weld envelope evidence"
            if any(item.code == "missing_weld_access_intent" for item in findings)
            else access
        )
        unloading = (
            "provisional: unload direction supplied; envelope evidence incomplete"
            if project.workflow and project.workflow.setup.unloading_direction is not None
            else "unknown: unload direction not supplied"
        )
        automation = (
            "provisional: " + project.workflow.setup.automation_assumptions
            if project.workflow and project.workflow.setup.automation_assumptions
            else "unknown: robot or cobot intent not supplied"
        )
        manufacturing = "blocked" if any(item.severity == "error" and item.subsystem in {
            "geometry", "manufacturing", "structure"} for item in findings) else "review evidence"
        purchased = sum(feature.kind == "clamp_mount" for feature in concept.fixture.features)
        fabricated = len(concept.fixture.features) - purchased
        rows.append(ConceptComparison(
            concept.identity, concept.objective, validation.status,
            recommended is not None and concept.identity == recommended.identity,
            concept.score.total,
            f"relative score {breakdown.get('cost', 0):.0f}/100; not a quote",
            f"relative loading score {breakdown.get('loading_speed', 0):.0f}/100",
            unloading,
            f"relative repeatability score {breakdown.get('repeatability', 0):.0f}/100",
            len(concept.fixture.features), fabricated, purchased,
            ("provisional: " + project.workflow.setup.operator_access
             if project.workflow and project.workflow.setup.operator_access
             else "unknown: operator-access intent not supplied"),
            weld_access, automation, manufacturing,
            "provisional: replacement and maintenance clearance require engineer review",
            sum(len(item.assumptions) for item in findings),
            concept.score.rationale + (
                "deterministic validation status precedes preference score",
                "qualified fixture-engineering and commercial review remain mandatory",
            ),
        ))
    order = {"valid": 0, "provisional": 1, "invalid": 2}
    return tuple(sorted(rows, key=lambda item: (
        order[item.validation_status], not item.recommended, -item.preference_score,
        item.concept_identity,
    )))


def tooling_record_from_file(path: str | Path, *, identity: str, kind: str,
                             manufacturer: str | None = None,
                             part_number: str | None = None,
                             revision: str | None = None,
                             mounting_direction: Vec3 | None = None,
                             working_direction: Vec3 | None = None,
                             stroke_mm: float | None = None,
                             reach_mm: float | None = None,
                             force_n: float | None = None,
                             verified: bool = False) -> CustomerToolingRecord:
    """Record customer-owned tooling without downloading or redistributing it."""
    source = Path(path)
    if not source.is_file():
        raise InteractiveWorkflowError("customer tooling file does not exist")
    return CustomerToolingRecord(
        identity, kind, manufacturer, part_number, revision,
        str(source.resolve()), sha256(source.read_bytes()).hexdigest(),
        mounting_direction, working_direction, stroke_mm, reach_mm, force_n,
        verified,
    )
