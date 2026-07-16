import unittest
import tempfile
from pathlib import Path

from fxd_geometry import OcpKernel, load_step_for_workbench
from fxd_app import FxdApp


class WorkbenchTests(unittest.TestCase):
    def test_loads_step_with_real_ocp_display_evidence(self):
        kernel = OcpKernel()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "real_box.step"
            source.write_bytes(kernel.export_step(kernel.make_box((0, 0, 0), (40, 30, 20))))
            document = load_step_for_workbench(source, kernel=kernel)
            self.assertEqual(document.source_name, source.name)
            self.assertEqual(document.source_bytes, source.read_bytes())
        self.assertEqual(document.source_name, source.name)
        self.assertEqual(document.units, "mm")
        self.assertGreater(document.component_count, 0)
        self.assertTrue(document.meshes)

    def test_synthetic_fixture_uses_explicit_real_ocp_proof_fallback(self):
        source = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"
        document = load_step_for_workbench(source, kernel=OcpKernel())
        self.assertTrue(document.provisional)
        self.assertGreater(document.component_count, 0)
        self.assertTrue(document.meshes)
        self.assertEqual(document.source_bytes, source.read_bytes())

    def test_camera_controls_have_deterministic_standard_views_and_fit(self):
        app = FxdApp.__new__(FxdApp)
        app.yaw, app.pitch = 35.0, 22.0
        app.pan_x, app.pan_y, app.zoom = 20.0, -10.0, 2.0
        app.status = type("Status", (), {"set": lambda self, value: setattr(self, "value", value)})()
        app.render = lambda: None
        app.set_standard_view("front")
        self.assertEqual((app.yaw, app.pitch, app.pan_x, app.pan_y, app.zoom), (0.0, 0.0, 0.0, 0.0, 1.0))
        app.set_standard_view("top")
        self.assertEqual((app.yaw, app.pitch), (0.0, 90.0))
        app.fit_view()
        self.assertEqual((app.yaw, app.pitch, app.pan_x, app.pan_y, app.zoom), (35.0, 22.0, 0.0, 0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
