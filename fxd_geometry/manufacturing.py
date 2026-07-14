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
    dxf_bytes: bytes

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
        if not self.dxf_bytes.startswith(b"0\nSECTION") or not self.dxf_bytes.rstrip().endswith(b"0\nEOF"):
            raise KernelOperationError("manufacturing DXF output is malformed or partial")


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
    shape = kernel.make_box(low, high)
    # These are deliberately simple, axis-aligned fabrication operations.  The
    # resulting solids are still true B-Rep and the operation names remain in
    # the traceable ManufacturingSpec rather than being hidden in AI output.
    if feature.kind == "baseplate":
        margin = max(feature.parameters.get("margin", 0.0) / 2.0, 2.0)
        z0, z1 = low[2], high[2]
        for x in (low[0] + margin, high[0] - margin):
            for y in (low[1] + margin, high[1] - margin):
                slot = kernel.make_slot((x - 2.5, y - 2.5, z0 - 1.0),
                                        (x + 2.5, y + 2.5, z1 + 1.0))
                shape = kernel.cut(shape, slot)
    elif feature.kind in {"support_pad", "hard_stop", "clamp_mount"}:
        # A shallow relief on the stock makes the adjustable/tab interface an
        # authored operation, not merely metadata on an AABB envelope.
        axis = min(range(3), key=lambda i: high[i] - low[i])
        relief_low, relief_high = list(low), list(high)
        relief_high[axis] = relief_low[axis] + min(1.0, (high[axis] - low[axis]) / 3.0)
        shape = kernel.cut(shape, kernel.make_slot(tuple(relief_low), tuple(relief_high)))
    elif feature.kind == "relieved_locator":
        relief_low, relief_high = list(low), list(high)
        relief_high[0] = relief_low[0] + min(2.0, (high[0] - low[0]) / 2.0)
        shape = kernel.cut(shape, kernel.make_slot(tuple(relief_low), tuple(relief_high)))
    return shape


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
    pin_features = tuple(item for item in concept.fixture.features if item.kind == "round_pin")
    for feature in concept.fixture.features:
        spec = _spec(feature)
        shape = _shape_for(feature, kernel)
        if feature.kind == "baseplate" and pin_features:
            # The starter fixture uses a vertical build axis.  The hole tool
            # extends beyond stock so the Boolean is unambiguously through.
            pin = pin_features[0].bounds
            radius = min(pin.maximum.x - pin.minimum.x,
                         pin.maximum.y - pin.minimum.y) / 2.0 + spec.clearance
            center = ((pin.minimum.x + pin.maximum.x) / 2.0,
                      (pin.minimum.y + pin.maximum.y) / 2.0,
                      feature.bounds.minimum.z - 1.0)
            shape = kernel.cut(shape, kernel.make_hole(
                center, radius, feature.bounds.maximum.z - feature.bounds.minimum.z + 2.0))
        topology = kernel.topology_counts(shape)
        if topology.solids < 1:
            raise KernelOperationError(f"manufacturing feature {feature.identity} did not produce a solid")
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
        _profiles_dxf(concept),
    )


def _profiles_dxf(concept: CompleteFixtureConcept) -> bytes:
    """Emit deterministic profiles for the authored prismatic/cylindrical solids.

    Profiles are derived from the same feature dimensions used to author the
    kernel solids.  They are intentionally limited to the supported axis-
    aligned fabrication operations; unsupported free-form geometry must not be
    mislabeled as a fabrication profile.
    """
    def n(value: float) -> str:
        return format(value, ".9g")

    lines = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4",
             "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for feature in concept.fixture.features:
        low, high = feature.bounds.minimum, feature.bounds.maximum
        if feature.kind == "round_pin":
            cx, cy = (low.x + high.x) / 2, (low.y + high.y) / 2
            radius = min(high.x - low.x, high.y - low.y) / 2
            lines += ["0", "CIRCLE", "8", feature.kind, "10", n(cx), "20", n(cy), "40", n(radius)]
            continue
        points = ((low.x, low.y), (high.x, low.y), (high.x, high.y),
                  (low.x, high.y), (low.x, low.y))
        lines += ["0", "LWPOLYLINE", "8", feature.kind, "90", "5", "70", "1"]
        for x, y in points:
            lines += ["10", n(x), "20", n(y)]
        if feature.kind == "baseplate":
            margin = max(feature.parameters.get("margin", 0.0) / 2.0, 2.0)
            for x in (low.x + margin, high.x - margin):
                for y in (low.y + margin, high.y - margin):
                    slot = ((x - 2.5, y - 2.5), (x + 2.5, y - 2.5),
                            (x + 2.5, y + 2.5), (x - 2.5, y + 2.5), (x - 2.5, y - 2.5))
                    lines += ["0", "LWPOLYLINE", "8", "baseplate_slot", "90", "5", "70", "1"]
                    for sx, sy in slot:
                        lines += ["10", n(sx), "20", n(sy)]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return ("\n".join(lines) + "\n").encode("ascii")
