"""Small, deterministic geometry contracts used by the FXD baseline proof."""

from .aabb import Aabb, Box, Transform, Vec3, neutral_export
from .product_model import Body, Component, Edge, Face, ProductModel
from .step_import import StepImportError, import_step
from .annotations import AnnotationError, Assumption, CriticalCharacteristic, EngineeringAnnotations, GeometryReference, WeldJoint
from .fixture import FixtureConcept, FixtureFeature, FixtureFinding, FixtureGenerationError, FixtureParameters, generate_fixture_primitives

__all__ = ["Aabb", "AnnotationError", "Assumption", "Body", "Box", "Component", "CriticalCharacteristic", "Edge", "EngineeringAnnotations", "Face", "FixtureConcept", "FixtureFeature", "FixtureFinding", "FixtureGenerationError", "FixtureParameters", "GeometryReference", "ProductModel", "StepImportError", "Transform", "Vec3", "WeldJoint", "generate_fixture_primitives", "import_step", "neutral_export"]
