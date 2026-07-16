import unittest
import tempfile
from pathlib import Path

from fxd_geometry import OcpKernel, load_step_for_workbench


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


if __name__ == "__main__":
    unittest.main()
