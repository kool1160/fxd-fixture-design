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

    def test_multi_component_assembly_transforms_normals_and_references_survive_reload(self):
        from OCP.BRep import BRep_Builder
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.TopoDS import TopoDS_Compound
        from OCP.gp import gp_Trsf, gp_Vec

        kernel = require_real_kernel()
        first = BRepPrimAPI_MakeBox(10.0, 20.0, 3.0).Shape()
        move = gp_Trsf()
        move.SetTranslation(gp_Vec(25.0, 5.0, 8.0))
        second = BRepBuilderAPI_Transform(
            BRepPrimAPI_MakeBox(5.0, 7.0, 9.0).Shape(), move, False
        ).Shape()
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        builder.Add(compound, first)
        builder.Add(compound, second)

        exported = kernel.export_step(compound)
        assembly = kernel.import_step_assembly(exported)
        self.assertEqual(assembly.root_reference, "assembly:root")
        self.assertEqual(assembly.units, "mm")
        self.assertEqual(len(assembly.components), 2)
        self.assertTrue(all(component.parent_reference == "assembly:root"
                            for component in assembly.components))
        self.assertTrue(all(len(component.transform) == 12 for component in assembly.components))
        self.assertTrue(all(component.faces for component in assembly.components))
        for component in assembly.components:
            for face in component.faces:
                magnitude = sum(value * value for value in face.normal) ** 0.5
                self.assertAlmostEqual(magnitude, 1.0, places=7)

        roundtrip = kernel.export_step(kernel.import_step(exported))
        reloaded = kernel.import_step_assembly(roundtrip)
        self.assertEqual(
            tuple(component.reference for component in assembly.components),
            tuple(component.reference for component in reloaded.components),
        )
        self.assertEqual(
            tuple(tuple(face.reference for face in component.faces)
                  for component in assembly.components),
            tuple(tuple(face.reference for face in component.faces)
                  for component in reloaded.components),
        )

    def test_malformed_partial_and_missing_step_fail_clearly(self):
        kernel = require_real_kernel()
        with self.assertRaisesRegex(KernelOperationError, "malformed or partial"):
            kernel.import_step(b"ISO-10303-21;\nHEADER;\n")
        with self.assertRaisesRegex(KernelOperationError, "does not exist"):
            kernel.import_step("tests/fixtures/does-not-exist.step")
        with self.assertRaisesRegex(KernelOperationError, "no solid components"):
            # Valid STEP containing a wire but no solid assembly component.
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
            from OCP.gp import gp_Pnt
            wire_step = kernel.export_step(
                BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(1, 0, 0)).Shape()
            )
            kernel.import_step_assembly(wire_step)


if __name__ == "__main__":
    unittest.main()
