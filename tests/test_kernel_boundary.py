import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from fxd_geometry.kernel import (KernelCapabilities, KernelOperationError,
                                 OcpKernel, require_real_kernel)


def _nested_assembly_step() -> bytes:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.gp import gp_Trsf, gp_Vec

    application = XCAFApp_Application.GetApplication_s()
    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    application.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), document)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())

    plate = shape_tool.AddShape(BRepPrimAPI_MakeBox(10, 20, 3).Shape(), False)
    block = shape_tool.AddShape(BRepPrimAPI_MakeBox(5, 7, 9).Shape(), False)
    TDataStd_Name.Set_s(plate, TCollection_ExtendedString("Plate"))
    TDataStd_Name.Set_s(block, TCollection_ExtendedString("Block"))

    subassembly = shape_tool.NewShape()
    TDataStd_Name.Set_s(subassembly, TCollection_ExtendedString("Subassembly"))
    block_move = gp_Trsf()
    block_move.SetTranslation(gp_Vec(4, 2, 1))
    shape_tool.AddComponent(subassembly, block, TopLoc_Location(block_move))

    root = shape_tool.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("Root"))
    shape_tool.AddComponent(root, plate, TopLoc_Location())
    subassembly_move = gp_Trsf()
    subassembly_move.SetTranslation(gp_Vec(25, 5, 8))
    shape_tool.AddComponent(root, subassembly, TopLoc_Location(subassembly_move))
    shape_tool.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    if not writer.Transfer(document, STEPControl_AsIs):
        raise AssertionError("could not transfer synthetic XCAF assembly")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "nested.step"
        if writer.Write(str(path)) != IFSelect_RetDone:
            raise AssertionError("could not write synthetic XCAF assembly")
        return path.read_bytes()


class KernelBoundaryTests(unittest.TestCase):
    def test_capability_gate_requires_every_real_geometry_operation(self):
        complete = KernelCapabilities("test", "1", True, True, True, True, True, True)
        incomplete = KernelCapabilities("test", "1", True, True, True, False, True, True)
        self.assertTrue(complete.is_complete)
        self.assertFalse(incomplete.is_complete)

    @unittest.skipUnless(find_spec("OCP"), "pinned OCP is unavailable; GitHub Actions is authoritative")
    def test_reviewed_runtime_is_available_and_complete(self):
        kernel = require_real_kernel()
        self.assertIsInstance(kernel, OcpKernel)
        self.assertTrue(kernel.capabilities.is_complete)
        self.assertEqual(kernel.capabilities.backend, "cadquery-ocp")
        self.assertTrue(kernel.capabilities.version.startswith("7.9.3.1"))

    @unittest.skipUnless(find_spec("OCP"), "pinned OCP is unavailable; GitHub Actions is authoritative")
    def test_real_topology_clearance_boolean_and_step_roundtrip(self):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Trsf, gp_Vec

        kernel = require_real_kernel()
        left = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(15, 0, 0))
        right = BRepBuilderAPI_Transform(left, transform, True).Shape()
        counts = kernel.topology_counts(left)
        self.assertEqual((counts.solids, counts.shells, counts.faces), (1, 1, 6))
        self.assertAlmostEqual(kernel.clearance(left, right), 5.0, places=7)
        self.assertGreaterEqual(
            kernel.topology_counts(kernel.boolean("fuse", left, right)).solids, 1
        )
        with self.assertRaises(KernelOperationError):
            kernel.boolean("invent", left, right)
        exported = kernel.export_step(left)
        reloaded = kernel.import_step(exported)
        self.assertEqual(kernel.topology_counts(reloaded), counts)
        self.assertEqual(kernel.export_step(reloaded), kernel.export_step(reloaded))

    @unittest.skipUnless(find_spec("OCP"), "pinned OCP is unavailable; GitHub Actions is authoritative")
    def test_xcaf_hierarchy_composed_transforms_normals_and_references(self):
        kernel = require_real_kernel()
        source = _nested_assembly_step()
        first = kernel.import_step_assembly(source)
        second = kernel.import_step_assembly(source)
        self.assertEqual(first, second)
        self.assertEqual(first.root_reference, "assembly:root")
        self.assertIn("assembly:1.2", first.assembly_references)
        self.assertEqual({item.name for item in first.components}, {"Plate", "Block"})
        by_name = {item.name: item for item in first.components}
        self.assertEqual(by_name["Plate"].parent_reference, "assembly:1")
        self.assertEqual(by_name["Block"].parent_reference, "assembly:1.2")
        self.assertEqual(by_name["Plate"].transform[3::4], (0.0, 0.0, 0.0))
        self.assertEqual(by_name["Block"].transform[3::4], (29.0, 7.0, 9.0))
        for component in first.components:
            self.assertEqual(component.topology.solids, 1)
            self.assertTrue(component.faces)
            for face in component.faces:
                self.assertAlmostEqual(
                    sum(value * value for value in face.normal), 1.0, places=7
                )

    @unittest.skipUnless(find_spec("OCP"), "pinned OCP is unavailable; GitHub Actions is authoritative")
    def test_source_is_immutable_and_bad_step_fails_clearly(self):
        kernel = require_real_kernel()
        source = _nested_assembly_step()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.step"
            path.write_bytes(source)
            kernel.import_step_assembly(path)
            self.assertEqual(path.read_bytes(), source)
        with self.assertRaisesRegex(KernelOperationError, "malformed or partial"):
            kernel.import_step(b"ISO-10303-21;\nHEADER;\n")
        with self.assertRaisesRegex(KernelOperationError, "does not exist"):
            kernel.import_step("does-not-exist.step")
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCP.gp import gp_Pnt
        wire = kernel.export_step(
            BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(1, 0, 0)).Shape()
        )
        with self.assertRaisesRegex(KernelOperationError, "no solid components"):
            kernel.import_step_assembly(wire)


if __name__ == "__main__":
    unittest.main()
