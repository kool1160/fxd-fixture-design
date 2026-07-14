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
from .kernel import (KernelAssembly, KernelCapabilities, KernelComponent, KernelFace,
                     KernelOperationError, KernelUnavailable, OcpKernel, RealKernel,
                     TopologyCounts, installed_backend_candidates,
                     require_real_kernel)
from .validation import (VALIDATION_VERSION, ValidationFinding, ValidationResult,
                         validate_fixture_concept)
from .visual import FeatureOverride, VisualProject, load_project, save_project, scene_payload, serve

__all__ = [name for name in globals() if not name.startswith("_")]
