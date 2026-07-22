"""Small, deterministic geometry contracts used by the FXD baseline proof."""

from .aabb import Aabb, Box, Transform, Vec3, neutral_export
from .product_model import Body, Component, Edge, Face, ProductModel
from .step_import import StepImportError, import_step
from .annotations import AnnotationError, Assumption, CriticalCharacteristic, EngineeringAnnotations, GeometryReference, WeldJoint
from .fixture import (FixtureConcept, FixtureFeature, FixtureFinding, FixtureGenerationError,
                      FixtureParameters, ManufacturingSpec, generate_fixture_primitives)
from .manufacturing import ManufacturingGeometry, ManufacturingSolid, generate_manufacturing_geometry
from .concepts import (CompleteFixtureConcept, ConceptScore, ConstraintAnalysis,
                       FixtureCorrection, RankedFixtureConcepts, generate_fixture_concepts)
from .constraints import (ConstraintAnalysisError, ConstraintFinding, LocatorContact,
                          LocatingAnalysis, LocatingStrategy, analyze_locating_strategy)
from .access import (AccessAnalysis, AccessAnalysisError, AccessEnvelope, AccessFinding,
                     WeldAccessRequest, evaluate_access)
from .weld_rules import (WeldRecommendation, WeldRuleAnalysis, WeldRuleConfig,
                         WeldRuleError, WeldRuleFinding, evaluate_weld_rules)
from .tooling import (ToolingItem, ToolingLibrary, ToolingLibraryError, ToolingSelection,
                      generic_tooling_library)
from .export import (ExportError, FabricationPackage, build_fabrication_package,
                     write_fabrication_package)
from .knowledge import (CorrectionRecord, KnowledgeError, KnowledgeStore,
                        ProposedFeature, digest_text, private_knowledge_path)
from .connectors import (ApprovalRequired, CompatibilityProbe, ConnectorCapabilities,
                         ConnectorDescriptor, ConnectorError, NeutralStepConnector,
                         connector_registry, probe_solidworks,
                         require_destructive_approval)
from .kernel import (KernelAssembly, KernelCapabilities, KernelComponent, KernelEdgeRecord, KernelFace,
                     KernelTriangleMesh, KernelOperationError, KernelUnavailable, RealKernel,
                     TopologyCounts, installed_backend_candidates)
from .review_kernel import OcpKernel
from .visual import ReviewGeometry, ReviewVisualItem, VisualEdge, build_review_geometry
from .project import FixtureEdit, ProjectRevision
from .operations import (DiagnosticEvent, OperationsError, ProjectRecovery, StructuredLog,
                         export_project_package, load_preferences, project_export_block_reason,
                         save_preferences)
from .validation import (VALIDATION_VERSION, ValidationFinding, ValidationResult,
                         validate_fixture_concept)
from .workflow import (SequencePlan, WorkflowComparison, WorkflowEnvelope, WorkflowError,
                       WorkflowFinding, WorkflowReport, WorkflowStep, WorkflowVariant,
                       WorkflowVisualItem,
                       ReviewZone, compare_workflow_variants, evaluate_workflow)
from .structure import (StructuralAssembly, StructuralComparison, StructuralFinding,
                         StructuralGenerationError, StructuralMember, StructuralParameters,
                         StructuralStrategy, compare_structural_concepts,
                         generate_structural_assembly, select_structural_strategy,
                         validate_structural_assembly)
from .placement import (DatumCandidate, DatumCandidateScore, Placement, PlacementAlternative,
                        PlacementError, PlacementFinding, PlacementParameters, PlacementPlan,
                        PlacementRole, compare_placement_plans, generate_placement_plan,
                        rank_datum_candidates, validate_placement_plan)
from .component_geometry import (ComponentClassification, ComponentExport, ComponentGeometryError,
                                 ComponentType, HoleSpec, ManufacturingAssembly, ManufacturingComponent,
                                 ManufacturingFinding, TabSlotSpec, build_manufacturing_export_package,
                                 generate_manufacturing_assembly, generate_manufacturing_assembly_for_product,
                                 validate_manufacturing_assembly, write_manufacturing_export_package)
from .workbench import WorkbenchDocument, load_step_for_workbench
from .vtk_viewer import (RenderDiagnostics, VtkSceneController,
                         VtkViewerUnavailable, VtkWorkbenchViewer)
