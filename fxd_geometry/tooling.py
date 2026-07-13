"""Vendor-neutral standard tooling contracts and deterministic selection.

The public library contains only generic metadata. A catalog item describes
an envelope and engineering requirements; it is not a vendor part, a force
certificate, or production approval. Private shop libraries can be supplied
at runtime without being copied into the public project model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .aabb import Aabb


class ToolingLibraryError(ValueError):
    """Raised when a tooling contract or selection request is invalid."""


@dataclass(frozen=True)
class ToolingItem:
    """Neutral metadata for a clamp, pin, rest, or other tooling item."""

    identity: str
    kind: str
    envelope: Aabb
    stroke: float = 0.0
    force: float = 0.0
    force_units: str = "N"
    mounting: tuple[str, ...] = ()
    access: tuple[str, ...] = ()
    source: str = "public-generic"
    license: str = "FXD generic metadata"
    attribution: str | None = None
    preferred: bool = True
    custom_geometry: bool = False
    units: str = "mm"

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.kind.strip():
            raise ToolingLibraryError("tooling identity and kind are required")
        if self.units != "mm":
            raise ToolingLibraryError("tooling contracts require explicit millimetres")
        if self.force_units != "N":
            raise ToolingLibraryError("tooling force must use explicit newtons")
        values = (self.stroke, self.force)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ToolingLibraryError("stroke and force must be finite and non-negative")
        if self.custom_geometry and self.source == "public-generic":
            raise ToolingLibraryError("custom geometry must come from a separate library source")


@dataclass(frozen=True)
class ToolingSelection:
    """Deterministic selection evidence, including why a candidate won."""

    item: ToolingItem
    reason: str
    warnings: tuple[str, ...] = ()


class ToolingLibrary:
    """An immutable, caller-owned collection of neutral tooling metadata."""

    def __init__(self, items: Iterable[ToolingItem] = ()) -> None:
        values = tuple(items)
        identities = [item.identity for item in values]
        if len(set(identities)) != len(identities):
            raise ToolingLibraryError("tooling identities must be unique")
        self._items = values

    @property
    def items(self) -> tuple[ToolingItem, ...]:
        return self._items

    def by_kind(self, kind: str) -> tuple[ToolingItem, ...]:
        return tuple(item for item in self._items if item.kind == kind)

    def select(self, kind: str, *, minimum_stroke: float = 0.0,
               minimum_force: float = 0.0, force_units: str = "N") -> ToolingSelection | None:
        """Choose a preferred standard item before a custom item.

        Selection requirements and catalog force values are compared only in
        newtons. Candidates are ordered by preferred status, custom status,
        then smallest adequate force/stroke and identity for reproducibility.
        """
        if force_units != "N":
            raise ToolingLibraryError("selection force requirements must use newtons")
        if any(not math.isfinite(value) or value < 0 for value in
               (minimum_stroke, minimum_force)):
            raise ToolingLibraryError("selection requirements must be finite and non-negative")
        candidates = tuple(item for item in self.by_kind(kind)
                           if item.stroke >= minimum_stroke and item.force >= minimum_force)
        if not candidates:
            return None
        selected = sorted(candidates, key=lambda item: (
            not item.preferred, item.custom_geometry, item.force, item.stroke, item.identity
        ))[0]
        warnings = (
            "catalog metadata does not validate clamp force, contact stability, or tolerance stack",
            "human engineering approval is required before production use",
        )
        if selected.custom_geometry:
            warnings += ("custom shop geometry is supplied outside the public library",)
        return ToolingSelection(
            selected,
            f"preferred standard candidate selected deterministically using {force_units}",
            warnings,
        )


def generic_tooling_library() -> ToolingLibrary:
    """Return safe, generic proof items without vendor catalog attribution."""
    return ToolingLibrary((
        ToolingItem("generic-toggle-clamp", "clamp", Aabb.from_values(0, 0, 0, 80, 40, 60),
                    stroke=20, force=1000, force_units="N", mounting=("base_plate", "slot"),
                    access=("operator_side",), attribution=None),
        ToolingItem("generic-round-pin", "pin", Aabb.from_values(0, 0, 0, 20, 20, 50),
                    stroke=50, force=0, force_units="N", mounting=("reamed_hole", "replaceable"),
                    access=("top_load",), attribution=None),
        ToolingItem("generic-support-rest", "rest", Aabb.from_values(0, 0, 0, 30, 30, 40),
                    force_units="N", mounting=("base_plate", "slot"),
                    access=("top_load",), attribution=None),
    ))
