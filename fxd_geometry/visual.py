"""CAD-neutral real-kernel review geometry for the local application."""
from __future__ import annotations

from dataclasses import dataclass

from .concepts import CompleteFixtureConcept
from .kernel import KernelEdgeRecord, KernelTriangleMesh, RealKernel
from .manufacturing import ManufacturingGeometry
from .product_model import ProductModel


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
    rule: str | None
    parameters: tuple[tuple[str, object], ...]
    source_references: tuple[str, ...]
    findings: tuple[str, ...]
    meshes: tuple[KernelTriangleMesh, ...]
    edges: tuple[VisualEdge, ...]


@dataclass(frozen=True)
class ReviewGeometry:
    units: str
    source_sha256: str
    items: tuple[ReviewVisualItem, ...]
    provisional: bool = False

    @property
    def meshes(self) -> tuple[KernelTriangleMesh, ...]:
        return tuple(mesh for item in self.items for mesh in item.meshes)

    def item(self, identity: str) -> ReviewVisualItem | None:
        return next((item for item in self.items if item.identity == identity), None)


def _mesh(mesh: KernelTriangleMesh, identity: str) -> KernelTriangleMesh:
    return KernelTriangleMesh(f"{identity}/{mesh.face_reference}", mesh.vertices_mm, mesh.triangles)


def _edges(edges: tuple[KernelEdgeRecord, ...], identity: str) -> tuple[VisualEdge, ...]:
    return tuple(VisualEdge(f"{identity}/{edge.reference}", edge.start_mm, edge.end_mm)
                 for edge in edges)


def build_review_geometry(kernel: RealKernel, product: ProductModel,
                          product_shape: object, concept: CompleteFixtureConcept,
                          manufacturing: ManufacturingGeometry) -> ReviewGeometry:
    """Build selectable product and fixture display records from real B-Rep data."""
    items: list[ReviewVisualItem] = []
    product_meshes = tuple(_mesh(mesh, "product") for mesh in kernel.tessellate(product_shape))
    product_edges = _edges(kernel.edge_records(product_shape), "product")
    items.append(ReviewVisualItem(
        "product", "product", None, (),
        tuple(component.identity for component in product.components), (),
        product_meshes, product_edges))
    findings = tuple(finding.code for finding in concept.fixture.findings)
    solids = {solid.identity: solid for solid in manufacturing.solids}
    for feature in concept.fixture.features:
        solid = solids.get(feature.identity)
        if solid is None:
            raise ValueError(f"manufacturing geometry is missing feature {feature.identity}")
        items.append(ReviewVisualItem(
            feature.identity, feature.kind, feature.rule,
            tuple(sorted(feature.parameters.items())),
            tuple(f"{ref.component_identity}/{ref.body_identity}" for ref in feature.source_references),
            findings, tuple(_mesh(mesh, feature.identity)
                            for mesh in kernel.tessellate(solid.shape)),
            _edges(kernel.edge_records(solid.shape), feature.identity)))
    return ReviewGeometry("mm", product.source_sha256, tuple(items), False)
