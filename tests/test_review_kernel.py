from __future__ import annotations

import unittest

from fxd_geometry import KernelOperationError, KernelTriangleMesh, OcpKernel
from fxd_geometry.review_kernel import has_volumetric_overlap, zero_based_triangle


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

    def test_public_ocp_adapter_is_the_hardened_review_adapter(self) -> None:
        self.assertEqual(OcpKernel.__module__, "fxd_geometry.review_kernel")

    def test_mesh_contract_uses_zero_based_indices(self) -> None:
        mesh = KernelTriangleMesh(
            "face:proof",
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            ((0, 1, 2),),
        )
        self.assertEqual(tuple(mesh.vertices_mm[index] for index in mesh.triangles[0]), mesh.vertices_mm)


if __name__ == "__main__":
    unittest.main()