from .drawings import (APPROVAL_TEXT, NOT_RELEASED_TEXT, BomEntry, DrawingAnnotation,
                       DrawingDimension, DrawingFinding, DrawingPackage, DrawingPackageError,
                       DrawingSheet, DrawingView, HoleTableRow, RevisionBlock,
                       generate_drawing_package, validate_drawing_package, write_drawing_package)
from .optimization import (ENGINEERING_ESTIMATE_NOTICE, CostAnalysis, CostAssumptions, CostEvidence, CostModel,
                            CostRateTable, CostValidationFinding, ComponentCost, FixtureCostSummary,
                            LaborCost, ManufacturabilityFinding, MaterialCost, OptimizationAlternative,
                            OptimizationError, OptimizationRecommendation, ProcessCost, PurchasedToolingCost,
                            VolumeScenario, analyze_fixture_cost)
from .interactive_workflow import (
    WORKFLOW_SCHEMA, AnnotationRole, ConceptComparison, CustomerToolingRecord,
    GeometryAnnotation, InteractiveWorkflow, InteractiveWorkflowError,
    OperationTiming, ProcessSetup, analyze_engineering_workflow, compare_concepts,
    face_annotation, product_from_workbench_document, tooling_record_from_file,
)
from .manufacturing_orientation import (
    CoordinateSystem,
    ManufacturingOrientation,
    ManufacturingOrientationError,
    OrientationMethod,
    OrientationRecommendation,
    ReferencePlane,
    orientation_from_face,
    orientation_from_faces,
    orientation_from_plane,
    recommend_orientations,
    reference_plane_orientation,
    source_orientation,
)
from .fabrication_workflow import (
    M30_SCHEMA, M32_SCHEMA, RULE_CATALOG, RULES_BY_ID, AdjustmentState, AuthoredFixtureAssembly,
    AuthoredFixtureComponent, BuildComponentRole, ClecoSpec, ClecoStrategy,
    ConfirmedWeldIntent, ConstructionMethod, FixtureBuildComparison, FixtureBuildComponent, FixtureBuildError,
    FixtureBuildFinding, FixtureBuildPlan, FixtureBuildRequirements, FixtureBuildValidation,
    FixtureFamily, FixtureLifecycle, FixturePurpose, GeometryAuthority, HoleProcess, HoleProcessSpec,
    MultiStationFitProposal, MultiStationLayout, MultiStationRequirements, SlotProcessSpec, StationTransform,
    WeldJointAccessResult,
    M30Rule, NestClassification, PokaYokeSpec, TabSlotJoint, author_fixture_build, propose_multi_station_fit,
    bind_fixture_build_plan_to_proposal, build_fixture_build_package, compare_fixture_build_plans, generate_fixture_build_plan,
    generate_multi_station_fixture_alternatives, generate_multi_station_fixture_build_plan,
    generate_multi_station_layout,
    propose_multi_station_count, validate_fixture_build_plan, write_fixture_build_package,
)
from .ai_fixture_engineer import (
    PROMPT_CONTRACT_VERSION, PROPOSAL_REQUEST_SCHEMA, PROPOSAL_SCHEMA,
    AiFixtureProvider, AiProposalRequest, CancellationToken, EditableParameter,
    FixtureProposal, FixtureProposalError, GuidedValidationIssue, HttpJsonAiProvider,
    OpenAiResponsesProvider,
    IntentQuestion, MissingIntentError, ProposalAuditEvent, ProposalCancelled,
    ProposalContractRejection, ProposalEvidence, ProposalGenerationOutcome, ProposalProvenance,
    ProposalRecommendation, ProposalSource, ProviderState, ProviderUnavailable,
    PROPOSAL_CONTRACT_REJECTION_CATEGORIES,
    RecommendationDecision, RecommendationType, RecommendationValidation,
    StaticAiProvider, UnavailableAiProvider, ai_response_from_proposal,
    apply_recommended_intent, build_ai_request, decide_proposal,
    decide_recommendation, deterministic_baseline_proposal, edit_recommendation,
    generate_fixture_proposal, minimal_intent_questions, proposal_from_ai_response,
    proposal_engineering_context_identity, validate_fixture_proposal,
)


def require_real_kernel() -> RealKernel:
    """Return the hardened reviewed adapter; AABB is never a runtime fallback."""
    from importlib.util import find_spec
    if find_spec("OCP") is None:
        raise KernelUnavailable(f"Install {OcpKernel.PINNED_DISTRIBUTION}; AABB is not a fallback")
    kernel = OcpKernel()
    if not kernel.capabilities.is_complete:
        raise KernelUnavailable("reviewed OCP adapter lacks required capabilities")
    return kernel


