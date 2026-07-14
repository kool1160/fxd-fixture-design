"""Manufacturing-aware solid authoring behind the CAD-neutral kernel boundary.

The product and fixture contracts contain only immutable metadata and AABBs.
This module is the explicit hand-off to a reviewed real kernel: generated
shapes are opaque, source geometry is never edited, and missing OCP is an
error rather than a silent proof-layer fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from .concepts import CompleteFixtureConcept
from .fixture import FixtureFeature, ManufacturingSpec
from .kernel import KernelOperationError, RealKernel


@dataclass(frozen=True)
class ManufacturingSolid:
    identity: str
    kind: str
    method: str
    material: str
    thickness: float | None
    fit: str
    clearance: float
    allowance: float
    interface: str | None
    operations: tuple[str, ...]
    shape: object


@dataclass(frozen=True)
class ManufacturingGeometry:
    concept_identity: str
    source_sha256: str
    units: str
    feature_identities: tuple[str, ...]
    solids: tuple[ManufacturingSolid, ...]
    model: object
    step_bytes: bytes

    @property
    def identities(self) -> tuple[str, ...]:
        return tuple(item.identity for item in self.solids)

    def __post_init__(self) -> None:
        if not self.concept_identity or not self.source_sha256:
            raise KernelOperationError("manufacturing geometry identity and source hash are required")
        if self.units != "mm":
            raise KernelOperationError("manufacturing geometry must use millimetres")
        if len(set(self.feature_identities)) != len(self.feature_identities):
            raise KernelOperationError("manufacturing feature identities must be unique")
        if self.identities != self.feature_identities:
            raise KernelOperationError("manufacturing solids must exactly match the declared feature order")
        if not self.step_bytes.startswith(b"ISO-10303-21") or b"END-ISO-10303-21" not in self.step_bytes:
            raise KernelOperationError("manufacturing STEP output is malformed or partial")


def _spec(feature: FixtureFeature) -> ManufacturingSpec:
    if feature.manufacturing is None:
        raise KernelOperationError(f"feature {feature.identity} has no manufacturing specification")
    return feature.manufacturing


def _shape_for(feature: FixtureFeature, kernel: RealKernel) -> object:
    box = feature.bounds
    low = (box.minimum.x, box.minimum.y, box.minimum.z)
    high = (box.maximum.x, box.maximum.y, box.maximum.z)
    if feature.kind == "round_pin":
        radius = min(high[0] - low[0], high[1] - low[1]) / 2.0
        return kernel.make_cylinder((low[0] + radius, low[1] + radius, low[2]), radius, high[2] - low[2])
    return kernel.make_box(low, high)


def generate_manufacturing_geometry(concept: CompleteFixtureConcept,
                                    kernel: RealKernel) -> ManufacturingGeometry:
    """Author true solids for every generated feature using the supplied kernel.

    The operation is intentionally explicit: callers must provide a complete
    `RealKernel`, so a missing or incomplete reviewed backend cannot produce
    geometry that looks fabrication-ready while remaining an AABB proof.
    """
    if concept.engineering_status == "invalid":
        raise KernelOperationError("invalid fixture concepts cannot author manufacturing geometry")
    if not kernel.capabilities.is_complete:
        raise KernelOperationError("complete real-kernel capabilities are required")
    feature_identities = tuple(feature.identity for feature in concept.fixture.features)
    if len(set(feature_identities)) != len(feature_identities):
        raise KernelOperationError("fixture feature identities must be unique")
    solids: list[ManufacturingSolid] = []
    shapes: list[object] = []
    for feature in concept.fixture.features:
        spec = _spec(feature)
        shape = _shape_for(feature, kernel)
        solids.append(ManufacturingSolid(
            feature.identity, feature.kind, spec.method, spec.material, spec.thickness,
            spec.fit, spec.clearance, spec.allowance, spec.interface, spec.operations, shape,
        ))
        shapes.append(shape)
    model = kernel.compound(tuple(shapes))
    return ManufacturingGeometry(
        concept.identity,
        concept.fixture.source_sha256,
        concept.fixture.units,
        feature_identities,
        tuple(solids),
        model,
        kernel.export_step(model),
    )
