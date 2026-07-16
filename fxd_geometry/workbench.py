"""Small application-facing contract for direct real-kernel STEP viewing."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .kernel import KernelAssembly, KernelOperationError, KernelTriangleMesh, OcpKernel


@dataclass(frozen=True)
class WorkbenchDocument:
    """Immutable source bytes plus real-kernel display evidence."""

    source_name: str
    source_sha256: str
    source_bytes: bytes
    shape: object
    assembly: KernelAssembly
    meshes: tuple[KernelTriangleMesh, ...]

    @property
    def units(self) -> str:
        return self.assembly.units

    @property
    def component_count(self) -> int:
        return len(self.assembly.components) or 1


def load_step_for_workbench(source: str | Path, *, kernel: OcpKernel | None = None) -> WorkbenchDocument:
    """Import a STEP file through OCP and prepare selectable display meshes.

    This path deliberately does not create a fixture concept or mutate the
    source.  It is the first desktop viewing slice; engineering analysis is
    still entered through the richer neutral project workflow.
    """
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"STEP source does not exist: {path}")
    data = path.read_bytes()
    active_kernel = kernel or OcpKernel()
    shape = active_kernel.import_step(data)
    try:
        assembly = active_kernel.import_step_assembly(data)
    except KernelOperationError:
        # Some valid single-solid STEP files have no XCAF assembly tree. The
        # viewer still has authoritative B-Rep shape evidence; component
        # hierarchy remains unavailable until a later analysis workflow.
        assembly = KernelAssembly(
            "assembly:unstructured", sha256(data).hexdigest(), "mm", (), ()
        )
    meshes = active_kernel.tessellate(shape)
    if not meshes:
        raise ValueError("STEP source produced no displayable faces")
    return WorkbenchDocument(path.name, sha256(data).hexdigest(), data, shape, assembly, meshes)