__all__ = ["Aabb", "AccessAnalysis", "AccessAnalysisError", "AccessEnvelope", "AccessFinding", "AnnotationError", "ApprovalRequired", "Assumption", "Body", "Box", "CompatibilityProbe", "Component", "CompleteFixtureConcept", "ConceptScore", "ConnectorCapabilities", "ConnectorDescriptor", "ConnectorError", "ConstraintAnalysis", "ConstraintAnalysisError", "ConstraintFinding", "CorrectionRecord", "CriticalCharacteristic", "Edge", "EngineeringAnnotations", "ExportError", "FabricationPackage", "Face", "FixtureConcept", "FixtureCorrection", "FixtureEdit", "FixtureFeature", "FixtureFinding", "FixtureGenerationError", "FixtureParameters", "GeometryReference", "KernelAssembly", "KernelCapabilities", "KernelComponent", "KernelEdgeRecord", "KernelFace", "KernelOperationError", "KernelTriangleMesh", "KernelUnavailable", "KnowledgeError", "KnowledgeStore", "LocatorContact", "LocatingAnalysis", "LocatingStrategy", "ManufacturingGeometry", "ManufacturingSolid", "ManufacturingSpec", "NeutralStepConnector", "OcpKernel", "ProductModel", "ProjectRevision", "ProposedFeature", "RealKernel", "RankedFixtureConcepts", "ReviewGeometry", "ReviewVisualItem", "StepImportError", "ToolingItem", "ToolingLibrary", "ToolingLibraryError", "ToolingSelection", "TopologyCounts", "Transform", "ValidationFinding", "ValidationResult", "VALIDATION_VERSION", "Vec3", "VisualEdge", "WeldAccessRequest", "WeldJoint", "WeldRecommendation", "WeldRuleAnalysis", "WeldRuleConfig", "WeldRuleError", "WeldRuleFinding", "analyze_locating_strategy", "build_fabrication_package", "build_review_geometry", "connector_registry", "digest_text", "evaluate_access", "evaluate_weld_rules", "generate_fixture_concepts", "generate_fixture_primitives", "generate_manufacturing_geometry", "generic_tooling_library", "import_step", "installed_backend_candidates", "neutral_export", "private_knowledge_path", "probe_solidworks", "require_destructive_approval", "require_real_kernel", "validate_fixture_concept", "write_fabrication_package"]
__all__ += ["ReviewZone", "SequencePlan", "WorkflowComparison", "WorkflowEnvelope", "WorkflowError",
            "WorkflowFinding", "WorkflowReport", "WorkflowStep", "WorkflowVariant",
            "WorkflowVisualItem",
            "compare_workflow_variants", "evaluate_workflow"]
__all__ += ["DiagnosticEvent", "OperationsError", "ProjectRecovery", "StructuredLog",
            "export_project_package", "load_preferences", "project_export_block_reason",
            "save_preferences"]
__all__ += ["StructuralAssembly", "StructuralComparison", "StructuralFinding", "StructuralGenerationError",
            "StructuralMember", "StructuralParameters", "StructuralStrategy", "compare_structural_concepts",
            "generate_structural_assembly", "select_structural_strategy", "validate_structural_assembly"]
__all__ += ["DatumCandidate", "DatumCandidateScore", "Placement", "PlacementAlternative", "PlacementError",
            "PlacementFinding", "PlacementParameters", "PlacementPlan", "PlacementRole",
            "compare_placement_plans", "generate_placement_plan", "rank_datum_candidates",
            "validate_placement_plan"]
__all__ += ["ComponentClassification", "ComponentExport", "ComponentGeometryError", "ComponentType",
            "HoleSpec", "ManufacturingAssembly", "ManufacturingComponent", "ManufacturingFinding",
            "TabSlotSpec", "build_manufacturing_export_package", "generate_manufacturing_assembly",
            "generate_manufacturing_assembly_for_product", "validate_manufacturing_assembly",
            "write_manufacturing_export_package"]
__all__ += ["WorkbenchDocument", "load_step_for_workbench"]
__all__ += ["RenderDiagnostics", "VtkSceneController", "VtkViewerUnavailable",
            "VtkWorkbenchViewer"]
