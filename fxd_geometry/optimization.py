"""Deterministic cost, volume, and manufacturability review contracts.

This module produces engineering estimates from validated Milestone 23
manufacturing metadata and the Milestone 24 drawing evidence.  Rates are
explicit, configurable assumptions; they are not supplier quotations or
production approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Mapping

from .component_geometry import ComponentClassification, ManufacturingAssembly


OPTIMIZATION_VERSION = "fxd-cost-optimization-v1"
ENGINEERING_ESTIMATE_NOTICE = "ENGINEERING ESTIMATE ONLY; NOT A SUPPLIER QUOTATION; NOT APPROVED FOR PRODUCTION"


class OptimizationError(ValueError):
    """Raised when an optimization contract cannot be evaluated safely."""


def _money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _hours(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class CostAssumptions:
    currency: str = "USD"
    prototype_max_quantity: int = 1
    low_volume_max_quantity: int = 25
    medium_volume_max_quantity: int = 250
    expected_fixture_life_cycles: int = 10000
    scrap_factor: float = 0.10
    maintenance_factor: float = 0.05
    replacement_factor: float = 0.03
    overhead_factor: float = 0.0
    contingency_factor: float = 0.0
    notes: tuple[str, ...] = ("All rates and thresholds are configurable engineering assumptions.",)

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise OptimizationError("currency is required")
        if min(self.prototype_max_quantity, self.low_volume_max_quantity,
               self.medium_volume_max_quantity, self.expected_fixture_life_cycles) < 1:
            raise OptimizationError("volume thresholds and fixture life must be positive")
        if not 0 <= self.scrap_factor < 1 or min(self.maintenance_factor,
                                                 self.replacement_factor,
                                                 self.overhead_factor,
                                                 self.contingency_factor) < 0:
            raise OptimizationError("cost factors must be non-negative and scrap must be below one")
        if not (self.prototype_max_quantity <= self.low_volume_max_quantity <= self.medium_volume_max_quantity):
            raise OptimizationError("volume thresholds must be ordered")

    def to_dict(self) -> dict[str, object]:
        return {"currency": self.currency, "prototype_max_quantity": self.prototype_max_quantity,
                "low_volume_max_quantity": self.low_volume_max_quantity,
                "medium_volume_max_quantity": self.medium_volume_max_quantity,
                "expected_fixture_life_cycles": self.expected_fixture_life_cycles,
                "scrap_factor": self.scrap_factor, "maintenance_factor": self.maintenance_factor,
                "replacement_factor": self.replacement_factor, "overhead_factor": self.overhead_factor,
                "contingency_factor": self.contingency_factor, "notes": list(self.notes)}


@dataclass(frozen=True)
class CostRateTable:
    identity: str = "default-rate-table-v1"
    currency: str = "USD"
    material_cost_per_kg: Mapping[str, float] = None  # type: ignore[assignment]
    density_kg_per_m3: Mapping[str, float] = None  # type: ignore[assignment]
    process_cost_per_hour: Mapping[str, float] = None  # type: ignore[assignment]
    purchased_tooling_unit_cost: Mapping[str, float] = None  # type: ignore[assignment]
    engineering_hours: float = 8.0
    programming_hours: float = 2.0
    setup_hours: float = 1.0
    commissioning_hours: float = 2.0
    assembly_hours_per_component: float = 0.25
    inspection_hours_per_component: float = 0.10
    finishing_hours_per_fabricated_component: float = 0.10

    def __post_init__(self) -> None:
        materials = {"mild_steel": 4.0, "tool_steel": 12.0, "aluminum": 6.0} | dict(self.material_cost_per_kg or {})
        density = {"mild_steel": 7850.0, "tool_steel": 7850.0, "aluminum": 2700.0} | dict(self.density_kg_per_m3 or {})
        processes = {"laser_cut": 75.0, "saw_cut": 55.0, "machined": 110.0,
                                                    "weld": 80.0, "formed": 75.0, "assembly": 65.0,
                                                    "inspection": 90.0, "finish": 60.0, "design": 100.0,
                                                    "programming": 100.0, "commissioning": 80.0} | dict(self.process_cost_per_hour or {})
        tooling = dict(self.purchased_tooling_unit_cost or {})
        object.__setattr__(self, "material_cost_per_kg", dict(sorted(materials.items())))
        object.__setattr__(self, "density_kg_per_m3", dict(sorted(density.items())))
        object.__setattr__(self, "process_cost_per_hour", dict(sorted(processes.items())))
        object.__setattr__(self, "purchased_tooling_unit_cost", dict(sorted(tooling.items())))
        if not self.identity.strip() or not self.currency.strip():
            raise OptimizationError("rate-table identity and currency are required")
        if not {"assembly", "inspection", "finish", "design", "programming", "commissioning"} <= set(self.process_cost_per_hour):
            raise OptimizationError("rate table is missing a required process rate")
        rates = (*self.material_cost_per_kg.values(), *self.density_kg_per_m3.values(),
                 *self.process_cost_per_hour.values(), *self.purchased_tooling_unit_cost.values(),
                 self.engineering_hours, self.programming_hours, self.setup_hours,
                 self.commissioning_hours, self.assembly_hours_per_component,
                 self.inspection_hours_per_component, self.finishing_hours_per_fabricated_component)
        if any(value < 0 for value in rates) or any(value == 0 for value in self.density_kg_per_m3.values()):
            raise OptimizationError("rates and durations must be non-negative and densities positive")
        if any(unit != self.currency for unit in (self.currency,)):
            raise OptimizationError("rate-table currency is inconsistent")

    def to_dict(self) -> dict[str, object]:
        return {"identity": self.identity, "currency": self.currency,
                "material_cost_per_kg": dict(self.material_cost_per_kg),
                "density_kg_per_m3": dict(self.density_kg_per_m3),
                "process_cost_per_hour": dict(self.process_cost_per_hour),
                "purchased_tooling_unit_cost": dict(self.purchased_tooling_unit_cost),
                "engineering_hours": self.engineering_hours, "programming_hours": self.programming_hours,
                "setup_hours": self.setup_hours, "commissioning_hours": self.commissioning_hours,
                "assembly_hours_per_component": self.assembly_hours_per_component,
                "inspection_hours_per_component": self.inspection_hours_per_component,
                "finishing_hours_per_fabricated_component": self.finishing_hours_per_fabricated_component}


@dataclass(frozen=True)
class CostEvidence:
    rule_id: str
    formula: str
    source_references: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: str = "provisional"

    def to_dict(self) -> dict[str, object]:
        return {"rule_id": self.rule_id, "formula": self.formula,
                "source_references": list(self.source_references), "assumptions": list(self.assumptions),
                "confidence": self.confidence}


@dataclass(frozen=True)
class CostValidationFinding:
    code: str
    severity: str
    message: str
    evidence: tuple[str, ...] = ()
    affected_components: tuple[str, ...] = ()
    rule_id: str = "cost_validation"

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "severity": self.severity, "message": self.message,
                "evidence": list(self.evidence), "affected_components": list(self.affected_components),
                "rule_id": self.rule_id}


@dataclass(frozen=True)
class MaterialCost:
    component_identity: str
    part_number: str
    revision: str
    material: str
    quantity: int
    volume_mm3: float
    mass_kg: float
    rate_per_kg: float
    scrap_factor: float
    total_cost: float
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class ProcessCost:
    component_identity: str
    process_identity: str
    quantity: int
    setup_hours: float
    run_hours: float
    rate_per_hour: float
    total_cost: float
    formula: str
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class LaborCost:
    category: str
    hours: float
    rate_per_hour: float
    total_cost: float
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class PurchasedToolingCost:
    component_identity: str
    tooling_identity: str
    quantity: int
    unit_cost: float
    mounting_cost: float
    replacement_allowance: float
    total_cost: float
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class ComponentCost:
    component_identity: str
    material: MaterialCost | None
    processes: tuple[ProcessCost, ...]
    purchased_tooling: PurchasedToolingCost | None
    total_cost: float

    def to_dict(self) -> dict[str, object]:
        return {"component_identity": self.component_identity,
                "material": self.material.to_dict() if self.material else None,
                "processes": [item.to_dict() for item in self.processes],
                "purchased_tooling": self.purchased_tooling.to_dict() if self.purchased_tooling else None,
                "total_cost": self.total_cost}


@dataclass(frozen=True)
class FixtureCostSummary:
    currency: str
    engineering_cost: float
    programming_cost: float
    fixture_build_cost: float
    material_cost: float
    process_cost: float
    purchased_tooling_cost: float
    assembly_cost: float
    inspection_cost: float
    finishing_cost: float
    setup_cost: float
    cutting_cost: float
    machining_cost: float
    welding_cost: float
    commissioning_cost: float
    maintenance_allowance: float
    replacement_allowance: float
    total_estimated_cost: float
    component_costs: tuple[ComponentCost, ...]
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"component_costs": [item.to_dict() for item in self.component_costs],
                                "evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class VolumeScenario:
    identity: str
    label: str
    production_quantity: int
    fixture_count: int
    total_fixture_investment: float
    amortized_cost_per_unit: float
    maintenance_allowance: float
    replacement_allowance: float
    setup_savings_hours: float
    cycle_savings_hours: float
    recommended_strategy: str
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class ManufacturabilityFinding:
    code: str
    severity: str
    message: str
    affected_components: tuple[str, ...]
    rule_id: str
    threshold: str
    recommendation: str
    confidence: str = "provisional"

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"affected_components": list(self.affected_components)}


@dataclass(frozen=True)
class OptimizationAlternative:
    identity: str
    description: str
    assumptions: tuple[str, ...]
    cost_delta: float
    expected_benefit: str
    volume_suitability: str
    manufacturability_impact: str
    access_impact: str
    maintenance_impact: str
    confidence: str
    blocking_findings: tuple[str, ...]
    explanation: str
    break_even_quantity: int | None = None

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"assumptions": list(self.assumptions), "blocking_findings": list(self.blocking_findings)}


@dataclass(frozen=True)
class OptimizationRecommendation:
    scenario_identity: str
    alternative_identity: str
    explanation: str
    evidence: CostEvidence

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {"evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class CostAnalysis:
    version: str
    source_sha256: str
    concept_identity: str
    manufacturing_evidence_digest: str
    drawing_evidence_digest: str | None
    selected_quantity: int
    rate_table: CostRateTable
    assumptions: CostAssumptions
    summary: FixtureCostSummary | None
    scenarios: tuple[VolumeScenario, ...]
    findings: tuple[CostValidationFinding, ...]
    manufacturability_findings: tuple[ManufacturabilityFinding, ...]
    alternatives: tuple[OptimizationAlternative, ...]
    recommendations: tuple[OptimizationRecommendation, ...]

    @property
    def blocked(self) -> bool:
        return any(item.severity == "error" for item in self.findings)

    @property
    def valid(self) -> bool:
        return self.summary is not None and not self.blocked

    @property
    def evidence_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {"version": self.version, "source_sha256": self.source_sha256,
                "concept_identity": self.concept_identity,
                "manufacturing_evidence_digest": self.manufacturing_evidence_digest,
                "drawing_evidence_digest": self.drawing_evidence_digest,
                "selected_quantity": self.selected_quantity, "rate_table": self.rate_table.to_dict(),
                "assumptions": self.assumptions.to_dict(),
                "summary": self.summary.to_dict() if self.summary else None,
                "scenarios": [item.to_dict() for item in self.scenarios],
                "findings": [item.to_dict() for item in self.findings],
                "manufacturability_findings": [item.to_dict() for item in self.manufacturability_findings],
                "alternatives": [item.to_dict() for item in self.alternatives],
                "recommendations": [item.to_dict() for item in self.recommendations],
                "notice": ENGINEERING_ESTIMATE_NOTICE}


def _finding(code: str, severity: str, message: str, components: tuple[str, ...] = (),
             evidence: tuple[str, ...] = ()) -> CostValidationFinding:
    return CostValidationFinding(code, severity, message, evidence, components, f"m25_{code}")


def _material_cost(component: object, rates: CostRateTable, assumptions: CostAssumptions) -> MaterialCost:
    material = str(component.material).strip()
    if material not in rates.material_cost_per_kg or material not in rates.density_kg_per_m3:
        raise OptimizationError(f"unsupported material evidence for {component.identity}: {material}")
    low, high = component.bounds.minimum, component.bounds.maximum
    volume = (high.x - low.x) * (high.y - low.y) * (high.z - low.z)
    if volume <= 0:
        raise OptimizationError(f"component {component.identity} has no positive geometry volume")
    mass = volume * 1e-9 * rates.density_kg_per_m3[material]
    cost = mass * rates.material_cost_per_kg[material] * component.quantity * (1 + assumptions.scrap_factor)
    return MaterialCost(component.identity, component.part_number, component.revision, material, component.quantity,
                        volume, mass, rates.material_cost_per_kg[material], assumptions.scrap_factor, _money(cost),
                        CostEvidence("m25_material_mass", "volume_mm3 * 1e-9 * density_kg_per_m3 * quantity * rate_per_kg * (1 + scrap_factor)",
                                     (f"component={component.identity}", "B-Rep bounds"),
                                     (f"density_kg_per_m3={rates.density_kg_per_m3[material]}",)))


def _process_cost(component: object, rates: CostRateTable) -> tuple[ProcessCost, ...]:
    process = str(component.manufacturing_process).strip().lower()
    if process not in rates.process_cost_per_hour:
        raise OptimizationError(f"unsupported process evidence for {component.identity}: {process}")
    feature_hours = 0.02 * len(component.holes) + 0.03 * len(component.tab_slots)
    base_hours = {"laser_cut": 0.05, "saw_cut": 0.04, "machined": 0.25, "formed": 0.10,
                  "weld": 0.20, "assembly": 0.15, "purchased": 0.0}.get(process, 0.10)
    run = base_hours + feature_hours
    if process == "purchased":
        return ()
    evidence = CostEvidence("m25_process_time", "(base_process_hours + 0.02 * holes + 0.03 * tab_slots) * quantity",
                             (f"component={component.identity}",), (f"process={process}",))
    return (ProcessCost(component.identity, process, component.quantity, 0.0, _hours(run * component.quantity),
                        rates.process_cost_per_hour[process], _money(run * component.quantity * rates.process_cost_per_hour[process]),
                        evidence.formula, evidence),)


def analyze_fixture_cost(assembly: ManufacturingAssembly, *, validation: object,
                         drawing_package: object | None = None,
                         rates: CostRateTable | None = None,
                         assumptions: CostAssumptions | None = None,
                         production_quantity: int | None = None) -> CostAnalysis:
    """Analyze one validated assembly; no geometry or policy is silently inferred."""
    rates = rates or CostRateTable()
    assumptions = assumptions or CostAssumptions(currency=rates.currency)
    quantity = production_quantity if production_quantity is not None else assumptions.low_volume_max_quantity
    findings: list[CostValidationFinding] = []
    if quantity < 1:
        findings.append(_finding("invalid_quantity", "error", "production quantity must be positive"))
    if rates.currency != assumptions.currency:
        findings.append(_finding("currency_mismatch", "error", "rate table and assumptions use different currencies"))
    if not assembly.valid:
        findings.append(_finding("manufacturing_blocked", "error", "invalid manufacturing assembly blocks cost analysis"))
    if validation is None or getattr(validation, "blocked", True):
        findings.append(_finding("validation_blocked", "error", "authoritative fixture validation blocks cost analysis"))
    if getattr(validation, "source_sha256", assembly.source_sha256) != assembly.source_sha256:
        findings.append(_finding("source_identity_mismatch", "error", "validation source identity does not match assembly"))
    if getattr(validation, "concept_identity", assembly.concept_identity) != assembly.concept_identity:
        findings.append(_finding("concept_identity_mismatch", "error", "validation concept identity does not match assembly"))
    drawing_digest = None
    if drawing_package is not None:
        from .drawings import validate_drawing_package
        drawing_findings = validate_drawing_package(assembly, drawing_package, validation)
        drawing_digest = getattr(drawing_package, "pdf_digest", None)
        if getattr(drawing_package, "blocked", True) or any(item.severity == "error" for item in drawing_findings):
            findings.append(_finding("drawing_package_blocked", "error", "invalid drawing package blocks cost analysis"))
    component_costs: list[ComponentCost] = []
    manufacturing_findings: list[ManufacturabilityFinding] = []
    try:
        for component in sorted(assembly.components, key=lambda item: item.identity):
            material = None if component.classification == ComponentClassification.PURCHASED else _material_cost(component, rates, assumptions)
            processes = _process_cost(component, rates)
            purchased = None
            if component.classification == ComponentClassification.PURCHASED:
                tooling = component.purchased_tooling_identity or ""
                if tooling not in rates.purchased_tooling_unit_cost:
                    findings.append(_finding("missing_tooling_rate", "warning", f"no explicit price assumption for tooling {tooling}", (component.identity,)))
                    unit = 0.0
                else:
                    unit = rates.purchased_tooling_unit_cost[tooling]
                total = unit * component.quantity
                purchased = PurchasedToolingCost(component.identity, tooling, component.quantity, _money(unit), 0.0,
                                                 _money(total * assumptions.replacement_factor), _money(total),
                                                 CostEvidence("m25_purchased_tooling", "unit_cost * quantity", (f"component={component.identity}",),
                                                              ("vendor-neutral price assumption; supplier approval external",)))
            total = sum(item.total_cost for item in processes) + (material.total_cost if material else 0.0) + (purchased.total_cost if purchased else 0.0)
            component_costs.append(ComponentCost(component.identity, material, processes, purchased, _money(total)))
        if len(assembly.components) > 12:
            manufacturing_findings.append(ManufacturabilityFinding("excessive_fabricated_part_count", "warning", "component count exceeds the configurable review threshold", tuple(item.identity for item in assembly.components), "m25_part_count", "component_count > 12", "compare modular consolidation before release"))
        if sum(len(item.holes) for item in assembly.components) > 10:
            manufacturing_findings.append(ManufacturabilityFinding("machining_feature_review", "warning", "machining feature count warrants shop-capability review", tuple(item.identity for item in assembly.components), "m25_machining_features", "hole_count > 10", "verify machining access and tolerance need"))
        if sum(item.classification == ComponentClassification.PURCHASED for item in assembly.components) > 4:
            manufacturing_findings.append(ManufacturabilityFinding("purchased_tooling_cost_review", "warning", "purchased tooling count warrants replacement and vendor review", tuple(item.identity for item in assembly.components), "m25_purchased_count", "purchased_count > 4", "compare standard tooling and spare strategy"))
    except OptimizationError as exc:
        findings.append(_finding("insufficient_cost_evidence", "error", str(exc)))
    summary = None
    scenarios: tuple[VolumeScenario, ...] = ()
    alternatives: tuple[OptimizationAlternative, ...] = ()
    recommendations: tuple[OptimizationRecommendation, ...] = ()
    if not any(item.severity == "error" for item in findings):
        material_total = _money(sum((item.material.total_cost if item.material else 0.0) for item in component_costs))
        process_total = _money(sum(item.total_cost for component in component_costs for item in component.processes))
        tooling_total = _money(sum((item.purchased_tooling.total_cost if item.purchased_tooling else 0.0) for item in component_costs))
        assembly_cost = _money(len(component_costs) * rates.assembly_hours_per_component * rates.process_cost_per_hour["assembly"])
        inspection = _money(len(component_costs) * rates.inspection_hours_per_component * rates.process_cost_per_hour["inspection"])
        finishing = _money(sum(1 for item in assembly.components if item.classification == ComponentClassification.FABRICATED) * rates.finishing_hours_per_fabricated_component * rates.process_cost_per_hour["finish"])
        engineering = _money(rates.engineering_hours * rates.process_cost_per_hour["design"])
        programming = _money(rates.programming_hours * rates.process_cost_per_hour["programming"])
        commissioning = _money(rates.commissioning_hours * rates.process_cost_per_hour["commissioning"])
        cutting = _money(sum(item.total_cost for component in component_costs for item in component.processes if item.process_identity in {"laser_cut", "saw_cut"}))
        machining = _money(sum(item.total_cost for component in component_costs for item in component.processes if item.process_identity == "machined"))
        welding = _money(sum(item.total_cost for component in component_costs for item in component.processes if item.process_identity == "weld"))
        setup = _money(rates.setup_hours * rates.process_cost_per_hour["assembly"])
        fixture_build = _money(material_total + process_total + tooling_total + assembly_cost + inspection + finishing + setup)
        maintenance = _money(fixture_build * assumptions.maintenance_factor)
        replacement = _money(tooling_total * assumptions.replacement_factor)
        total = _money(engineering + programming + fixture_build + commissioning + maintenance + replacement)
        summary = FixtureCostSummary(rates.currency, engineering, programming, fixture_build, material_total, process_total,
                                     tooling_total, assembly_cost, inspection, finishing, setup, cutting, machining, welding, commissioning, maintenance,
                                     replacement, total, tuple(component_costs), CostEvidence("m25_total_cost", "engineering + programming + fixture_build + commissioning + maintenance + replacement", (f"assembly={assembly.concept_identity}",), assumptions.notes))
        bands = (("prototype", "prototype", assumptions.prototype_max_quantity, 1, "simple-tack-fixture"),
                 ("low-volume", "low volume", assumptions.low_volume_max_quantity, 1, "manual-modular-fixture"),
                 ("medium-volume", "medium volume", assumptions.medium_volume_max_quantity, 1, "dedicated-manual-fixture"),
                 ("high-volume", "high volume", max(assumptions.medium_volume_max_quantity + 1, quantity), 2, "dedicated-manual-fixture"))
        scenarios = tuple(VolumeScenario(identity, label, band_quantity, fixture_count,
                                         _money(total * fixture_count), _money(total * fixture_count / band_quantity),
                                         _money(maintenance * fixture_count), _money(replacement * fixture_count),
                                         _hours(rates.setup_hours), _hours(rates.setup_hours * 0.5), strategy,
                                         CostEvidence("m25_volume_scenario", "total_fixture_investment / production_quantity", (f"scenario={identity}",), assumptions.notes))
                         for identity, label, band_quantity, fixture_count, strategy in bands)
        alternatives = (OptimizationAlternative("manual-modular-fixture", "Manual modular fixture", ("standard purchased tooling preferred",), 0.0, "lower initial investment and adjustable loading", "prototype and low volume", "simple fabricated structure", "manual access review required", "replaceable standard tooling", "provisional", (), "Selected as the baseline where production quantity does not justify duplication."),
                        OptimizationAlternative("dedicated-manual-fixture", "Dedicated manual fixture", ("repeatability evidence requires engineering review",), _money(total * 0.15), "repeatability and faster loading", "medium volume", "more dedicated components", "operator loading must be reviewed", "dedicated wear items require service plan", "provisional", (), "Higher investment is considered only when recurring quantity supports amortization.", 150),
                        OptimizationAlternative("duplicated-fixture", "Duplicated fixture option", ("two-station throughput claim requires process evidence",), _money(total), "parallel throughput", "high volume", "duplicate BOM and maintenance burden", "automation and operator access require review", "doubles service inventory", "provisional", (), "The option is exposed for comparison and is not an automatic production recommendation.", 500))
        recommendations = tuple(OptimizationRecommendation(item.identity, item.recommended_strategy,
            f"{item.label} uses {item.recommended_strategy}; deterministic estimate is {_money(item.amortized_cost_per_unit):.2f} {rates.currency}/unit. Qualified engineering and commercial review remain mandatory.",
            item.evidence) for item in scenarios)
    return CostAnalysis(OPTIMIZATION_VERSION, assembly.source_sha256, assembly.concept_identity, assembly.evidence_digest,
                        drawing_digest, quantity, rates, assumptions, summary, scenarios, tuple(findings),
                        tuple(manufacturing_findings), alternatives, recommendations)


CostModel = CostAnalysis
