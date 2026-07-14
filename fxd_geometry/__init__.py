"""Small, deterministic geometry contracts used by the FXD baseline proof."""

from .aabb import Aabb, Box, Transform, Vec3, neutral_export
from .product_model import Body, Component, Edge, Face, ProductModel
from .step_import import StepImportError, import_step
from .annotations import AnnotationError, Assumption, CriticalCharacteristic, EngineeringAnnotations, GeometryReference, WeldJoint
from .fixture import FixtureConcept, FixtureFeature, FixtureFinding, FixtureGenerationError, FixtureParameters, generate_fixture_primitives
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
from .kernel import (KernelAssembly, KernelCapabilities, KernelComponent, KernelFace,
                     KernelOperationError, KernelUnavailable, OcpKernel, RealKernel,
                     TopologyCounts, installed_backend_candidates,
                     require_real_kernel)

__all__ = ["Aabb", "AccessAnalysis", "AccessAnalysisError", "AccessEnvelope", "AccessFinding", "AnnotationError", "ApprovalRequired", "Assumption", "Body", "Box", "CompatibilityProbe", "Component", "CompleteFixtureConcept", "ConceptScore", "ConnectorCapabilities", "ConnectorDescriptor", "ConnectorError", "ConstraintAnalysis", "ConstraintAnalysisError", "ConstraintFinding", "CorrectionRecord", "CriticalCharacteristic", "Edge", "EngineeringAnnotations", "ExportError", "FabricationPackage", "Face", "FixtureConcept", "FixtureCorrection", "FixtureFeature", "FixtureFinding", "FixtureGenerationError", "FixtureParameters", "GeometryReference", "KernelAssembly", "KernelCapabilities", "KernelComponent", "KernelFace", "KernelOperationError", "KernelUnavailable", "KnowledgeError", "KnowledgeStore", "LocatorContact", "LocatingAnalysis", "LocatingStrategy", "NeutralStepConnector", "OcpKernel", "ProductModel", "ProposedFeature", "RealKernel", "RankedFixtureConcepts", "StepImportError", "ToolingItem", "ToolingLibrary", "ToolingLibraryError", "ToolingSelection", "TopologyCounts", "Transform", "Vec3", "WeldAccessRequest", "WeldJoint", "WeldRecommendation", "WeldRuleAnalysis", "WeldRuleConfig", "WeldRuleError", "WeldRuleFinding", "analyze_locating_strategy", "build_fabrication_package", "connector_registry", "digest_text", "evaluate_access", "evaluate_weld_rules", "generate_fixture_concepts", "generate_fixture_primitives", "generic_tooling_library", "import_step", "installed_backend_candidates", "neutral_export", "private_knowledge_path", "probe_solidworks", "require_destructive_approval", "require_real_kernel", "write_fabrication_package"]
