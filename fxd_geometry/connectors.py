"""Optional CAD connector contracts with a safe, neutral default.

Connectors are deliberately capability based.  A connector may translate a
vendor document into the immutable :class:`ProductModel`, but it may not hand
vendor objects to the engineering core or mutate a source document as part of
an import.  The SOLIDWORKS probe below only inspects the local host; it never
starts SOLIDWORKS and does not require or import a vendor SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
from pathlib import Path
from typing import Literal

from .product_model import ProductModel
from .step_import import import_step


ConnectorStatus = Literal["available", "not_detected", "unsupported", "unknown"]


@dataclass(frozen=True)
class CompatibilityProbe:
    connector: str
    status: ConnectorStatus
    host: str
    version: str | None
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ConnectorCapabilities:
    import_product: bool
    export_review_package: bool
    mutate_vendor_document: bool = False


class ConnectorError(RuntimeError):
    """A connector could not complete a safe translation."""


class ApprovalRequired(ConnectorError):
    """Raised before a connector is allowed to mutate a vendor document."""


@dataclass(frozen=True)
class ConnectorDescriptor:
    identity: str
    display_name: str
    capabilities: ConnectorCapabilities
    license_status: str


class NeutralStepConnector:
    """Standalone connector that keeps FXD useful without a CAD vendor."""

    descriptor = ConnectorDescriptor(
        identity="neutral-step",
        display_name="FXD neutral STEP proof connector",
        capabilities=ConnectorCapabilities(import_product=True, export_review_package=True),
        license_status="repository-local proof; no third-party dependency",
    )

    def probe(self) -> CompatibilityProbe:
        return CompatibilityProbe(
            self.descriptor.identity, "available", platform.system(), None,
            ("FXD dependency-free STEP proof importer is present",), (),
        )

    def import_product(self, source: str | Path) -> ProductModel:
        try:
            return import_step(source)
        except Exception as exc:
            raise ConnectorError(f"neutral STEP import failed: {exc}") from exc

    def export_review_package(self, package: object, destination: str | Path) -> tuple[Path, ...]:
        """Write only neutral review artifacts; never opens a vendor document."""

        from .export import FabricationPackage, write_fabrication_package

        if not isinstance(package, FabricationPackage):
            raise ConnectorError("neutral export requires a FabricationPackage")
        try:
            return tuple(write_fabrication_package(package, destination))
        except Exception as exc:
            raise ConnectorError(f"neutral review-package export failed: {exc}") from exc


def probe_solidworks() -> CompatibilityProbe:
    """Perform a conservative, read-only SOLIDWORKS host compatibility probe.

    Detection is opt-in through ``FXD_SOLIDWORKS_VERSION`` because filesystem
    and registry probing would create platform-specific behavior and still
    could not establish SDK or license rights.  A detected host is therefore
    reported as ``unknown`` rather than as compatible.
    """

    host = platform.system()
    version = os.environ.get("FXD_SOLIDWORKS_VERSION")
    if host != "Windows":
        return CompatibilityProbe(
            "solidworks", "unsupported", host, version,
            ("SOLIDWORKS Connected/Makers requires a Windows host",),
            ("No vendor SDK or COM automation was invoked", "Run the approved probe on Windows"),
        )
    if not version:
        return CompatibilityProbe(
            "solidworks", "not_detected", host, None,
            ("FXD_SOLIDWORKS_VERSION was not provided",),
            ("Host installation, edition, API access, and license terms were not inspected",),
        )
    return CompatibilityProbe(
        "solidworks", "unknown", host, version,
        ("Version was supplied by the operator; no SDK call was made",),
        ("Compatibility and Makers/Connected API rights require vendor-approved Windows testing",),
    )


def require_destructive_approval(operation: str, approved: bool = False) -> None:
    """Guard all future vendor-document mutation behind explicit approval."""

    if operation not in {"mutate_vendor_document", "save_into_vendor_document"}:
        raise ConnectorError(f"unsupported connector operation: {operation}")
    if not approved:
        raise ApprovalRequired(
            f"explicit human approval is required before connector operation {operation!r}"
        )


def connector_registry() -> tuple[NeutralStepConnector, ...]:
    """Return connectors available without vendor SDKs or commercial terms."""

    return (NeutralStepConnector(),)