__all__ += ["APPROVAL_TEXT", "NOT_RELEASED_TEXT", "BomEntry", "DrawingAnnotation", "DrawingDimension",
            "DrawingFinding", "DrawingPackage", "DrawingPackageError", "DrawingSheet", "DrawingView",
            "HoleTableRow", "RevisionBlock", "generate_drawing_package", "validate_drawing_package",
            "write_drawing_package"]
__all__ += ["ENGINEERING_ESTIMATE_NOTICE", "CostAnalysis", "CostAssumptions", "CostEvidence", "CostModel", "CostRateTable",
            "CostValidationFinding", "ComponentCost", "FixtureCostSummary", "LaborCost",
            "ManufacturabilityFinding", "MaterialCost", "OptimizationAlternative", "OptimizationError",
            "OptimizationRecommendation", "ProcessCost", "PurchasedToolingCost", "VolumeScenario",
            "analyze_fixture_cost"]
__all__ += ["WORKFLOW_SCHEMA", "AnnotationRole", "ConceptComparison", "CustomerToolingRecord",
            "GeometryAnnotation", "InteractiveWorkflow", "InteractiveWorkflowError",
            "OperationTiming", "ProcessSetup", "analyze_engineering_workflow", "compare_concepts",
            "face_annotation", "product_from_workbench_document", "tooling_record_from_file"]
__all__ += ["CoordinateSystem", "ManufacturingOrientation", "ManufacturingOrientationError",
            "OrientationMethod", "OrientationRecommendation", "ReferencePlane",
            "orientation_from_face", "orientation_from_faces", "orientation_from_plane", "recommend_orientations",
            "reference_plane_orientation", "source_orientation"]
__all__ += ["M30_SCHEMA", "M32_SCHEMA", "RULE_CATALOG", "RULES_BY_ID", "AdjustmentState", "AuthoredFixtureAssembly",
            "AuthoredFixtureComponent", "BuildComponentRole", "ClecoSpec", "ClecoStrategy",
            "ConfirmedWeldIntent", "ConstructionMethod", "FixtureBuildComparison", "FixtureBuildComponent", "FixtureBuildError",
            "FixtureBuildFinding", "FixtureBuildPlan", "FixtureBuildRequirements", "FixtureBuildValidation",
            "FixtureFamily", "FixtureLifecycle", "FixturePurpose", "GeometryAuthority", "HoleProcess", "HoleProcessSpec",
            "MultiStationFitProposal", "MultiStationLayout", "MultiStationRequirements", "SlotProcessSpec", "StationTransform",
            "WeldJointAccessResult",
            "M30Rule", "NestClassification", "PokaYokeSpec", "TabSlotJoint", "author_fixture_build", "propose_multi_station_fit",
            "bind_fixture_build_plan_to_proposal", "build_fixture_build_package", "compare_fixture_build_plans", "generate_fixture_build_plan",
            "generate_multi_station_fixture_alternatives", "generate_multi_station_fixture_build_plan",
            "generate_multi_station_layout",
            "propose_multi_station_count", "validate_fixture_build_plan", "write_fixture_build_package"]
__all__ += ["PROMPT_CONTRACT_VERSION", "PROPOSAL_REQUEST_SCHEMA", "PROPOSAL_SCHEMA",
            "AiFixtureProvider", "AiProposalRequest", "CancellationToken", "EditableParameter",
            "FixtureProposal", "FixtureProposalError", "GuidedValidationIssue", "HttpJsonAiProvider",
            "OpenAiResponsesProvider",
            "IntentQuestion", "MissingIntentError", "ProposalAuditEvent", "ProposalCancelled",
            "ProposalContractRejection", "ProposalEvidence", "ProposalGenerationOutcome", "ProposalProvenance",
            "ProposalRecommendation", "ProposalSource", "ProviderState", "ProviderUnavailable",
            "PROPOSAL_CONTRACT_REJECTION_CATEGORIES",
            "RecommendationDecision", "RecommendationType", "RecommendationValidation",
            "StaticAiProvider", "UnavailableAiProvider", "ai_response_from_proposal",
            "apply_recommended_intent", "build_ai_request", "decide_proposal",
            "decide_recommendation", "deterministic_baseline_proposal", "edit_recommendation",
            "generate_fixture_proposal", "minimal_intent_questions", "proposal_from_ai_response",
            "validate_fixture_proposal"]
