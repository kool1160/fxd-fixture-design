import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import subprocess
import sys
import tempfile
import unittest
from importlib.util import find_spec
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

if find_spec("PySide6") is None:
    raise unittest.SkipTest("PySide6 desktop runtime is not installed")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from fxd_geometry import (
    EngineeringAnnotations,
    KernelOperationError,
    OcpKernel,
    RenderDiagnostics,
    Vec3,
    import_step,
)
from fxd_geometry.project import FxdProject
from fxd_qt_app import (
    EVIDENCE_PROVISIONAL,
    EVIDENCE_REAL,
    EmbeddedVtkViewport,
    FxdWorkbenchWindow,
    create_application,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_assembly.step"


class FakeScene:
    def __init__(self):
        self.calls = []
        self.selected_identity = None

    def fit(self):
        self.calls.append(("fit",))

    def standard_view(self, view):
        self.calls.append(("view", view))

    def set_navigation_mode(self, mode):
        self.calls.append(("navigation", mode))

    def set_wireframe(self, enabled):
        self.calls.append(("wireframe", enabled))

    def set_transparent(self, enabled):
        self.calls.append(("transparent", enabled))

    def set_visible(self, enabled):
        self.calls.append(("visible", enabled))

    def select(self, identity, focus=False):
        self.selected_identity = identity
        self.calls.append(("select", identity, focus))
        return identity.startswith("component:") or identity == "source:geometry"

    def benchmark(self, frames=20):
        self.calls.append(("benchmark", frames))
        return RenderDiagnostics(
            "FakeEmbeddedOpenGL", 1, 24, 12, True, True, False,
            average_render_ms=5.25, frames_per_second=190.5,
        )


class FakeViewport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = FakeScene()
        self.document = None
        self.separate_window_created = False
        self.closed = False

    def load_document(self, document):
        self.document = document

    def clear(self):
        self.document = None
        self.scene = None

    def diagnostics(self):
        if self.document is None:
            return None
        return RenderDiagnostics(
            "FakeEmbeddedOpenGL", 1, 24,
            sum(len(mesh.triangles) for mesh in self.document.meshes),
            True, True, False,
        )

    def close_viewport(self):
        self.closed = True


class FailingViewport(FakeViewport):
    def load_document(self, document):
        self.document = document
        raise RuntimeError("injected native renderer startup failure")


class QtWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = create_application([])
        cls.kernel = OcpKernel()

    def setUp(self):
        self.window = FxdWorkbenchWindow(viewport_factory=FakeViewport)

    def tearDown(self):
        self.window.close()
        self.application.processEvents()

    def _real_step(self, directory: str, *, compound: bool = False) -> Path:
        first = self.kernel.make_box((0, 0, 0), (20, 15, 10))
        shape = first
        if compound:
            second = self.kernel.make_box((30, 0, 0), (40, 12, 8))
            shape = self.kernel.compound((first, second))
        source = Path(directory) / "ordinary.step"
        source.write_bytes(self.kernel.export_step(shape))
        return source

    def _project(self) -> FxdProject:
        product = import_step(FIXTURE)
        annotations = EngineeringAnnotations.for_product(
            product,
            build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG",
            production_quantity=1,
        )
        return FxdProject.from_product(product, annotations)

    def test_shell_creation_has_one_embedded_viewport_and_no_side_effects(self):
        self.assertIs(self.window.centralWidget().findChild(FakeViewport), self.window.viewport)
        self.assertFalse(self.window.viewport.separate_window_created)
        self.assertEqual(self.window.tree.topLevelItemCount(), 0)
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_PROVISIONAL)

    @unittest.skipUnless(os.name == "nt", "native embedded VTK is Windows-only")
    def test_real_vtk_host_is_a_child_not_a_separate_window(self):
        viewport = EmbeddedVtkViewport()
        try:
            self.assertIsNotNone(viewport.render_host)
            self.assertFalse(viewport.render_host.isWindow())
            self.assertFalse(viewport.separate_window_created)
        finally:
            viewport.close_viewport()
            viewport.close()

    @unittest.skipUnless(
        os.name == "nt" and not os.environ.get("CI"),
        "live native HWND embedding requires an interactive Windows desktop",
    )
    def test_live_native_worker_embeds_real_source_and_closes_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory, compound=True)
            script = """
import json
import sys
from fxd_geometry import load_step_for_workbench
from fxd_qt_app import EmbeddedVtkViewport, create_application

app = create_application([])
document = load_step_for_workbench(sys.argv[1])
viewport = EmbeddedVtkViewport()
viewport.resize(640, 480)
viewport.show()
app.processEvents()
viewport.load_document(document)
diagnostics = viewport.diagnostics()
worker = viewport.worker
result = {
    "native_window": bool(viewport.native_window_id),
    "worker_running": worker is not None and worker.poll() is None,
    "native": diagnostics.native_rendering_active,
    "fallback": diagnostics.fallback_active,
    "triangles": diagnostics.triangle_count,
    "selection_mapped": viewport.scene.select(
        document.assembly.components[0].reference
        if document.assembly.components else "source:geometry"
    ),
    "source_unchanged": document.source_bytes == open(sys.argv[1], "rb").read(),
}
viewport.close_viewport()
viewport.close()
app.processEvents()
result["worker_closed"] = worker is not None and worker.poll() is not None
print(json.dumps(result, sort_keys=True))
"""
            environment = os.environ.copy()
            environment.pop("QT_QPA_PLATFORM", None)
            completed = subprocess.run(
                [sys.executable, "-c", script, str(source)],
                cwd=Path(__file__).parents[1], env=environment,
                text=True, capture_output=True, timeout=90, check=True,
            )
            result = json.loads(completed.stdout.strip().splitlines()[-1])
            self.assertTrue(result["native_window"])
            self.assertTrue(result["worker_running"])
            self.assertTrue(result["native"])
            self.assertFalse(result["fallback"])
            self.assertGreater(result["triangles"], 0)
            self.assertTrue(result["selection_mapped"])
            self.assertTrue(result["source_unchanged"])
            self.assertTrue(result["worker_closed"])

    def test_real_step_populates_tree_properties_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory, compound=True)
            before = source.read_bytes()
            self.window.load_step_path(source)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(self.window.document.source_sha256, sha256(before).hexdigest())
        titles = [
            self.window.tree.topLevelItem(index).text(0)
            for index in range(self.window.tree.topLevelItemCount())
        ]
        self.assertIn("Imported assembly", titles)
        self.assertIn("Components", titles)
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_REAL)
        self.assertGreater(int(self.window._property_values["Faces"].text()), 0)
        self.assertGreater(int(self.window._property_values["Triangles"].text()), 0)
        self.assertFalse(self.window.viewport.separate_window_created)

    def test_component_selection_preserves_identity_and_routes_to_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
        component_category = next(
            self.window.tree.topLevelItem(index)
            for index in range(self.window.tree.topLevelItemCount())
            if self.window.tree.topLevelItem(index).text(0) == "Components"
        )
        component = component_category.child(0)
        self.window.tree.setCurrentItem(component)
        self.application.processEvents()
        identity = component.data(0, Qt.ItemDataRole.UserRole)
        self.assertEqual(self.window.selected_identity, identity)
        self.assertEqual(self.window._property_values["Selected identity"].text(), identity)

    def test_display_and_camera_commands_reach_persistent_scene(self):
        scene = self.window.viewport.scene
        self.window.fit_view()
        self.window.set_standard_view("bottom")
        self.window.set_navigation_mode("pan")
        self.window._actions["wireframe"].setChecked(True)
        self.window.toggle_wireframe()
        self.window._actions["transparency"].setChecked(True)
        self.window.toggle_transparency()
        self.assertEqual(
            scene.calls,
            [("fit",), ("view", "bottom"), ("navigation", "pan"),
             ("wireframe", True), ("transparent", True)],
        )

    def test_benchmark_updates_registered_property_rows(self):
        self.window.viewport.document = object()
        result = self.window.benchmark_renderer(frames=12)
        self.assertEqual(result.average_render_ms, 5.25)
        self.assertEqual(self.window._property_values["Average render"].text(), "5.25 ms")
        self.assertEqual(self.window._property_values["Visible FPS"].text(), "190.5")
        self.assertIn(("benchmark", 12), self.window.viewport.scene.calls)

    def test_metadata_only_step_fails_closed_and_never_claims_real_ocp(self):
        with patch("fxd_qt_app.QMessageBox.critical"):
            with self.assertRaises(KernelOperationError):
                self.window.load_step_path(FIXTURE)
        self.assertIsNone(self.window.document)
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_PROVISIONAL)

    def test_failed_replacement_clears_previous_real_source_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_REAL)
        with patch("fxd_qt_app.QMessageBox.critical"):
            with self.assertRaises(KernelOperationError):
                self.window.load_step_path(FIXTURE)
        self.assertIsNone(self.window.document)
        self.assertIsNone(self.window.viewport.document)
        self.assertEqual(self.window.tree.topLevelItemCount(), 0)
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_PROVISIONAL)
        self.assertEqual(self.window._property_values["Source SHA-256"].text(), "-")

    def test_project_open_save_and_provisional_evidence_remain_functional(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "project.fxd.json"
            destination = Path(directory) / "saved.fxd.json"
            self._project().save(source)
            self.window.load_project_path(source)
            self.assertTrue(self.window._actions["layer_product"].isEnabled())
            self.window._actions["layer_product"].setChecked(False)
            self.window.toggle_project_layer("product")
            self.window.save_project_path(destination)
            restored = FxdProject.load(destination)
        self.assertEqual(restored.product.source_sha256, self.window.project.product.source_sha256)
        self.assertIn("product", restored.hidden_layers)
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_PROVISIONAL)
        titles = [
            self.window.tree.topLevelItem(index).text(0)
            for index in range(self.window.tree.topLevelItemCount())
        ]
        self.assertIn("Product geometry", titles)
        self.assertTrue(self.window.findings.count())

    def test_project_remains_open_when_native_renderer_startup_fails(self):
        window = FxdWorkbenchWindow(viewport_factory=FailingViewport)
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "project.fxd.json"
                project = self._project()
                project.save(source)
                with patch("fxd_qt_app.load_step_for_workbench", return_value=object()):
                    window.load_project_path(source)
            self.assertEqual(window.project.revision_id, project.revision_id)
            self.assertIsNone(window.document)
            self.assertIsNone(window.viewport.document)
            self.assertEqual(window._property_values["Evidence"].text(), EVIDENCE_PROVISIONAL)
            titles = [
                window.tree.topLevelItem(index).text(0)
                for index in range(window.tree.topLevelItemCount())
            ]
            self.assertIn("Product geometry", titles)
        finally:
            window.close()
            self.application.processEvents()


if __name__ == "__main__":
    unittest.main()
