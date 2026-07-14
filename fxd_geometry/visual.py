"""CAD-neutral real-kernel review geometry for the local application."""
from __future__ import annotations

from dataclasses import dataclass

from .concepts import CompleteFixtureConcept
from .kernel import KernelEdgeRecord, KernelTriangleMesh, RealKernel
from .manufacturing import ManufacturingGeometry
from .product_model import ProductModel


COLLISION_FINDING_CODES = frozenset({"obvious_collision", "interference", "manufacturing_interference"})
_FEATURE_LAYERS = {
    "baseplate": "fixture",
    "support_pad": "supports",
    "hard_stop": "stops",
    "round_pin": "locators",
    "relieved_locator": "locators",
    "clamp_mount": "clamps",
}


@dataclass(frozen=True)
class VisualEdge:
    reference: str
    start_mm: tuple[float, float, float]
    end_mm: tuple[float, float, float]


@dataclass(frozen=True)
class ReviewVisualItem:
    """Selectable display item linked to deterministic engineering evidence."""
    identity: str
    category: str
    layer: str
    rule: str | None
    parameters: tuple[tuple[str, object], ...]
    source_references: tuple[str, ...]
    findings: tuple[str, ...]
    meshes: tuple[KernelTriangleMesh, ...]
    edges: tuple[VisualEdge, ...]
    section_edges: tuple[VisualEdge, ...]

    @property
    def has_collision(self) -> bool:
        return bool(COLLISION_FINDING_CODES.intersection(self.findings))


@dataclass(frozen=True)
class ReviewGeometry:
    units: str
    source_sha256: str
    concept_identity: str
    items: tuple[ReviewVisualItem, ...]
    provisional: bool = False

    @property
    def meshes(self) -> tuple[KernelTriangleMesh, ...]:
        return tuple(mesh for item in self.items for mesh in item.meshes)

    def item(self, identity: str) -> ReviewVisualItem | None:
        return next((item for item in self.items if item.identity == identity), None)


def _mesh(mesh: KernelTriangleMesh, identity: str) -> KernelTriangleMesh:
    return KernelTriangleMesh(f"{identity}/{mesh.face_reference}", mesh.vertices_mm, mesh.triangles)


def _edges(edges: tuple[KernelEdgeRecord, ...], identity: str, prefix: str = "edge") -> tuple[VisualEdge, ...]:
    return tuple(VisualEdge(f"{identity}/{prefix}/{edge.reference}", edge.start_mm, edge.end_mm)
                 for edge in edges)


def _section_edges(kernel: RealKernel, shape: object, identity: str,
                   meshes: tuple[KernelTriangleMesh, ...]) -> tuple[VisualEdge, ...]:
    vertices = [point for mesh in meshes for point in mesh.vertices_mm]
    if not vertices:
        return ()
    center_z = (min(point[2] for point in vertices) + max(point[2] for point in vertices)) / 2.0
    section = kernel.section(shape, (0.0, 0.0, center_z), (0.0, 0.0, 1.0))
    return _edges(kernel.edge_records(section), identity, "section")


def build_review_geometry(kernel: RealKernel, product: ProductModel,
                          product_shape: object, concept: CompleteFixtureConcept,
                          manufacturing: ManufacturingGeometry) -> ReviewGeometry:
    """Build selectable product and fixture records from authoritative B-Rep data."""
    if manufacturing.source_sha256 != product.source_sha256:
        raise ValueError("manufacturing geometry does not match immutable product source")
    items: list[ReviewVisualItem] = []
    product_raw = kernel.tessellate(product_shape)
    product_meshes = tuple(_mesh(mesh, "product") for mesh in product_raw)
    product_refs = tuple(
        f"{component.identity}/{body.identity}"
        for component in product.components for body in component.bodies
    )
    items.append(ReviewVisualItem(
        "product", "product", "product", None, (), product_refs, (), product_meshes,
        _edges(kernel.edge_records(product_shape), "product"),
        _section_edges(kernel, product_shape, "product", product_raw)))

    global_findings = tuple(
        finding.code for finding in concept.fixture.findings
        if finding.feature_identity is None
    )
    feature_findings: dict[str, list[str]] = {}
    for finding in concept.fixture.findings:
        if finding.feature_identity is not None:
            feature_findings.setdefault(finding.feature_identity, []).append(finding.code)

    solids = {solid.identity: solid for solid in manufacturing.solids}
    for feature in concept.fixture.features:
        solid = solids.get(feature.identity)
        if solid is None:
            raise ValueError(f"manufacturing geometry is missing feature {feature.identity}")
        raw_meshes = kernel.tessellate(solid.shape)
        findings = tuple(global_findings + tuple(feature_findings.get(feature.identity, ())))
        items.append(ReviewVisualItem(
            feature.identity,
            feature.kind,
            _FEATURE_LAYERS.get(feature.kind, "fixture"),
            feature.rule,
            tuple(sorted(feature.parameters.items())),
            tuple(f"{ref.component_identity}/{ref.body_identity}" for ref in feature.source_references),
            findings,
            tuple(_mesh(mesh, feature.identity) for mesh in raw_meshes),
            _edges(kernel.edge_records(solid.shape), feature.identity),
            _section_edges(kernel, solid.shape, feature.identity, raw_meshes),
        ))
    return ReviewGeometry("mm", product.source_sha256, concept.identity, tuple(items), False)
