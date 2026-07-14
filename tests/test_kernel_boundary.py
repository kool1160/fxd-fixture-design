import unittest

from fxd_geometry.kernel import (KernelCapabilities, KernelOperationError,
                                 OcpKernel, require_real_kernel)


class KernelBoundaryTests(unittest.TestCase):
    def test_capability_gate_requires_every_real_geometry_operation(self):
        complete = KernelCapabilities("test", "1", True, True, True, True, True, True)
        incomplete = KernelCapabilities("test", "1", True, True, True, False, True, True)
        self.assertTrue(complete.is_complete)
        self.assertFalse(incomplete.is_complete)

    def test_reviewed_runtime_is_available_and_complete(self):
        kernel = require_real_kernel()
        self.assertIsInstance(kernel, OcpKernel)
        self.assertTrue(kernel.capabilities.is_complete)
        self.assertEqual(kernel.capabilities.backend, "cadquery-ocp")
        self.assertTrue(kernel.capabilities.version.startswith("7.9.3.1"))

    def test_real_topology_clearance_boolean_and_step_roundtrip(self):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Trsf, gp_Vec

        kernel = require_real_kernel()
        left = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(15.0, 0.0, 0.0))
        right = BRepBuilderAPI_Transform(left, transform, True).Shape()

        counts = kernel.topology_counts(left)
        self.assertEqual((counts.solids, counts.shells, counts.faces), (1, 1, 6))
        self.assertGreater(counts.edges, 0)
        self.assertAlmostEqual(kernel.clearance(left, right), 5.0, places=7)

        fused = kernel.boolean("fuse", left, right)
        self.assertGreaterEqual(kernel.topology_counts(fused).solids, 1)
        with self.assertRaises(KernelOperationError):
            kernel.boolean("invent", left, right)

        exported = kernel.export_step(left)
        self.assertIn(b"ISO-10303-21", exported)
        reloaded = kernel.import_step(exported)
        self.assertEqual(kernel.topology_counts(reloaded), counts)
        self.assertEqual(kernel.export_step(reloaded), kernel.export_step(reloaded))


if __name__ == "__main__":
    unittest.main()
