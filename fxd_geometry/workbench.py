"""Small application-facing contract for direct real-kernel STEP viewing."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .kernel import KernelAssembly, KernelOperationError, KernelTriangleMesh, OcpKernel
from .step_import import import_step


@dataclass(frozen=True)
class WorkbenchDocument:
    """Immutable source bytes plus real-kernel display evidence."""

    source_name: str
    source_sha256: str
    source_bytes: bytes
    shape: object
    assembly: KernelAssembly
    meshes: tuple[KernelTriangleMesh, ...]
    provisional: bool = False

    @property
    def units(self) -> str:
        return self.assembly.units

    @property
    def component_count(self) -> int:
        return len(self.assembly.components) or 1


def load_step_for_workbench(source: str | Path | bytes, *, kernel: OcpKernel | None = None,
                            source_name: str | None = None) -> WorkbenchDocument:
    """Import a STEP file through OCP and prepare selectable display meshes.

    This path deliberately does not create a fixture concept or mutate the
    source.  It is the first desktop viewing slice; engineering analysis is
    still entered through the richer neutral project workflow.
    """
    path = Path(source) if not isinstance(source, bytes) else None
    if path is not None and not path.is_file():
        raise FileNotFoundError(f"STEP source does not exist: {path}")
    data = path.read_bytes() if path is not None else source
    active_kernel = kernel or OcpKernel()
    provisional = False
    try:
        shape = active_kernel.import_step(data)
    except KernelOperationError as real_import_error:
        try:
            product = import_step(
                data.decode("utf-8"),
                source_name=source_name or (path.name if path else "<memory>"),
            )
        except Exception:
            raise real_import_error
        shapes = tuple(
            active_kernel.make_box(
                (component.bounds.minimum.x, component.bounds.minimum.y, component.bounds.minimum.z),
                (component.bounds.maximum.x, component.bounds.maximum.y, component.bounds.maximum.z),
            )
            for component in product.components
            if component.bodies
        )
        if not shapes:
            raise real_import_error
        shape = active_kernel.compound(shapes)
        provisional = True
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
    return WorkbenchDocument(
        source_name or (path.name if path else "<memory>"), sha256(data).hexdigest(),
        data, shape, assembly, meshes, provisional,
    )
