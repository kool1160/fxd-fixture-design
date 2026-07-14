"""CAD-neutral geometry-kernel boundary.

The AABB proof geometry is explicitly a test double. A reviewed B-Rep adapter
must implement this boundary without leaking vendor objects into the product
model. This module remains dependency-free until package and redistribution
terms are approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class KernelUnavailableError(RuntimeError):
    """Raised when no reviewed B-Rep kernel is available."""


@dataclass(frozen=True)
class KernelCapabilities:
    name: str
    version: str | None
    b_rep: bool
    step_import: bool
    step_export: bool
    topology: bool
    transforms: bool
    booleans: bool
    distance_and_clearance: bool


class GeometryKernel(Protocol):
    """Minimal neutral contract for a reviewed geometry adapter."""

    @property
    def capabilities(self) -> KernelCapabilities: ...

    def import_step(self, source: str | bytes) -> object: ...

    def export_step(self, model: object) -> bytes: ...


class AabbTestDouble:
    """Explicit marker for the dependency-free proof implementation."""

    capabilities = KernelCapabilities(
        name="fxd-aabb-test-double", version=None, b_rep=False,
        step_import=False, step_export=False, topology=False,
        transforms=True, booleans=False, distance_and_clearance=False,
    )

    def import_step(self, source: str | bytes) -> object:
        raise KernelUnavailableError(
            "AABB test double cannot import real STEP; install an approved B-Rep adapter"
        )

    def export_step(self, model: object) -> bytes:
        raise KernelUnavailableError(
            "AABB test double cannot export real STEP; install an approved B-Rep adapter"
        )


def reviewed_kernel() -> GeometryKernel:
    """Fail closed until a concrete kernel and its terms are reviewed."""

    raise KernelUnavailableError(
        "No reviewed B-Rep kernel is configured; the AABB implementation is test-only"
    )
