"""Milestone 30 fixture-construction contracts and deterministic checks.

This module composes the existing structure, placement, component geometry, and
validation layers.  It deliberately does not interpret provisional dimensions,
shop practices, or customer tooling as universal manufacturing policy.  A
fixture build plan is editable review evidence; OCP authoring happens only for
components whose authority is explicitly ``AUTHORED_MANUFACTURING``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import itertools
import json
import math
import re
from pathlib import Path

from .aabb import Aabb, Vec3
from .annotations import GeometryReference
from .concepts import CompleteFixtureConcept
from .kernel import KernelOperationError, RealKernel, TopologyCounts
from .product_model import ProductModel


M30_SCHEMA = "fxd-fixture-build-v1"
M32_SCHEMA = "fxd-multi-station-weld-fixture-v1"


class FixtureBuildError(ValueError):
    """Raised when fixture-build evidence is malformed or unsafe to author."""


class FixturePurpose(str, Enum):
    FULL_WELD = "full_weld_fixture"
    TACK_LOCATION = "tack_location_fixture"
    ASSEMBLY = "assembly_fixture"
    INSPECTION = "inspection_fixture"
    PROFILE_CHECK = "profile_check_fixture"
    GO_NO_GO = "go_no_go_gauge"
    REWORK = "rework_fixture"
    ROBOTIC = "robotic_or_cobot_fixture"
    COMBINED_BUILD_CHECK = "combined_build_and_check_fixture"


class FixtureFamily(str, Enum):
    """Fixture families supported by a governed deterministic generator."""

    LINEAR_MULTI_STATION_WELD = "linear_multi_station_weld_fixture"


class ConstructionMethod(str, Enum):
    AUTO = "auto_select"
    LASER_CUT_FABRICATED = "laser_cut_fabricated"
    CNC_MACHINED = "cnc_machined"
    HYBRID = "hybrid_fabricated_and_machined"
    WELDED_TUBE_FRAME = "welded_tube_frame"
    SHOP_STANDARD = "shop_standard"
    TACK_LOCATION = "tack_location_fixture"


class FixtureLifecycle(str, Enum):
    STORE_AND_REUSE = "store_and_reuse"
    DISPOSABLE_RECUT = "disposable_or_job_run_recut"
    REUSABLE_TOOLING_ON_DISPOSABLE = "reusable_tooling_on_disposable_fixture"
    PERMANENT = "full_permanent_fixture"


class ClecoStrategy(str, Enum):
    NONE = "none"
    PRODUCT_HOLES = "product_cleco_holes"
    SEPARATE_FIXTURE_HOLES = "separate_fixture_cleco_holes"


class GeometryAuthority(str, Enum):
    SOURCE = "source_geometry"
    AUTHORED_MANUFACTURING = "authored_manufacturing_geometry"
    PURCHASED_COMPONENT = "purchased_component_geometry"
    PROVISIONAL_ENVELOPE = "provisional_engineering_envelope"


class BuildComponentRole(str, Enum):
    BASEPLATE = "baseplate"
    STATION_PLATE = "local_station_plate"
    TUBE_FRAME = "tube_frame"
    CROSSMEMBER = "crossmember"
    RISER = "riser"
    TOWER = "tower"
    GUSSET = "gusset"
    LOCATOR_PLATE = "locator_plate"
    SUPPORT_PAD = "support_pad"
    HARD_STOP = "hard_stop"
    ROUND_PIN = "round_pin"
    DIAMOND_PIN = "diamond_pin"
    PIN_BUSHING = "pin_bushing"
    SHIM_PACK = "shim_pack"
    CLAMP_PLATE = "clamp_plate"
    TAB = "tab"
    SLOT = "slot"
    RELIEF = "relief"
    ACCESS_CUTOUT = "access_cutout"
    WEAR_PLATE = "wear_plate"
    LOCATOR_BLOCK = "replaceable_locator_block"
    TOOLING_MOUNT = "purchased_tooling_mount"
    FORK_POCKET = "fork_pocket"
    LIFTING_FEATURE = "lifting_feature"
    DATUM_RAIL = "datum_rail_or_backplate"
    CLAMP_BRACKET = "toggle_clamp_mounting_bracket"
    TOGGLE_CLAMP = "vendor_neutral_toggle_clamp"
    CLAMP_OPEN_ENVELOPE = "vendor_neutral_clamp_open_envelope"
    END_BRACE = "end_brace"
    MOUNTING_FOOT = "mounting_foot"


class HoleProcess(str, Enum):
    LASER_CLEARANCE = "laser_cut_clearance"
    LASER_PILOT = "laser_cut_pilot"
    DRILLED = "drilled"
    TAPPED = "tapped"
    REAMED = "reamed"
    BORED = "bored"
    MACHINED = "machined"
    DOWEL = "dowel"
    LOCATOR_BORE = "locator_bore"
    ACCESS = "access"
    INSPECTION_ONLY = "inspection_only"
    CLECO = "cleco"
    PLUG_WELD = "plug_weld"
    WELD_FILL_GRIND = "weld_fill_and_grind"


class AdjustmentState(str, Enum):
    PROVISIONAL = "provisional_adjustment"
    PROVE_OUT = "prove_out_setting"
    LOCKED = "locked_production_position"
    DOWELED = "doweled_production_position"
    REVALIDATION_REQUIRED = "revalidation_required"


class NestClassification(str, Enum):
    PRODUCT = "sellable_product_part"
    FIXTURE = "fixture_part_not_for_shipment"
    REUSABLE_HARDWARE = "reusable_fixture_hardware"
    PURCHASED_TOOLING = "purchased_tooling"


@dataclass(frozen=True)
class M30Rule:
    """Stable, auditable rule definition tied to the supplied M30 handoff."""

    identity: str
    title: str
    description: str
    applicability: str
    required_evidence: tuple[str, ...]
    deterministic_logic: str
    result_states: tuple[str, ...]
    severity: str
    override_policy: str
    source_handoff_reference: str
    test_mapping: tuple[str, ...]


def _rule(identity: str, title: str, description: str, applicability: str,
          evidence: tuple[str, ...], logic: str, severity: str,
          test: tuple[str, ...]) -> M30Rule:
    return M30Rule(
        identity, title, description, applicability, evidence, logic,
        ("valid", "provisional", "invalid", "not_evaluated"), severity,
        "Engineer assumptions and overrides remain explicit evidence; they never silently pass a gate.",
        "M30-USER-SPEC", test,
    )


# Each required category is represented by at least one stable public rule.
RULE_CATALOG: tuple[M30Rule, ...] = (
    _rule("FXD-DAT-001", "Three-point primary datum", "Four fixed primary datum pads can overconstrain a workpiece.", "locating", ("primary datum contacts",), "flag more than three fixed primary pads", "error", ("test_four_fixed_pads",)),
    _rule("FXD-LOC-001", "Locator contact suitability", "Locators cannot silently use weld seams or tube radii.", "locating", ("contact condition",), "flag seam or radius contacts", "error", ("test_locator_contact",)),
    _rule("FXD-SUP-001", "Clamp reaction support", "A clamp reaction requires an explicit supporting feature.", "clamping", ("reaction support",), "flag a missing support reference", "error", ("test_clamp_support",)),
    _rule("FXD-PIN-001", "Two-hole locating pattern", "Two full round pins may bind under tolerance variation.", "pin locating", ("pin roles",), "flag two or more full round pins", "error", ("test_round_diamond",)),
    _rule("FXD-CLP-001", "Clamp loading and release", "Clamp information must remain explicit and supported.", "clamping", ("clamp reaction", "unload evidence"), "flag unsupported clamps or fixed-pin traps", "error", ("test_clamp_support", "test_unload_trap")),
    _rule("FXD-ACC-001", "Purpose-specific access", "Tack fixtures require tack access; full-weld access is a separate check.", "access", ("fixture purpose", "tack access"), "do not require full weld access for tack purpose", "warning", ("test_tack_access",)),
    _rule("FXD-WLD-001", "Weld-access evidence", "Visible weld geometry is not proof of workable torch access.", "weld access", ("torch approach evidence",), "retain unavailable evidence as provisional", "warning", ("test_tack_access",)),
    _rule("FXD-DST-001", "Welded-shape unloading", "Nominal CAD is not proof of post-weld unloading clearance.", "unloading", ("unload clearance evidence",), "flag fixed pins without unload clearance", "error", ("test_unload_trap",)),
    _rule("FXD-MFG-001", "Manufacturing geometry authority", "Only authored or purchased geometry is eligible for manufacturing export.", "export", ("geometry authority",), "block provisional envelopes", "error", ("test_geometry_authority",)),
    _rule("FXD-TAB-001", "Tab and slot fit", "Tabs require deterministic clearance, engagement, relief, and insertion evidence.", "fabrication", ("tab thickness", "slot width", "assembly direction"), "reject undersized slots and bottoming tabs", "error", ("test_tab_slot",)),
    _rule("FXD-HOL-001", "Hole process authority", "Circular CAD is not proof of a precision manufactured hole.", "holes", ("hole process",), "reject precision requested from laser-only holes", "error", ("test_hole_process",)),
    _rule("FXD-THR-001", "Threaded mounting evidence", "Tapped mount holes require explicit thread and plate evidence.", "threaded mounts", ("thread pitch", "engagement"), "flag incomplete tapped-hole evidence", "warning", ("test_hole_process",)),
    _rule("FXD-PKY-001", "Poka-yoke accessibility", "Poka-yoke must not silently create a trapped or hidden seating state.", "loading", ("poka-yoke evidence",), "flag absent explicit orientation evidence", "warning", ("test_poka_yoke",)),
    _rule("FXD-CLE-001", "Cleco construction and removal", "Clecos are temporary construction aids, not automatic precision locators.", "Cleco", ("diameter", "grip range", "access", "removal"), "validate fit, access, and product-hole approval", "error", ("test_cleco",)),
    _rule("FXD-TACK-001", "Tack/location workflow", "Tack fixtures locate, tack, release, and unload before finish welding elsewhere.", "tack fixture", ("tack access", "release sequence"), "validate tack evidence without requiring full-weld access", "error", ("test_tack_workflow",)),
    _rule("FXD-COST-001", "Lifecycle comparison", "Store/reuse versus recut is a ranked preference, not universal law.", "lifecycle", ("quantity", "repeat frequency", "job revision"), "keep lifecycle rationale explicit", "warning", ("test_lifecycle",)),
    _rule("FXD-MNT-001", "Replaceable service items", "Wear and locator items need accessible replacement evidence.", "maintenance", ("replacement evidence",), "flag inaccessible non-replaceable wear contacts", "warning", ("test_maintenance",)),
    _rule("FXD-EXP-001", "Review-only export gate", "Stale, suppressed, provisional, or invalid build evidence cannot export.", "export", ("validation digest", "authority"), "fail closed before package creation", "error", ("test_export_gate",)),
    _rule("FXD-M32-STA", "Multi-station layout", "Station count, pitch, product instances, and fixture length require deterministic evidence.", "multi-station synthesis", ("station layout", "product envelope"), "reject overlap or out-of-bounds station layouts", "error", ("test_multi_station_fixture",)),
    _rule("FXD-M32-CLP", "Multi-station clamp reach", "Each station requires a reachable clamp tip and a clear open envelope.", "multi-station clamping", ("clamp reach", "release envelope"), "reject unreachable or blocked clamp stations", "error", ("test_multi_station_fixture",)),
    _rule("FXD-M32-ACC", "Multi-station access", "Loading, unloading, hand, and weld access remain first-class station evidence.", "multi-station access", ("access envelopes",), "reject trapped or inaccessible stations", "error", ("test_multi_station_fixture",)),
    _rule("FXD-M32-CON", "Multi-station connectivity", "A datum rail, stations, braces, and base must share a connected load path.", "multi-station structure", ("component parent connectivity",), "reject disconnected station or brace components", "error", ("test_multi_station_fixture",)),
)
RULES_BY_ID = {item.identity: item for item in RULE_CATALOG}


@dataclass(frozen=True)
class HoleProcessSpec:
    identity: str
    center_mm: Vec3
    diameter_mm: float
    process: HoleProcess
    precision_required: bool = False
    thread_pitch: str | None = None
    thread_engagement_mm: float | None = None
    final_operation: HoleProcess | None = None
    notes: str = ""
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not math.isfinite(self.diameter_mm) or self.diameter_mm <= 0:
            raise FixtureBuildError("hole identity and positive finite diameter are required")
        if self.thread_engagement_mm is not None and self.thread_engagement_mm <= 0:
            raise FixtureBuildError("thread engagement must be positive when supplied")
        if self.process == HoleProcess.TAPPED and not self.thread_pitch:
            raise FixtureBuildError("tapped holes require an explicit thread pitch")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "center_mm": self.center_mm.__dict__,
            "diameter_mm": self.diameter_mm, "process": self.process.value,
            "precision_required": self.precision_required, "thread_pitch": self.thread_pitch,
            "thread_engagement_mm": self.thread_engagement_mm,
            "final_operation": self.final_operation.value if self.final_operation else None,
            "notes": self.notes, "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "HoleProcessSpec":
        final = data.get("final_operation")
        return cls(str(data["identity"]), Vec3(**data["center_mm"]), float(data["diameter_mm"]),
                   HoleProcess(data["process"]), bool(data.get("precision_required", False)),
                   data.get("thread_pitch"), data.get("thread_engagement_mm"),
                   HoleProcess(final) if final else None, str(data.get("notes", "")),
                   tuple(data.get("evidence", ())))


@dataclass(frozen=True)
class SlotProcessSpec:
    """Through-slot operation kept in parity between OCP and planar review data."""

    identity: str
    minimum_mm: Vec3
    maximum_mm: Vec3
    purpose: str

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.purpose.strip():
            raise FixtureBuildError("slot identity and purpose are required")
        if any(left >= right for left, right in zip(
                self.minimum_mm.__dict__.values(), self.maximum_mm.__dict__.values())):
            raise FixtureBuildError("slot bounds must have positive extent")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "minimum_mm": self.minimum_mm.__dict__,
            "maximum_mm": self.maximum_mm.__dict__, "purpose": self.purpose,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SlotProcessSpec":
        return cls(str(data["identity"]), Vec3(**data["minimum_mm"]),
                   Vec3(**data["maximum_mm"]), str(data["purpose"]))


@dataclass(frozen=True)
class TabSlotJoint:
    identity: str
    tab_component_identity: str
    slot_component_identity: str
    tab_thickness_mm: float
    slot_width_mm: float
    engagement_mm: float
    clearance_mm: float
    insertion_direction: Vec3
    dog_bone_relief: bool = False
    weld_relief: bool = False
    bottoms_out: bool = False
    assembly_sequence: int = 1
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (self.tab_thickness_mm, self.slot_width_mm, self.engagement_mm, self.clearance_mm)
        if not self.identity.strip() or self.assembly_sequence < 1 or any(value < 0 for value in values):
            raise FixtureBuildError("tab-slot dimensions and a positive assembly sequence are required")
        if self.insertion_direction == Vec3(0.0, 0.0, 0.0):
            raise FixtureBuildError("tab-slot insertion direction must be non-zero")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "tab_component_identity": self.tab_component_identity,
            "slot_component_identity": self.slot_component_identity,
            "tab_thickness_mm": self.tab_thickness_mm, "slot_width_mm": self.slot_width_mm,
            "engagement_mm": self.engagement_mm, "clearance_mm": self.clearance_mm,
            "insertion_direction": self.insertion_direction.__dict__, "dog_bone_relief": self.dog_bone_relief,
            "weld_relief": self.weld_relief, "bottoms_out": self.bottoms_out,
            "assembly_sequence": self.assembly_sequence, "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TabSlotJoint":
        return cls(str(data["identity"]), str(data["tab_component_identity"]), str(data["slot_component_identity"]),
                   float(data["tab_thickness_mm"]), float(data["slot_width_mm"]),
                   float(data["engagement_mm"]), float(data["clearance_mm"]),
                   Vec3(**data["insertion_direction"]), bool(data.get("dog_bone_relief", False)),
                   bool(data.get("weld_relief", False)), bool(data.get("bottoms_out", False)),
                   int(data.get("assembly_sequence", 1)), tuple(data.get("evidence", ())))


@dataclass(frozen=True)
class ClecoSpec:
    identity: str
    strategy: ClecoStrategy
    component_identity: str
    diameter_mm: float
    hole_diameter_mm: float
    material_stack_mm: float
    minimum_grip_mm: float
    maximum_grip_mm: float
    quantity: int
    installation_access: bool
    removal_access: bool
    plier_access: bool
    removed_before_welding: bool
    retained_during_tack: bool
    product_hole_approved: bool = False
    post_use_process: HoleProcess | None = None
    spacing_mm: float | None = None
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    installation_side: str = "fixture assembly side"
    removal_side: str = "fixture assembly side"
    fixture_build_role: str = "temporary fixture assembly"
    product_location_role: str | None = None
    hole_remains: bool = True

    def __post_init__(self) -> None:
        values = (self.diameter_mm, self.hole_diameter_mm, self.material_stack_mm,
                  self.minimum_grip_mm, self.maximum_grip_mm)
        if not self.identity.strip() or self.quantity < 1 or any(value <= 0 for value in values):
            raise FixtureBuildError("Cleco dimensions, identity, and quantity must be positive")
        if self.minimum_grip_mm > self.maximum_grip_mm:
            raise FixtureBuildError("Cleco grip range is reversed")
        if self.spacing_mm is not None and self.spacing_mm <= 0:
            raise FixtureBuildError("Cleco spacing must be positive when supplied")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "strategy": self.strategy.value,
            "component_identity": self.component_identity, "diameter_mm": self.diameter_mm,
            "hole_diameter_mm": self.hole_diameter_mm, "material_stack_mm": self.material_stack_mm,
            "minimum_grip_mm": self.minimum_grip_mm, "maximum_grip_mm": self.maximum_grip_mm,
            "quantity": self.quantity, "installation_access": self.installation_access,
            "removal_access": self.removal_access, "plier_access": self.plier_access,
            "removed_before_welding": self.removed_before_welding,
            "retained_during_tack": self.retained_during_tack,
            "product_hole_approved": self.product_hole_approved,
            "post_use_process": self.post_use_process.value if self.post_use_process else None,
            "spacing_mm": self.spacing_mm, "evidence": list(self.evidence),
            "assumptions": list(self.assumptions),
            "installation_side": self.installation_side, "removal_side": self.removal_side,
            "fixture_build_role": self.fixture_build_role,
            "product_location_role": self.product_location_role, "hole_remains": self.hole_remains,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ClecoSpec":
        post = data.get("post_use_process")
        return cls(str(data["identity"]), ClecoStrategy(data["strategy"]), str(data["component_identity"]),
                   float(data["diameter_mm"]), float(data["hole_diameter_mm"]), float(data["material_stack_mm"]),
                   float(data["minimum_grip_mm"]), float(data["maximum_grip_mm"]), int(data["quantity"]),
                   bool(data["installation_access"]), bool(data["removal_access"]), bool(data["plier_access"]),
                   bool(data["removed_before_welding"]), bool(data["retained_during_tack"]),
                   bool(data.get("product_hole_approved", False)), HoleProcess(post) if post else None,
                   data.get("spacing_mm"), tuple(data.get("evidence", ())), tuple(data.get("assumptions", ())),
                   str(data.get("installation_side", "fixture assembly side")),
                   str(data.get("removal_side", "fixture assembly side")),
                   str(data.get("fixture_build_role", "temporary fixture assembly")),
                   data.get("product_location_role"), bool(data.get("hole_remains", True)))


@dataclass(frozen=True)
class PokaYokeSpec:
    """Explicit anti-reversal evidence for a fabricated fixture feature."""

    identity: str
    component_identity: str
    strategy: str
    prevents_reversal: bool
    avoids_pinch_point: bool
    avoids_hidden_seating: bool
    supports_unloading: bool
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.component_identity.strip() or not self.strategy.strip():
            raise FixtureBuildError("poka-yoke identity, component, and strategy are required")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "component_identity": self.component_identity,
            "strategy": self.strategy, "prevents_reversal": self.prevents_reversal,
            "avoids_pinch_point": self.avoids_pinch_point,
            "avoids_hidden_seating": self.avoids_hidden_seating,
            "supports_unloading": self.supports_unloading,
            "evidence": list(self.evidence), "assumptions": list(self.assumptions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PokaYokeSpec":
        return cls(
            str(data["identity"]), str(data["component_identity"]), str(data["strategy"]),
            bool(data.get("prevents_reversal", False)), bool(data.get("avoids_pinch_point", False)),
            bool(data.get("avoids_hidden_seating", False)), bool(data.get("supports_unloading", False)),
            tuple(data.get("evidence", ())), tuple(data.get("assumptions", ())),
        )


@dataclass(frozen=True)
class MultiStationRequirements:
    """Only the additional intent required for the first M32 fixture family.

    These are review inputs, not hidden shop standards.  Clearance allowances
    are explicit so an engineer can inspect and change the synthesis basis.
    """

    fixture_family: FixtureFamily
    requested_station_count: int
    maximum_fixture_length_mm: float
    preferred_station_pitch_mm: float | None
    operator_loading_side: str
    unloading_direction: str
    clamp_operating_side: str
    operation_mode: str
    table_mounting_preference: str
    expected_production_quantity: int
    compare_one_up_and_multi_up: bool = True
    hand_clearance_mm: float = 75.0
    weld_clearance_mm: float = 25.0
    adjustment_allowance_mm: float = 10.0
    clamp_sweep_mm: float | None = None
    # The accepted count may be lower than the engineer's original request.
    # Keep that request as immutable review evidence instead of silently
    # rewriting the stated production intent.
    requested_intent_station_count: int | None = None
    # Manufacturing-frame choices are converted at the accepted-orientation
    # workflow boundary.  The deterministic geometry engine consumes only
    # these source-coordinate vectors; the display strings above remain
    # human-readable intent and persistence evidence.
    loading_direction_source: Vec3 | None = None
    unloading_direction_source: Vec3 | None = None
    operator_loading_direction_source: Vec3 | None = None
    clamp_operating_direction_source: Vec3 | None = None
    manufacturing_up_direction_source: Vec3 | None = None
    source_to_manufacturing: tuple[float, ...] = ()
    manufacturing_to_source: tuple[float, ...] = ()
    manufacturing_orientation_identity: str | None = None

    def __post_init__(self) -> None:
        if self.fixture_family != FixtureFamily.LINEAR_MULTI_STATION_WELD:
            value = self.fixture_family.value if isinstance(self.fixture_family, FixtureFamily) else str(self.fixture_family)
            raise FixtureBuildError(f"unsupported fixture family {value!r}")
        if not 1 <= self.requested_station_count <= 8:
            raise FixtureBuildError("multi-station fixture count must be between 1 and 8")
        if (self.requested_intent_station_count is not None
                and not 1 <= self.requested_intent_station_count <= 8):
            raise FixtureBuildError("original multi-station request must be between 1 and 8")
        numeric = (self.maximum_fixture_length_mm, self.hand_clearance_mm,
                   self.weld_clearance_mm, self.adjustment_allowance_mm)
        if any(not math.isfinite(value) or value <= 0 for value in numeric):
            raise FixtureBuildError("multi-station lengths and clearance allowances must be positive finite millimetres")
        if self.preferred_station_pitch_mm is not None and self.preferred_station_pitch_mm <= 0:
            raise FixtureBuildError("preferred station pitch must be positive when supplied")
        if self.clamp_sweep_mm is not None and self.clamp_sweep_mm <= 0:
            raise FixtureBuildError("clamp sweep must be positive when supplied")
        if self.expected_production_quantity < 1:
            raise FixtureBuildError("expected production quantity must be positive")
        if self.operation_mode not in {"manual", "cobot", "robot"}:
            raise FixtureBuildError("operation mode must be manual, cobot, or robot")
        if not all(value.strip() for value in (
                self.operator_loading_side, self.unloading_direction,
                self.clamp_operating_side, self.table_mounting_preference)):
            raise FixtureBuildError("multi-station handling and mounting intent is required")
        for matrix, label in ((self.source_to_manufacturing, "source-to-manufacturing"),
                              (self.manufacturing_to_source, "manufacturing-to-source")):
            if matrix and (len(matrix) != 16 or not all(math.isfinite(value) for value in matrix)):
                raise FixtureBuildError(f"{label} transform must contain 16 finite values")

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_family": self.fixture_family.value,
            "requested_station_count": self.requested_station_count,
            "maximum_fixture_length_mm": self.maximum_fixture_length_mm,
            "preferred_station_pitch_mm": self.preferred_station_pitch_mm,
            "operator_loading_side": self.operator_loading_side,
            "unloading_direction": self.unloading_direction,
            "clamp_operating_side": self.clamp_operating_side,
            "operation_mode": self.operation_mode,
            "table_mounting_preference": self.table_mounting_preference,
            "expected_production_quantity": self.expected_production_quantity,
            "compare_one_up_and_multi_up": self.compare_one_up_and_multi_up,
            "hand_clearance_mm": self.hand_clearance_mm,
            "weld_clearance_mm": self.weld_clearance_mm,
            "adjustment_allowance_mm": self.adjustment_allowance_mm,
            "clamp_sweep_mm": self.clamp_sweep_mm,
            "requested_intent_station_count": self.requested_intent_station_count,
            "loading_direction_source": self.loading_direction_source.__dict__ if self.loading_direction_source else None,
            "unloading_direction_source": self.unloading_direction_source.__dict__ if self.unloading_direction_source else None,
            "operator_loading_direction_source": self.operator_loading_direction_source.__dict__ if self.operator_loading_direction_source else None,
            "clamp_operating_direction_source": self.clamp_operating_direction_source.__dict__ if self.clamp_operating_direction_source else None,
            "manufacturing_up_direction_source": self.manufacturing_up_direction_source.__dict__ if self.manufacturing_up_direction_source else None,
            "source_to_manufacturing": list(self.source_to_manufacturing),
            "manufacturing_to_source": list(self.manufacturing_to_source),
            "manufacturing_orientation_identity": self.manufacturing_orientation_identity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MultiStationRequirements":
        return cls(
            FixtureFamily(data["fixture_family"]), int(data["requested_station_count"]),
            float(data["maximum_fixture_length_mm"]), data.get("preferred_station_pitch_mm"),
            str(data["operator_loading_side"]), str(data["unloading_direction"]),
            str(data["clamp_operating_side"]), str(data["operation_mode"]),
            str(data["table_mounting_preference"]), int(data["expected_production_quantity"]),
            bool(data.get("compare_one_up_and_multi_up", True)),
            float(data.get("hand_clearance_mm", 75.0)), float(data.get("weld_clearance_mm", 25.0)),
            float(data.get("adjustment_allowance_mm", 10.0)), data.get("clamp_sweep_mm"),
            data.get("requested_intent_station_count"),
            Vec3(**data["loading_direction_source"]) if data.get("loading_direction_source") else None,
            Vec3(**data["unloading_direction_source"]) if data.get("unloading_direction_source") else None,
            Vec3(**data["operator_loading_direction_source"]) if data.get("operator_loading_direction_source") else None,
            Vec3(**data["clamp_operating_direction_source"]) if data.get("clamp_operating_direction_source") else None,
            Vec3(**data["manufacturing_up_direction_source"]) if data.get("manufacturing_up_direction_source") else None,
            tuple(float(value) for value in data.get("source_to_manufacturing", ())),
            tuple(float(value) for value in data.get("manufacturing_to_source", ())),
            data.get("manufacturing_orientation_identity"),
        )


@dataclass(frozen=True)
class WeldJointAccessResult:
    """One deterministic station/joint torch-envelope result."""

    joint_identity: str
    clear: bool | None
    torch_envelope: Aabb
    approach_direction_source: Vec3
    blocking_component_identities: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    unevaluated_product_body_identities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.joint_identity.strip():
            raise FixtureBuildError("weld access result requires a joint identity")
        if self.clear is not None and not isinstance(self.clear, bool):
            raise FixtureBuildError("weld access result must be clear, blocked, or unevaluated")

    def to_dict(self) -> dict[str, object]:
        return {
            "joint_identity": self.joint_identity,
            "clear": self.clear,
            "torch_envelope": self.torch_envelope.as_dict(),
            "approach_direction_source": self.approach_direction_source.__dict__,
            "blocking_component_identities": list(self.blocking_component_identities),
            "evidence": list(self.evidence),
            "unevaluated_product_body_identities": list(
                self.unevaluated_product_body_identities
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "WeldJointAccessResult":
        bounds = data["torch_envelope"]
        return cls(
            str(data["joint_identity"]), data.get("clear"),
            Aabb(Vec3(**bounds["minimum"]), Vec3(**bounds["maximum"])),
            Vec3(**data["approach_direction_source"]),
            tuple(data.get("blocking_component_identities", ())),
            tuple(data.get("evidence", ())),
            tuple(data.get("unevaluated_product_body_identities", ())),
        )


@dataclass(frozen=True)
class StationTransform:
    """Immutable source-instance evidence for one review station."""

    identity: str
    station_index: int
    translation_mm: Vec3
    product_source_sha256: str
    source_component_identities: tuple[str, ...]
    product_bounds: Aabb
    clamp_tip_reaches_surface: bool | None = None
    open_clamp_envelope_clear: bool | None = None
    hand_access_clear: bool | None = None
    weld_access_clear: bool | None = None
    unload_path_clear: bool | None = None
    trapped_part: bool | None = None
    loading_direction: str = ""
    unloading_direction: str = ""
    operator_side: str = ""
    loading_envelope: Aabb | None = None
    unloading_envelope: Aabb | None = None
    open_clamp_envelope: Aabb | None = None
    closed_clamp_envelope: Aabb | None = None
    access_evidence: tuple[str, ...] = ()
    loading_direction_source: Vec3 | None = None
    unloading_direction_source: Vec3 | None = None
    operator_direction_source: Vec3 | None = None
    weld_access_results: tuple[WeldJointAccessResult, ...] = ()
    source_to_station_manufacturing: tuple[float, ...] = ()
    access_evidence_digest: str = ""

    def __post_init__(self) -> None:
        if not self.identity.strip() or self.station_index < 1 or len(self.product_source_sha256) != 64:
            raise FixtureBuildError("station identity, positive index, and source SHA-256 are required")
        if not self.source_component_identities:
            raise FixtureBuildError("product review station must reference immutable source components")
        if self.source_to_station_manufacturing and (
                len(self.source_to_station_manufacturing) != 16
                or not all(math.isfinite(value) for value in self.source_to_station_manufacturing)):
            raise FixtureBuildError("station source-to-manufacturing transform must contain 16 finite values")
        if self.access_evidence_digest and (
                len(self.access_evidence_digest) != 64
                or any(value not in "0123456789abcdef" for value in self.access_evidence_digest)):
            raise FixtureBuildError("station access evidence digest must be a lowercase SHA-256")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "station_index": self.station_index,
            "translation_mm": self.translation_mm.__dict__,
            "product_source_sha256": self.product_source_sha256,
            "source_component_identities": list(self.source_component_identities),
            "product_bounds": self.product_bounds.as_dict(),
            "clamp_tip_reaches_surface": self.clamp_tip_reaches_surface,
            "open_clamp_envelope_clear": self.open_clamp_envelope_clear,
            "hand_access_clear": self.hand_access_clear,
            "weld_access_clear": self.weld_access_clear,
            "unload_path_clear": self.unload_path_clear,
            "trapped_part": self.trapped_part,
            "loading_direction": self.loading_direction,
            "unloading_direction": self.unloading_direction,
            "operator_side": self.operator_side,
            "loading_envelope": self.loading_envelope.as_dict() if self.loading_envelope else None,
            "unloading_envelope": self.unloading_envelope.as_dict() if self.unloading_envelope else None,
            "open_clamp_envelope": self.open_clamp_envelope.as_dict() if self.open_clamp_envelope else None,
            "closed_clamp_envelope": self.closed_clamp_envelope.as_dict() if self.closed_clamp_envelope else None,
            "access_evidence": list(self.access_evidence),
            "loading_direction_source": self.loading_direction_source.__dict__ if self.loading_direction_source else None,
            "unloading_direction_source": self.unloading_direction_source.__dict__ if self.unloading_direction_source else None,
            "operator_direction_source": self.operator_direction_source.__dict__ if self.operator_direction_source else None,
            "weld_access_results": [item.to_dict() for item in self.weld_access_results],
            "source_to_station_manufacturing": list(self.source_to_station_manufacturing),
            "access_evidence_digest": self.access_evidence_digest,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "StationTransform":
        bounds = data["product_bounds"]
        def optional_bounds(key: str) -> Aabb | None:
            value = data.get(key)
            if not value:
                return None
            return Aabb(Vec3(**value["minimum"]), Vec3(**value["maximum"]))
        return cls(
            str(data["identity"]), int(data["station_index"]), Vec3(**data["translation_mm"]),
            str(data["product_source_sha256"]), tuple(data["source_component_identities"]),
            Aabb(Vec3(**bounds["minimum"]), Vec3(**bounds["maximum"])),
            data.get("clamp_tip_reaches_surface"), data.get("open_clamp_envelope_clear"),
            data.get("hand_access_clear"), data.get("weld_access_clear"),
            data.get("unload_path_clear"), data.get("trapped_part"),
            str(data.get("loading_direction", "")), str(data.get("unloading_direction", "")),
            str(data.get("operator_side", "")), optional_bounds("loading_envelope"),
            optional_bounds("unloading_envelope"), optional_bounds("open_clamp_envelope"),
            optional_bounds("closed_clamp_envelope"), tuple(data.get("access_evidence", ())),
            Vec3(**data["loading_direction_source"]) if data.get("loading_direction_source") else None,
            Vec3(**data["unloading_direction_source"]) if data.get("unloading_direction_source") else None,
            Vec3(**data["operator_direction_source"]) if data.get("operator_direction_source") else None,
            tuple(WeldJointAccessResult.from_dict(item) for item in data.get("weld_access_results", ())),
            tuple(float(value) for value in data.get("source_to_station_manufacturing", ())),
            str(data.get("access_evidence_digest", "")),
        )


@dataclass(frozen=True)
class MultiStationLayout:
    """Deterministic layout and source-instance evidence stored with the build."""

    identity: str
    requirements: MultiStationRequirements
    primary_axis: str
    station_pitch_mm: float
    required_fixture_length_mm: float
    proposed_smaller_station_count: int | None
    stations: tuple[StationTransform, ...]
    rationale: tuple[str, ...]
    requested_intent_required_length_mm: float | None = None

    def __post_init__(self) -> None:
        if self.primary_axis not in {"x", "y"} or self.station_pitch_mm <= 0:
            raise FixtureBuildError("multi-station layout requires X or Y primary axis and positive pitch")
        if len(self.stations) != self.requirements.requested_station_count:
            raise FixtureBuildError("station layout count does not match requested station count")
        if tuple(item.station_index for item in self.stations) != tuple(range(1, len(self.stations) + 1)):
            raise FixtureBuildError("station indices must be stable and contiguous")
        if len({item.identity for item in self.stations}) != len(self.stations):
            raise FixtureBuildError("station identities must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": M32_SCHEMA, "identity": self.identity,
            "requirements": self.requirements.to_dict(), "primary_axis": self.primary_axis,
            "station_pitch_mm": self.station_pitch_mm,
            "required_fixture_length_mm": self.required_fixture_length_mm,
            "proposed_smaller_station_count": self.proposed_smaller_station_count,
            "requested_intent_required_length_mm": self.requested_intent_required_length_mm,
            "stations": [item.to_dict() for item in self.stations],
            "rationale": list(self.rationale),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MultiStationLayout":
        if data.get("schema") != M32_SCHEMA:
            raise FixtureBuildError("unsupported multi-station layout schema")
        return cls(
            str(data["identity"]), MultiStationRequirements.from_dict(data["requirements"]),
            str(data["primary_axis"]), float(data["station_pitch_mm"]),
            float(data["required_fixture_length_mm"]), data.get("proposed_smaller_station_count"),
            tuple(StationTransform.from_dict(item) for item in data["stations"]),
            tuple(data.get("rationale", ())),
            data.get("requested_intent_required_length_mm"),
        )


@dataclass(frozen=True)
class ConfirmedWeldIntent:
    """Engineer-confirmed weld and torch evidence in both frame contexts."""

    identity: str
    references: tuple[GeometryReference, ...]
    weld_side: str
    weld_length_mm: float
    process: str
    sequence: int
    joint_position_source_mm: Vec3
    approach_direction_manufacturing: Vec3
    approach_direction_source: Vec3
    torch_envelope_mm: Vec3
    manufacturing_orientation_identity: str
    evidence: tuple[str, ...] = ()
    weld_direction_manufacturing: Vec3 | None = None
    weld_direction_source: Vec3 | None = None

    def __post_init__(self) -> None:
        if not all((self.identity.strip(), self.weld_side.strip(), self.process.strip(),
                    self.manufacturing_orientation_identity.strip())):
            raise FixtureBuildError("confirmed weld identity, side, process, and orientation are required")
        if not self.references:
            raise FixtureBuildError("confirmed weld intent requires source geometry references")
        if not math.isfinite(self.weld_length_mm) or self.weld_length_mm <= 0.0 or self.sequence < 1:
            raise FixtureBuildError("confirmed weld length and sequence must be positive")
        for vector, label in (
                (self.approach_direction_manufacturing, "manufacturing torch approach"),
                (self.approach_direction_source, "source torch approach")):
            magnitude = math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2)
            if not math.isfinite(magnitude) or magnitude <= 1e-9:
                raise FixtureBuildError(f"{label} must be a finite non-zero vector")
        if (self.weld_direction_manufacturing is None) != (self.weld_direction_source is None):
            raise FixtureBuildError("confirmed weld direction requires both source and manufacturing vectors")
        for vector, label in (
                (self.weld_direction_manufacturing, "manufacturing weld direction"),
                (self.weld_direction_source, "source weld direction")):
            if vector is None:
                continue
            magnitude = math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2)
            if not math.isfinite(magnitude) or magnitude <= 1e-9:
                raise FixtureBuildError(f"{label} must be a finite non-zero vector")
        if any(not math.isfinite(value) or value <= 0.0
               for value in self.torch_envelope_mm.__dict__.values()):
            raise FixtureBuildError("torch body width, height, and approach length must be positive millimetres")
        if any(not math.isfinite(value) for value in self.joint_position_source_mm.__dict__.values()):
            raise FixtureBuildError("confirmed weld joint position must be finite source-coordinate millimetres")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "references": [item.__dict__ for item in self.references],
            "weld_side": self.weld_side,
            "weld_length_mm": self.weld_length_mm,
            "process": self.process,
            "sequence": self.sequence,
            "joint_position_source_mm": self.joint_position_source_mm.__dict__,
            "approach_direction_manufacturing": self.approach_direction_manufacturing.__dict__,
            "approach_direction_source": self.approach_direction_source.__dict__,
            "torch_envelope_mm": self.torch_envelope_mm.__dict__,
            "manufacturing_orientation_identity": self.manufacturing_orientation_identity,
            "evidence": list(self.evidence),
            "weld_direction_manufacturing": (
                self.weld_direction_manufacturing.__dict__
                if self.weld_direction_manufacturing is not None else None
            ),
            "weld_direction_source": (
                self.weld_direction_source.__dict__
                if self.weld_direction_source is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ConfirmedWeldIntent":
        manufacturing_direction = data.get("weld_direction_manufacturing")
        source_direction = data.get("weld_direction_source")
        return cls(
            str(data["identity"]),
            tuple(GeometryReference(**item) for item in data.get("references", ())),
            str(data["weld_side"]), float(data["weld_length_mm"]),
            str(data["process"]), int(data["sequence"]),
            Vec3(**data["joint_position_source_mm"]),
            Vec3(**data["approach_direction_manufacturing"]),
            Vec3(**data["approach_direction_source"]),
            Vec3(**data["torch_envelope_mm"]),
            str(data["manufacturing_orientation_identity"]),
            tuple(data.get("evidence", ())),
            Vec3(**manufacturing_direction) if manufacturing_direction is not None else None,
            Vec3(**source_direction) if source_direction is not None else None,
        )


@dataclass(frozen=True)
class FixtureBuildRequirements:
    source_sha256: str
    fixture_purpose: FixturePurpose
    construction_method: ConstructionMethod
    lifecycle: FixtureLifecycle
    job_revision: str | None
    fixture_revision: str
    production_quantity: int | None = None
    repeat_frequency: str | None = None
    weld_process: str | None = None
    shop_capabilities: tuple[str, ...] = ()
    tack_access_available: bool | None = None
    full_weld_access_available: bool | None = None
    unload_clearance_evaluated: bool | None = None
    adjustment_state: AdjustmentState = AdjustmentState.PROVISIONAL
    assumptions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    cleco_strategy: ClecoStrategy = ClecoStrategy.NONE
    product_hole_approved: bool = False
    product_hole_justification: str | None = None
    confirmed_weld_intent: bool = False
    confirmed_weld_evidence: tuple[str, ...] = ()
    confirmed_weld_joint_count: int = 0
    confirmed_welds: tuple[ConfirmedWeldIntent, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise FixtureBuildError("fixture build requires a SHA-256 source identity")
        if not self.fixture_revision.strip():
            raise FixtureBuildError("fixture revision is required")
        if self.production_quantity is not None and self.production_quantity < 1:
            raise FixtureBuildError("production quantity must be positive when supplied")
        if self.confirmed_weld_joint_count < 0:
            raise FixtureBuildError("confirmed weld joint count cannot be negative")
        if len({item.identity for item in self.confirmed_welds}) != len(self.confirmed_welds):
            raise FixtureBuildError("confirmed weld identities must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256, "fixture_purpose": self.fixture_purpose.value,
            "construction_method": self.construction_method.value, "lifecycle": self.lifecycle.value,
            "job_revision": self.job_revision, "fixture_revision": self.fixture_revision,
            "production_quantity": self.production_quantity, "repeat_frequency": self.repeat_frequency,
            "weld_process": self.weld_process, "shop_capabilities": list(self.shop_capabilities),
            "tack_access_available": self.tack_access_available,
            "full_weld_access_available": self.full_weld_access_available,
            "unload_clearance_evaluated": self.unload_clearance_evaluated,
            "adjustment_state": self.adjustment_state.value, "assumptions": list(self.assumptions),
            "evidence": list(self.evidence),
            "cleco_strategy": self.cleco_strategy.value,
            "product_hole_approved": self.product_hole_approved,
            "product_hole_justification": self.product_hole_justification,
            "confirmed_weld_intent": self.confirmed_weld_intent,
            "confirmed_weld_evidence": list(self.confirmed_weld_evidence),
            "confirmed_weld_joint_count": self.confirmed_weld_joint_count,
            "confirmed_welds": [item.to_dict() for item in self.confirmed_welds],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FixtureBuildRequirements":
        return cls(str(data["source_sha256"]), FixturePurpose(data["fixture_purpose"]),
                   ConstructionMethod(data["construction_method"]), FixtureLifecycle(data["lifecycle"]),
                   data.get("job_revision"), str(data["fixture_revision"]), data.get("production_quantity"),
                   data.get("repeat_frequency"), data.get("weld_process"), tuple(data.get("shop_capabilities", ())),
                   data.get("tack_access_available"), data.get("full_weld_access_available"),
                   data.get("unload_clearance_evaluated"), AdjustmentState(data.get("adjustment_state", AdjustmentState.PROVISIONAL.value)),
                   tuple(data.get("assumptions", ())), tuple(data.get("evidence", ())),
                   ClecoStrategy(data.get("cleco_strategy", ClecoStrategy.NONE.value)),
                   bool(data.get("product_hole_approved", False)), data.get("product_hole_justification"),
                   bool(data.get("confirmed_weld_intent", False)),
                   tuple(data.get("confirmed_weld_evidence", ())),
                   int(data.get("confirmed_weld_joint_count", 0)),
                   tuple(ConfirmedWeldIntent.from_dict(item) for item in data.get("confirmed_welds", ())))


@dataclass(frozen=True)
class FixtureBuildComponent:
    identity: str
    part_number: str
    description: str
    role: BuildComponentRole
    geometry_authority: GeometryAuthority
    material: str
    thickness_mm: float | None
    stock_mm: tuple[float, ...]
    quantity: int
    manufacturing_process: str
    bounds: Aabb
    source_references: tuple[GeometryReference, ...]
    rule_ids: tuple[str, ...]
    parent_component_identity: str | None = None
    nest_classification: NestClassification = NestClassification.FIXTURE
    reusable: bool = False
    disposable: bool = False
    contact_condition: str | None = None
    reaction_support_identity: str | None = None
    fixed: bool = False
    locating_constraint: bool = False
    holes: tuple[HoleProcessSpec, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    replaceable: bool = False
    maintenance_access: bool | None = None
    slots: tuple[SlotProcessSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.part_number.strip() or not self.description.strip():
            raise FixtureBuildError("build component identity, part number, and description are required")
        if not self.material.strip() or not self.manufacturing_process.strip() or self.quantity < 1:
            raise FixtureBuildError("build component material, process, and quantity are required")
        if self.thickness_mm is not None and self.thickness_mm <= 0:
            raise FixtureBuildError("component thickness must be positive")
        if any(value <= 0 for value in self.stock_mm):
            raise FixtureBuildError("component stock dimensions must be positive")
        if not self.source_references:
            raise FixtureBuildError("every fixture component needs source geometry traceability")
        if not self.rule_ids or any(rule not in RULES_BY_ID for rule in self.rule_ids):
            raise FixtureBuildError("every fixture component needs known deterministic rule references")
        if self.disposable and self.reusable:
            raise FixtureBuildError("a component cannot be both disposable and reusable")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "part_number": self.part_number, "description": self.description,
            "role": self.role.value, "geometry_authority": self.geometry_authority.value,
            "material": self.material, "thickness_mm": self.thickness_mm,
            "stock_mm": list(self.stock_mm), "quantity": self.quantity,
            "manufacturing_process": self.manufacturing_process, "bounds": self.bounds.as_dict(),
            "source_references": [item.__dict__ for item in self.source_references],
            "rule_ids": list(sorted(self.rule_ids)), "parent_component_identity": self.parent_component_identity,
            "nest_classification": self.nest_classification.value, "reusable": self.reusable,
            "disposable": self.disposable, "contact_condition": self.contact_condition,
            "reaction_support_identity": self.reaction_support_identity, "fixed": self.fixed,
            "locating_constraint": self.locating_constraint,
            "holes": [item.to_dict() for item in sorted(self.holes, key=lambda item: item.identity)],
            "assumptions": list(self.assumptions), "evidence": list(self.evidence),
            "replaceable": self.replaceable, "maintenance_access": self.maintenance_access,
            "slots": [item.to_dict() for item in sorted(self.slots, key=lambda item: item.identity)],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FixtureBuildComponent":
        bounds = data["bounds"]
        return cls(
            str(data["identity"]), str(data["part_number"]), str(data["description"]),
            BuildComponentRole(data["role"]), GeometryAuthority(data["geometry_authority"]),
            str(data["material"]), data.get("thickness_mm"), tuple(float(item) for item in data.get("stock_mm", ())),
            int(data["quantity"]), str(data["manufacturing_process"]),
            Aabb(Vec3(**bounds["minimum"]), Vec3(**bounds["maximum"])),
            tuple(GeometryReference(**item) for item in data.get("source_references", ())),
            tuple(data.get("rule_ids", ())), data.get("parent_component_identity"),
            NestClassification(data.get("nest_classification", NestClassification.FIXTURE.value)),
            bool(data.get("reusable", False)), bool(data.get("disposable", False)), data.get("contact_condition"),
            data.get("reaction_support_identity"), bool(data.get("fixed", False)),
            bool(data.get("locating_constraint", False)),
            tuple(HoleProcessSpec.from_dict(item) for item in data.get("holes", ())),
            tuple(data.get("assumptions", ())), tuple(data.get("evidence", ())),
            bool(data.get("replaceable", False)), data.get("maintenance_access"),
            tuple(SlotProcessSpec.from_dict(item) for item in data.get("slots", ())),
        )


@dataclass(frozen=True)
class FixtureBuildPlan:
    identity: str
    concept_identity: str
    requirements: FixtureBuildRequirements
    components: tuple[FixtureBuildComponent, ...]
    tab_slots: tuple[TabSlotJoint, ...] = ()
    clecos: tuple[ClecoSpec, ...] = ()
    loading_sequence: tuple[str, ...] = ()
    tack_sequence: tuple[str, ...] = ()
    release_sequence: tuple[str, ...] = ()
    unload_sequence: tuple[str, ...] = ()
    finish_weld_handoff: str = ""
    assumptions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    poka_yokes: tuple[PokaYokeSpec, ...] = ()
    multi_station_layout: MultiStationLayout | None = None
    authoring_state: str = "not_authored"
    fixture_proposal_identity: str | None = None
    fixture_proposal_evidence_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.identity.strip() or not self.concept_identity.strip():
            raise FixtureBuildError("build plan identity and concept identity are required")
        if len({item.identity for item in self.components}) != len(self.components):
            raise FixtureBuildError("fixture build component identities must be unique")
        if len({item.part_number for item in self.components}) != len(self.components):
            raise FixtureBuildError("fixture build part numbers must be unique")
        if len({item.identity for item in self.tab_slots}) != len(self.tab_slots):
            raise FixtureBuildError("tab-slot identities must be unique")
        if len({item.identity for item in self.clecos}) != len(self.clecos):
            raise FixtureBuildError("Cleco identities must be unique")
        if len({item.identity for item in self.poka_yokes}) != len(self.poka_yokes):
            raise FixtureBuildError("poka-yoke identities must be unique")
        if self.authoring_state not in {"not_authored", "normal", "provisional"}:
            raise FixtureBuildError("fixture build authoring state is unsupported")
        if bool(self.fixture_proposal_identity) != bool(self.fixture_proposal_evidence_digest):
            raise FixtureBuildError("fixture proposal identity and evidence binding must be recorded together")
        if (self.fixture_proposal_evidence_digest is not None
                and not re.fullmatch(r"[0-9a-f]{64}", self.fixture_proposal_evidence_digest)):
            raise FixtureBuildError("fixture proposal evidence digest is malformed")

    @property
    def evidence_digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": M30_SCHEMA, "identity": self.identity, "concept_identity": self.concept_identity,
            "requirements": self.requirements.to_dict(),
            "components": [item.to_dict() for item in sorted(self.components, key=lambda item: item.identity)],
            "tab_slots": [item.to_dict() for item in sorted(self.tab_slots, key=lambda item: item.identity)],
            "clecos": [item.to_dict() for item in sorted(self.clecos, key=lambda item: item.identity)],
            "loading_sequence": list(self.loading_sequence), "tack_sequence": list(self.tack_sequence),
            "release_sequence": list(self.release_sequence), "unload_sequence": list(self.unload_sequence),
            "finish_weld_handoff": self.finish_weld_handoff, "assumptions": list(self.assumptions),
            "evidence": list(self.evidence),
            "poka_yokes": [item.to_dict() for item in sorted(self.poka_yokes, key=lambda item: item.identity)],
            "multi_station_layout": self.multi_station_layout.to_dict() if self.multi_station_layout else None,
            "authoring_state": self.authoring_state,
            "fixture_proposal_identity": self.fixture_proposal_identity,
            "fixture_proposal_evidence_digest": self.fixture_proposal_evidence_digest,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FixtureBuildPlan":
        if data.get("schema", M30_SCHEMA) != M30_SCHEMA:
            raise FixtureBuildError("unsupported fixture build schema")
        return cls(
            str(data["identity"]), str(data["concept_identity"]),
            FixtureBuildRequirements.from_dict(data["requirements"]),
            tuple(FixtureBuildComponent.from_dict(item) for item in data.get("components", ())),
            tuple(TabSlotJoint.from_dict(item) for item in data.get("tab_slots", ())),
            tuple(ClecoSpec.from_dict(item) for item in data.get("clecos", ())),
            tuple(data.get("loading_sequence", ())), tuple(data.get("tack_sequence", ())),
            tuple(data.get("release_sequence", ())), tuple(data.get("unload_sequence", ())),
            str(data.get("finish_weld_handoff", "")), tuple(data.get("assumptions", ())),
            tuple(data.get("evidence", ())),
            tuple(PokaYokeSpec.from_dict(item) for item in data.get("poka_yokes", ())),
            MultiStationLayout.from_dict(data["multi_station_layout"])
            if data.get("multi_station_layout") else None,
            str(data.get("authoring_state", "not_authored")),
            data.get("fixture_proposal_identity"),
            data.get("fixture_proposal_evidence_digest"),
        )


@dataclass(frozen=True)
class FixtureBuildFinding:
    identity: str
    rule_id: str
    severity: str
    status: str
    message: str
    component_identities: tuple[str, ...] = ()
    geometry_references: tuple[GeometryReference, ...] = ()
    evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: str = "deterministic"
    disposition: str = ""

    def __post_init__(self) -> None:
        if self.rule_id not in RULES_BY_ID:
            raise FixtureBuildError(f"unknown Milestone 30 rule {self.rule_id!r}")
        if self.severity not in {"error", "warning", "info"}:
            raise FixtureBuildError("fixture build finding severity is unsupported")
        if self.status not in {"valid", "provisional", "invalid", "not_evaluated"}:
            raise FixtureBuildError("fixture build finding status is unsupported")
        if self.disposition not in {"authoring_blocker", "review_blocker", "export_blocker", "warning", "informational"}:
            raise FixtureBuildError("fixture build finding disposition is unsupported")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity, "rule_id": self.rule_id, "severity": self.severity,
            "status": self.status, "message": self.message,
            "component_identities": list(self.component_identities),
            "geometry_references": [item.__dict__ for item in self.geometry_references],
            "evidence": list(self.evidence), "assumptions": list(self.assumptions),
            "confidence": self.confidence,
            "disposition": self.disposition,
        }


@dataclass(frozen=True)
class FixtureBuildValidation:
    plan_identity: str
    source_sha256: str
    status: str
    findings: tuple[FixtureBuildFinding, ...]
    evidence_digest: str

    @property
    def valid(self) -> bool:
        return self.status == "valid"

    @property
    def blocked(self) -> bool:
        return self.status == "invalid"

    @property
    def authoring_blocked(self) -> bool:
        """Only deterministic computational/safety prerequisites stop review solids."""
        return any(item.disposition == "authoring_blocker" for item in self.findings)

    @property
    def review_blocked(self) -> bool:
        return any(item.disposition == "review_blocker" for item in self.findings)

    @property
    def export_blocked(self) -> bool:
        return self.status != "valid" or any(
            item.disposition in {"authoring_blocker", "review_blocker", "export_blocker"}
            for item in self.findings
        )


@dataclass(frozen=True)
class FixtureBuildComparison:
    plan_identity: str
    construction_method: ConstructionMethod
    lifecycle: FixtureLifecycle
    status: str
    score: float
    cost: float
    access: float
    precision: float
    build_time: float
    maintenance: float
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class AuthoredFixtureComponent:
    component: FixtureBuildComponent
    shape: object
    topology: TopologyCounts
    step_bytes: bytes
    dxf_bytes: bytes | None


@dataclass(frozen=True)
class AuthoredFixtureAssembly:
    plan_identity: str
    source_sha256: str
    units: str
    components: tuple[AuthoredFixtureComponent, ...]
    model: object
    validation: FixtureBuildValidation
    plan_evidence_digest: str
    provisional: bool = False
    review_labels: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.validation.blocked

    @property
    def evidence_digest(self) -> str:
        payload = json.dumps({
            "plan": self.plan_identity, "source": self.source_sha256,
            "plan_evidence_digest": self.plan_evidence_digest,
            "validation": self.validation.evidence_digest,
            "provisional": self.provisional, "review_labels": self.review_labels,
            "components": [(item.component.identity, hashlib.sha256(item.step_bytes).hexdigest()) for item in self.components],
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finding(rule_id: str, severity: str, message: str, *, components: tuple[str, ...] = (),
             references: tuple[GeometryReference, ...] = (), evidence: tuple[str, ...] = (),
             assumptions: tuple[str, ...] = (), status: str | None = None,
             disposition: str | None = None) -> FixtureBuildFinding:
    payload = (rule_id, severity, message, tuple(sorted(components)),
               tuple(sorted((item.component_identity, item.body_identity or "", item.face_identity or "") for item in references)),
               tuple(sorted(evidence)), tuple(sorted(assumptions)))
    identity = "m30-" + hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:20]
    resolved_disposition = disposition or (
        "informational" if severity == "info" else "warning" if severity == "warning" else "review_blocker"
    )
    return FixtureBuildFinding(identity, rule_id, severity, status or ("invalid" if severity == "error" else "provisional"),
                               message, tuple(sorted(components)), references, tuple(sorted(evidence)),
                               tuple(sorted(assumptions)), "deterministic", resolved_disposition)


def _reference_valid(product: ProductModel, reference: GeometryReference) -> bool:
    component = next((item for item in product.components if item.identity == reference.component_identity), None)
    if component is None:
        return False
    if reference.body_identity is None:
        return True
    body = next((item for item in component.bodies if item.identity == reference.body_identity), None)
    if body is None:
        return False
    faces = {item.identity for item in body.faces}
    edges = {item.identity for item in body.edges}
    return (reference.face_identity is None or reference.face_identity in faces) and (
        reference.edge_identity is None or reference.edge_identity in edges)


def _component_reference(product: ProductModel) -> GeometryReference:
    for component in product.components:
        if component.bodies:
            return GeometryReference(component.identity, component.bodies[0].identity)
        return GeometryReference(component.identity)
    raise FixtureBuildError("product has no component available for source traceability")


def _product_bounds(product: ProductModel) -> Aabb:
    boxes: list[Aabb] = []
    for component in product.components:
        boxes.extend(body.bounds.transformed(component.transform) for body in component.bodies)
    if not boxes:
        raise FixtureBuildError("product has no physical bodies")
    return Aabb(
        Vec3(min(item.minimum.x for item in boxes), min(item.minimum.y for item in boxes), min(item.minimum.z for item in boxes)),
        Vec3(max(item.maximum.x for item in boxes), max(item.maximum.y for item in boxes), max(item.maximum.z for item in boxes)),
    )


def _matrix_apply(matrix: tuple[float, ...], point: Vec3, *, vector: bool = False) -> Vec3:
    if len(matrix) != 16:
        raise FixtureBuildError("manufacturing transform must contain 16 values")
    homogeneous = 0.0 if vector else 1.0
    return Vec3(
        matrix[0] * point.x + matrix[1] * point.y + matrix[2] * point.z + matrix[3] * homogeneous,
        matrix[4] * point.x + matrix[5] * point.y + matrix[6] * point.z + matrix[7] * homogeneous,
        matrix[8] * point.x + matrix[9] * point.y + matrix[10] * point.z + matrix[11] * homogeneous,
    )


def _matrix_product(left: tuple[float, ...], right: tuple[float, ...]) -> tuple[float, ...]:
    if len(left) != 16 or len(right) != 16:
        raise FixtureBuildError("manufacturing transform multiplication requires 16-value matrices")
    return tuple(
        sum(left[row * 4 + item] * right[item * 4 + column] for item in range(4))
        for row in range(4) for column in range(4)
    )


def _matrices_close(left: tuple[float, ...], right: tuple[float, ...], *, tolerance: float = 1e-7) -> bool:
    return len(left) == len(right) == 16 and all(
        abs(left_value - right_value) <= tolerance
        for left_value, right_value in zip(left, right)
    )


def _identity_matrix() -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0)


def _translation_matrix(value: Vec3) -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, value.x,
            0.0, 1.0, 0.0, value.y,
            0.0, 0.0, 1.0, value.z,
            0.0, 0.0, 0.0, 1.0)


def _transformed_bounds(bounds: Aabb, matrix: tuple[float, ...]) -> Aabb:
    points = tuple(
        _matrix_apply(matrix, Vec3(x, y, z))
        for x, y, z in itertools.product(
            (bounds.minimum.x, bounds.maximum.x),
            (bounds.minimum.y, bounds.maximum.y),
            (bounds.minimum.z, bounds.maximum.z),
        )
    )
    return Aabb(
        Vec3(*(min(getattr(point, name) for point in points) for name in ("x", "y", "z"))),
        Vec3(*(max(getattr(point, name) for point in points) for name in ("x", "y", "z"))),
    )


def _manufacturing_product_bounds(product: ProductModel,
                                  requirements: MultiStationRequirements) -> Aabb:
    if not requirements.source_to_manufacturing:
        raise FixtureBuildError("multi-station synthesis requires the accepted source-to-manufacturing transform")
    return _transformed_bounds(_product_bounds(product), requirements.source_to_manufacturing)


def _stock(bounds: Aabb) -> tuple[float, float, float]:
    return tuple(round(high - low, 6) for low, high in zip(bounds.minimum.__dict__.values(), bounds.maximum.__dict__.values()))


_M32_PLATE_ROLES = frozenset({
    BuildComponentRole.BASEPLATE,
    BuildComponentRole.STATION_PLATE,
    BuildComponentRole.DATUM_RAIL,
    BuildComponentRole.LOCATOR_PLATE,
    BuildComponentRole.HARD_STOP,
    BuildComponentRole.CLAMP_BRACKET,
    BuildComponentRole.END_BRACE,
    BuildComponentRole.SHIM_PACK,
})


def _plate_geometry_contract(bounds: Aabb, thickness_mm: float | None) -> tuple[int, str, str] | None:
    """Return the sole thickness axis and profile plane for proven plate stock."""
    if thickness_mm is None:
        return None
    spans = tuple(
        getattr(bounds.maximum, axis) - getattr(bounds.minimum, axis)
        for axis in ("x", "y", "z")
    )
    matching_axes = tuple(
        index for index, span in enumerate(spans)
        if abs(span - thickness_mm) <= 1e-7
    )
    if len(matching_axes) != 1:
        return None
    thickness_axis = matching_axes[0]
    axis_name = "XYZ"[thickness_axis]
    profile_plane = "".join(
        axis for index, axis in enumerate("XYZ") if index != thickness_axis
    )
    return thickness_axis, axis_name, profile_plane


def _is_m32_plate_component(component: FixtureBuildComponent) -> bool:
    return (
        component.identity.startswith("m32-")
        and component.geometry_authority == GeometryAuthority.AUTHORED_MANUFACTURING
        and component.role in _M32_PLATE_ROLES
    )


def _component(identity: str, part: str, description: str, role: BuildComponentRole,
               bounds: Aabb, reference: GeometryReference, *, parent: str | None,
               process: str, thickness: float | None, rule_ids: tuple[str, ...],
               authority: GeometryAuthority = GeometryAuthority.AUTHORED_MANUFACTURING,
               nest: NestClassification = NestClassification.FIXTURE,
               reusable: bool = False, disposable: bool = False, fixed: bool = False,
               locating: bool = False, reaction_support: str | None = None,
               contact_condition: str | None = None, holes: tuple[HoleProcessSpec, ...] = (),
               assumptions: tuple[str, ...] = (), evidence: tuple[str, ...] = (),
               replaceable: bool = False, maintenance_access: bool | None = None,
               slots: tuple[SlotProcessSpec, ...] = ()) -> FixtureBuildComponent:
    if (identity.startswith("m32-") and authority == GeometryAuthority.AUTHORED_MANUFACTURING
            and role in _M32_PLATE_ROLES):
        plate_contract = _plate_geometry_contract(bounds, thickness)
        if plate_contract is not None:
            _, thickness_axis, profile_plane = plate_contract
            evidence = evidence + (
                f"plate_thickness_axis={thickness_axis}",
                f"plate_profile_plane={profile_plane}",
                f"plate_thickness_mm={thickness:.6f}",
            )
    return FixtureBuildComponent(
        identity, part, description, role, authority, "mild steel" if authority != GeometryAuthority.PURCHASED_COMPONENT else "purchased tooling",
        thickness, _stock(bounds), 1, process, bounds, (reference,), rule_ids, parent,
        nest, reusable, disposable, contact_condition, reaction_support, fixed, locating,
        holes, assumptions, evidence, replaceable, maintenance_access,
        slots,
    )


def _method_for(requirements: FixtureBuildRequirements) -> ConstructionMethod:
    if requirements.construction_method != ConstructionMethod.AUTO:
        return requirements.construction_method
    if requirements.fixture_purpose == FixturePurpose.TACK_LOCATION:
        return ConstructionMethod.TACK_LOCATION
    if requirements.production_quantity is not None and requirements.production_quantity >= 100:
        return ConstructionMethod.WELDED_TUBE_FRAME
    return ConstructionMethod.LASER_CUT_FABRICATED


def generate_fixture_build_plan(product: ProductModel, concept: CompleteFixtureConcept,
                                requirements: FixtureBuildRequirements) -> FixtureBuildPlan:
    """Create a small, editable construction plan around immutable product geometry.

    The sizing is visible proof geometry derived from product bounds.  It is not
    a structural calculation, final drawing package, or production approval.
    """
    if product.source_sha256 != requirements.source_sha256:
        raise FixtureBuildError("fixture build requirements do not match immutable source geometry")
    if concept.fixture.source_sha256 != product.source_sha256:
        raise FixtureBuildError("fixture concept does not match immutable source geometry")
    method = _method_for(requirements)
    if method != requirements.construction_method:
        requirements = replace(requirements, construction_method=method)
    product_box = _product_bounds(product)
    reference = _component_reference(product)
    margin, plate = 35.0, 12.0
    base = Aabb(Vec3(product_box.minimum.x - margin, product_box.minimum.y - margin, product_box.minimum.z - 32.0),
                Vec3(product_box.maximum.x + margin, product_box.maximum.y + margin, product_box.minimum.z - 32.0 + plate))
    base_holes = (
        HoleProcessSpec("m30-fixture-cleco-hole", Vec3(base.minimum.x + 20.0, base.minimum.y + 20.0, base.minimum.z),
                        5.0, HoleProcess.CLECO, evidence=("Separate fixture construction Cleco hole.",)),
    ) if requirements.cleco_strategy == ClecoStrategy.SEPARATE_FIXTURE_HOLES else ()
    support_top = product_box.minimum.z
    components: list[FixtureBuildComponent] = [
        _component("m30-baseplate", "FXD-M30-001", "fixture baseplate", BuildComponentRole.BASEPLATE, base,
                   reference, parent=None, process="laser cut", thickness=plate,
                   rule_ids=("FXD-MFG-001", "FXD-EXP-001"),
                   disposable=requirements.lifecycle in {FixtureLifecycle.DISPOSABLE_RECUT, FixtureLifecycle.REUSABLE_TOOLING_ON_DISPOSABLE},
                   holes=base_holes,
                   evidence=("Generated from immutable product bounds with explicit clearance margin.",)),
    ]
    support_points = (
        (product_box.minimum.x + 10.0, product_box.minimum.y + 10.0),
        (product_box.maximum.x - 20.0, product_box.minimum.y + 10.0),
        ((product_box.minimum.x + product_box.maximum.x) / 2.0, product_box.maximum.y - 20.0),
    )
    for index, (x, y) in enumerate(support_points, 1):
        bounds = Aabb(Vec3(x, y, base.maximum.z), Vec3(x + 10.0, y + 10.0, support_top))
        components.append(_component(
            f"m30-support-{index}", f"FXD-M30-01{index}", f"replaceable primary support pad {index}",
            BuildComponentRole.SUPPORT_PAD, bounds, reference, parent="m30-baseplate", process="machined",
            thickness=10.0, rule_ids=("FXD-DAT-001", "FXD-SUP-001"), fixed=True, locating=True,
            assumptions=("Support contact height is provisional and requires measured incoming-part evidence.",),
            replaceable=True, maintenance_access=True,
        ))
    locator_bounds = Aabb(Vec3(product_box.minimum.x - 22.0, product_box.minimum.y + 12.0, base.maximum.z),
                          Vec3(product_box.minimum.x - 10.0, product_box.minimum.y + 32.0, support_top))
    components.append(_component("m30-round-pin", "FXD-M30-020", "round locating pin cartridge", BuildComponentRole.ROUND_PIN,
                                 locator_bounds, reference, parent="m30-baseplate", process="machined", thickness=12.0,
                                 rule_ids=("FXD-PIN-001", "FXD-LOC-001"), fixed=True, locating=True,
                                 contact_condition="functional_hole", assumptions=("Pin fit and hole tolerance require product evidence.",),
                                 replaceable=True, maintenance_access=True))
    diamond_bounds = Aabb(Vec3(product_box.minimum.x - 22.0, product_box.maximum.y - 32.0, base.maximum.z),
                          Vec3(product_box.minimum.x - 10.0, product_box.maximum.y - 12.0, support_top))
    components.append(_component("m30-diamond-pin", "FXD-M30-021", "relieved diamond locating pin cartridge", BuildComponentRole.DIAMOND_PIN,
                                 diamond_bounds, reference, parent="m30-baseplate", process="machined", thickness=12.0,
                                 rule_ids=("FXD-PIN-001", "FXD-DST-001"), fixed=False, locating=True,
                                 contact_condition="functional_hole",
                                 assumptions=("Diamond-pin clearance remains an engineer-selected tolerance strategy.",),
                                 evidence=("relief_axis=fixture_x", "locating_axis=fixture_y", "relief_style=opposed_flats"),
                                 replaceable=True, maintenance_access=True))
    stop_bounds = Aabb(Vec3(product_box.maximum.x + 10.0, product_box.minimum.y + 15.0, base.maximum.z),
                       Vec3(product_box.maximum.x + 22.0, product_box.minimum.y + 35.0, support_top))
    components.append(_component("m30-end-stop", "FXD-M30-022", "tertiary hard stop", BuildComponentRole.HARD_STOP,
                                 stop_bounds, reference, parent="m30-baseplate", process="laser cut", thickness=12.0,
                                 rule_ids=("FXD-LOC-001", "FXD-DST-001"), fixed=True, locating=True,
                                 replaceable=True, maintenance_access=True))
    clamp_bounds = Aabb(Vec3(product_box.minimum.x + 15.0, product_box.minimum.y + 15.0, support_top),
                        Vec3(product_box.minimum.x + 45.0, product_box.minimum.y + 45.0, support_top + 45.0))
    components.append(_component("m30-clamp-plate", "FXD-M30-030", "replaceable clamp mounting plate", BuildComponentRole.CLAMP_PLATE,
                                 clamp_bounds, reference, parent="m30-support-1", process="laser cut then drill/tap", thickness=12.0,
                                 rule_ids=("FXD-CLP-001", "FXD-SUP-001", "FXD-THR-001"),
                                 reaction_support="m30-support-1",
                                 holes=(HoleProcessSpec("m30-clamp-pilot", Vec3(clamp_bounds.minimum.x + 15.0, clamp_bounds.minimum.y + 15.0, clamp_bounds.minimum.z), 6.8, HoleProcess.LASER_PILOT, False, "M8x1.25", 12.0, HoleProcess.TAPPED, evidence=("Laser pilot is followed by explicit tapping operation.",)),),
                                 assumptions=("Clamp force, fastener loading, and plate adequacy require engineering review.",),
                                 replaceable=True, maintenance_access=True))
    if method in {ConstructionMethod.WELDED_TUBE_FRAME, ConstructionMethod.HYBRID}:
        rail_y = Aabb(Vec3(base.minimum.x, base.minimum.y, base.maximum.z), Vec3(base.maximum.x, base.minimum.y + 35.0, base.maximum.z + 35.0))
        rail_x = Aabb(Vec3(base.minimum.x, base.minimum.y, base.maximum.z), Vec3(base.minimum.x + 35.0, base.maximum.y, base.maximum.z + 35.0))
        components.extend((
            _component("m30-frame-rail-longitudinal", "FXD-M30-040", "welded tube-frame longitudinal rail", BuildComponentRole.TUBE_FRAME, rail_y, reference, parent="m30-baseplate", process="cut tube and weld", thickness=3.0, rule_ids=("FXD-MFG-001", "FXD-SUP-001"), assumptions=("Tube section wall and member sizing are explicit review assumptions, not structural certification.",)),
            _component("m30-frame-crossmember", "FXD-M30-041", "welded tube-frame crossmember", BuildComponentRole.CROSSMEMBER, rail_x, reference, parent="m30-baseplate", process="cut tube and weld", thickness=3.0, rule_ids=("FXD-MFG-001", "FXD-SUP-001")),
        ))
    if method in {ConstructionMethod.LASER_CUT_FABRICATED, ConstructionMethod.HYBRID, ConstructionMethod.TACK_LOCATION}:
        riser = Aabb(Vec3(product_box.minimum.x - 8.0, product_box.minimum.y + 45.0, base.maximum.z), Vec3(product_box.minimum.x + 8.0, product_box.minimum.y + 95.0, support_top + 30.0))
        gusset = Aabb(Vec3(product_box.minimum.x + 8.0, product_box.minimum.y + 45.0, base.maximum.z), Vec3(product_box.minimum.x + 28.0, product_box.minimum.y + 65.0, support_top + 30.0))
        components.extend((
            _component("m30-riser", "FXD-M30-050", "laser-cut locating riser", BuildComponentRole.RISER, riser, reference, parent="m30-baseplate", process="laser cut and weld", thickness=10.0, rule_ids=("FXD-TAB-001", "FXD-PKY-001")),
            _component("m30-gusset", "FXD-M30-051", "laser-cut riser gusset", BuildComponentRole.GUSSET, gusset, reference, parent="m30-riser", process="laser cut and weld", thickness=10.0, rule_ids=("FXD-TAB-001", "FXD-MFG-001")),
        ))
    tab_slots: tuple[TabSlotJoint, ...] = ()
    poka_yokes: tuple[PokaYokeSpec, ...] = ()
    if any(item.identity == "m30-riser" for item in components):
        tab_slots = (TabSlotJoint("m30-riser-to-base", "m30-riser", "m30-baseplate", 10.0, 10.4, 10.0, 0.4,
                                  Vec3(0.0, 0.0, -1.0), True, True, False, 1,
                                  ("Slot-and-tab construction remains an assembly aid, not a precision datum.",)),)
        poka_yokes = (PokaYokeSpec(
            "m30-riser-key", "m30-riser", "asymmetric tab and keyed slot", True, True, True, True,
            ("Asymmetric tab geometry prevents left-right reversal without creating a hidden seating condition.",),
        ),)
    clecos: tuple[ClecoSpec, ...] = ()
    if requirements.cleco_strategy == ClecoStrategy.SEPARATE_FIXTURE_HOLES:
        clecos = (ClecoSpec("m30-fixture-cleco", ClecoStrategy.SEPARATE_FIXTURE_HOLES, "m30-baseplate", 4.8, 5.0,
                            5.0, 3.0, 6.5, 4, True, True, True, True, True, spacing_mm=80.0,
                            evidence=("Separate fixture Cleco holes preserve immutable product CAD.",)),)
    elif requirements.cleco_strategy == ClecoStrategy.PRODUCT_HOLES:
        clecos = (ClecoSpec("m30-product-cleco", ClecoStrategy.PRODUCT_HOLES, "m30-baseplate", 4.8, 5.0,
                            5.0, 3.0, 6.5, 4, True, True, True, True, True,
                            product_hole_approved=requirements.product_hole_approved,
                            post_use_process=HoleProcess.WELD_FILL_GRIND if requirements.product_hole_approved else None,
                            spacing_mm=80.0,
                            evidence=((requirements.product_hole_justification or "product-hole justification missing"),),
                            assumptions=("Product holes are a proposed modification only; source CAD remains immutable.",)),)
    identity_payload = json.dumps({"concept": concept.identity, "requirements": requirements.to_dict(),
                                   "components": [item.identity for item in components]}, sort_keys=True, separators=(",", ":"))
    identity = "m30-build-" + hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()[:20]
    tack_sequence = ("load loose components", "locate", "temporary hold", "tack", "release", "unload") if requirements.fixture_purpose == FixturePurpose.TACK_LOCATION else ()
    return FixtureBuildPlan(
        identity, concept.identity, requirements, tuple(components), tab_slots, clecos,
        ("clean and open fixture", "load datum member", "load remaining members", "engage pins", "apply clamps", "verify contacts"),
        tack_sequence, ("release clamps", "release removable or retractable locators"),
        ("unload tacked or welded assembly",),
        "Finish welding is outside the tack/location fixture and requires separately approved process evidence." if tack_sequence else "",
        ("All dimensions are explicit millimetre proof geometry and remain editable.",
         "No structural adequacy, safety certification, production approval, or final weld-distortion prediction is claimed."),
        (f"source_sha256={product.source_sha256}", f"construction_method={method.value}"),
        poka_yokes,
    )


def _axis_span(bounds: Aabb, axis: str) -> float:
    return getattr(bounds.maximum, axis) - getattr(bounds.minimum, axis)


def _translated(bounds: Aabb, translation: Vec3) -> Aabb:
    return Aabb(bounds.minimum + translation, bounds.maximum + translation)


def _oriented_bounds(primary: str, primary_min: float, primary_max: float,
                     secondary_min: float, secondary_max: float,
                     z_min: float, z_max: float) -> Aabb:
    """Create an AABB using layout-local primary/secondary coordinates."""
    if primary == "x":
        return Aabb(Vec3(primary_min, secondary_min, z_min),
                    Vec3(primary_max, secondary_max, z_max))
    return Aabb(Vec3(secondary_min, primary_min, z_min),
                Vec3(secondary_max, primary_max, z_max))


def _oriented_point(primary: str, primary_value: float,
                    secondary_value: float, z_value: float) -> Vec3:
    return (Vec3(primary_value, secondary_value, z_value) if primary == "x"
            else Vec3(secondary_value, primary_value, z_value))


def _unit_direction(value: Vec3, label: str) -> Vec3:
    magnitude = math.sqrt(value.x ** 2 + value.y ** 2 + value.z ** 2)
    if not math.isfinite(magnitude) or magnitude <= 1e-9:
        raise FixtureBuildError(f"{label} must be a finite non-zero source-coordinate vector")
    return Vec3(value.x / magnitude, value.y / magnitude, value.z / magnitude)


def _axis_token(value: Vec3) -> str:
    values = ((abs(value.x), "X", value.x), (abs(value.y), "Y", value.y),
              (abs(value.z), "Z", value.z))
    _, axis, signed = max(values)
    return ("+" if signed >= 0.0 else "-") + axis


def _swept_bounds(bounds: Aabb, motion: Vec3, distance: float) -> Aabb:
    moved = _translated(bounds, Vec3(motion.x * distance, motion.y * distance, motion.z * distance))
    return Aabb(
        Vec3(min(bounds.minimum.x, moved.minimum.x), min(bounds.minimum.y, moved.minimum.y),
             min(bounds.minimum.z, moved.minimum.z)),
        Vec3(max(bounds.maximum.x, moved.maximum.x), max(bounds.maximum.y, moved.maximum.y),
             max(bounds.maximum.z, moved.maximum.z)),
    )


def _positive_bounds_overlap(left: Aabb, right: Aabb, tolerance: float = 1e-7) -> bool:
    return all(
        min(left_high, right_high) - max(left_low, right_low) > tolerance
        for left_low, left_high, right_low, right_high in zip(
            left.minimum.__dict__.values(), left.maximum.__dict__.values(),
            right.minimum.__dict__.values(), right.maximum.__dict__.values(),
        )
    )


def _bounds_share_face(left: Aabb, right: Aabb, tolerance: float = 1e-7) -> bool:
    """Return true only for a boundary contact with positive shared face area."""
    for axis in ("x", "y", "z"):
        touches = (
            abs(getattr(left.maximum, axis) - getattr(right.minimum, axis)) <= tolerance
            or abs(getattr(right.maximum, axis) - getattr(left.minimum, axis)) <= tolerance
        )
        if not touches:
            continue
        other_axes = tuple(item for item in ("x", "y", "z") if item != axis)
        if all(
            min(getattr(left.maximum, item), getattr(right.maximum, item))
            - max(getattr(left.minimum, item), getattr(right.minimum, item)) > tolerance
            for item in other_axes
        ):
            return True
    return False


def _current_product_torch_overlap_candidates(
        product: ProductModel, torch_envelope: Aabb, translation: Vec3,
        source_to_manufacturing: tuple[float, ...]) -> tuple[str, ...]:
    """Conservative product broad phase; any overlap stays unevaluated.

    A disjoint transformed body AABB proves the torch cannot intersect that
    body.  A positive AABB overlap does not prove safe seam contact versus a
    workpiece collision, so the caller must not report access as clear.
    """
    candidates: list[str] = []
    for component in product.components:
        for body in component.bodies:
            source_bounds = body.bounds.transformed(component.transform)
            station_bounds = _translated(
                _transformed_bounds(source_bounds, source_to_manufacturing), translation,
            )
            if _positive_bounds_overlap(torch_envelope, station_bounds):
                candidates.append(f"{component.identity}/{body.identity}")
    return tuple(sorted(candidates))


def _motion_path_clear(bounds: Aabb, motion: Vec3, distance: float,
                       obstacles: tuple[Aabb, ...]) -> bool:
    # Deliberate seating contacts at the final position are allowed.  The
    # swept removal/loading volume begins 1 mm away from that seated state.
    offset = min(1.0, distance * 0.1)
    start = _translated(bounds, Vec3(motion.x * offset, motion.y * offset, motion.z * offset))
    path = _swept_bounds(start, motion, max(0.0, distance - offset))
    return not any(_positive_bounds_overlap(path, obstacle) for obstacle in obstacles)


def _projection_interval(bounds: Aabb, direction: Vec3) -> tuple[float, float]:
    values = tuple(
        direction.x * x + direction.y * y + direction.z * z
        for x, y, z in itertools.product(
            (bounds.minimum.x, bounds.maximum.x),
            (bounds.minimum.y, bounds.maximum.y),
            (bounds.minimum.z, bounds.maximum.z),
        )
    )
    return min(values), max(values)


def _complete_exit_distance(bounds: Aabb, motion: Vec3,
                            obstacles: tuple[Aabb, ...], clearance: float) -> float:
    """Move the complete product beyond every occupied fixture projection."""
    product_low, _ = _projection_interval(bounds, motion)
    obstacle_high = max(
        (_projection_interval(obstacle, motion)[1] for obstacle in obstacles),
        default=product_low,
    )
    return max(clearance, obstacle_high - product_low + clearance)


def _confirmed_weld_evidence_complete(requirements: FixtureBuildRequirements) -> bool:
    expected = requirements.confirmed_weld_joint_count or len(requirements.confirmed_welds)
    return (
        requirements.confirmed_weld_intent
        and expected > 0
        and len(requirements.confirmed_welds) == expected
        and all(
            weld.weld_direction_manufacturing is not None
            and weld.weld_direction_source is not None
            for weld in requirements.confirmed_welds
        )
    )


def _cross(left: Vec3, right: Vec3) -> Vec3:
    return Vec3(
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    )


def _torch_body_envelope(intent: ConfirmedWeldIntent, translation: Vec3,
                         source_to_manufacturing: tuple[float, ...]) -> Aabb:
    """Manufacturing AABB for the torch swept across the full confirmed seam."""
    direction = _unit_direction(intent.approach_direction_manufacturing, "torch approach direction")
    if intent.weld_direction_manufacturing is None:
        raise FixtureBuildError("full-seam torch access requires an explicit manufacturing weld direction")
    seam_axis = _unit_direction(intent.weld_direction_manufacturing, "weld seam direction")
    if abs(direction.x * seam_axis.x + direction.y * seam_axis.y + direction.z * seam_axis.z) > 1e-6:
        raise FixtureBuildError("torch approach and weld seam direction must be perpendicular")
    height_axis = _unit_direction(_cross(direction, seam_axis), "torch height axis")
    joint = _matrix_apply(source_to_manufacturing, intent.joint_position_source_mm)
    origin = Vec3(joint.x + translation.x, joint.y + translation.y, joint.z + translation.z)
    points: list[Vec3] = []
    # The governed weld reference supplies the seam centre and length while the
    # engineer supplies its actual manufacturing-frame tangent.  No tangent is
    # inferred from a global seed or torch approach.
    for seam in (-intent.weld_length_mm * 0.5, intent.weld_length_mm * 0.5):
        for length in (0.0, intent.torch_envelope_mm.z):
            for width in (-intent.torch_envelope_mm.x * 0.5, intent.torch_envelope_mm.x * 0.5):
                for height in (-intent.torch_envelope_mm.y * 0.5, intent.torch_envelope_mm.y * 0.5):
                    points.append(Vec3(
                        origin.x + seam_axis.x * seam + direction.x * length
                        + seam_axis.x * width + height_axis.x * height,
                        origin.y + seam_axis.y * seam + direction.y * length
                        + seam_axis.y * width + height_axis.y * height,
                        origin.z + seam_axis.z * seam + direction.z * length
                        + seam_axis.z * width + height_axis.z * height,
                    ))
    return Aabb(
        Vec3(*(min(getattr(point, axis) for point in points) for axis in ("x", "y", "z"))),
        Vec3(*(max(getattr(point, axis) for point in points) for axis in ("x", "y", "z"))),
    )


def _cardinal_clamp_review_bounds(product: Aabb, outward: Vec3) -> tuple[Aabb, Aabb, Aabb]:
    """Create proven fixture geometry in the accepted manufacturing frame."""
    z0, z1 = 0.0, product.maximum.z
    if outward.y > 0:
        bracket = Aabb(Vec3(product.maximum.x + 4.0, product.maximum.y + 12.0, z0),
                       Vec3(product.maximum.x + 28.0, product.maximum.y + 24.0, z1 + 30.0))
        closed = Aabb(Vec3(product.maximum.x - 10.0, product.maximum.y - 8.0, z1 - 10.0),
                      Vec3(product.maximum.x + 22.0, product.maximum.y + 26.0, z1 + 22.0))
        opened = Aabb(Vec3(product.maximum.x + 12.0, product.maximum.y + 14.0, z1 + 12.0),
                      Vec3(product.maximum.x + 60.0, product.maximum.y + 46.0, z1 + 72.0))
    elif outward.y < 0:
        bracket = Aabb(Vec3(product.maximum.x + 4.0, product.minimum.y - 24.0, z0),
                       Vec3(product.maximum.x + 28.0, product.minimum.y - 12.0, z1 + 30.0))
        closed = Aabb(Vec3(product.maximum.x - 10.0, product.minimum.y - 26.0, z1 - 10.0),
                      Vec3(product.maximum.x + 22.0, product.minimum.y + 8.0, z1 + 22.0))
        opened = Aabb(Vec3(product.maximum.x + 12.0, product.minimum.y - 46.0, z1 + 12.0),
                      Vec3(product.maximum.x + 60.0, product.minimum.y - 14.0, z1 + 72.0))
    elif outward.x > 0:
        bracket = Aabb(Vec3(product.maximum.x + 12.0, product.maximum.y + 4.0, z0),
                       Vec3(product.maximum.x + 24.0, product.maximum.y + 28.0, z1 + 30.0))
        closed = Aabb(Vec3(product.maximum.x - 8.0, product.maximum.y - 10.0, z1 - 10.0),
                      Vec3(product.maximum.x + 26.0, product.maximum.y + 22.0, z1 + 22.0))
        opened = Aabb(Vec3(product.maximum.x + 14.0, product.maximum.y + 12.0, z1 + 12.0),
                      Vec3(product.maximum.x + 46.0, product.maximum.y + 60.0, z1 + 72.0))
    else:
        bracket = Aabb(Vec3(product.minimum.x - 24.0, product.maximum.y + 4.0, z0),
                       Vec3(product.minimum.x - 12.0, product.maximum.y + 28.0, z1 + 30.0))
        closed = Aabb(Vec3(product.minimum.x - 26.0, product.maximum.y - 10.0, z1 - 10.0),
                      Vec3(product.minimum.x + 8.0, product.maximum.y + 22.0, z1 + 22.0))
        opened = Aabb(Vec3(product.minimum.x - 46.0, product.maximum.y + 12.0, z1 + 12.0),
                      Vec3(product.minimum.x - 14.0, product.maximum.y + 60.0, z1 + 72.0))
    return bracket, closed, opened


def _clamp_review_bounds(product: Aabb, operator_outward: Vec3,
                         manufacturing_up: Vec3) -> tuple[Aabb, Aabb, Aabb]:
    """Create clamp review bounds after all inputs enter manufacturing coordinates."""
    outward = _unit_direction(operator_outward, "clamp operating direction")
    up = _unit_direction(manufacturing_up, "manufacturing up direction")
    if (abs(up.x) > 1e-7 or abs(up.y) > 1e-7 or up.z < 1.0 - 1e-7
            or abs(outward.z) > 1e-7
            or not (abs(abs(outward.x) - 1.0) <= 1e-7
                    or abs(abs(outward.y) - 1.0) <= 1e-7)):
        raise FixtureBuildError("accepted fixture directions did not normalize into the manufacturing frame")
    return _cardinal_clamp_review_bounds(product, outward)


def _station_access_evidence_digest(
        station: StationTransform,
        components: tuple[FixtureBuildComponent, ...],
        stations: tuple[StationTransform, ...],
        requirements: FixtureBuildRequirements,
        multi_station: MultiStationRequirements) -> str:
    station_evidence = station.to_dict()
    station_evidence.pop("access_evidence_digest", None)
    placement_evidence = tuple({
        "identity": item.identity,
        "translation_mm": item.translation_mm.__dict__,
        "product_bounds": {
            "minimum": item.product_bounds.minimum.__dict__,
            "maximum": item.product_bounds.maximum.__dict__,
        },
        "source_to_station_manufacturing": list(item.source_to_station_manufacturing),
    } for item in sorted(stations, key=lambda value: value.identity))
    payload = {
        "schema": "fxd-m32-access-evidence-v1",
        "station": station_evidence,
        "station_placements": placement_evidence,
        "components": [item.to_dict() for item in sorted(components, key=lambda value: value.identity)],
        "fixture_requirements": requirements.to_dict(),
        "multi_station_requirements": multi_station.to_dict(),
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MultiStationFitProposal:
    """Deterministic, explicitly accepted response to a length-constrained request."""

    requested_station_count: int
    feasible_station_count: int
    primary_axis: str
    station_pitch_mm: float
    requested_required_length_mm: float
    feasible_required_length_mm: float
    maximum_fixture_length_mm: float
    station_span_mm: float
    clamp_sweep_mm: float
    end_allowance_mm: float
    hand_clearance_mm: float
    weld_clearance_mm: float
    adjustment_allowance_mm: float

    @property
    def requires_explicit_acceptance(self) -> bool:
        return self.feasible_station_count < self.requested_station_count

    @property
    def explanation(self) -> tuple[str, ...]:
        return (
            f"requested_station_count={self.requested_station_count}",
            f"feasible_station_count={self.feasible_station_count}",
            f"station_pitch_mm={self.station_pitch_mm:.3f}",
            f"requested_required_length_mm={self.requested_required_length_mm:.3f}",
            f"feasible_required_length_mm={self.feasible_required_length_mm:.3f}",
            f"maximum_fixture_length_mm={self.maximum_fixture_length_mm:.3f}",
            "limiting_margin=product envelope + clamp sweep + hand clearance + weld clearance + adjustment allowance + end margins",
        )


def _multi_station_fit(product: ProductModel,
                       requirements: MultiStationRequirements) -> MultiStationFitProposal:
    bounds = _manufacturing_product_bounds(product, requirements)
    axis = "x" if _axis_span(bounds, "x") >= _axis_span(bounds, "y") else "y"
    station_span = _axis_span(bounds, axis)
    secondary = _axis_span(bounds, "y" if axis == "x" else "x")
    clamp_sweep = requirements.clamp_sweep_mm or max(30.0, secondary * 0.60)
    pitch = max(requirements.preferred_station_pitch_mm or 0.0,
                station_span + clamp_sweep + requirements.hand_clearance_mm
                + requirements.weld_clearance_mm + requirements.adjustment_allowance_mm)
    end_allowance = max(45.0, requirements.hand_clearance_mm * 0.5)
    usable = requirements.maximum_fixture_length_mm - (2.0 * end_allowance) - station_span
    feasible = max(0, min(8, int(math.floor(usable / pitch)) + 1))
    requested_intent = requirements.requested_intent_station_count or requirements.requested_station_count
    length_for = lambda count: 2.0 * end_allowance + station_span + pitch * (count - 1)
    return MultiStationFitProposal(
        requested_intent, feasible, axis, pitch, length_for(requested_intent),
        length_for(max(1, feasible)), requirements.maximum_fixture_length_mm,
        station_span, clamp_sweep, end_allowance, requirements.hand_clearance_mm,
        requirements.weld_clearance_mm, requirements.adjustment_allowance_mm,
    )


def propose_multi_station_fit(product: ProductModel,
                              requirements: MultiStationRequirements) -> MultiStationFitProposal:
    """Expose the governed fit basis before any station-count reduction is accepted."""
    return _multi_station_fit(product, requirements)


def propose_multi_station_count(product: ProductModel,
                                requirements: MultiStationRequirements) -> int:
    """Return the largest equal-pitch count that fits the explicit length limit."""
    return _multi_station_fit(product, requirements).feasible_station_count


def generate_multi_station_layout(product: ProductModel,
                                  requirements: MultiStationRequirements) -> MultiStationLayout:
    """Derive equal-pitch manufacturing-frame instances without copying source CAD."""
    bounds = _manufacturing_product_bounds(product, requirements)
    fit = _multi_station_fit(product, requirements)
    axis, pitch, end_allowance = fit.primary_axis, fit.station_pitch_mm, fit.end_allowance_mm
    required_length, proposed = (2.0 * end_allowance + fit.station_span_mm
                                 + pitch * (requirements.requested_station_count - 1)), fit.feasible_station_count
    if proposed < 1:
        raise FixtureBuildError("maximum fixture length cannot fit one product station with its explicit access allowances")
    if requirements.requested_station_count > proposed:
        raise FixtureBuildError(
            f"requested {requirements.requested_station_count} stations require {required_length:.3f} mm, "
            f"exceeding the {requirements.maximum_fixture_length_mm:.3f} mm limit; "
            f"deterministic smaller-layout proposal is {proposed} station(s)"
        )
    source_components = tuple(component.identity for component in product.components)
    stations: list[StationTransform] = []
    for index in range(1, requirements.requested_station_count + 1):
        location = end_allowance + (index - 1) * pitch
        translation = (
            Vec3(location - bounds.minimum.x, 52.0 - bounds.minimum.y, 12.0 - bounds.minimum.z)
            if axis == "x" else
            Vec3(52.0 - bounds.minimum.x, location - bounds.minimum.y, 12.0 - bounds.minimum.z)
        )
        stations.append(StationTransform(
            f"m32-station-{index:02d}", index, translation, product.source_sha256,
            source_components, _translated(bounds, translation),
            source_to_station_manufacturing=_matrix_product(
                _translation_matrix(translation), requirements.source_to_manufacturing,
            ),
        ))
    payload = json.dumps({"source": product.source_sha256, "requirements": requirements.to_dict(),
                          "axis": axis, "pitch": pitch,
                          "stations": [item.identity for item in stations]},
                         sort_keys=True, separators=(",", ":"))
    return MultiStationLayout(
        "m32-layout-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20], requirements,
        axis, round(pitch, 6), round(required_length, 6),
        proposed if proposed < (requirements.requested_intent_station_count or requirements.requested_station_count) else None, tuple(stations),
        (
            f"primary_axis={axis} derived from the largest product horizontal envelope span.",
            f"pitch={pitch:.3f} mm combines product envelope, clamp sweep, hand clearance, weld clearance, and adjustment allowance.",
            *fit.explanation,
            "Product stations apply the accepted full source-to-manufacturing transform plus manufacturing-frame pitch while referencing immutable source identities.",
        ),
        round(fit.requested_required_length_mm, 6),
    )


def generate_multi_station_fixture_build_plan(
        product: ProductModel, concept: CompleteFixtureConcept,
        requirements: FixtureBuildRequirements,
        multi_station: MultiStationRequirements) -> FixtureBuildPlan:
    """Author M32 manufacturing intent through the existing fixture-build plan.

    This is deliberately a supported-family generator, not an unconstrained
    B-Rep authoring API.  Every real solid is still created only by
    :func:`author_fixture_build` after the same deterministic gate used by M30.
    """
    if requirements.source_sha256 != product.source_sha256:
        raise FixtureBuildError("multi-station requirements do not match immutable source geometry")
    if concept.fixture.source_sha256 != product.source_sha256:
        raise FixtureBuildError("multi-station concept does not match immutable source geometry")
    if not multi_station.manufacturing_orientation_identity:
        raise FixtureBuildError("multi-station synthesis requires accepted manufacturing orientation identity")
    for weld in requirements.confirmed_welds:
        if weld.manufacturing_orientation_identity != multi_station.manufacturing_orientation_identity:
            raise FixtureBuildError("confirmed weld approach does not match the accepted manufacturing orientation")
        if any(not _reference_valid(product, reference) for reference in weld.references):
            raise FixtureBuildError("confirmed weld intent contains an invalid immutable source reference")
        for source_vector, manufacturing_vector, label in (
                (weld.approach_direction_source, weld.approach_direction_manufacturing,
                 "torch approach"),
                (weld.weld_direction_source, weld.weld_direction_manufacturing,
                 "weld direction")):
            if source_vector is None or manufacturing_vector is None:
                continue
            transformed = _unit_direction(
                _matrix_apply(multi_station.source_to_manufacturing, source_vector, vector=True),
                f"transformed {label}",
            )
            governed = _unit_direction(manufacturing_vector, f"manufacturing {label}")
            if any(abs(getattr(transformed, axis) - getattr(governed, axis)) > 1e-7
                   for axis in ("x", "y", "z")):
                raise FixtureBuildError(
                    f"confirmed weld {label} source and manufacturing vectors do not match the accepted orientation"
                )
    layout = generate_multi_station_layout(product, multi_station)
    manufacturing_bounds = _manufacturing_product_bounds(product, multi_station)
    primary = layout.primary_axis
    product_height = _axis_span(manufacturing_bounds, "z")
    plate = 12.0
    base_length = layout.required_fixture_length_mm
    # The long member is a low backbone, not a product-sized rear wall.  Local
    # station plates carry the product-shaped locating and clamp structure.
    # The backbone ends at the station-plate boundary.  The two separately
    # authored solids share a weldable face but never occupy the same volume.
    base = _oriented_bounds(primary, 0.0, base_length, 0.0, 24.0, -plate, 0.0)
    rail = _oriented_bounds(primary, 0.0, base_length, 12.0, 24.0, 0.0,
                            min(24.0, product_height * 0.45 + 6.0))
    reference = _component_reference(product)
    mount_holes = tuple(
        HoleProcessSpec(
            f"m32-table-mount-{index}", _oriented_point(primary, along, across, base.minimum.z), 12.0,
            HoleProcess.LASER_CLEARANCE, evidence=("Table-mount review hole; fastener and table standard require engineer confirmation.",),
        )
        for index, (along, across) in enumerate(((18.0, 6.0), (base_length - 18.0, 6.0),
                                                  (18.0, 18.0), (base_length - 18.0, 18.0)), 1)
    )
    rail_slots = tuple(
        SlotProcessSpec(
            f"m32-rail-slot-{index}",
            Vec3(x - 6.0, 12.0, base.minimum.z - 1.0) if primary == "x" else Vec3(12.0, x - 6.0, base.minimum.z - 1.0),
            Vec3(x + 6.0, 24.0, 1.0) if primary == "x" else Vec3(24.0, x + 6.0, 1.0),
            "datum rail tab-and-slot location during fixture fabrication",
        ) for index, x in enumerate((48.0, base_length - 48.0), 1)
    )
    components: list[FixtureBuildComponent] = [
        _component("m32-backbone", "FXD-M32-001", "low linear backbone with table mounting holes",
                   BuildComponentRole.BASEPLATE, base, reference, parent=None, process="laser cut then drill as required",
                   thickness=plate, rule_ids=("FXD-MFG-001", "FXD-M32-STA", "FXD-M32-CON", "FXD-EXP-001"),
                   holes=mount_holes, slots=rail_slots,
                   evidence=("Overall length is derived from deterministic station pitch and explicit maximum-length intent.",
                             "Backbone secondary extent terminates at the local station-plate weld boundary; separately authored solids do not interpenetrate.",
                             "Mounting holes are review geometry; table-fastener selection remains engineer controlled.")),
        _component("m32-datum-rail", "FXD-M32-002", "low common datum and structural backbone rail",
                   BuildComponentRole.DATUM_RAIL, rail, reference, parent="m32-backbone", process="laser cut and weld",
                   thickness=12.0, rule_ids=("FXD-MFG-001", "FXD-TAB-001", "FXD-M32-CON"),
                   evidence=(f"Low common rail is selected because {len(layout.stations)} repeated local plate(s) need one table-mounted load path.",
                             "Rail height is limited by product height and operator/weld access; no structural capacity is claimed.")),
    ]
    tab_slots = tuple(TabSlotJoint(
        f"m32-rail-tab-{index}", "m32-datum-rail", "m32-backbone", 12.0, 12.5, 12.0, 0.5,
        Vec3(0.0, 0.0, -1.0), True, True, False, index,
        ("Rail tab-and-slot fit is explicit review evidence, not a final tolerance release.",),
    ) for index in (1, 2))
    source_directions = (
        multi_station.loading_direction_source,
        multi_station.unloading_direction_source,
        multi_station.operator_loading_direction_source,
        multi_station.clamp_operating_direction_source,
        multi_station.manufacturing_up_direction_source,
    )
    if any(value is None for value in source_directions):
        raise FixtureBuildError(
            "multi-station process directions require accepted-orientation source-coordinate evidence"
        )
    if not multi_station.source_to_manufacturing or not multi_station.manufacturing_to_source:
        raise FixtureBuildError("multi-station synthesis requires accepted manufacturing-frame transforms")
    identity = _identity_matrix()
    if not (
        _matrices_close(
            _matrix_product(multi_station.source_to_manufacturing, multi_station.manufacturing_to_source),
            identity,
        )
        and _matrices_close(
            _matrix_product(multi_station.manufacturing_to_source, multi_station.source_to_manufacturing),
            identity,
        )
    ):
        raise FixtureBuildError("accepted manufacturing-frame transforms are not mutual inverses")
    insertion_direction = _unit_direction(
        _matrix_apply(multi_station.source_to_manufacturing, source_directions[0], vector=True),
        "loading direction",
    )
    unload_direction = _unit_direction(
        _matrix_apply(multi_station.source_to_manufacturing, source_directions[1], vector=True),
        "unloading direction",
    )
    operator_outward = _unit_direction(
        _matrix_apply(multi_station.source_to_manufacturing, source_directions[2], vector=True),
        "operator loading side",
    )
    clamp_outward = _unit_direction(
        _matrix_apply(multi_station.source_to_manufacturing, source_directions[3], vector=True),
        "clamp operating side",
    )
    manufacturing_up = _unit_direction(
        _matrix_apply(multi_station.source_to_manufacturing, source_directions[4], vector=True),
        "manufacturing up direction",
    )
    loading_outward = Vec3(-insertion_direction.x, -insertion_direction.y, -insertion_direction.z)
    clamp_review: dict[str, tuple[Aabb, Aabb, Aabb]] = {}
    for station in layout.stations:
        box = station.product_bounds
        x0, x1 = box.minimum.x, box.maximum.x
        y0, y1 = box.minimum.y, box.maximum.y
        z1 = box.maximum.z
        prefix = station.identity
        p0, p1 = ((x0, x1) if primary == "x" else (y0, y1))
        s0, s1 = ((y0, y1) if primary == "x" else (x0, x1))
        station_plate_id = f"{prefix}-station-plate"
        station_plate = _oriented_bounds(primary, p0 - 18.0, p1 + 18.0,
                                          min(24.0, s0 - 28.0), s1 + 28.0, -plate, 0.0)
        station_mount_holes = tuple(
            HoleProcessSpec(
                f"{prefix}-plate-mount-{index}", Vec3(x, y, -plate), 10.0,
                HoleProcess.LASER_CLEARANCE,
                evidence=("Local station-plate mounting hole; final fastener standard requires engineer confirmation.",),
            )
            for index, (x, y) in enumerate((
                (station_plate.minimum.x + 12.0, station_plate.minimum.y + 12.0),
                (station_plate.maximum.x - 12.0, station_plate.maximum.y - 12.0),
            ), 1)
        )
        components.append(_component(
            station_plate_id, f"FXD-M32-{station.station_index:02d}00",
            f"station {station.station_index} local laser-cut station plate",
            BuildComponentRole.STATION_PLATE, station_plate, reference, parent="m32-backbone",
            process="laser cut, tab to backbone, and weld after station alignment", thickness=plate,
            rule_ids=("FXD-MFG-001", "FXD-TAB-001", "FXD-M32-STA", "FXD-M32-CON"),
            holes=station_mount_holes,
            evidence=(f"station={station.identity}",
                      "Local plate extent follows product bounds plus explicit locating and operator-side margins.",
                      "Assembly sequence: locate plate on backbone, verify access, tack, inspect, then finish weld."),
        ))
        support_points = ((x0 + (x1 - x0) * 0.22, y0 + (y1 - y0) * 0.30),
                          (x0 + (x1 - x0) * 0.78, y0 + (y1 - y0) * 0.30),
                          (x0 + (x1 - x0) * 0.50, y0 + (y1 - y0) * 0.72))
        for support_index, (x, y) in enumerate(support_points, 1):
            support = Aabb(Vec3(x - 7.0, y - 7.0, 0.0), Vec3(x + 7.0, y + 7.0, 12.0))
            components.append(_component(
                f"{prefix}-support-{support_index}", f"FXD-M32-{station.station_index:02d}1{support_index}",
                f"station {station.station_index} replaceable support rest {support_index}",
                BuildComponentRole.SUPPORT_PAD, support, reference, parent=station_plate_id, process="machined replaceable rest",
                thickness=12.0, rule_ids=("FXD-DAT-001", "FXD-SUP-001", "FXD-M32-STA"), fixed=True,
                locating=True, replaceable=True, maintenance_access=True,
                evidence=(f"station={station.identity}", "Three-point primary support arrangement."),
            ))
        locator = _oriented_bounds(primary, p0 + 8.0, p0 + 30.0, s0 - 12.0, s0,
                                   0.0, min(z1 + 18.0, product_height + 42.0))
        locator_slot = SlotProcessSpec(
            f"{prefix}-locator-adjustment-slot",
            Vec3(locator.minimum.x + 5.0, locator.minimum.y - 1.0, 8.0),
            Vec3(locator.maximum.x - 5.0, locator.maximum.y + 1.0, min(30.0, locator.maximum.z - 2.0)),
            "station locator adjustment and prove-out",
        )
        components.append(_component(
            f"{prefix}-locator-plate", f"FXD-M32-{station.station_index:02d}20",
            f"station {station.station_index} secondary locator plate with adjustment slot",
            BuildComponentRole.LOCATOR_PLATE, locator, reference, parent=station_plate_id, process="laser cut and machine locator face",
            thickness=12.0, rule_ids=("FXD-LOC-001", "FXD-TAB-001", "FXD-M32-STA"), fixed=True,
            locating=True, contact_condition="functional_face", replaceable=True, maintenance_access=True,
            slots=(locator_slot,), evidence=(f"station={station.identity}", "Relieved contact and adjustment slot remain editable."),
        ))
        stop = _oriented_bounds(primary, p1, p1 + 12.0, s0 + 8.0, s0 + 30.0,
                                0.0, min(z1 + 12.0, product_height + 34.0))
        components.append(_component(
            f"{prefix}-hard-stop", f"FXD-M32-{station.station_index:02d}30",
            f"station {station.station_index} longitudinal hard stop", BuildComponentRole.HARD_STOP,
            stop, reference, parent=station_plate_id, process="laser cut replaceable stop", thickness=12.0,
            rule_ids=("FXD-LOC-001", "FXD-DST-001", "FXD-M32-STA"), fixed=True, locating=True,
            replaceable=True, maintenance_access=True, evidence=(f"station={station.identity}", "Longitudinal location is explicit and replaceable."),
        ))
        bracket, clamp, open_envelope = _clamp_review_bounds(box, clamp_outward, manufacturing_up)
        components.append(_component(
            f"{prefix}-clamp-bracket", f"FXD-M32-{station.station_index:02d}40",
            f"station {station.station_index} toggle-clamp mounting bracket", BuildComponentRole.CLAMP_BRACKET,
            bracket, reference, parent=station_plate_id, process="laser cut, weld, drill and tap", thickness=12.0,
            rule_ids=("FXD-CLP-001", "FXD-SUP-001", "FXD-THR-001", "FXD-M32-CLP"),
            reaction_support=f"{prefix}-support-2", replaceable=True, maintenance_access=True,
            holes=(HoleProcessSpec(f"{prefix}-clamp-mount", Vec3(bracket.minimum.x + 14.0, bracket.minimum.y + 8.0, 0.0),
                                   6.8, HoleProcess.LASER_PILOT, False, "M8x1.25", 12.0, HoleProcess.TAPPED,
                                   evidence=("Generic clamp mounting pattern is review evidence, not released vendor CAD.",)),),
            evidence=(f"station={station.identity}", "Clamp bracket has an explicit base-to-support reaction path."),
        ))
        components.append(_component(
            f"{prefix}-toggle-clamp", f"FXD-M32-{station.station_index:02d}50",
            f"station {station.station_index} vendor-neutral toggle-clamp review geometry", BuildComponentRole.TOGGLE_CLAMP,
            clamp, reference, parent=f"{prefix}-clamp-bracket", process="generic purchased-clamp review representation",
            thickness=8.0, rule_ids=("FXD-CLP-001", "FXD-M32-CLP", "FXD-M32-ACC"),
            authority=GeometryAuthority.PURCHASED_COMPONENT, nest=NestClassification.PURCHASED_TOOLING,
            reaction_support=f"{prefix}-support-2", replaceable=True, maintenance_access=True,
            evidence=(f"station={station.identity}", "generic_vendor_neutral=true", "clamp_state=closed",
                      "clamp_tip_target=intended clamp surface", f"clamp_operating_side={multi_station.clamp_operating_side}",
                      "provisional purchased tooling review geometry; excluded from manufacturing release outputs"),
        ))
        components.append(_component(
            f"{prefix}-clamp-open-envelope", f"FXD-M32-{station.station_index:02d}51",
            f"station {station.station_index} vendor-neutral clamp open operating envelope",
            BuildComponentRole.CLAMP_OPEN_ENVELOPE, open_envelope, reference,
            parent=f"{prefix}-clamp-bracket", process="provisional purchased-tooling motion envelope",
            thickness=8.0, rule_ids=("FXD-CLP-001", "FXD-M32-CLP", "FXD-M32-ACC"),
            authority=GeometryAuthority.PURCHASED_COMPONENT, nest=NestClassification.PURCHASED_TOOLING,
            reaction_support=f"{prefix}-support-2", replaceable=True, maintenance_access=True,
            evidence=(f"station={station.identity}", "generic_vendor_neutral=true", "clamp_state=open",
                      f"clamp_operating_side={multi_station.clamp_operating_side}",
                      "representative handle and open-sweep envelope; excluded from manufacturing release outputs"),
        ))
        clamp_review[station.identity] = (bracket, clamp, open_envelope)
        shim = Aabb(Vec3(x0 + 36.0, y0 + 10.0, 0.0), Vec3(x0 + 56.0, y0 + 30.0, 2.0))
        components.append(_component(
            f"{prefix}-wear-shim", f"FXD-M32-{station.station_index:02d}60",
            f"station {station.station_index} replaceable wear shim", BuildComponentRole.SHIM_PACK,
            shim, reference, parent=station_plate_id, process="laser cut shim stock", thickness=2.0,
            rule_ids=("FXD-MNT-001", "FXD-M32-STA"), replaceable=True, maintenance_access=True,
            evidence=(f"station={station.identity}", "Replaceable wear and shim evidence."),
        ))
    brace_height = min(30.0, product_height * 0.4 + 6.0)
    brace_bounds = (
        _oriented_bounds(primary, 4.0, 34.0, 0.0, 12.0, 0.0, brace_height),
        _oriented_bounds(primary, base_length - 34.0, base_length - 4.0, 0.0, 12.0, 0.0, brace_height),
    )
    for index, brace in enumerate(brace_bounds, 1):
        components.append(_component(
            f"m32-end-brace-{index}", f"FXD-M32-00{index + 2}", f"datum rail end brace {index}",
            BuildComponentRole.END_BRACE, brace, reference, parent="m32-backbone", process="laser cut and weld",
            thickness=12.0, rule_ids=("FXD-MFG-001", "FXD-M32-CON"),
            evidence=("Compact end gusset meets the datum rail at its secondary face without occupying the rail volume.",),
        ))
    access_obstacles = tuple(
        component.bounds for component in components
        if component.role != BuildComponentRole.TOGGLE_CLAMP
    )
    weld_fixture_obstacles = tuple(
        (component.identity, component.bounds) for component in components
        if component.role != BuildComponentRole.CLAMP_OPEN_ENVELOPE
    )
    evaluated_stations: list[StationTransform] = []
    for station in layout.stations:
        bracket, closed, opened = clamp_review[station.identity]
        other_products = tuple(
            other.product_bounds for other in layout.stations
            if other.identity != station.identity
        )
        station_obstacles = access_obstacles + other_products
        loading_distance = _complete_exit_distance(
            station.product_bounds, loading_outward, station_obstacles,
            multi_station.hand_clearance_mm,
        )
        unloading_distance = _complete_exit_distance(
            station.product_bounds, unload_direction, station_obstacles,
            multi_station.hand_clearance_mm,
        )
        loading_envelope = _swept_bounds(
            station.product_bounds, loading_outward, loading_distance,
        )
        unloading_envelope = _swept_bounds(
            station.product_bounds, unload_direction, unloading_distance,
        )
        loading_clear = _motion_path_clear(
            station.product_bounds, loading_outward, loading_distance,
            station_obstacles,
        )
        unloading_clear = _motion_path_clear(
            station.product_bounds, unload_direction, unloading_distance,
            station_obstacles,
        )
        open_clear = not opened.intersects(station.product_bounds)
        hand_clear = loading_clear and open_clear
        weld_clear: bool | None = None
        weld_results: list[WeldJointAccessResult] = []
        if _confirmed_weld_evidence_complete(requirements) and requirements.full_weld_access_available is True:
            adjacent_products = tuple(
                (other.identity, other.product_bounds) for other in layout.stations
                if other.identity != station.identity
            )
            for weld in requirements.confirmed_welds:
                torch_envelope = _torch_body_envelope(
                    weld, station.translation_mm, multi_station.source_to_manufacturing,
                )
                blockers = list(
                    identity for identity, bounds in weld_fixture_obstacles + adjacent_products
                    if _positive_bounds_overlap(torch_envelope, bounds)
                )
                approach_manufacturing = _unit_direction(
                    weld.approach_direction_manufacturing, "manufacturing torch approach direction",
                )
                approach_source = _unit_direction(
                    weld.approach_direction_source, "source torch approach direction",
                )
                side_alignment = (
                    approach_manufacturing.x * operator_outward.x
                    + approach_manufacturing.y * operator_outward.y
                    + approach_manufacturing.z * operator_outward.z
                )
                normalized_side = weld.weld_side.strip().lower()
                side_conflict = (("opposite" in normalized_side and side_alignment >= -1e-7)
                                 or ("operator" in normalized_side and "opposite" not in normalized_side
                                     and side_alignment <= 1e-7))
                blockers_tuple = tuple(blockers)
                current_product_candidates = _current_product_torch_overlap_candidates(
                    product, torch_envelope, station.translation_mm,
                    multi_station.source_to_manufacturing,
                )
                fixture_clear = not blockers_tuple and not side_conflict
                clear = False if not fixture_clear else (
                    None if current_product_candidates else True
                )
                weld_results.append(WeldJointAccessResult(
                    weld.identity, clear, torch_envelope,
                    approach_source,
                    blockers_tuple,
                    (
                        f"joint={weld.identity}",
                        f"weld_side={weld.weld_side}",
                        f"weld_length_mm={weld.weld_length_mm:.3f}",
                        "torch_sweep_over_full_weld_length=true",
                        "weld_direction_manufacturing="
                        f"({weld.weld_direction_manufacturing.x:.6f},"
                        f"{weld.weld_direction_manufacturing.y:.6f},"
                        f"{weld.weld_direction_manufacturing.z:.6f})",
                        f"weld_process={weld.process}",
                        f"weld_sequence={weld.sequence}",
                        f"orientation={weld.manufacturing_orientation_identity}",
                        f"torch_envelope_mm=({weld.torch_envelope_mm.x:.3f},{weld.torch_envelope_mm.y:.3f},{weld.torch_envelope_mm.z:.3f})",
                        "weld_side_vs_approach=" + ("conflict" if side_conflict else "consistent"),
                        "torch_body_vs_fixture_clamps_adjacent_stations="
                        + ("clear" if fixture_clear else "blocked"),
                        "torch_body_vs_current_product="
                        + ("not_evaluated" if current_product_candidates else "clear"),
                        f"current_product_overlap_candidate_count={len(current_product_candidates)}",
                        *(f"current_product_overlap_candidate={identity}"
                          for identity in current_product_candidates),
                    ),
                    current_product_candidates,
                ))
            weld_clear = (
                False if any(item.clear is False for item in weld_results)
                else True if weld_results and all(item.clear is True for item in weld_results)
                else None
            )
        evaluated_station = replace(
            station,
            clamp_tip_reaches_surface=closed.intersects(station.product_bounds),
            open_clamp_envelope_clear=open_clear,
            hand_access_clear=hand_clear,
            weld_access_clear=weld_clear,
            unload_path_clear=unloading_clear,
            trapped_part=not (loading_clear and unloading_clear),
            loading_direction=_axis_token(insertion_direction),
            unloading_direction=_axis_token(unload_direction),
            operator_side=multi_station.operator_loading_side,
            loading_envelope=loading_envelope,
            unloading_envelope=unloading_envelope,
            open_clamp_envelope=opened,
            closed_clamp_envelope=closed,
            loading_direction_source=_unit_direction(source_directions[0], "source loading direction"),
            unloading_direction_source=_unit_direction(source_directions[1], "source unloading direction"),
            operator_direction_source=_unit_direction(source_directions[2], "source operator direction"),
            weld_access_results=tuple(weld_results),
            access_evidence=(
                f"operator_side={multi_station.operator_loading_side}",
                f"insertion_direction_manufacturing=({insertion_direction.x:.6g},{insertion_direction.y:.6g},{insertion_direction.z:.6g})",
                f"unloading_direction_manufacturing=({unload_direction.x:.6g},{unload_direction.y:.6g},{unload_direction.z:.6g})",
                f"clamp_direction_manufacturing=({clamp_outward.x:.6g},{clamp_outward.y:.6g},{clamp_outward.z:.6g})",
                f"manufacturing_orientation={multi_station.manufacturing_orientation_identity or 'unrecorded'}",
                f"hand_clearance_mm={multi_station.hand_clearance_mm:.3f}",
                f"complete_loading_exit_distance_mm={loading_distance:.3f}",
                f"complete_unloading_exit_distance_mm={unloading_distance:.3f}",
                "loading_sweep_vs_rail_station_plate_locator_stop_open_clamp_brace=" + ("clear" if loading_clear else "blocked"),
                "unloading_sweep_vs_rail_station_plate_locator_stop_open_clamp_brace=" + ("clear" if unloading_clear else "blocked"),
                "open_clamp_sweep_vs_product=" + ("clear" if open_clear else "blocked"),
                "weld_access=" + ("clear" if weld_clear is True else "blocked" if weld_clear is False else "not_evaluated"),
            ),
        )
        evaluated_stations.append(replace(
            evaluated_station,
            access_evidence_digest=_station_access_evidence_digest(
                evaluated_station, tuple(components), layout.stations,
                requirements, multi_station,
            ),
        ))
    layout = replace(layout, stations=tuple(evaluated_stations), rationale=layout.rationale + (
        "structure=low common backbone plus product-bounded local laser-cut station plates; a tall full-length wall is not emitted.",
        f"construction_rationale={len(layout.stations)} repeated station(s) share a table load path while local plates preserve loading, clamp, and weld review access.",
        "stiffness_intent=low rail and end gussets provide review load-path continuity; no certified capacity is claimed.",
    ))
    identity_payload = json.dumps({"concept": concept.identity, "requirements": requirements.to_dict(),
                                   "layout": layout.to_dict(), "components": [item.identity for item in components]},
                                  sort_keys=True, separators=(",", ":"))
    return FixtureBuildPlan(
        "m32-build-" + hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()[:20], concept.identity,
        requirements, tuple(components), tab_slots, (),
        ("open clamp envelopes", "load immutable product review instances", "seat on three supports", "locate against rail and stop", "close toggle clamps"),
        (), ("open toggle clamps", "release removable contact items"),
        ("remove completed assembly along the recorded unload direction",),
        "Weld process, clamp force, and structural adequacy remain qualified engineering review work.",
        ("M32 geometry is deterministic review geometry authored from explicit station intent.",
         "No source CAD bytes or source topology are modified by product review instances."),
        (f"source_sha256={product.source_sha256}", f"fixture_family={multi_station.fixture_family.value}",
         f"station_count={multi_station.requested_station_count}"),
        (PokaYokeSpec("m32-rail-key", "m32-datum-rail", "asymmetric rail tab pattern", True, True, True, True,
                      ("Asymmetric rail tab pattern prevents backplate reversal while preserving visible seating and unload direction.",)),),
        layout,
    )


def generate_multi_station_fixture_alternatives(
        product: ProductModel, concept: CompleteFixtureConcept,
        requirements: FixtureBuildRequirements,
        multi_station: MultiStationRequirements) -> tuple[FixtureBuildPlan, ...]:
    """Create governed one-up and selected multi-up alternatives.

    The result consists of ordinary immutable build plans so both alternatives
    go through the same validation, OCP authoring, and review gates.  The
    selected count is last, making selection deterministic without turning a
    comparison into a release decision.
    """
    counts = ((1, multi_station.requested_station_count)
              if multi_station.compare_one_up_and_multi_up
              and multi_station.requested_station_count > 1
              else (multi_station.requested_station_count,))
    return tuple(
        generate_multi_station_fixture_build_plan(
            product, concept, requirements,
            replace(multi_station, requested_station_count=count),
        )
        for count in counts
    )


def bind_fixture_build_plan_to_proposal(plan: FixtureBuildPlan, proposal: object) -> FixtureBuildPlan:
    """Bind an M32 build to one current, accepted deterministic proposal."""
    if plan.multi_station_layout is None:
        raise FixtureBuildError("fixture proposal binding is only defined for multi-station builds")
    if getattr(proposal, "source_sha256", None) != plan.requirements.source_sha256:
        raise FixtureBuildError("fixture proposal does not match immutable build source geometry")
    orientation = plan.multi_station_layout.requirements.manufacturing_orientation_identity
    if getattr(proposal, "manufacturing_orientation_identity", None) != orientation:
        raise FixtureBuildError("fixture proposal does not match the build manufacturing orientation")
    if getattr(proposal, "blocker_count", 1):
        raise FixtureBuildError("fixture proposal with deterministic blockers cannot bind a build")
    if getattr(proposal, "proposal_decision", None) != "accepted_for_engineering_review":
        raise FixtureBuildError("fixture proposal must be accepted before binding a multi-station build")
    return replace(
        plan,
        fixture_proposal_identity=str(getattr(proposal, "proposal_identity")),
        fixture_proposal_evidence_digest=str(getattr(proposal, "evidence_digest")),
    )


def _component_by_id(plan: FixtureBuildPlan) -> dict[str, FixtureBuildComponent]:
    return {item.identity: item for item in plan.components}


def _multi_station_findings(plan: FixtureBuildPlan) -> tuple[FixtureBuildFinding, ...]:
    """Validate the extra M32 station evidence without weakening M30 gates."""
    layout = plan.multi_station_layout
    if layout is None:
        return ()
    findings: list[FixtureBuildFinding] = []
    req = layout.requirements
    for component in plan.components:
        if not _is_m32_plate_component(component):
            continue
        plate_contract = _plate_geometry_contract(component.bounds, component.thickness_mm)
        if plate_contract is None:
            findings.append(_finding(
                "FXD-MFG-001", "error",
                "M32 plate thickness must match exactly one authored geometry axis",
                components=(component.identity,),
                evidence=(
                    f"recorded_thickness_mm={component.thickness_mm}",
                    f"recorded_stock_mm={component.stock_mm}",
                ),
                disposition="authoring_blocker",
            ))
            continue
        _, thickness_axis, profile_plane = plate_contract
        expected_evidence = {
            f"plate_thickness_axis={thickness_axis}",
            f"plate_profile_plane={profile_plane}",
            f"plate_thickness_mm={component.thickness_mm:.6f}",
        }
        if component.stock_mm != _stock(component.bounds) or not expected_evidence.issubset(component.evidence):
            findings.append(_finding(
                "FXD-MFG-001", "error",
                "M32 plate thickness, stock, and profile-plane evidence do not reconcile",
                components=(component.identity,),
                evidence=tuple(sorted(expected_evidence)) + (
                    f"recorded_stock_mm={component.stock_mm}",
                    f"authored_bounds_stock_mm={_stock(component.bounds)}",
                ),
                disposition="authoring_blocker",
            ))
    if req.fixture_family != FixtureFamily.LINEAR_MULTI_STATION_WELD:
        findings.append(_finding("FXD-M32-STA", "error", "unsupported multi-station fixture family", disposition="review_blocker"))
    if layout.required_fixture_length_mm > req.maximum_fixture_length_mm + 1e-7:
        findings.append(_finding("FXD-M32-STA", "error", "station layout exceeds the requested maximum fixture length", disposition="review_blocker"))
    if len(layout.stations) != req.requested_station_count:
        findings.append(_finding("FXD-M32-STA", "error", "station layout does not contain the accepted station count", disposition="review_blocker"))
    transforms_are_inverse = False
    if req.source_to_manufacturing and req.manufacturing_to_source:
        identity = _identity_matrix()
        transforms_are_inverse = (
            _matrices_close(
                _matrix_product(req.source_to_manufacturing, req.manufacturing_to_source), identity,
            )
            and _matrices_close(
                _matrix_product(req.manufacturing_to_source, req.source_to_manufacturing), identity,
            )
        )
    if not transforms_are_inverse:
        findings.append(_finding(
            "FXD-M32-STA", "error",
            "accepted manufacturing transforms are missing or are not mutual inverses",
            disposition="authoring_blocker",
        ))
    for left, right in zip(layout.stations, layout.stations[1:]):
        if left.product_bounds.intersects(right.product_bounds):
            findings.append(_finding("FXD-M32-STA", "error", "product review instances overlap", components=(left.identity, right.identity), disposition="review_blocker"))
        left_axis = getattr(left.translation_mm, layout.primary_axis)
        right_axis = getattr(right.translation_mm, layout.primary_axis)
        if abs((right_axis - left_axis) - layout.station_pitch_mm) > 1e-7:
            findings.append(_finding("FXD-M32-STA", "error", "station transforms are not stable equal-pitch placements", components=(left.identity, right.identity), disposition="review_blocker"))
    base = next((item for item in plan.components if item.role == BuildComponentRole.BASEPLATE), None)
    rail = next((item for item in plan.components if item.role == BuildComponentRole.DATUM_RAIL), None)
    if base is None or rail is None:
        findings.append(_finding("FXD-M32-CON", "error", "multi-station fixture requires one connected backbone and governed datum structure", disposition="authoring_blocker"))
    elif _axis_span(base.bounds, layout.primary_axis) + 1e-7 < layout.required_fixture_length_mm:
        findings.append(_finding("FXD-M32-CON", "error", "baseplate does not span the deterministic station layout", disposition="review_blocker"))
    braces = [item for item in plan.components if item.role == BuildComponentRole.END_BRACE]
    if len(braces) < 2:
        findings.append(_finding("FXD-M32-CON", "error", "upright datum structure requires end braces", disposition="review_blocker"))
    if rail is not None:
        for brace in braces:
            if _positive_bounds_overlap(rail.bounds, brace.bounds):
                findings.append(_finding(
                    "FXD-M32-CON", "error",
                    "end brace occupies the datum rail volume instead of meeting its boundary",
                    components=(brace.identity, rail.identity), disposition="authoring_blocker",
                ))
            elif not _bounds_share_face(rail.bounds, brace.bounds):
                findings.append(_finding(
                    "FXD-M32-CON", "error",
                    "end brace does not share a weldable face boundary with the datum rail",
                    components=(brace.identity, rail.identity), disposition="authoring_blocker",
                ))
    component_ids = {item.identity for item in plan.components}
    expected_weld_identities = tuple(item.identity for item in plan.requirements.confirmed_welds)
    for station in layout.stations:
        prefix = station.identity + "-"
        station_components = tuple(item for item in plan.components if item.identity.startswith(prefix))
        role_counts = {role: sum(item.role == role for item in station_components) for role in (
            BuildComponentRole.SUPPORT_PAD, BuildComponentRole.LOCATOR_PLATE,
            BuildComponentRole.HARD_STOP, BuildComponentRole.CLAMP_BRACKET,
            BuildComponentRole.TOGGLE_CLAMP, BuildComponentRole.CLAMP_OPEN_ENVELOPE,
        )}
        if any(role_counts[role] < 1 for role in role_counts):
            findings.append(_finding("FXD-M32-STA", "error", "station is missing required support, locating, stop, clamp-mount, or clamp geometry", components=(station.identity,), disposition="review_blocker"))
        if role_counts[BuildComponentRole.SUPPORT_PAD] > 3:
            findings.append(_finding("FXD-DAT-001", "error", "station uses more than three fixed primary supports", components=(station.identity,), disposition="review_blocker"))
        expected_access_digest = _station_access_evidence_digest(
            station, plan.components, layout.stations, plan.requirements, req,
        )
        if station.access_evidence_digest != expected_access_digest:
            findings.append(_finding(
                "FXD-M32-ACC", "error",
                "station access evidence is missing or stale for the current fixture geometry and station transforms",
                components=(station.identity,), evidence=station.access_evidence,
                disposition="review_blocker",
            ))
        access_checks = (
            (station.clamp_tip_reaches_surface, "FXD-M32-CLP", "clamp-tip reach"),
            (station.open_clamp_envelope_clear, "FXD-M32-CLP", "open-clamp loading and release envelope"),
            (station.hand_access_clear, "FXD-M32-ACC", "operator hand clearance"),
            (station.unload_path_clear, "FXD-M32-ACC", "unloading path"),
        )
        for result, rule, label in access_checks:
            if result is not True:
                state = "not evaluated" if result is None else "blocked"
                findings.append(_finding(rule, "error", f"station {label} is {state}",
                                         components=(station.identity,),
                                         evidence=station.access_evidence,
                                         disposition="review_blocker"))
        result_identities = tuple(item.joint_identity for item in station.weld_access_results)
        result_identity_set = set(result_identities)
        expected_identity_set = set(expected_weld_identities)
        exact_weld_result_set = (
            len(result_identities) == len(expected_weld_identities)
            and len(result_identity_set) == len(result_identities)
            and result_identity_set == expected_identity_set
        )
        if expected_weld_identities and not exact_weld_result_set:
            findings.append(_finding(
                "FXD-M32-ACC", "error",
                "station weld/torch access results do not cover every confirmed joint exactly once",
                components=(station.identity,), evidence=station.access_evidence,
                disposition="review_blocker",
            ))
        elif not expected_weld_identities and result_identities:
            findings.append(_finding(
                "FXD-M32-ACC", "error",
                "station contains weld/torch access results without confirmed joint evidence",
                components=(station.identity,), evidence=station.access_evidence,
                disposition="review_blocker",
            ))
        if exact_weld_result_set and expected_weld_identities:
            aggregate = (
                False if any(item.clear is False for item in station.weld_access_results)
                else True if all(item.clear is True for item in station.weld_access_results)
                else None
            )
            if station.weld_access_clear is not aggregate:
                findings.append(_finding(
                    "FXD-M32-ACC", "error",
                    "station weld/torch aggregate disagrees with its per-joint results",
                    components=(station.identity,), evidence=station.access_evidence,
                    disposition="review_blocker",
                ))
        if station.weld_access_results:
            for result in station.weld_access_results:
                if result.clear is False:
                    findings.append(_finding(
                        "FXD-M32-ACC", "error",
                        f"station weld/torch access is blocked for confirmed joint {result.joint_identity}",
                        components=(station.identity,) + result.blocking_component_identities,
                        evidence=result.evidence,
                        disposition="review_blocker",
                    ))
                elif result.clear is None:
                    findings.append(_finding(
                        "FXD-M32-ACC", "error",
                        f"station weld/torch access is not evaluated against current product geometry for confirmed joint {result.joint_identity}",
                        components=(station.identity,), evidence=result.evidence,
                        disposition="review_blocker",
                    ))
        elif station.weld_access_clear is False:
            findings.append(_finding("FXD-M32-ACC", "error", "station weld/torch access envelope is blocked",
                                     components=(station.identity,), evidence=station.access_evidence,
                                     disposition="review_blocker"))
        elif station.weld_access_clear is None and plan.requirements.confirmed_weld_intent:
            findings.append(_finding("FXD-M32-ACC", "error", "station weld/torch access is not evaluated",
                                     components=(station.identity,), evidence=station.access_evidence,
                                     disposition="review_blocker"))
        if station.trapped_part is not False:
            state = "not evaluated" if station.trapped_part is None else "detected"
            findings.append(_finding("FXD-M32-ACC", "error", f"station trapped-part risk is {state}",
                                     components=(station.identity,), evidence=station.access_evidence,
                                     disposition="review_blocker"))
        if station.product_source_sha256 != plan.requirements.source_sha256:
            findings.append(_finding("FXD-M32-STA", "error", "product review instance does not reference immutable plan source", components=(station.identity,), disposition="authoring_blocker"))
        expected_transform = _matrix_product(
            _translation_matrix(station.translation_mm), req.source_to_manufacturing,
        ) if req.source_to_manufacturing else ()
        if not _matrices_close(station.source_to_station_manufacturing, expected_transform):
            findings.append(_finding(
                "FXD-M32-STA", "error",
                "product review instance transform does not match the accepted manufacturing orientation and station placement",
                components=(station.identity,), disposition="authoring_blocker",
            ))
        if not station.source_component_identities:
            findings.append(_finding("FXD-M32-STA", "error", "product review instance has no immutable source-component references", components=(station.identity,), disposition="authoring_blocker"))
    if any(item.role == BuildComponentRole.TOGGLE_CLAMP and "generic_vendor_neutral=true" not in item.evidence
           for item in plan.components):
        findings.append(_finding("FXD-M32-CLP", "error", "toggle-clamp geometry must state its vendor-neutral review boundary", disposition="review_blocker"))
    if any(item.parent_component_identity and item.parent_component_identity not in component_ids
           for item in plan.components):
        findings.append(_finding("FXD-M32-CON", "error", "multi-station fixture contains an unknown structural parent", disposition="authoring_blocker"))
    station_plates = [item for item in plan.components if item.role == BuildComponentRole.STATION_PLATE]
    if len(station_plates) != len(layout.stations):
        findings.append(_finding("FXD-M32-CON", "error", "each station requires one local station plate",
                                 components=tuple(item.identity for item in station_plates),
                                 disposition="review_blocker"))
    backbone = next((item for item in plan.components
                     if item.identity == "m32-backbone"), None)
    if backbone is not None:
        for station_plate in station_plates:
            if _positive_bounds_overlap(backbone.bounds, station_plate.bounds):
                findings.append(_finding(
                    "FXD-M32-CON", "error",
                    "local station plate interpenetrates the separately authored backbone solid",
                    components=(backbone.identity, station_plate.identity),
                    evidence=("A face contact or an explicit tab/cutout is required; volumetric overlap is not a buildable joint.",),
                    disposition="authoring_blocker",
                ))
    end_stations = (layout.stations[0], layout.stations[-1]) if layout.stations else ()
    for station in end_stations:
        for brace in braces:
            if station.product_bounds.intersects(brace.bounds):
                findings.append(_finding("FXD-M32-CON", "error", "end brace interferes with an end-station product envelope",
                                         components=(station.identity, brace.identity), disposition="review_blocker"))
    return tuple(findings)


def validate_fixture_build_plan(product: ProductModel, plan: FixtureBuildPlan) -> FixtureBuildValidation:
    """Evaluate M30 construction evidence without inventing shop-specific policy."""
    findings: list[FixtureBuildFinding] = []
    req = plan.requirements
    if product.source_sha256 != req.source_sha256:
        findings.append(_finding("FXD-MFG-001", "error", "fixture build source identity does not match immutable product source", disposition="authoring_blocker"))
    for weld in req.confirmed_welds:
        if any(not _reference_valid(product, reference) for reference in weld.references):
            findings.append(_finding(
                "FXD-WLD-001", "error",
                f"confirmed weld {weld.identity} contains an invalid immutable source reference",
                evidence=(f"joint={weld.identity}",), disposition="authoring_blocker",
            ))
        if (plan.multi_station_layout is not None
                and weld.manufacturing_orientation_identity
                != plan.multi_station_layout.requirements.manufacturing_orientation_identity):
            findings.append(_finding(
                "FXD-WLD-001", "error",
                f"confirmed weld {weld.identity} is stale for the active manufacturing orientation",
                evidence=(f"joint={weld.identity}",), disposition="review_blocker",
            ))
    if req.production_quantity is None:
        findings.append(_finding("FXD-COST-001", "warning", "production quantity is missing; lifecycle comparison is provisional"))
    if not req.weld_process:
        findings.append(_finding("FXD-WLD-001", "warning", "weld process is missing; access and distortion intent remain provisional"))
    if (plan.multi_station_layout is not None and req.fixture_purpose == FixturePurpose.FULL_WELD
            and not req.confirmed_weld_intent):
        findings.append(_finding(
            "FXD-WLD-001", "error",
            "No confirmed weld intent is recorded. Geometry can show only unconfirmed candidate interfaces; weld location, side, length, process, and sequence require engineer confirmation before weld access is validated.",
            evidence=("candidate_weld_interfaces=unconfirmed",),
            assumptions=("No weld symbols, sizes, locations, or sequence are invented from STEP geometry.",),
            disposition="review_blocker",
        ))
    elif (plan.multi_station_layout is not None and req.fixture_purpose == FixturePurpose.FULL_WELD
          and not _confirmed_weld_evidence_complete(req)):
        findings.append(_finding(
            "FXD-WLD-001", "error",
            "Confirmed weld intent is incomplete. Every joint requires its own source reference, side, length, process, sequence, engineer-accepted approach direction, and torch body envelope before weld access can be evaluated.",
            evidence=("confirmed_weld_contract=incomplete",
                      f"confirmed_joint_count={req.confirmed_weld_joint_count}",
                      f"complete_joint_count={len(req.confirmed_welds)}"),
            disposition="review_blocker",
        ))
    if req.lifecycle in {FixtureLifecycle.DISPOSABLE_RECUT, FixtureLifecycle.REUSABLE_TOOLING_ON_DISPOSABLE} and not req.job_revision:
        findings.append(_finding("FXD-COST-001", "error", "disposable or recut fixture is not tied to an explicit job revision"))
    if req.adjustment_state in {AdjustmentState.PROVISIONAL, AdjustmentState.PROVE_OUT, AdjustmentState.REVALIDATION_REQUIRED}:
        findings.append(_finding("FXD-EXP-001", "warning", "fixture adjustment state is not a locked or doweled production position", evidence=(f"adjustment_state={req.adjustment_state.value}",)))
    if req.fixture_purpose == FixturePurpose.TACK_LOCATION:
        if req.tack_access_available is not True:
            findings.append(_finding("FXD-TACK-001", "error", "tack/location fixture requires explicit tack-access evidence"))
        if not plan.tack_sequence or not plan.release_sequence or not plan.unload_sequence:
            findings.append(_finding("FXD-TACK-001", "error", "tack/location fixture requires tack, release, and unload sequences"))
        if req.full_weld_access_available is None:
            findings.append(_finding("FXD-ACC-001", "info", "full-weld access was not evaluated because this is a tack/location fixture", status="not_evaluated"))
    elif req.full_weld_access_available is not True:
        findings.append(_finding("FXD-ACC-001", "warning", "full-weld access is not evidenced for this fixture purpose; contact geometry supplies only unconfirmed candidate interfaces"))
    components = _component_by_id(plan)
    roots = tuple(item for item in plan.components if item.parent_component_identity is None)
    if len(roots) != 1:
        findings.append(_finding("FXD-MFG-001", "error", "fixture build must have exactly one connected root component", components=tuple(item.identity for item in roots), disposition="authoring_blocker"))
    for item in plan.components:
        if item.geometry_authority not in {GeometryAuthority.AUTHORED_MANUFACTURING, GeometryAuthority.PURCHASED_COMPONENT}:
            findings.append(_finding("FXD-MFG-001", "error", "provisional or source geometry cannot be labeled as manufacturing fixture geometry", components=(item.identity,), disposition="authoring_blocker"))
        for reference in item.source_references:
            if not _reference_valid(product, reference):
                findings.append(_finding("FXD-MFG-001", "error", "fixture component has an invalid source geometry reference", components=(item.identity,), references=(reference,), disposition="authoring_blocker"))
        if item.parent_component_identity:
            parent = components.get(item.parent_component_identity)
            if parent is None:
                findings.append(_finding("FXD-MFG-001", "error", "fixture component has an unknown parent component", components=(item.identity,), disposition="authoring_blocker"))
            elif parent.bounds.clearance_to(item.bounds) > 0.1:
                findings.append(_finding("FXD-MFG-001", "error", "fixture component is physically disconnected from its parent", components=(parent.identity, item.identity), disposition="authoring_blocker"))
        if item.role == BuildComponentRole.CLAMP_PLATE and not item.reaction_support_identity:
            findings.append(_finding("FXD-SUP-001", "error", "clamp plate has no explicit reaction support", components=(item.identity,)))
        if item.reaction_support_identity and item.reaction_support_identity not in components:
            findings.append(_finding("FXD-SUP-001", "error", "clamp reaction references an unknown support", components=(item.identity,)))
        if item.contact_condition in {"weld_seam", "tube_radius"}:
            findings.append(_finding("FXD-LOC-001", "error", "locator contact is on an unsuitable weld seam or tube radius", components=(item.identity,), evidence=(f"contact_condition={item.contact_condition}",)))
        for hole in item.holes:
            if hole.precision_required and hole.process in {HoleProcess.LASER_CLEARANCE, HoleProcess.LASER_PILOT} and hole.final_operation is None:
                findings.append(_finding("FXD-HOL-001", "error", "laser-cut hole is incorrectly used as a precision bore", components=(item.identity,), evidence=(f"hole={hole.identity}",)))
            if hole.process == HoleProcess.TAPPED and (not hole.thread_pitch or hole.thread_engagement_mm is None):
                findings.append(_finding("FXD-THR-001", "warning", "tapped hole lacks complete thread engagement evidence", components=(item.identity,), evidence=(f"hole={hole.identity}",)))
        if item.role in {BuildComponentRole.SUPPORT_PAD, BuildComponentRole.HARD_STOP,
                         BuildComponentRole.ROUND_PIN, BuildComponentRole.DIAMOND_PIN,
                         BuildComponentRole.PIN_BUSHING, BuildComponentRole.WEAR_PLATE,
                         BuildComponentRole.CLAMP_PLATE}:
            if not item.replaceable:
                findings.append(_finding("FXD-MNT-001", "warning", "service or contact item is not marked replaceable", components=(item.identity,)))
            if item.maintenance_access is not True:
                findings.append(_finding("FXD-MNT-001", "warning", "service or contact item lacks explicit maintenance-access evidence", components=(item.identity,)))
    fixed_pads = tuple(item.identity for item in plan.components if item.role == BuildComponentRole.SUPPORT_PAD and item.fixed and item.locating_constraint)
    if plan.multi_station_layout is None and len(fixed_pads) > 3:
        findings.append(_finding("FXD-DAT-001", "error", "four or more fixed primary support pads can overconstrain the datum", components=fixed_pads))
    round_pins = tuple(item.identity for item in plan.components if item.role == BuildComponentRole.ROUND_PIN and item.fixed)
    if len(round_pins) >= 2:
        findings.append(_finding("FXD-PIN-001", "error", "two full round pins can bind under tolerance variation; use a relieved or diamond pin where supported", components=round_pins))
    fixed_stops = tuple(item.identity for item in plan.components if item.role == BuildComponentRole.HARD_STOP and item.fixed)
    if plan.multi_station_layout is None and len(fixed_stops) > 1:
        findings.append(_finding("FXD-LOC-001", "error", "opposing fixed hard stops can overconstrain loading", components=fixed_stops))
    if req.unload_clearance_evaluated is not True and any(item.role == BuildComponentRole.ROUND_PIN and item.fixed for item in plan.components):
        findings.append(_finding("FXD-DST-001", "error", "fixed locating pin has no welded-shape unloading clearance evidence", components=round_pins))
    for joint in plan.tab_slots:
        if joint.tab_component_identity not in components or joint.slot_component_identity not in components:
            findings.append(_finding("FXD-TAB-001", "error", "tab-slot joint references an unknown component", components=(joint.tab_component_identity, joint.slot_component_identity)))
        if joint.slot_width_mm < joint.tab_thickness_mm + joint.clearance_mm:
            findings.append(_finding("FXD-TAB-001", "error", "slot width is smaller than tab thickness plus assembly clearance", evidence=(f"joint={joint.identity}",)))
        if joint.bottoms_out:
            findings.append(_finding("FXD-TAB-001", "error", "tab bottoms out before its intended seating condition", evidence=(f"joint={joint.identity}",)))
        if not joint.weld_relief:
            findings.append(_finding("FXD-TAB-001", "warning", "tab-slot joint has no explicit weld-relief evidence", evidence=(f"joint={joint.identity}",)))
    for poka_yoke in plan.poka_yokes:
        if poka_yoke.component_identity not in components:
            findings.append(_finding("FXD-PKY-001", "error", "poka-yoke references an unknown fixture component", components=(poka_yoke.component_identity,)))
            continue
        if not poka_yoke.prevents_reversal:
            findings.append(_finding("FXD-PKY-001", "error", "poka-yoke does not prevent the documented reversal risk", components=(poka_yoke.component_identity,)))
        if not poka_yoke.avoids_pinch_point:
            findings.append(_finding("FXD-PKY-001", "error", "poka-yoke introduces an unresolved operator pinch-point risk", components=(poka_yoke.component_identity,)))
        if not poka_yoke.avoids_hidden_seating:
            findings.append(_finding("FXD-PKY-001", "error", "poka-yoke can create hidden seating that cannot be deterministically reviewed", components=(poka_yoke.component_identity,)))
        if not poka_yoke.supports_unloading:
            findings.append(_finding("FXD-PKY-001", "error", "poka-yoke can trap the assembly during unloading", components=(poka_yoke.component_identity,)))
    if not plan.poka_yokes:
        findings.append(_finding("FXD-PKY-001", "warning", "fixture plan has no explicit poka-yoke or orientation evidence"))
    for cleco in plan.clecos:
        target = components.get(cleco.component_identity)
        if target is None:
            findings.append(_finding("FXD-CLE-001", "error", "Cleco references an unknown fixture component", components=(cleco.component_identity,)))
            continue
        if cleco.hole_diameter_mm < cleco.diameter_mm:
            findings.append(_finding("FXD-CLE-001", "error", "Cleco hole diameter is smaller than the specified Cleco", components=(target.identity,)))
        if not cleco.minimum_grip_mm <= cleco.material_stack_mm <= cleco.maximum_grip_mm:
            findings.append(_finding("FXD-CLE-001", "error", "Cleco material stack is outside the stated grip range", components=(target.identity,)))
        if not (cleco.installation_access and cleco.removal_access and cleco.plier_access):
            findings.append(_finding("FXD-CLE-001", "error", "Cleco installation, removal, or plier access is blocked", components=(target.identity,)))
        if cleco.strategy == ClecoStrategy.PRODUCT_HOLES:
            if not cleco.product_hole_approved:
                findings.append(_finding("FXD-CLE-001", "error", "product Cleco holes require explicit customer/process approval", components=(target.identity,)))
            if not req.product_hole_justification:
                findings.append(_finding("FXD-CLE-001", "warning", "product Cleco holes have no explicit cost, process, or customer justification", components=(target.identity,)))
            if cleco.post_use_process is None:
                findings.append(_finding("FXD-CLE-001", "warning", "product Cleco-hole finishing process is not documented", components=(target.identity,)))
        if cleco.strategy == ClecoStrategy.SEPARATE_FIXTURE_HOLES:
            findings.append(_finding("FXD-CLE-001", "info", "separate fixture Cleco holes preserve product CAD and are preferred unless product holes are justified", components=(target.identity,), status="valid"))
        if cleco.retained_during_tack and not cleco.removed_before_welding:
            findings.append(_finding("FXD-CLE-001", "warning", "Cleco retained during tack-up lacks explicit removal-before-weld evidence", components=(target.identity,)))
    if req.lifecycle in {FixtureLifecycle.DISPOSABLE_RECUT, FixtureLifecycle.REUSABLE_TOOLING_ON_DISPOSABLE}:
        mixed = tuple(item.identity for item in plan.components if item.nest_classification == NestClassification.PRODUCT)
        if mixed:
            findings.append(_finding("FXD-COST-001", "error", "disposable fixture parts are mixed with sellable product parts in nesting classification", components=mixed))
    findings.extend(_multi_station_findings(plan))
    status = "invalid" if any(item.severity == "error" for item in findings) else ("provisional" if any(item.severity == "warning" for item in findings) else "valid")
    encoded = json.dumps([item.to_dict() for item in sorted(findings, key=lambda item: item.identity)], sort_keys=True, separators=(",", ":"))
    return FixtureBuildValidation(plan.identity, req.source_sha256, status, tuple(sorted(findings, key=lambda item: item.identity)), hashlib.sha256(encoded.encode("utf-8")).hexdigest())


def compare_fixture_build_plans(plans: tuple[FixtureBuildPlan, ...], product: ProductModel) -> tuple[FixtureBuildComparison, ...]:
    """Compare valid plans deterministically; invalid plans cannot be preferred."""
    rows: list[FixtureBuildComparison] = []
    method_weight = {
        ConstructionMethod.TACK_LOCATION: (0.90, 0.75, 0.45, 0.95, 0.45),
        ConstructionMethod.LASER_CUT_FABRICATED: (0.75, 0.70, 0.65, 0.80, 0.65),
        ConstructionMethod.WELDED_TUBE_FRAME: (0.55, 0.85, 0.70, 0.55, 0.70),
        ConstructionMethod.HYBRID: (0.45, 0.80, 0.85, 0.50, 0.80),
        ConstructionMethod.CNC_MACHINED: (0.20, 0.65, 0.95, 0.35, 0.85),
        ConstructionMethod.SHOP_STANDARD: (0.60, 0.70, 0.60, 0.70, 0.60),
        ConstructionMethod.AUTO: (0.50, 0.50, 0.50, 0.50, 0.50),
    }
    for plan in plans:
        validation = validate_fixture_build_plan(product, plan)
        cost, access, precision, build_time, maintenance = method_weight[plan.requirements.construction_method]
        score = access + precision + build_time + maintenance - cost
        if plan.requirements.cleco_strategy == ClecoStrategy.SEPARATE_FIXTURE_HOLES:
            score += 0.05
        elif (plan.requirements.cleco_strategy == ClecoStrategy.PRODUCT_HOLES
              and not plan.requirements.product_hole_justification):
            score -= 0.05
        if validation.blocked:
            score = -1.0
        rows.append(FixtureBuildComparison(plan.identity, plan.requirements.construction_method,
                                           plan.requirements.lifecycle, validation.status, round(score, 6),
                                           cost, access, precision, build_time, maintenance,
                                           ("Cost and lifecycle scores are ranked engineering preferences, not quotes.",
                                            "Deterministic invalid findings override comparison scoring.")))
    return tuple(sorted(rows, key=lambda item: (item.status == "invalid", -item.score, item.plan_identity)))


def _shape_for(component: FixtureBuildComponent, kernel: RealKernel) -> object:
    low, high = component.bounds.minimum, component.bounds.maximum
    if component.role in {BuildComponentRole.ROUND_PIN, BuildComponentRole.PIN_BUSHING}:
        radius = min(high.x - low.x, high.y - low.y) / 2.0
        shape = kernel.make_cylinder((low.x + radius, low.y + radius, low.z), radius, high.z - low.z)
    elif component.role == BuildComponentRole.DIAMOND_PIN:
        radius = min(high.x - low.x, high.y - low.y) / 2.0
        center_x = low.x + radius
        center_y = low.y + radius
        shape = kernel.make_cylinder((center_x, center_y, low.z), radius, high.z - low.z)
        # Two opposed flats provide X clearance while the remaining Y contacts locate the part.
        relief_half_width = radius * 0.60
        relief_height = high.z - low.z + 2.0
        for minimum_x, maximum_x in (
                (low.x - 1.0, center_x - relief_half_width),
                (center_x + relief_half_width, high.x + 1.0)):
            shape = kernel.cut(shape, kernel.make_box(
                (minimum_x, low.y - 1.0, low.z - 1.0),
                (maximum_x, high.y + 1.0, low.z - 1.0 + relief_height),
            ))
    elif component.role == BuildComponentRole.TOGGLE_CLAMP:
        # A generic, intentionally vendor-neutral review representation: a
        # mounting body, upright pivot housing, and clamp arm/tip.  It is real
        # OCP geometry but never claims to be released supplier CAD.
        body = kernel.make_box((low.x, high.y - 12.0, low.z),
                               (high.x, high.y, min(high.z, low.z + 14.0)))
        tower = kernel.make_box(((low.x + high.x) / 2.0 - 7.0, high.y - 12.0, low.z),
                                ((low.x + high.x) / 2.0 + 7.0, high.y, high.z))
        arm = kernel.make_box(((low.x + high.x) / 2.0 - 4.0, low.y, high.z - 10.0),
                              ((low.x + high.x) / 2.0 + 4.0, high.y, high.z))
        shape = kernel.boolean("fuse", kernel.boolean("fuse", body, tower), arm)
    else:
        shape = kernel.make_box((low.x, low.y, low.z), (high.x, high.y, high.z))
    if component.role in {BuildComponentRole.TUBE_FRAME, BuildComponentRole.CROSSMEMBER}:
        wall = component.thickness_mm
        dimensions = (high.x - low.x, high.y - low.y, high.z - low.z)
        if wall is None or wall <= 0 or sum(value <= 2.0 * wall for value in dimensions) > 1:
            raise KernelOperationError(f"fixture tube member {component.identity} has no viable wall-thickness evidence")
        longitudinal_axis = max(range(3), key=lambda index: dimensions[index])
        inner_low = [low.x, low.y, low.z]
        inner_high = [high.x, high.y, high.z]
        inner_low[longitudinal_axis] -= 1.0
        inner_high[longitudinal_axis] += 1.0
        for index in range(3):
            if index != longitudinal_axis:
                inner_low[index] += wall
                inner_high[index] -= wall
        shape = kernel.cut(shape, kernel.make_box(tuple(inner_low), tuple(inner_high)))
    for hole in component.holes:
        shape = kernel.cut(shape, kernel.make_hole((hole.center_mm.x, hole.center_mm.y, low.z - 1.0),
                                                   hole.diameter_mm / 2.0, high.z - low.z + 2.0))
    for slot in component.slots:
        shape = kernel.cut(shape, kernel.make_slot(
            tuple(slot.minimum_mm.__dict__.values()),
            tuple(slot.maximum_mm.__dict__.values()),
        ))
    topology = kernel.topology_counts(shape)
    if topology.solids < 1:
        raise KernelOperationError(f"fixture build component {component.identity} did not author a real solid")
    return shape


def _dxf_for(component: FixtureBuildComponent) -> bytes | None:
    if component.role in {BuildComponentRole.ROUND_PIN, BuildComponentRole.DIAMOND_PIN, BuildComponentRole.PIN_BUSHING,
                          BuildComponentRole.TUBE_FRAME, BuildComponentRole.CROSSMEMBER}:
        return None
    low, high = component.bounds.minimum, component.bounds.maximum
    coordinates = lambda point: (point.x, point.y, point.z)
    plane_axes = (0, 1)
    if component.thickness_mm is not None:
        plate_contract = _plate_geometry_contract(component.bounds, component.thickness_mm)
        # A DXF is release evidence, so an ambiguous/non-reconciling plate
        # envelope is suppressed instead of guessed. Vertical holes are also
        # suppressed until the OCP authoring path supports their true axis.
        if plate_contract is None or (plate_contract[0] != 2 and component.holes):
            return None
        plane_axes = tuple(index for index in range(3) if index != plate_contract[0])
    plane_name = "XYZ"[plane_axes[0]] + "XYZ"[plane_axes[1]]
    low_values, high_values = coordinates(low), coordinates(high)
    profile_low = (low_values[plane_axes[0]], low_values[plane_axes[1]])
    profile_high = (high_values[plane_axes[0]], high_values[plane_axes[1]])
    value = lambda item: format(item, ".9g")
    lines = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
             "999", f"FXD_PROFILE_PLANE={plane_name}", "0", "SECTION", "2", "ENTITIES",
             "0", "LWPOLYLINE", "8", f"PROFILE_{plane_name}", "90", "5", "70", "1"]
    for x, y in ((profile_low[0], profile_low[1]), (profile_high[0], profile_low[1]),
                 (profile_high[0], profile_high[1]), (profile_low[0], profile_high[1]),
                 (profile_low[0], profile_low[1])):
        lines.extend(("10", value(x), "20", value(y)))
    for hole in component.holes:
        center = coordinates(hole.center_mm)
        lines.extend(("0", "CIRCLE", "8", hole.process.value,
                      "10", value(center[plane_axes[0]]),
                      "20", value(center[plane_axes[1]]), "40", value(hole.diameter_mm / 2.0)))
    for slot in component.slots:
        slot_low, slot_high = coordinates(slot.minimum_mm), coordinates(slot.maximum_mm)
        lines.extend(("0", "LWPOLYLINE", "8", "ADJUSTMENT_SLOT", "90", "5", "70", "1"))
        for x, y in ((slot_low[plane_axes[0]], slot_low[plane_axes[1]]),
                     (slot_high[plane_axes[0]], slot_low[plane_axes[1]]),
                     (slot_high[plane_axes[0]], slot_high[plane_axes[1]]),
                     (slot_low[plane_axes[0]], slot_high[plane_axes[1]]),
                     (slot_low[plane_axes[0]], slot_low[plane_axes[1]])):
            lines.extend(("10", value(x), "20", value(y)))
    lines.extend(("0", "ENDSEC", "0", "EOF"))
    return ("\n".join(lines) + "\n").encode("ascii")


def author_fixture_build(plan: FixtureBuildPlan, product: ProductModel, kernel: RealKernel) -> AuthoredFixtureAssembly:
    """Author real OCP B-Rep components without weakening deterministic release gates.

    Engineering-review findings can be inspected as real, explicitly labelled
    provisional solids.  Source identity, graph connectivity, and other
    computational prerequisites remain hard authoring blockers.
    """
    validation = validate_fixture_build_plan(product, plan)
    if validation.authoring_blocked:
        reasons = tuple(item.message for item in validation.findings
                        if item.disposition == "authoring_blocker")
        summary = "; ".join(reasons[:3]) or "deterministic authoring prerequisites are missing"
        raise FixtureBuildError(f"fixture build has {len(reasons)} authoring-blocking finding(s): {summary}")
    if not kernel.capabilities.is_complete:
        raise FixtureBuildError("complete reviewed OCP capabilities are required for manufacturing geometry")
    authored: list[AuthoredFixtureComponent] = []
    for component in sorted(plan.components, key=lambda item: item.identity):
        if component.geometry_authority != GeometryAuthority.AUTHORED_MANUFACTURING:
            if component.geometry_authority == GeometryAuthority.PURCHASED_COMPONENT:
                continue
            raise FixtureBuildError("provisional geometry cannot be authored or exported as manufacturing geometry")
        shape = _shape_for(component, kernel)
        authored.append(AuthoredFixtureComponent(component, shape, kernel.topology_counts(shape), kernel.export_step(shape), _dxf_for(component)))
    if not authored:
        raise FixtureBuildError("fixture build plan contains no authored manufacturing components")
    provisional = validation.status != "valid"
    labels = (("PROVISIONAL", "NOT APPROVED", "INVALID BUILD PLAN") if provisional else ())
    return AuthoredFixtureAssembly(plan.identity, plan.requirements.source_sha256, "mm", tuple(authored),
                                   kernel.compound(tuple(item.shape for item in authored)), validation,
                                   plan.evidence_digest,
                                   provisional, labels)


def build_fixture_build_package(assembly: AuthoredFixtureAssembly, plan: FixtureBuildPlan, product: ProductModel,
                                 *, project_validation: object | None = None,
                                 accepted_proposal: object | None = None) -> dict[str, bytes | str]:
    """Create deterministic review-only manufacturing outputs behind all available gates."""
    if assembly.plan_identity != plan.identity or assembly.source_sha256 != plan.requirements.source_sha256:
        raise FixtureBuildError("authored fixture geometry does not match the construction plan")
    if assembly.plan_evidence_digest != plan.evidence_digest:
        raise FixtureBuildError("authored fixture geometry is stale for the supplied construction plan")
    if plan.multi_station_layout is not None:
        if accepted_proposal is None:
            raise FixtureBuildError(
                "multi-station fixture release requires a build bound to an accepted fixture proposal"
            )
        expected_binding = bind_fixture_build_plan_to_proposal(plan, accepted_proposal)
        if (plan.fixture_proposal_identity != expected_binding.fixture_proposal_identity
                or plan.fixture_proposal_evidence_digest
                != expected_binding.fixture_proposal_evidence_digest):
            raise FixtureBuildError(
                "multi-station fixture build does not match the accepted proposal evidence"
            )
    current_validation = validate_fixture_build_plan(product, plan)
    if (current_validation.evidence_digest != assembly.validation.evidence_digest
            or current_validation.status != "valid"
            or assembly.validation.status != "valid" or assembly.provisional):
        raise FixtureBuildError("only a valid fixture build validation result can be exported")
    if assembly.blocked or plan.requirements.adjustment_state in {
            AdjustmentState.PROVISIONAL, AdjustmentState.PROVE_OUT, AdjustmentState.REVALIDATION_REQUIRED}:
        raise FixtureBuildError("stale, provisional, or invalid fixture build evidence cannot be exported")
    if project_validation is not None and getattr(project_validation, "blocked", True):
        raise FixtureBuildError("invalid project validation cannot export fixture build geometry")
    files: dict[str, bytes | str] = {}
    for item in assembly.components:
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.component.part_number)
        files[f"step/{stem}.step"] = item.step_bytes
        if item.dxf_bytes is not None:
            files[f"dxf/{stem}.dxf"] = item.dxf_bytes
    release_components = tuple(
        component for component in plan.components
        if not (component.geometry_authority == GeometryAuthority.PURCHASED_COMPONENT
                and "generic_vendor_neutral=true" in component.evidence)
    )
    bom = [{
        "item_number": index, "part_number": component.part_number, "description": component.description,
        "quantity": component.quantity, "material": component.material,
        "thickness_mm": component.thickness_mm,
        "plate_thickness_axis": (
            _plate_geometry_contract(component.bounds, component.thickness_mm)[1]
            if _is_m32_plate_component(component) else None
        ),
        "plate_profile_plane": (
            _plate_geometry_contract(component.bounds, component.thickness_mm)[2]
            if _is_m32_plate_component(component) else None
        ),
        "thickness_or_stock_mm": component.stock_mm, "manufacturing_process": component.manufacturing_process,
        "geometry_authority": component.geometry_authority.value,
        "nest_classification": component.nest_classification.value, "reusable": component.reusable,
        "disposable": component.disposable, "job_revision": plan.requirements.job_revision,
    } for index, component in enumerate(sorted(release_components, key=lambda item: item.part_number), 1)]
    manifest = {
        "format": "fxd-m30-review-manufacturing-package-v1", "plan": plan.to_dict(),
        "source_sha256": assembly.source_sha256, "assembly_evidence_digest": assembly.evidence_digest,
        "manufacturing_components": [{
            "identity": item.component.identity,
            "part_number": item.component.part_number,
            "stock_mm": list(item.component.stock_mm),
            "thickness_mm": item.component.thickness_mm,
            "plate_thickness_axis": (
                _plate_geometry_contract(item.component.bounds, item.component.thickness_mm)[1]
                if _is_m32_plate_component(item.component) else None
            ),
            "plate_profile_plane": (
                _plate_geometry_contract(item.component.bounds, item.component.thickness_mm)[2]
                if _is_m32_plate_component(item.component) else None
            ),
            "step_path": f"step/{re.sub(r'[^A-Za-z0-9_.-]+', '_', item.component.part_number)}.step",
            "dxf_path": (
                f"dxf/{re.sub(r'[^A-Za-z0-9_.-]+', '_', item.component.part_number)}.dxf"
                if item.dxf_bytes is not None else None
            ),
        } for item in assembly.components],
        "validation": {"status": current_validation.status, "evidence_digest": current_validation.evidence_digest,
                       "findings": [item.to_dict() for item in current_validation.findings]},
        "approval_boundary": "Engineering review only. Not production release, certification, structural adequacy, or safety approval.",
    }
    if plan.multi_station_layout is not None:
        manifest["multi_station_layout"] = plan.multi_station_layout.to_dict()
    files["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    files["bom.json"] = json.dumps(bom, indent=2, sort_keys=True) + "\n"
    files["hole-process-table.json"] = json.dumps([
        {"component": component.identity, **hole.to_dict()}
        for component in sorted(release_components, key=lambda item: item.identity)
        for hole in sorted(component.holes, key=lambda item: item.identity)
    ], indent=2, sort_keys=True) + "\n"
    files["slot-and-tab-map.json"] = json.dumps([item.to_dict() for item in plan.tab_slots], indent=2, sort_keys=True) + "\n"
    files["adjustment-slot-map.json"] = json.dumps([
        {"component": component.identity, **slot.to_dict()}
        for component in sorted(release_components, key=lambda item: item.identity)
        for slot in sorted(component.slots, key=lambda item: item.identity)
    ], indent=2, sort_keys=True) + "\n"
    files["poka-yoke-map.json"] = json.dumps([item.to_dict() for item in plan.poka_yokes], indent=2, sort_keys=True) + "\n"
    files["cleco-hole-map.json"] = json.dumps([item.to_dict() for item in plan.clecos], indent=2, sort_keys=True) + "\n"
    files["nest-classification.json"] = json.dumps([
        {"component": item.identity, "classification": item.nest_classification.value,
         "job_revision": plan.requirements.job_revision, "prevent_shipment": item.nest_classification == NestClassification.FIXTURE}
        for item in sorted(release_components, key=lambda item: item.identity)
    ], indent=2, sort_keys=True) + "\n"
    files["assembly-sequence.json"] = json.dumps({"loading": plan.loading_sequence, "tack": plan.tack_sequence,
                                                    "release": plan.release_sequence, "unload": plan.unload_sequence,
                                                    "finish_weld_handoff": plan.finish_weld_handoff}, indent=2, sort_keys=True) + "\n"
    return dict(sorted(files.items()))


def write_fixture_build_package(assembly: AuthoredFixtureAssembly, plan: FixtureBuildPlan, product: ProductModel,
                                destination: str | Path,
                                *, project_validation: object | None = None,
                                accepted_proposal: object | None = None) -> tuple[Path, ...]:
    files = build_fixture_build_package(
        assembly, plan, product, project_validation=project_validation,
        accepted_proposal=accepted_proposal,
    )
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload if isinstance(payload, bytes) else payload.encode("utf-8"))
        written.append(target)
    return tuple(written)
