"""Small, deterministic geometry contracts used by the FXD baseline proof."""

from .aabb import Aabb, Box, Transform, Vec3, neutral_export
from .product_model import Body, Component, Edge, Face, ProductModel
from .step_import import StepImportError, import_step

__all__ = ["Aabb", "Body", "Box", "Component", "Edge", "Face", "ProductModel", "StepImportError", "Transform", "Vec3", "import_step", "neutral_export"]
