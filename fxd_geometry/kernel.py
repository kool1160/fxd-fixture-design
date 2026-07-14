"""CAD-neutral boundary for a reviewed B-Rep geometry backend.

The public package intentionally does not import a kernel.  A deployment may
provide an approved backend (currently the OCCT family is the candidate), but
the rest of FXD must depend on this boundary rather than on vendor objects.
The AABB implementation remains available as a deliberately named test
double and is never returned by :func:`require_real_kernel`.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Protocol


class KernelUnavailable(RuntimeError):
    """Raised when a real, approved B-Rep backend is not installed."""


@dataclass(frozen=True)
class KernelCapabilities:
    """Capabilities a backend must expose before it can be accepted."""

    backend: str
    version: str
    step_import: bool
    topology: bool
    transforms: bool
    booleans: bool
    distance_and_clearance: bool
    neutral_export: bool

    @property
    def is_complete(self) -> bool:
        return all((self.step_import, self.topology, self.transforms,
                    self.booleans, self.distance_and_clearance,
                    self.neutral_export))


class RealKernel(Protocol):
    """Minimal neutral contract for a production geometry adapter."""

    @property
    def capabilities(self) -> KernelCapabilities: ...

    def import_step(self, source: str | bytes) -> object: ...

    def export_step(self, model: object) -> bytes: ...

    def boolean(self, operation: str, left: object, right: object) -> object: ...

    def clearance(self, left: object, right: object) -> float: ...


def installed_backend_candidates() -> tuple[str, ...]:
    """Return detectable candidates without importing or executing them."""
    candidates = []
    for module in ("OCC", "OCP"):
        if find_spec(module) is not None:
            candidates.append(module)
    return tuple(candidates)


def require_real_kernel() -> RealKernel:
    """Load an approved adapter or fail with an actionable, honest error.

    No implicit fallback is permitted: using the AABB test double for a
    real-kernel operation would invalidate geometry conclusions.
    """
    candidates = installed_backend_candidates()
    if not candidates:
        raise KernelUnavailable(
            "No approved B-Rep backend is installed. Install the reviewed "
            "OCCT adapter after recording its exact version, license, and "
            "redistribution obligations; the AABB test double is not a "
            "real-kernel fallback."
        )
    raise KernelUnavailable(
        f"Detected backend(s) {', '.join(candidates)}, but no reviewed FXD "
        "adapter is enabled for them. Complete the adapter and license review "
        "before using real-kernel operations."
    )

