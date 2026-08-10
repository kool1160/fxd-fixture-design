"""Source-bound native product/manufacturing reconstruction for M33.1.

The reconstruction is separate from immutable source CAD.  It records exact
OCP-derived evidence, bounded interpretations, and explicit ambiguity.  It is
not a universal feature recognizer and it never turns unsupported meaning into
manufacturing fact.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Mapping

from .kernel import KernelBody, KernelFace, TopologyCounts
from .product_model import Component, ProductModel
from .workbench import WorkbenchDocument

if TYPE_CHECKING:
    from .interactive_workflow import InteractiveWorkflow


RECONSTRUCTION_SCHEMA = "fxd-native-product-reconstruction-v1"


class ProductReconstructionError(ValueError):
    """Raised when reconstructed evidence is malformed, stale, or ambiguous."""


class ManufacturingClassification(str, Enum):
    PLATE_SHEET = "plate_sheet"
    TUBE_STRUCTURAL = "tube_structural"
    FORMED = "formed"
    MACHINED = "machined"
    PURCHASED = "purchased"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReconstructionQuestion:
    identity: str
    category: str
    prompt: str
    affected_identities: tuple[str, ...]
    blocking: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "category": self.category,
            "prompt": self.prompt,
            "affected_identities": list(self.affected_identities),
            "blocking": self.blocking,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ReconstructionBody:
    identity: str
    component_identity: str
    minimum_mm: tuple[float, float, float]
    maximum_mm: tuple[float, float, float]
    volume_mm3: float
    topology: TopologyCounts
    face_identities: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "component_identity": self.component_identity,
            "minimum_mm": list(self.minimum_mm),
            "maximum_mm": list(self.maximum_mm),
            "volume_mm3": self.volume_mm3,
            "topology": self.topology.__dict__,
            "face_identities": list(self.face_identities),
        }


@dataclass(frozen=True)
class ReconstructionFace:
    identity: str
    component_identity: str
    area_mm2: float
    center_mm: tuple[float, float, float]
    normal: tuple[float, float, float]
    surface_type: str
    orientation: str
    provenance: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "component_identity": self.component_identity,
            "area_mm2": self.area_mm2,
            "center_mm": list(self.center_mm),
            "normal": list(self.normal),
            "surface_type": self.surface_type,
            "orientation": self.orientation,
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True)
class PlaneEvidence:
    identity: str
    face_identity: str
    component_identity: str
    origin_mm: tuple[float, float, float]
    normal: tuple[float, float, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "face_identity": self.face_identity,
            "component_identity": self.component_identity,
            "origin_mm": list(self.origin_mm),
            "normal": list(self.normal),
        }


@dataclass(frozen=True)
class AxisEvidence:
    identity: str
    face_identity: str
    component_identity: str
    origin_mm: tuple[float, float, float]
    direction: tuple[float, float, float]
    radius_mm: float

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "face_identity": self.face_identity,
            "component_identity": self.component_identity,
            "origin_mm": list(self.origin_mm),
            "direction": list(self.direction),
            "radius_mm": self.radius_mm,
        }


@dataclass(frozen=True)
class HoleEvidence:
    identity: str
    face_identity: str
    axis_identity: str
    component_identity: str
    interpretation: str
    confirmed: bool
    confidence: float
    ambiguity: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "face_identity": self.face_identity,
            "axis_identity": self.axis_identity,
            "component_identity": self.component_identity,
            "interpretation": self.interpretation,
            "confirmed": self.confirmed,
            "confidence": self.confidence,
            "ambiguity": list(self.ambiguity),
        }


@dataclass(frozen=True)
class InterpretedFeature:
    identity: str
    kind: str
    geometry_identities: tuple[str, ...]
    confidence: float
    provenance: tuple[str, ...]
    ambiguity: tuple[str, ...] = ()
    engineer_confirmed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "kind": self.kind,
            "geometry_identities": list(self.geometry_identities),
            "confidence": self.confidence,
            "provenance": list(self.provenance),
            "ambiguity": list(self.ambiguity),
            "engineer_confirmed": self.engineer_confirmed,
        }


@dataclass(frozen=True)
class ReconstructionComponent:
    identity: str
    source_component_identity: str
    parent_identity: str | None
    name: str
    transform: tuple[float, ...]
    body_identities: tuple[str, ...]
    topology: TopologyCounts
    manufacturing_classification: ManufacturingClassification
    classification_confidence: float
    classification_provenance: tuple[str, ...]
    unresolved_ambiguity: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "source_component_identity": self.source_component_identity,
            "parent_identity": self.parent_identity,
            "name": self.name,
            "transform": list(self.transform),
            "body_identities": list(self.body_identities),
            "topology": self.topology.__dict__,
            "manufacturing_classification": self.manufacturing_classification.value,
            "classification_confidence": self.classification_confidence,
            "classification_provenance": list(self.classification_provenance),
            "unresolved_ambiguity": list(self.unresolved_ambiguity),
        }


@dataclass(frozen=True)
class ProductReconstruction:
    schema_version: str
    reconstruction_identity: str
    source_sha256: str
    source_name: str
    workflow_context_identity: str | None
    units: str
    components: tuple[ReconstructionComponent, ...]
    bodies: tuple[ReconstructionBody, ...]
    faces: tuple[ReconstructionFace, ...]
    planes: tuple[PlaneEvidence, ...]
    axes: tuple[AxisEvidence, ...]
    hole_evidence: tuple[HoleEvidence, ...]
    datum_contact_candidates: tuple[InterpretedFeature, ...]
    weld_candidates: tuple[InterpretedFeature, ...]
    confirmed_weld_intent: tuple[InterpretedFeature, ...]
    unresolved_questions: tuple[ReconstructionQuestion, ...]

    def __post_init__(self) -> None:
        if self.schema_version != RECONSTRUCTION_SCHEMA:
            raise ProductReconstructionError("unsupported product reconstruction schema")
        if self.units != "mm":
            raise ProductReconstructionError("product reconstruction units must be millimetres")
        if len(self.source_sha256) != 64:
            raise ProductReconstructionError("product reconstruction source SHA-256 is malformed")
        if (self.reconstruction_identity
                and self.reconstruction_identity != self.expected_identity()):
            raise ProductReconstructionError("product reconstruction identity does not match its evidence")
        component_ids = {item.identity for item in self.components}
        body_ids = {item.identity for item in self.bodies}
        face_ids = {item.identity for item in self.faces}
        plane_ids = {item.identity for item in self.planes}
        axis_ids = {item.identity for item in self.axes}
        for values, label in (
            (component_ids, "component"), (body_ids, "body"), (face_ids, "face"),
            (plane_ids, "plane"), (axis_ids, "axis"),
        ):
            sequence = {
                "component": self.components, "body": self.bodies, "face": self.faces,
                "plane": self.planes, "axis": self.axes,
            }[label]
            if len(values) != len(sequence):
                raise ProductReconstructionError(f"duplicate reconstruction {label} identity")
        if any(item.component_identity not in component_ids for item in self.bodies):
            raise ProductReconstructionError("reconstruction body references an unknown component")
        if any(not set(item.body_identities) <= body_ids for item in self.components):
            raise ProductReconstructionError("reconstruction component references an unknown body")
        if any(item.component_identity not in component_ids for item in self.faces):
            raise ProductReconstructionError("reconstruction face references an unknown component")
        if any(not set(item.face_identities) <= face_ids for item in self.bodies):
            raise ProductReconstructionError("reconstruction body references an unknown exact face")
        owned_face_sequence = tuple(
            face_identity for body in self.bodies for face_identity in body.face_identities
        )
        if (set(owned_face_sequence) != face_ids
                or len(owned_face_sequence) != len(face_ids)):
            raise ProductReconstructionError(
                "each exact reconstruction face must belong to exactly one body"
            )
        face_components = {item.identity: item.component_identity for item in self.faces}
        if any(
            face_components[face_identity] != body.component_identity
            for body in self.bodies for face_identity in body.face_identities
        ):
            raise ProductReconstructionError(
                "reconstruction body owns a face from a different component"
            )
        if any(
            item.volume_mm3 <= 0 or item.topology.solids != 1
            or any(high <= low for low, high in zip(item.minimum_mm, item.maximum_mm))
            for item in self.bodies
        ):
            raise ProductReconstructionError(
                "reconstruction body lacks positive exact solid evidence"
            )
        if any(item.face_identity not in face_ids for item in self.planes + self.axes):
            raise ProductReconstructionError("plane or axis references an unknown exact face")
        if any(item.axis_identity not in axis_ids for item in self.hole_evidence):
            raise ProductReconstructionError("hole evidence references an unknown axis")
        if any(not 0.0 <= item.confidence <= 1.0 for item in (
            self.datum_contact_candidates + self.weld_candidates + self.confirmed_weld_intent
        )):
            raise ProductReconstructionError("interpreted feature confidence is outside [0, 1]")
        known_evidence = component_ids | body_ids | face_ids | plane_ids | axis_ids
        if any(not set(item.geometry_identities) <= known_evidence for item in (
            self.datum_contact_candidates + self.weld_candidates + self.confirmed_weld_intent
        )):
            raise ProductReconstructionError("interpreted feature references unknown evidence")
        if any(not set(item.affected_identities) <= known_evidence
               for item in self.unresolved_questions):
            raise ProductReconstructionError("reconstruction question references unknown evidence")

    @property
    def blocked(self) -> bool:
        return any(item.blocking for item in self.unresolved_questions)

    @property
    def blocker_count(self) -> int:
        return sum(item.blocking for item in self.unresolved_questions)

    def _identity_payload(self) -> dict[str, object]:
        payload = self.to_dict()
        payload["reconstruction_identity"] = ""
        return payload

    def expected_identity(self) -> str:
        encoded = json.dumps(
            self._identity_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=True,
        )
        return "reconstruction-" + sha256(encoded.encode("utf-8")).hexdigest()[:24]

    def stale_reason(
        self, source_sha256: str, workflow: "InteractiveWorkflow | None" = None,
    ) -> str | None:
        if source_sha256 != self.source_sha256:
            return "source SHA-256 changed"
        if reconstruction_workflow_context_identity(workflow) != self.workflow_context_identity:
            return "manufacturing workflow context changed"
        return None

    def require_current_source(
        self, product: ProductModel, workflow: "InteractiveWorkflow | None" = None,
    ) -> None:
        if product.source_sha256 != self.source_sha256:
            raise ProductReconstructionError("product reconstruction is stale for the current source")
        if sha256(product.source_bytes).hexdigest() != self.source_sha256:
            raise ProductReconstructionError("immutable source bytes no longer match reconstruction evidence")
        if reconstruction_workflow_context_identity(workflow) != self.workflow_context_identity:
            raise ProductReconstructionError(
                "product reconstruction is stale for the current manufacturing workflow"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "reconstruction_identity": self.reconstruction_identity,
            "source_sha256": self.source_sha256,
            "source_name": self.source_name,
            "workflow_context_identity": self.workflow_context_identity,
            "units": self.units,
            "components": [item.to_dict() for item in self.components],
            "bodies": [item.to_dict() for item in self.bodies],
            "faces": [item.to_dict() for item in self.faces],
            "planes": [item.to_dict() for item in self.planes],
            "axes": [item.to_dict() for item in self.axes],
            "hole_evidence": [item.to_dict() for item in self.hole_evidence],
            "datum_contact_candidates": [
                item.to_dict() for item in self.datum_contact_candidates
            ],
            "weld_candidates": [item.to_dict() for item in self.weld_candidates],
            "confirmed_weld_intent": [
                item.to_dict() for item in self.confirmed_weld_intent
            ],
            "unresolved_questions": [item.to_dict() for item in self.unresolved_questions],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProductReconstruction":
        try:
            def vector(values: object) -> tuple[float, float, float]:
                result = tuple(float(item) for item in values)  # type: ignore[arg-type]
                if len(result) != 3:
                    raise ProductReconstructionError("reconstruction vector must contain three values")
                return result

            components = tuple(ReconstructionComponent(
                str(item["identity"]), str(item["source_component_identity"]),
                str(item["parent_identity"]) if item.get("parent_identity") is not None else None,
                str(item["name"]), tuple(float(value) for value in item["transform"]),
                tuple(str(value) for value in item["body_identities"]),
                TopologyCounts(**{key: int(value) for key, value in item["topology"].items()}),
                ManufacturingClassification(str(item["manufacturing_classification"])),
                float(item["classification_confidence"]),
                tuple(str(value) for value in item.get("classification_provenance", ())),
                tuple(str(value) for value in item.get("unresolved_ambiguity", ())),
            ) for item in data.get("components", ()))  # type: ignore[union-attr]
            bodies = tuple(ReconstructionBody(
                str(item["identity"]), str(item["component_identity"]),
                vector(item["minimum_mm"]), vector(item["maximum_mm"]),
                float(item["volume_mm3"]),
                TopologyCounts(**{
                    key: int(value) for key, value in item["topology"].items()
                }),
                tuple(str(value) for value in item["face_identities"]),
            ) for item in data.get("bodies", ()))  # type: ignore[union-attr]
            faces = tuple(ReconstructionFace(
                str(item["identity"]), str(item["component_identity"]),
                float(item["area_mm2"]), vector(item["center_mm"]), vector(item["normal"]),
                str(item["surface_type"]), str(item.get("orientation", "forward")),
                tuple(str(value) for value in item.get("provenance", ())),
            ) for item in data.get("faces", ()))  # type: ignore[union-attr]
            planes = tuple(PlaneEvidence(
                str(item["identity"]), str(item["face_identity"]),
                str(item["component_identity"]), vector(item["origin_mm"]),
                vector(item["normal"]),
            ) for item in data.get("planes", ()))  # type: ignore[union-attr]
            axes = tuple(AxisEvidence(
                str(item["identity"]), str(item["face_identity"]),
                str(item["component_identity"]), vector(item["origin_mm"]),
                vector(item["direction"]), float(item["radius_mm"]),
            ) for item in data.get("axes", ()))  # type: ignore[union-attr]
            holes = tuple(HoleEvidence(
                str(item["identity"]), str(item["face_identity"]), str(item["axis_identity"]),
                str(item["component_identity"]), str(item["interpretation"]),
                bool(item["confirmed"]), float(item["confidence"]),
                tuple(str(value) for value in item.get("ambiguity", ())),
            ) for item in data.get("hole_evidence", ()))  # type: ignore[union-attr]

            def features(key: str) -> tuple[InterpretedFeature, ...]:
                return tuple(InterpretedFeature(
                    str(item["identity"]), str(item["kind"]),
                    tuple(str(value) for value in item["geometry_identities"]),
                    float(item["confidence"]),
                    tuple(str(value) for value in item.get("provenance", ())),
                    tuple(str(value) for value in item.get("ambiguity", ())),
                    bool(item.get("engineer_confirmed", False)),
                ) for item in data.get(key, ()))  # type: ignore[union-attr]

            questions = tuple(ReconstructionQuestion(
                str(item["identity"]), str(item["category"]), str(item["prompt"]),
                tuple(str(value) for value in item["affected_identities"]),
                bool(item["blocking"]), str(item["reason"]),
            ) for item in data.get("unresolved_questions", ()))  # type: ignore[union-attr]
            result = cls(
                str(data["schema_version"]), str(data["reconstruction_identity"]),
                str(data["source_sha256"]), str(data["source_name"]),
                str(data["workflow_context_identity"])
                if data.get("workflow_context_identity") is not None else None,
                str(data["units"]),
                components, bodies, faces, planes, axes, holes,
                features("datum_contact_candidates"), features("weld_candidates"),
                features("confirmed_weld_intent"), questions,
            )
            if not result.reconstruction_identity:
                raise ProductReconstructionError("product reconstruction identity is missing")
            return result
        except ProductReconstructionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ProductReconstructionError(f"invalid product reconstruction: {exc}") from exc


def _token(prefix: str, *values: object) -> str:
    return prefix + "-" + sha256(repr(values).encode("utf-8")).hexdigest()[:20]


def reconstruction_workflow_context_identity(
    workflow: "InteractiveWorkflow | None",
) -> str | None:
    """Bind reconstruction-derived meaning to material manufacturing inputs."""
    if workflow is None:
        return None
    payload = {
        "source_sha256": workflow.source_sha256,
        "setup": workflow.setup.to_dict(),
        "geometry_annotations": [item.to_dict() for item in sorted(
            workflow.geometry_annotations, key=lambda value: value.identity,
        )],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "reconstruction-workflow-" + sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _component_faces(document: WorkbenchDocument) -> dict[str, tuple[KernelFace, ...]]:
    if document.assembly.components:
        return {item.reference: item.faces for item in document.assembly.components}
    return {"source:geometry": document.faces}


def _component_topology(document: WorkbenchDocument) -> dict[str, TopologyCounts]:
    if document.assembly.components:
        return {item.reference: item.topology for item in document.assembly.components}
    return {"source:geometry": TopologyCounts(
        solids=1,
        shells=0,
        faces=len(document.faces),
        edges=len(document.edges),
    )}


def _component_bodies(document: WorkbenchDocument) -> dict[str, tuple[KernelBody, ...]]:
    if document.assembly.components:
        return {item.reference: item.bodies for item in document.assembly.components}
    return {"source:geometry": document.bodies}


def _component_transforms(document: WorkbenchDocument) -> dict[str, tuple[float, ...]]:
    if document.assembly.components:
        return {item.reference: item.transform for item in document.assembly.components}
    return {"source:geometry": (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
    )}


def _classification(
    faces: tuple[KernelFace, ...],
    bodies: tuple[KernelBody, ...],
    override: ManufacturingClassification | None,
) -> tuple[ManufacturingClassification, float, tuple[str, ...], tuple[str, ...]]:
    if override is not None:
        return override, 1.0, ("engineer_explicit_classification",), ()
    if len(bodies) != 1:
        return (
            ManufacturingClassification.UNKNOWN, 0.0,
            ("component does not contain exactly one proven solid body",),
            ("multi-body manufacturing role requires engineer confirmation",),
        )
    body = bodies[0]
    bounds = body
    dimensions = sorted((
        bounds.maximum_mm[0] - bounds.minimum_mm[0],
        bounds.maximum_mm[1] - bounds.minimum_mm[1],
        bounds.maximum_mm[2] - bounds.minimum_mm[2],
    ))
    largest = dimensions[-1]
    thickness_ratio = dimensions[0] / largest if largest > 0 else 1.0
    planar = bool(faces) and all(item.surface_type == "plane" for item in faces)
    bounding_volume = dimensions[0] * dimensions[1] * dimensions[2]
    full_prism = (
        bounding_volume > 0
        and abs(body.volume_mm3 - bounding_volume)
        <= max(1e-6, bounding_volume * 1e-6)
    )
    rectangular_solid_topology = body.topology == TopologyCounts(1, 1, 6, 12)
    if planar and rectangular_solid_topology and full_prism and thickness_ratio <= 0.25:
        return (
            ManufacturingClassification.PLATE_SHEET,
            0.95,
            (
                "deterministic_full_rectangular_prismatic_solid",
                "topology=1_solid_1_shell_6_faces_12_unique_edges",
                f"bounding_dimension_ratio={thickness_ratio:.6f}",
                f"solid_to_bounding_volume_ratio={body.volume_mm3 / bounding_volume:.9f}",
            ),
            ("plate versus sheet process remains engineer-confirmed intent",),
        )
    return (
        ManufacturingClassification.UNKNOWN,
        0.0,
        ("no bounded deterministic classifier matched",),
        ("manufacturing role materially affects datum, support, and clamp strategy",),
    )


def reconstruct_product(
    document: WorkbenchDocument,
    product: ProductModel,
    workflow: "InteractiveWorkflow | None" = None,
    *,
    classification_overrides: Mapping[str, ManufacturingClassification] | None = None,
) -> ProductReconstruction:
    """Build deterministic OCP-backed evidence without modifying source bytes."""
    if document.source_sha256 != product.source_sha256:
        raise ProductReconstructionError("workbench and neutral product source identities differ")
    if document.source_bytes != product.source_bytes:
        raise ProductReconstructionError("workbench and neutral product source bytes differ")
    if sha256(document.source_bytes).hexdigest() != document.source_sha256:
        raise ProductReconstructionError("immutable STEP bytes changed before reconstruction")
    if workflow is not None and workflow.source_sha256 != document.source_sha256:
        raise ProductReconstructionError("workflow does not belong to reconstructed source")

    overrides = dict(classification_overrides or {})
    face_map = _component_faces(document)
    topology_map = _component_topology(document)
    body_map = _component_bodies(document)
    transform_map = _component_transforms(document)
    kernel_names = {
        item.reference: item.name for item in document.assembly.components
    }
    product_by_identity = {item.identity: item for item in product.components}
    components: list[ReconstructionComponent] = []
    bodies: list[ReconstructionBody] = []
    faces: list[ReconstructionFace] = []
    planes: list[PlaneEvidence] = []
    axes: list[AxisEvidence] = []
    holes: list[HoleEvidence] = []
    candidates: list[InterpretedFeature] = []
    questions: list[ReconstructionQuestion] = []

    for component_identity in sorted(face_map):
        component = product_by_identity.get(component_identity)
        if component is None:
            raise ProductReconstructionError(
                f"OCP component {component_identity!r} is missing from the neutral product"
            )
        kernel_faces = tuple(sorted(face_map[component_identity], key=lambda item: item.reference))
        classification, confidence, provenance, ambiguity = _classification(
            kernel_faces, body_map[component_identity],
            overrides.get(component_identity),
        )
        if classification == ManufacturingClassification.UNKNOWN:
            questions.append(ReconstructionQuestion(
                _token("question", "classification", component_identity),
                "manufacturing_classification",
                f"Confirm the manufacturing role for component {component.name!r}.",
                (component_identity,), True,
                "Support, locator, clamp, and contact choices depend on this component role.",
            ))
        kernel_bodies = tuple(sorted(
            body_map[component_identity], key=lambda item: item.reference,
        ))
        component_body_ids = tuple(item.reference for item in kernel_bodies)
        if component_body_ids != tuple(sorted(item.identity for item in component.bodies)):
            raise ProductReconstructionError(
                f"neutral body identities for {component_identity!r} do not match exact OCP solids"
            )
        components.append(ReconstructionComponent(
            component_identity, component.source_product_identity,
            component.parent_identity, kernel_names.get(component_identity, component.name),
            transform_map[component_identity], component_body_ids,
            topology_map[component_identity], classification, confidence, provenance, ambiguity,
        ))
        for body in kernel_bodies:
            bodies.append(ReconstructionBody(
                body.reference, component_identity,
                body.minimum_mm, body.maximum_mm, body.volume_mm3, body.topology,
                tuple(face.reference for face in body.faces),
            ))
        for face in kernel_faces:
            face_record = ReconstructionFace(
                face.reference, component_identity, face.area_mm2, face.center_mm,
                face.normal, face.surface_type, face.orientation,
                ("exact_ocp_face", f"source_sha256={document.source_sha256}"),
            )
            faces.append(face_record)
            if face.is_planar:
                plane_identity = _token("plane", component_identity, face.reference)
                planes.append(PlaneEvidence(
                    plane_identity, face.reference, component_identity,
                    face.center_mm, face.normal,
                ))
                candidates.append(InterpretedFeature(
                    _token("feature", "datum-contact", component_identity, face.reference),
                    "candidate_datum_contact", (face.reference, plane_identity), 0.75,
                    ("exact_planar_ocp_face", "candidate_only_not_engineer_selected"),
                    ("datum rank and permitted contact require engineering intent",), False,
                ))
            if (face.surface_type == "cylinder" and face.axis_origin_mm is not None
                    and face.axis_direction is not None and face.radius_mm is not None):
                axis_identity = _token("axis", component_identity, face.reference)
                axes.append(AxisEvidence(
                    axis_identity, face.reference, component_identity,
                    face.axis_origin_mm, face.axis_direction, face.radius_mm,
                ))
                holes.append(HoleEvidence(
                    _token("hole-evidence", component_identity, face.reference),
                    face.reference, axis_identity, component_identity,
                    "cylindrical_feature_candidate", False, 0.5,
                    ("internal hole versus external cylindrical surface is unresolved",),
                ))

    confirmed_welds: list[InterpretedFeature] = []
    if workflow is not None:
        for annotation in workflow.geometry_annotations:
            if annotation.role.value != "weld_joint_reference":
                continue
            geometry = tuple(value for value in (
                annotation.reference.component_identity,
                annotation.reference.body_identity,
                annotation.reference.face_identity,
                annotation.reference.edge_identity,
            ) if value)
            confirmed_welds.append(InterpretedFeature(
                _token("feature", "confirmed-weld", annotation.identity),
                "engineer_confirmed_weld_intent", geometry, 1.0,
                ("engineer_workflow_annotation", annotation.identity),
                annotation.assumptions, True,
            ))
        process = (workflow.setup.manufacturing_process or "").lower()
        if "weld" in process and not confirmed_welds:
            questions.append(ReconstructionQuestion(
                _token("question", "weld-intent", document.source_sha256),
                "weld_intent",
                "Confirm the weld joints and tack/weld intent that this fixture must expose.",
                tuple(item.identity for item in components), True,
                "Geometry alone does not establish which interfaces are welded or their sequence.",
            ))

    provisional = ProductReconstruction(
        RECONSTRUCTION_SCHEMA, "", document.source_sha256, document.source_name,
        reconstruction_workflow_context_identity(workflow), "mm",
        tuple(components), tuple(bodies), tuple(faces), tuple(planes), tuple(axes),
        tuple(holes), tuple(candidates), (), tuple(confirmed_welds), tuple(questions),
    )
    identity = provisional.expected_identity()
    return ProductReconstruction(
        provisional.schema_version, identity, provisional.source_sha256,
        provisional.source_name, provisional.workflow_context_identity,
        provisional.units, provisional.components,
        provisional.bodies, provisional.faces, provisional.planes, provisional.axes,
        provisional.hole_evidence, provisional.datum_contact_candidates,
        provisional.weld_candidates, provisional.confirmed_weld_intent,
        provisional.unresolved_questions,
    )
