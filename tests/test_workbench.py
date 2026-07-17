import unittest
import tempfile
import os
from pathlib import Path
from importlib.util import find_spec
import tkinter as tk

from fxd_geometry import (KernelOperationError, OcpKernel, StepImportError, VtkWorkbenchViewer,
                          import_step, load_step_for_workbench)
from fxd_app import FxdApp


class WorkbenchTests(unittest.TestCase):
    def test_loads_step_with_real_ocp_display_evidence(self):
        kernel = OcpKernel()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "real_box.step"
            source.write_bytes(kernel.export_step(kernel.make_box((0, 0, 0), (40, 30, 20))))
            with self.assertLogs(level="INFO") as logs:
                document = load_step_for_workbench(source, kernel=kernel)
            self.assertEqual(document.source_name, source.name)
            self.assertEqual(document.source_bytes, source.read_bytes())
        diagnostic_text = "\n".join(logs.output)
        self.assertIn("STEP read status=", diagnostic_text)
        self.assertIn("STEP roots=", diagnostic_text)
        self.assertIn("face_count=", diagnostic_text)
        self.assertIn("triangle_count=", diagnostic_text)
        self.assertEqual(document.source_name, source.name)
        self.assertEqual(document.units, "mm")
        self.assertGreater(document.component_count, 0)
        self.assertTrue(document.meshes)

    def test_synthetic_fixture_is_neutral_metadata_not_ordinary_brep(self):
        source = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"
        self.assertIsNotNone(import_step(source))
        with self.assertLogs("fxd.workbench", level="ERROR") as logs:
            with self.assertRaises(KernelOperationError):
                load_step_for_workbench(source, kernel=OcpKernel())
        self.assertIn("complete STEP import traceback", "\n".join(logs.output))

    def test_generated_compound_and_multiple_root_step_use_transferred_geometry(self):
        kernel = OcpKernel()
        shape = kernel.compound((kernel.make_box((0, 0, 0), (10, 10, 10)),
                                 kernel.make_box((20, 0, 0), (30, 10, 10))))
        data = kernel.export_step(shape)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "compound.step"
            source.write_bytes(data)
            document = load_step_for_workbench(source, kernel=kernel)
        counts = kernel.topology_counts(document.shape)
        self.assertEqual(counts.solids, 2)
        self.assertGreater(len(document.meshes), 0)
        self.assertGreater(sum(len(mesh.triangles) for mesh in document.meshes), 0)
        with self.assertRaises(StepImportError):
            import_step(data.decode("utf-8"))

    def test_camera_controls_have_deterministic_standard_views_and_fit(self):
        app = FxdApp.__new__(FxdApp)
        app.yaw, app.pitch = 35.0, 22.0
        app.pan_x, app.pan_y, app.zoom = 20.0, -10.0, 2.0
        app.vtk_viewer = None
        app.status = type("Status", (), {"set": lambda self, value: setattr(self, "value", value)})()
        app.render = lambda: None
        app.set_standard_view("front")
        self.assertEqual((app.yaw, app.pitch, app.pan_x, app.pan_y, app.zoom), (0.0, 0.0, 0.0, 0.0, 1.0))
        app.set_standard_view("top")
        self.assertEqual((app.yaw, app.pitch), (0.0, 90.0))
        app.fit_view()
        self.assertEqual((app.yaw, app.pitch, app.pan_x, app.pan_y, app.zoom), (35.0, 22.0, 0.0, 0.0, 1.0))

    @unittest.skipUnless(
        find_spec("vtk") and (os.name == "nt" or os.environ.get("DISPLAY")),
        "VTK/Tk display is unavailable",
    )
    def test_persistent_vtk_scene_defaults_and_camera_controls(self):
        kernel = OcpKernel()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "real_box.step"
            source.write_bytes(kernel.export_step(kernel.make_box((0, 0, 0), (40, 30, 20))))
            document = load_step_for_workbench(source, kernel=kernel)
        root = tk.Tk()
        root.withdraw()
        try:
            viewer = VtkWorkbenchViewer(root, document)
            mapper_input = viewer.actor.GetMapper().GetInput()
            self.assertFalse(viewer.wireframe)
            self.assertFalse(viewer.transparent)
            self.assertEqual(viewer.actor.GetProperty().GetRepresentation(), 2)
            self.assertEqual(viewer.actor.GetProperty().GetOpacity(), 1.0)
            self.assertEqual(mapper_input.GetNumberOfPolys(), sum(len(mesh.triangles) for mesh in document.meshes))
            source_identities = set(viewer.source_actor_identities)
            viewer.set_review_geometry(({
                "identity": "fixture-review-base",
                "minimum": (-5.0, -5.0, -5.0),
                "maximum": (45.0, 35.0, -1.0),
                "status": "provisional",
            },))
            self.assertEqual(set(viewer.source_actor_identities), source_identities)
            self.assertEqual(viewer.review_actor_identities, {"fixture-review-base"})
            self.assertEqual(viewer.actors["fixture-review-base"].GetProperty().GetRepresentation(), 1)
            self.assertEqual(viewer.actors["fixture-review-base"].GetProperty().GetOpacity(), 0.55)
            viewer.set_wireframe(True)
            viewer.set_transparent(True)
            viewer.set_visible(False)
            self.assertEqual(viewer.actor.GetVisibility(), 0)
            self.assertEqual(viewer.actors["fixture-review-base"].GetVisibility(), 1)
            viewer.set_visible(True)
            viewer.set_orbit(False)
            self.assertTrue(viewer.wireframe)
            self.assertTrue(viewer.transparent)
            self.assertFalse(viewer.orbit_enabled)
            self.assertIs(viewer.actor.GetMapper().GetInput(), mapper_input)
            viewer.standard_view("isometric")
            viewer.fit()
            viewer.destroy()
        finally:
            root.destroy()

    def test_default_workbench_path_uses_hardened_zero_based_meshes(self):
        base_kernel = OcpKernel()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "real_box.step"
            source.write_bytes(base_kernel.export_step(base_kernel.make_box((0, 0, 0), (12, 10, 8))))
            document = load_step_for_workbench(source)
        self.assertTrue(document.meshes)
        self.assertTrue(all(
            0 <= index < len(mesh.vertices_mm)
            for mesh in document.meshes
            for triangle in mesh.triangles
            for index in triangle
        ))

    def test_neutral_metadata_cannot_be_presented_as_authoritative_ocp(self):
        source = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"
        with self.assertRaises(KernelOperationError):
            load_step_for_workbench(source)


if __name__ == "__main__":
    unittest.main()
