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
class _CutOperation:
    """One deterministic cut used by both B-Rep authoring and DXF export."""

    identity: str
    feature_identity: str
    kind: str
    layer: str
    minimum: tuple[float, float, float] | None = None
    maximum: tuple[float, float, float] | None = None
    center: tuple[float, float, float] | None = None
    radius: float | None = None
    height: float | None = None

    def __post_init__(self) -> None:
        if self.kind == "slot":
            if self.minimum is None or self.maximum is None:
                raise KernelOperationError("slot operation requires minimum and maximum")
        elif self.kind == "hole":
            if self.center is None or self.radius is None or self.height is None:
                raise KernelOperationError("hole operation requires center, radius, and height")
            if self.radius <= 0 or self.height <= 0:
                raise KernelOperationError("hole operation dimensions must be positive")
        else:
            raise KernelOperationError(f"unsupported manufacturing cut operation: {self.kind}")


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


def _cut_plan(concept: CompleteFixtureConcept) -> tuple[_CutOperation, ...]:
    """Build the single source of truth for supported manufacturing cuts."""
    operations: list[_CutOperation] = []
    pin_features = tuple(item for item in concept.fixture.features if item.kind == "round_pin")
    for feature in concept.fixture.features:
        low = (feature.bounds.minimum.x, feature.bounds.minimum.y, feature.bounds.minimum.z)
        high = (feature.bounds.maximum.x, feature.bounds.maximum.y, feature.bounds.maximum.z)
        if feature.kind == "baseplate":
            margin = max(feature.parameters.get("margin", 0.0) / 2.0, 2.0)
            for x_index, x in enumerate((low[0] + margin, high[0] - margin), 1):
                for y_index, y in enumerate((low[1] + margin, high[1] - margin), 1):
                    operations.append(_CutOperation(
                        f"{feature.identity}-slot-{x_index}-{y_index}", feature.identity,
                        "slot", "baseplate_slot",
                        (x - 2.5, y - 2.5, low[2] - 1.0),
                        (x + 2.5, y + 2.5, high[2] + 1.0),
                    ))
            if pin_features:
                pin = pin_features[0].bounds
                spec = _spec(feature)
                radius = min(pin.maximum.x - pin.minimum.x,
                             pin.maximum.y - pin.minimum.y) / 2.0 + spec.clearance
                operations.append(_CutOperation(
                    f"{feature.identity}-pin-hole", feature.identity, "hole", "baseplate_pin_hole",
                    center=((pin.minimum.x + pin.maximum.x) / 2.0,
                            (pin.minimum.y + pin.maximum.y) / 2.0,
                            low[2] - 1.0),
                    radius=radius, height=high[2] - low[2] + 2.0,
                ))
        elif feature.kind in {"support_pad", "hard_stop", "clamp_mount"}:
            axis = min(range(3), key=lambda index: high[index] - low[index])
            relief_high = list(high)
            relief_high[axis] = low[axis] + min(1.0, (high[axis] - low[axis]) / 3.0)
            operations.append(_CutOperation(
                f"{feature.identity}-relief", feature.identity, "slot", f"{feature.kind}_relief",
                low, tuple(relief_high),
            ))
        elif feature.kind == "relieved_locator":
            relief_high = list(high)
            relief_high[0] = low[0] + min(2.0, (high[0] - low[0]) / 2.0)
            operations.append(_CutOperation(
                f"{feature.identity}-relief", feature.identity, "slot", "locator_relief",
                low, tuple(relief_high),
            ))
    identities = tuple(operation.identity for operation in operations)
    if len(set(identities)) != len(identities):
        raise KernelOperationError("manufacturing cut operation identities must be unique")
    return tuple(operations)


def _base_shape(feature: FixtureFeature, kernel: RealKernel) -> object:
    box = feature.bounds
    low = (box.minimum.x, box.minimum.y, box.minimum.z)
    high = (box.maximum.x, box.maximum.y, box.maximum.z)
    if feature.kind == "round_pin":
        radius = min(high[0] - low[0], high[1] - low[1]) / 2.0
        return kernel.make_cylinder((low[0] + radius, low[1] + radius, low[2]), radius, high[2] - low[2])
    return kernel.make_box(low, high)


def _apply_cut(shape: object, operation: _CutOperation, kernel: RealKernel) -> object:
    if operation.kind == "slot":
        tool = kernel.make_slot(operation.minimum, operation.maximum)
    else:
        tool = kernel.make_hole(operation.center, operation.radius, operation.height)
    return kernel.cut(shape, tool)


def generate_manufacturing_geometry(concept: CompleteFixtureConcept,
                                    kernel: RealKernel) -> ManufacturingGeometry:
    """Author true solids and matching DXF profiles from one operation plan."""
    if concept.engineering_status == "invalid":
        raise KernelOperationError("invalid fixture concepts cannot author manufacturing geometry")
    if not kernel.capabilities.is_complete:
        raise KernelOperationError("complete real-kernel capabilities are required")
    feature_identities = tuple(feature.identity for feature in concept.fixture.features)
    if len(set(feature_identities)) != len(feature_identities):
        raise KernelOperationError("fixture feature identities must be unique")
    cut_plan = _cut_plan(concept)
    cuts_by_feature = {
        identity: tuple(operation for operation in cut_plan if operation.feature_identity == identity)
        for identity in feature_identities
    }
    solids: list[ManufacturingSolid] = []
    shapes: list[object] = []
    for feature in concept.fixture.features:
        spec = _spec(feature)
        shape = _base_shape(feature, kernel)
        for operation in cuts_by_feature[feature.identity]:
            shape = _apply_cut(shape, operation, kernel)
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
        _profiles_dxf(concept, cut_plan),
    )


def _profiles_dxf(concept: CompleteFixtureConcept,
                  cut_plan: tuple[_CutOperation, ...]) -> bytes:
    """Emit profiles from the same operation plan used for B-Rep cuts."""
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
        else:
            points = ((low.x, low.y), (high.x, low.y), (high.x, high.y),
                      (low.x, high.y), (low.x, low.y))
            lines += ["0", "LWPOLYLINE", "8", feature.kind, "90", "5", "70", "1"]
            for x, y in points:
                lines += ["10", n(x), "20", n(y)]
    for operation in cut_plan:
        if operation.kind == "hole":
            lines += ["0", "CIRCLE", "8", operation.layer,
                      "10", n(operation.center[0]), "20", n(operation.center[1]),
                      "40", n(operation.radius)]
        else:
            low, high = operation.minimum, operation.maximum
            points = ((low[0], low[1]), (high[0], low[1]), (high[0], high[1]),
                      (low[0], high[1]), (low[0], low[1]))
            lines += ["0", "LWPOLYLINE", "8", operation.layer, "90", "5", "70", "1"]
            for x, y in points:
                lines += ["10", n(x), "20", n(y)]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return ("\n".join(lines) + "\n").encode("ascii")
