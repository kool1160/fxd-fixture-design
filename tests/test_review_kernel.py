from __future__ import annotations

import unittest

from fxd_geometry import KernelOperationError, KernelTriangleMesh, OcpKernel
from fxd_geometry.review_kernel import (
    has_volumetric_overlap,
    transformed_point,
    zero_based_triangle,
)


class _PlacedPoint:
    def __init__(self, coordinates: tuple[float, float, float]) -> None:
        self.coordinates = coordinates

    def Transformed(self, transform: tuple[float, float, float]) -> "_PlacedPoint":
        return _PlacedPoint(tuple(value + offset for value, offset in zip(self.coordinates, transform)))

    def X(self) -> float:
        return self.coordinates[0]

    def Y(self) -> float:
        return self.coordinates[1]

    def Z(self) -> float:
        return self.coordinates[2]


class _Location:
    def __init__(self, translation: tuple[float, float, float]) -> None:
        self.translation = translation

    def Transformation(self) -> tuple[float, float, float]:
        return self.translation


class ReviewKernelContractTests(unittest.TestCase):
    def test_occt_triangle_indices_are_converted_to_python_indices(self) -> None:
        self.assertEqual(zero_based_triangle((1, 2, 3), 3), (0, 1, 2))

    def test_invalid_triangle_indices_fail_closed(self) -> None:
        with self.assertRaises(KernelOperationError):
            zero_based_triangle((0, 2, 3), 3)
        with self.assertRaises(KernelOperationError):
            zero_based_triangle((1, 2, 4), 3)

    def test_touching_contact_is_not_volumetric_interference(self) -> None:
        self.assertFalse(has_volumetric_overlap(0.0, 1e-4))
        self.assertFalse(has_volumetric_overlap(1e-13, 1e-4))
        self.assertTrue(has_volumetric_overlap(1e-9, 1e-4))

    def test_negative_interference_tolerance_is_rejected(self) -> None:
        with self.assertRaises(KernelOperationError):
            has_volumetric_overlap(0.0, -0.1)

    def test_edge_points_are_reported_in_world_coordinates(self) -> None:
        point = _PlacedPoint((1.0, 2.0, 3.0))
        location = _Location((10.0, -2.0, 0.5))
        self.assertEqual(transformed_point(point, location), (11.0, 0.0, 3.5))

    def test_public_ocp_adapter_is_the_hardened_review_adapter(self) -> None:
        self.assertEqual(OcpKernel.__module__, "fxd_geometry.review_kernel")

    def test_mesh_contract_uses_zero_based_indices(self) -> None:
        mesh = KernelTriangleMesh(
            "face:proof",
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            ((0, 1, 2),),
        )
        self.assertEqual(tuple(mesh.vertices_mm[index] for index in mesh.triangles[0]), mesh.vertices_mm)

    def test_step_occurrence_labels_are_canonical_across_writer_history(self) -> None:
        first = b"""ISO-10303-21;\nFILE_NAME('fixture.step','2026-07-14T13:00:00',(''),(''),'Open CASCADE STEP translator 7.9 3','Open CASCADE 7.9','');\n#10 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('5','','',#1,#2,$);\n#11 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('6','','',#1,#2,$);\nEND-ISO-10303-21;\n"""
        second = b"""ISO-10303-21;\nFILE_NAME('fixture.step','2026-07-14T14:00:00',(''),(''),'Open CASCADE STEP translator 7.9 9','Open CASCADE 7.9','');\n#10 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('7','','',#1,#2,$);\n#11 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('8','','',#1,#2,$);\nEND-ISO-10303-21;\n"""
        normalized = OcpKernel._normalize_step(first)
        self.assertEqual(normalized, OcpKernel._normalize_step(second))
        self.assertIn(b"NEXT_ASSEMBLY_USAGE_OCCURRENCE('1'", normalized)
        self.assertIn(b"NEXT_ASSEMBLY_USAGE_OCCURRENCE('2'", normalized)


if __name__ == "__main__":
    unittest.main()
