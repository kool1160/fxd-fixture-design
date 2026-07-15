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
from .validation import (VALIDATION_VERSION, ValidationFinding, ValidationResult,
                         validate_fixture_concept)
from .workflow import (SequencePlan, WorkflowComparison, WorkflowEnvelope, WorkflowError,
                       WorkflowFinding, WorkflowReport, WorkflowStep, WorkflowVariant,
                       WorkflowVisualItem,
                       ReviewZone, compare_workflow_variants, evaluate_workflow)


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
