import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from importlib.util import find_spec
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

if find_spec("PySide6") is None:
    raise unittest.SkipTest("PySide6 desktop runtime is not installed")

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QPushButton, QWidget

from fxd_geometry import (
    EngineeringAnnotations,
    ExportError,
    KernelOperationError,
    InteractiveWorkflow,
    OcpKernel,
    ProcessSetup,
    RenderDiagnostics,
    Vec3,
    generate_fixture_proposal,
    import_step,
    load_step_for_workbench,
    minimal_intent_questions,
    product_from_workbench_document,
    source_orientation,
)
from fxd_geometry.project import FxdProject
from fxd_qt_app import (
    EVIDENCE_PROVISIONAL,
    EVIDENCE_REAL,
    EmbeddedVtkViewport,
    ADJUSTMENT_STATE_OPTIONS,
    BASE_STRATEGY_OPTIONS,
    CLECO_STRATEGY_OPTIONS,
    CONSTRUCTION_OPTIONS,
    DIRECTION_OPTIONS,
    FxdWorkbenchWindow,
    FIXTURE_TYPE_OPTIONS,
    LIFECYCLE_OPTIONS,
    OPERATION_MODE_OPTIONS,
    ORIENTATION_METHOD_OPTIONS,
    ORIENTATION_ROTATION_OPTIONS,
    PROCESS_OPTIONS,
    REFERENCE_PLANE_OPTIONS,
    ScrollPassthroughComboBox,
    VOLUME_OPTIONS,
    _load_user32,
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

    def set_face_picking(self, enabled):
        self.calls.append(("face_picking", enabled))

    def preview_orientation(self, right, front, up):
        self.calls.append(("orientation_preview", tuple(right), tuple(front), tuple(up)))

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

    def set_review_geometry(self, items):
        self.calls.append(("review_geometry", tuple(item["identity"] for item in items)))

    def benchmark(self, frames=20):
        self.calls.append(("benchmark", frames))
        return RenderDiagnostics(
            "FakeEmbeddedOpenGL", 1, 24, 12, True, True, False,
            average_render_ms=5.25, frames_per_second=190.5,
        )


class FakeViewport(QWidget):
    face_picked = Signal(str)

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


class _OpenAiSchemaFailureProvider:
    identity = "openai"
    engine_identifier = "configured-model"
    available = True

    def generate(self, request, *, timeout_seconds, cancellation):
        raise RuntimeError("OpenAI structured-output request was rejected")


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

    def _project(self, source: Path = FIXTURE) -> FxdProject:
        product = (
            import_step(source) if source == FIXTURE
            else product_from_workbench_document(load_step_for_workbench(source))
        )
        annotations = EngineeringAnnotations.for_product(
            product,
            build_orientation=Vec3(0, 0, 1),
            loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG",
            production_quantity=1,
        )
        return FxdProject.from_product(product, annotations)

    def _load_and_annotate_real_product(self, directory: str):
        source = self._real_step(directory)
        self.window.load_step_path(source)
        self.window.reset_to_source_orientation()
        self.window.accept_manufacturing_orientation()
        self.window.process_build.setCurrentText("+Z")
        self.window.process_load.setCurrentText("+X")
        self.window.process_unload.setCurrentText("-X")
        for role_index, face_index in enumerate((0, 1, 2)):
            category = next(
                self.window.tree.topLevelItem(index)
                for index in range(self.window.tree.topLevelItemCount())
                if self.window.tree.topLevelItem(index).text(0) == "Components"
            )
            component = category.child(0)
            self.window.tree.setCurrentItem(component.child(face_index))
            self.application.processEvents()
            self.window.annotation_role.setCurrentIndex(role_index)
            with patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.assign_selected_annotation()
            self.assertFalse(warning.called, warning.call_args)
        return source

    def _show_process_panel(self) -> None:
        self.window.resize(1366, 768)
        self.window.workflow_tabs.setCurrentWidget(self.window.process_scroll)
        self.window.show()
        self.application.processEvents()

    def _wheel(self, widget: QWidget, *, angle_delta_y: int = -120) -> None:
        position = widget.rect().center()
        event = QWheelEvent(
            QPointF(position),
            QPointF(widget.mapToGlobal(position)),
            QPoint(),
            QPoint(0, angle_delta_y),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(widget, event)
        self.application.processEvents()

    def _author_m30_tack_build(self, *, source: Path = FIXTURE):
        self.window._replace_project(self._project(source))
        self.window.workflow = InteractiveWorkflow(
            self.window.project.product.source_sha256,
            ProcessSetup(
                "M30 workbench",
                manufacturing_orientation=source_orientation(
                    self.window.project.product.source_sha256, accepted=True,
                ),
            ),
            concepts_generated=True,
        )
        self.window.process_fixture_type.setCurrentText("Tack or Location Fixture")
        self.window.process_construction.setCurrentText("Tack or Location Fixture")
        self.window.process_lifecycle.setCurrentText("Disposable or job-run recut")
        self.window.process_cleco_strategy.setCurrentText("Separate fixture Cleco holes")
        self.window.process_job_revision.setText("JOB-REV-A")
        self.window.process_tack_access.setChecked(True)
        self.window.process_unload_clearance.setChecked(True)
        self.window.process_adjustment_state.setCurrentText("Locked production position")
        self.window.generate_fixture_build_plan()
        self.window.author_real_fixture_geometry()
        return self.window.project.fixture_build, self.window.authored_fixture_build

    def test_shell_creation_has_one_embedded_viewport_and_no_side_effects(self):
        self.assertIs(self.window.centralWidget().findChild(FakeViewport), self.window.viewport)
        self.assertFalse(self.window.viewport.separate_window_created)
        self.assertEqual(self.window.tree.topLevelItemCount(), 0)
        self.assertEqual(self.window._property_values["Evidence"].text(), EVIDENCE_PROVISIONAL)

    def test_brand_shell_uses_shared_assets_and_accessible_engineering_states(self):
        self.assertIn("SOURCE CAD \u00b7 READ-ONLY", self.window.source_badge.text())
        self.assertEqual(self.window.workflow_rail.count(), 19)
        self.assertFalse(self.window._actions["import"].icon().isNull())
        self.assertFalse(self.window._actions["approve"].isEnabled())
        self.assertEqual(self.window.status_validation.text_label.text(), "NOT EVALUATED")
        self.assertEqual(self.window.minimumWidth(), 1180)
        self.assertEqual(self.window.minimumHeight(), 720)

    def test_m30_tack_location_controls_create_and_author_a_fixture_build(self):
        self.window._replace_project(self._project())
        self.window.workflow = InteractiveWorkflow(
            self.window.project.product.source_sha256,
            ProcessSetup(
                "M30 workbench",
                manufacturing_orientation=source_orientation(
                    self.window.project.product.source_sha256, accepted=True,
                ),
            ),
            concepts_generated=True,
        )
        self.window.process_fixture_type.setCurrentText("Tack or Location Fixture")
        self.window.process_construction.setCurrentText("Tack or Location Fixture")
        self.window.process_lifecycle.setCurrentText("Disposable or job-run recut")
        self.window.process_job_revision.setText("JOB-REV-A")
        self.window.process_tack_access.setChecked(True)
        self.window.process_unload_clearance.setChecked(True)
        self.window.process_adjustment_state.setCurrentText("Locked production position")
        self.window.generate_fixture_build_plan()
        self.assertIsNotNone(self.window.project.fixture_build)
        self.assertEqual(self.window.project.fixture_build.requirements.fixture_purpose.value, "tack_location_fixture")
        self.window.author_real_fixture_geometry()
        self.assertIsNotNone(self.window.authored_fixture_build)
        self.assertGreater(self.window.fabrication_components.count(), 0)
        self.assertIn("REAL OCP B-REP", self.window.fabrication_components.item(0).text())

    def test_m30_authored_geometry_cache_is_cleared_and_identity_gated(self):
        plan, authored = self._author_m30_tack_build()
        self.assertIs(self.window._active_authored_fixture_build(), authored)

        with tempfile.TemporaryDirectory() as directory:
            other_path = Path(directory) / "other.fxd.json"
            self._project().save(other_path)
            self.window.load_project_path(other_path)
            self.assertIsNone(self.window.authored_fixture_build)
            self.assertFalse(any(
                item["identity"].startswith("manufacturing:")
                for item in self.window._review_geometry_items()
            ))

        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            plan, authored = self._author_m30_tack_build(source=source)
            project_path = Path(directory) / "recover.fxd.json"
            self.window.save_project_path(project_path)
            self.window.recover_autosave()
            self.assertIsNone(self.window.authored_fixture_build)

        plan, authored = self._author_m30_tack_build()
        self.window.process_job_revision.setText("JOB-REV-B")
        self.window.generate_fixture_build_plan()
        self.assertIsNone(self.window.authored_fixture_build)
        self.assertNotEqual(self.window.project.fixture_build.identity, plan.identity)

        plan, authored = self._author_m30_tack_build()
        alternate = next(
            concept.identity for concept in self.window.project.concepts
            if concept.identity != self.window.project.active_concept
        )
        self.window.select_concept(alternate)
        self.assertIsNone(self.window.authored_fixture_build)

        self.window.authored_fixture_build = authored
        self.window.project = SimpleNamespace(
            fixture_build=plan,
            product=SimpleNamespace(source_sha256="0" * 64),
        )
        self.assertIsNone(self.window._active_authored_fixture_build())

    def test_m30_provisional_build_blocks_desktop_export_and_approval(self):
        clean_validation = SimpleNamespace(
            blocked=False, status="valid", findings=(), evidence_digest="evidence"
        )
        with patch.object(
            FxdProject, "active_validation", new_callable=PropertyMock,
            return_value=clean_validation,
        ):
            self.window._replace_project(self._project())
            self.window.workflow = InteractiveWorkflow(
                self.window.project.product.source_sha256,
                ProcessSetup(
                    "M30 workbench",
                    manufacturing_orientation=source_orientation(
                        self.window.project.product.source_sha256, accepted=True,
                    ),
                ),
                concepts_generated=True,
            )
            self.window.process_fixture_type.setCurrentText("Full weld fixture")
            self.window.process_construction.setCurrentText("Welded tube-frame")
            self.window.process_lifecycle.setCurrentText("Full permanent fixture")
            self.window.process_job_revision.setText("JOB-REV-A")
            self.window.process_unload_clearance.setChecked(True)
            self.window.process_adjustment_state.setCurrentText("Locked production position")
            self.window.generate_fixture_build_plan()
            self.assertEqual(
                self.window.project.fixture_build.requirements.fixture_purpose.value,
                "full_weld_fixture",
            )
            self.assertFalse(self.window._actions["export"].isEnabled())
            self.assertFalse(self.window._actions["approve"].isEnabled())
            self.assertEqual(self.window._workflow_states()["Export"], "blocked")
            with patch("fxd_qt_app.QFileDialog.getExistingDirectory") as chooser, patch(
                "fxd_qt_app.export_project_package"
            ) as export, patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.export_package()
            chooser.assert_not_called()
            export.assert_not_called()
            warning.assert_called_once()

    def test_m30_process_controls_scroll_at_supported_desktop_size(self):
        self.window.resize(1366, 768)
        self.window.workflow_tabs.setCurrentWidget(self.window.process_scroll)
        self.window.show()
        self.application.processEvents()

        self.assertIs(self.window.process_scroll.widget(), self.window.process_form_widget)
        self.assertGreater(self.window.process_scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.window.process_tack_access.isVisible())
        self.assertTrue(self.window.process_unload_clearance.isVisible())

    def test_m30_process_selector_exposes_all_fixture_purposes(self):
        choices = {
            self.window.process_fixture_type.itemText(index)
            for index in range(self.window.process_fixture_type.count())
        }
        self.assertEqual(choices, set(FIXTURE_TYPE_OPTIONS))
        self.assertIn("Full weld fixture", choices)
        self.assertIn("Tack or Location Fixture", choices)

    def test_m30_process_controls_use_locked_deterministic_dropdowns(self):
        expected = {
            self.window.process_fixture_type: FIXTURE_TYPE_OPTIONS,
            self.window.process_method: PROCESS_OPTIONS,
            self.window.process_mode: OPERATION_MODE_OPTIONS,
            self.window.process_volume: VOLUME_OPTIONS,
            self.window.process_build: DIRECTION_OPTIONS,
            self.window.process_load: DIRECTION_OPTIONS,
            self.window.process_unload: DIRECTION_OPTIONS,
            self.window.process_base: BASE_STRATEGY_OPTIONS,
            self.window.process_construction: CONSTRUCTION_OPTIONS,
            self.window.process_lifecycle: LIFECYCLE_OPTIONS,
            self.window.process_cleco_strategy: CLECO_STRATEGY_OPTIONS,
            self.window.process_adjustment_state: ADJUSTMENT_STATE_OPTIONS,
            self.window.orientation_method: ORIENTATION_METHOD_OPTIONS,
            self.window.orientation_reference_plane: REFERENCE_PLANE_OPTIONS,
            self.window.orientation_rotation: ORIENTATION_ROTATION_OPTIONS,
        }
        for control, options in expected.items():
            with self.subTest(control=control.objectName() or type(control).__name__):
                self.assertIsInstance(control, QComboBox)
                self.assertFalse(control.isEditable())
                self.assertEqual(
                    tuple(control.itemText(index) for index in range(control.count())), options
                )
        self.window.process_fixture_type.setCurrentText("Tack or Location Fixture")
        self.window.process_construction.setCurrentText("Tack or Location Fixture")
        self.window.process_lifecycle.setCurrentText("Disposable or job-run recut")
        self.window.process_cleco_strategy.setCurrentText("Separate fixture Cleco holes")
        self.assertEqual(self.window.process_fixture_type.currentText(), "Tack or Location Fixture")
        self.assertEqual(self.window.process_construction.currentText(), "Tack or Location Fixture")
        self.assertEqual(self.window.process_lifecycle.currentText(), "Disposable or job-run recut")
        self.assertEqual(self.window.process_cleco_strategy.currentText(), "Separate fixture Cleco holes")

    def test_guided_orientation_uses_direct_bottom_and_front_face_picks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            original = source.read_bytes()
            self.window.load_step_path(source)
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            parallel = next(face for face in component.faces if face.reference != bottom.reference and abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) > 0.9)

            self.assertIs(self.window.workflow_tabs.currentWidget(), self.window.orientation_page)
            self.assertEqual(self.window.orientation_guided_step, 0)
            self.assertFalse(self.window.analyze_button.isEnabled())
            self.assertTrue(self.window.orientation_advanced_group.isHidden())

            self.window.viewport.face_picked.emit(bottom.reference)
            self.application.processEvents()
            draft = self.window.workflow.setup.manufacturing_orientation
            self.assertIsNotNone(draft)
            self.assertFalse(draft.accepted)
            self.assertIn("Bottom face selected", self.window.orientation_bottom_status.text())
            self.assertNotIn(bottom.reference, self.window.orientation_bottom_status.text())
            self.window.accept_guided_bottom_face()
            self.assertEqual(self.window.orientation_guided_step, 1)

            self.window.viewport.face_picked.emit(parallel.reference)
            self.application.processEvents()
            self.assertIn("parallel", self.window.orientation_guided_error.text())
            self.window.viewport.face_picked.emit(front.reference)
            self.application.processEvents()
            self.assertEqual(self.window.orientation_guided_error.text(), "")
            self.window.preview_guided_orientation()
            self.assertEqual(self.window.orientation_guided_step, 2)
            review_ids = next(
                call[1] for call in reversed(self.window.viewport.scene.calls)
                if call[0] == "review_geometry"
            )
            self.assertIn("orientation:build-plane", review_ids)
            self.assertIn("orientation:bottom-face", review_ids)
            self.assertIn("orientation:front-face", review_ids)
            self.assertIn("orientation:manufacturing-z", review_ids)
            self.assertIn("orientation:gravity", review_ids)
            self.assertIn("Source CAD remains unchanged", self.window.orientation_summary.text())

            self.window.accept_guided_orientation()
            accepted = self.window.workflow.setup.manufacturing_orientation
            self.assertTrue(accepted.accepted)
            self.assertIsNotNone(accepted.front_reference)
            self.assertTrue(self.window.analyze_button.isEnabled())
            self.assertIs(self.window.workflow_tabs.currentWidget(), self.window.proposal_page)
            self.assertEqual(source.read_bytes(), original)

    def test_fixture_proposal_step_generates_offline_baseline_and_hides_raw_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            original = source.read_bytes()
            self.window.load_step_path(source)
            self.window.process_fixture_type.setCurrentText("Full weld fixture")
            self.window.process_method.setCurrentText("MIG welding")
            self.window.process_mode.setCurrentText("Manual")
            self.window.process_quantity.setValue(10)
            self.window.process_lifecycle.setCurrentText("Store and reuse")
            self.window.process_load.setCurrentText("+X")
            self.window.process_unload.setCurrentText("-X")
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            unanswered = minimal_intent_questions(self.window.workflow)
            self.assertTrue(unanswered)
            with patch.object(self.window.analysis_pool, "start") as start:
                self.window.generate_fixture_proposal_action()
            start.assert_not_called()
            self.assertEqual(minimal_intent_questions(self.window.workflow), unanswered)
            self.assertFalse(self.window.proposal_interview.isHidden())
            self.window.apply_proposal_recommended_intent()
            outcome = self.window.generate_fixture_proposal_now()
        self.assertIsNotNone(self.window.project.fixture_proposal)
        self.assertEqual(outcome.provider_state.value, "ai_unavailable")
        self.assertIn("Deterministic baseline proposal", self.window.proposal_status.text())
        self.assertGreater(self.window.proposal_recommendations.count(), 0)
        normal_text = "\n".join(
            self.window.proposal_recommendations.item(index).text()
            for index in range(self.window.proposal_recommendations.count())
        )
        self.assertNotIn("face:", normal_text)
        self.assertNotIn("proposal-", normal_text)
        self.assertIn("Proposal identity:", self.window.proposal_technical_details.text())
        self.assertIn("Mode: Deterministic baseline", self.window.proposal_technical_details.text())
        self.assertIn("Fallback used: Yes", self.window.proposal_technical_details.text())
        self.assertEqual(self.window.document.source_bytes, original)

    def test_failed_openai_reason_is_visible_only_in_technical_proposal_details(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            original = source.read_bytes()
            self.window.load_step_path(source)
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            self.window.apply_proposal_recommended_intent()
            outcome = self.window.generate_fixture_proposal_now(_OpenAiSchemaFailureProvider())
        self.assertEqual(outcome.provider_state.value, "proposal_generation_failed")
        self.assertIn("Deterministic baseline proposal", self.window.proposal_status.text())
        self.assertIn(
            "Provider failure: AI proposal failed or was quarantined: "
            "OpenAI structured-output request was rejected.",
            self.window.proposal_technical_details.text(),
        )
        self.assertNotIn("OpenAI structured-output", self.window.proposal_status.text())
        self.assertEqual(self.window.document.source_bytes, original)

    def test_stale_background_proposal_completion_is_discarded_after_source_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self._real_step(directory)
            self.window.load_step_path(first)
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            self.window.apply_proposal_recommended_intent()
            old_outcome = self.window.generate_fixture_proposal_now()
            self.window.process_quantity.setValue(
                self.window.workflow.setup.production_quantity + 1
            )
            with patch.object(self.window.analysis_pool, "start") as start:
                self.window.generate_fixture_proposal_action()
            start.assert_called_once()
            old_request = self.window._proposal_request
            self.assertEqual(
                self.window.workflow.setup.production_quantity,
                self.window.process_quantity.value(),
            )
            request_outcome = generate_fixture_proposal(
                self.window.document, self.window.workflow,
                current_project=self.window.project,
            )
            self.window._replace_project(self.window.project.toggle_layer("datums"))
            self.window._proposal_completed(request_outcome, old_request)
            self.assertIn("datums", self.window.project.hidden_layers)
            self.assertIn("project evidence", self.window.statusBar().currentMessage())
            with patch.object(self.window.analysis_pool, "start") as start:
                self.window.generate_fixture_proposal_action()
            start.assert_called_once()
            old_request = self.window._proposal_request
            request_outcome = generate_fixture_proposal(
                self.window.document, self.window.workflow,
                current_project=self.window.project,
            )
            self.window.process_operator.setText(
                "changed while provider request was running"
            )
            self.window._proposal_completed(request_outcome, old_request)
            self.assertEqual(
                self.window.workflow.setup.operator_access,
                "changed while provider request was running",
            )
            self.assertIn("workflow", self.window.statusBar().currentMessage())
            replacement = Path(directory) / "replacement.step"
            replacement.write_bytes(self.kernel.export_step(
                self.kernel.make_box((0, 0, 0), (35, 18, 12))
            ))
            self.window.load_step_path(replacement)
            replacement_sha = self.window.document.source_sha256
            self.window._proposal_completed(old_outcome, old_request)
            self.assertEqual(self.window.document.source_sha256, replacement_sha)
            self.assertIsNone(self.window.project)
            self.window._proposal_request = old_request
            self.window._proposal_completed(old_outcome, old_request)
            self.assertEqual(self.window.document.source_sha256, replacement_sha)
            self.assertIsNone(self.window.project)
            self.assertIn("replaced source, workflow", self.window.statusBar().currentMessage())

    def test_proposal_selection_highlights_evidence_and_decision_is_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            self.window.apply_proposal_recommended_intent()
            self.window.generate_fixture_proposal_now()
        self.window.proposal_recommendations.setCurrentRow(0)
        self.application.processEvents()
        self.assertIn("Why proposed:", self.window.proposal_explanation.text())
        self.assertTrue(any(call[0] == "select" for call in self.window.viewport.scene.calls))
        before = self.window.project.fixture_proposal.proposal_identity
        self.window.proposal_reject_recommendation.click()
        self.assertNotEqual(self.window.project.fixture_proposal.proposal_identity, before)
        self.assertTrue(self.window.project.fixture_proposal.audit_history)

    def test_guided_validation_summary_and_fix_navigation_are_plain_language(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            self.window.apply_proposal_recommended_intent()
            self.window.generate_fixture_proposal_now()
        self.assertIn("blocking issues", self.window.guided_validation_summary.text())
        self.assertIn("warnings requiring review", self.window.guided_validation_summary.text())
        self.assertGreater(self.window.guided_issues.count(), 0)
        routed_row = next(
            index for index in range(self.window.guided_issues.count())
            if self.window._guided_issue_records[str(
                self.window.guided_issues.item(index).data(Qt.ItemDataRole.UserRole)
            )].fix_target == "proposal_recommendations"
        )
        self.window.guided_issues.setCurrentRow(routed_row)
        self.application.processEvents()
        self.assertIn("What is wrong:", self.window.guided_issue_explanation.text())
        issue = self.window._selected_guided_issue()
        self.window.fix_selected_guided_issue()
        self.assertEqual(self.window._ui_active_stage, issue.workflow_section)
        self.assertEqual(issue.workflow_section, "Proposal")
        self.assertEqual(self.window.workflow_tabs.currentIndex(), 2)
        self.assertFalse(self.window.proposal_recommendations.isHidden())

    def test_stale_orientation_keeps_proposal_visible_and_disables_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            self.window.apply_proposal_recommended_intent()
            self.window.generate_fixture_proposal_now()
        prior_identity = self.window.project.fixture_proposal.proposal_identity
        self.window.edit_orientation()
        self.window.flip_guided_bottom_side()
        self.window._refresh_all()
        self.assertIsNotNone(self.window.project)
        self.assertTrue(any(
            issue.rule_id == "proposal_stale"
            for issue in self.window.project.fixture_proposal.guided_issues
        ))
        self.assertNotEqual(self.window.project.fixture_proposal.proposal_identity, prior_identity)
        self.assertGreater(self.window.proposal_recommendations.count(), 0)
        self.assertIn("STALE", self.window.proposal_summary.text())
        self.assertFalse(self.window.proposal_accept.isEnabled())

    def test_first_run_guide_waits_for_successful_source_import(self):
        self.window._settings_enabled = True
        self.window.settings.remove("guide/fixture_proposal_dismissed")
        self.application.processEvents()
        self.assertFalse(getattr(self.window, "_first_run_dialog", None))
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
            QTest.qWait(5)
        dialog = self.window._first_run_dialog
        self.assertTrue(dialog.isVisible())
        dialog.close()
        self.window.settings.remove("guide/fixture_proposal_dismissed")

    def test_first_run_guide_ignores_failed_or_cancelled_imports(self):
        self.window._settings_enabled = True
        self.window.settings.remove("guide/fixture_proposal_dismissed")
        with patch("fxd_qt_app.QMessageBox.critical"):
            with self.assertRaises(KernelOperationError):
                self.window.load_step_path(FIXTURE)
        self.application.processEvents()
        self.assertFalse(getattr(self.window, "_first_run_dialog", None))
        with patch("fxd_qt_app.QFileDialog.getOpenFileName", return_value=("", "")):
            self.window.import_step()
        self.application.processEvents()
        self.assertFalse(getattr(self.window, "_first_run_dialog", None))
        self.window.settings.remove("guide/fixture_proposal_dismissed")

    def test_first_run_guide_can_be_disabled_and_reopened(self):
        self.window.settings.remove("guide/fixture_proposal_dismissed")
        self.window.show_first_run_guide(True)
        dialog = self.window._first_run_dialog
        self.assertTrue(dialog.isVisible())
        never = next(item for item in dialog.findChildren(QCheckBox)
                     if "show this again" in item.text())
        dismiss = next(item for item in dialog.findChildren(QPushButton)
                       if item.text() == "Dismiss")
        never.setChecked(True)
        dismiss.click()
        self.assertTrue(self.window.settings.value(
            "guide/fixture_proposal_dismissed", False, type=bool
        ))
        self.window._settings_enabled = True
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
            QTest.qWait(5)
        self.assertFalse(self.window._first_run_dialog.isVisible())
        self.window._actions["first_run_guide"].trigger()
        self.assertTrue(self.window._first_run_dialog.isVisible())
        self.window._first_run_dialog.close()
        self.window.settings.remove("guide/fixture_proposal_dismissed")

    def test_changing_guided_face_or_flip_clears_downstream_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            self.window.load_step_path(source)
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            self.window.workflow = replace(
                self.window.workflow, analysis_completed=True, concepts_generated=True,
            )
            self.window.project = self._project(source)
            self.window.authored_fixture_build = object()
            self.window.edit_orientation()
            self.window.flip_guided_bottom_side()
            self.assertIsNone(self.window.project)
            self.assertIsNone(self.window.authored_fixture_build)
            self.assertFalse(self.window.workflow.analysis_completed)
            self.assertFalse(self.window.workflow.setup.manufacturing_orientation.accepted)

    def test_auto_recommendation_requires_confirmation_and_advanced_stays_collapsed(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.load_step_path(self._real_step(directory))
            self.assertIsNone(self.window.workflow.setup.manufacturing_orientation)
            self.assertIn(
                "This appears to be the primary support face",
                self.window.orientation_recommendation_text.text(),
            )
            self.assertTrue(self.window.orientation_advanced_group.isHidden())
            self.window.use_recommended_bottom_face()
            proposal = self.window.workflow.setup.manufacturing_orientation
            self.assertIsNotNone(proposal)
            self.assertFalse(proposal.accepted)
            self.assertEqual(self.window.orientation_guided_step, 1)
            self.window.orientation_advanced_toggle.setChecked(True)
            self.assertFalse(self.window.orientation_advanced_group.isHidden())
            self.assertFalse(self.window.orientation_matrix.text() == "Not defined")
            self.assertIn("ocp_face=", self.window.orientation_raw_evidence.text())

    def test_guided_orientation_persists_after_analysis_save_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            self.window.load_step_path(source)
            component = self.window.document.assembly.components[0]
            bottom = component.faces[0]
            front = next(face for face in component.faces if abs(sum(
                left * right for left, right in zip(bottom.normal, face.normal)
            )) < 0.1)
            self.window.viewport.face_picked.emit(bottom.reference)
            self.window.accept_guided_bottom_face()
            self.window.viewport.face_picked.emit(front.reference)
            self.window.preview_guided_orientation()
            self.window.accept_guided_orientation()
            accepted = self.window.workflow.setup.manufacturing_orientation
            self.window.analyze_assembly_now()
            destination = Path(directory) / "guided.fxd.json"
            self.window.save_project_path(destination)
            self.window.load_project_path(destination)
            restored = self.window.workflow.setup.manufacturing_orientation
            self.assertEqual(restored, accepted)
            self.assertTrue(restored.accepted)
            self.assertIsNotNone(restored.front_reference)
            self.assertTrue(self.window.analyze_button.isEnabled())

    def test_source_replacement_invalidates_manufacturing_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self._real_step(directory)
            second = Path(directory) / "replacement.step"
            second.write_bytes(self.kernel.export_step(self.kernel.make_box((0, 0, 0), (40, 20, 8))))
            self.window.load_step_path(first)
            self.window.reset_to_source_orientation()
            self.window.accept_manufacturing_orientation()
            self.assertTrue(self.window.workflow.setup.manufacturing_orientation.accepted)
            self.window.load_step_path(second)
            self.assertIsNone(self.window.workflow.setup.manufacturing_orientation)
            self.assertFalse(self.window.analyze_button.isEnabled())

    def test_m30_closed_process_dropdown_wheel_scrolls_the_parent_without_changing_input(self):
        self._show_process_panel()
        controls = (
            self.window.process_fixture_type, self.window.process_method, self.window.process_mode,
            self.window.process_volume, self.window.process_build, self.window.process_load,
            self.window.process_unload, self.window.process_base, self.window.process_construction,
            self.window.process_lifecycle, self.window.process_cleco_strategy,
            self.window.process_adjustment_state,
        )
        for control in controls:
            with self.subTest(control=control.objectName() or control.currentText()):
                self.assertIsInstance(control, ScrollPassthroughComboBox)

        combo = self.window.process_fixture_type
        scroll_bar = self.window.process_scroll.verticalScrollBar()
        scroll_bar.setValue(0)
        combo.setFocus()
        selected_before = combo.currentIndex()
        self._wheel(combo)

        self.assertEqual(combo.currentIndex(), selected_before)
        self.assertGreater(scroll_bar.value(), 0)

    def test_m30_open_process_dropdown_and_keyboard_selection_remain_available(self):
        self._show_process_panel()
        combo = self.window.process_fixture_type
        target_index = 1

        combo.showPopup()
        self.application.processEvents()
        self.assertTrue(combo.view().isVisible())
        target = combo.view().visualRect(combo.model().index(target_index, 0))
        QTest.mouseClick(
            combo.view().viewport(), Qt.MouseButton.LeftButton, pos=target.center()
        )
        self.application.processEvents()
        self.assertEqual(combo.currentIndex(), target_index)

        combo.setCurrentIndex(0)
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Down)
        self.application.processEvents()
        self.assertEqual(combo.currentIndex(), target_index)

    def test_m30_process_form_grows_without_horizontal_clipping(self):
        self.window.resize(1366, 768)
        self.window.workflow_dock.raise_()
        self.window.workflow_tabs.setCurrentWidget(self.window.process_scroll)
        self.window.show()
        self.application.processEvents()
        self.window.resizeDocks(
            [self.window.workflow_dock], [400], Qt.Orientation.Horizontal
        )
        self.application.processEvents()
        narrow_width = self.window.process_fixture_type.width()
        self.assertEqual(self.window.process_scroll.horizontalScrollBar().maximum(), 0)
        self.window.resizeDocks(
            [self.window.workflow_dock], [520], Qt.Orientation.Horizontal
        )
        self.application.processEvents()
        self.assertGreater(self.window.process_fixture_type.width(), narrow_width)
        self.assertGreater(self.window.process_construction.width(), narrow_width)
        self.assertEqual(self.window.process_scroll.horizontalScrollBar().maximum(), 0)

        self.window.resize(1920, 1080)
        self.application.processEvents()
        self.assertGreaterEqual(self.window.process_fixture_type.width(), 480)
        self.assertEqual(self.window.process_scroll.horizontalScrollBar().maximum(), 0)

    def test_m30_process_selection_persists_after_save_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            self._author_m30_tack_build(source=source)
            destination = Path(directory) / "m30-process.fxd.json"
            self.window.save_project_path(destination)
            self.window.load_project_path(destination)
        self.assertEqual(self.window.process_fixture_type.currentText(), "Tack or Location Fixture")
        self.assertEqual(self.window.process_construction.currentText(), "Tack or Location Fixture")
        self.assertEqual(self.window.process_lifecycle.currentText(), "Disposable or job-run recut")
        self.assertEqual(self.window.process_cleco_strategy.currentText(), "Separate fixture Cleco holes")
        self.assertEqual(self.window.process_adjustment_state.currentText(), "Locked production position")
        self.assertEqual(self.window.process_job_revision.text(), "JOB-REV-A")

    def test_real_source_identity_badge_is_verified_without_mutating_step(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            before = source.read_bytes()
            self.window.load_step_path(source)
            self.assertEqual(source.read_bytes(), before)
            self.assertIn(source.name, self.window.source_badge.text())
            self.assertIn("VERIFIED", self.window.source_badge.text())
            self.assertIn(sha256(before).hexdigest(), self.window.source_badge.toolTip())
            self.assertEqual(self.window.renderer_health.text_label.text(), "VTK")

    def test_layout_reset_preserves_document_viewport_and_project_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            self.window.load_step_path(source)
            document = self.window.document
            viewport = self.window.viewport
            self.window.reset_workbench_layout()
            self.assertIs(self.window.document, document)
            self.assertIs(self.window.viewport, viewport)
            self.assertEqual(source.read_bytes(), document.source_bytes)

    def test_user32_loader_enables_reliable_last_error_capture(self):
        with patch(
            "fxd_qt_app.ctypes.WinDLL", return_value=object(), create=True
        ) as loader:
            self.assertIsNotNone(_load_user32())
        loader.assert_called_once_with("user32", use_last_error=True)

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
            source = self._real_step(directory)
            script = """
import json
import sys
import time
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
picked = []
viewport.face_picked.connect(picked.append)
viewport.scene.set_face_picking(True)
viewport.scene.fit()
app.processEvents()
time.sleep(0.25)
width = max(1, viewport.render_host.width())
height = max(1, viewport.render_host.height())
x, y = width // 2, height // 2
viewport.scene.simulate_face_click_for_acceptance(-1, -1)
deadline = time.monotonic() + 5.0
while not picked and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.02)
face_identities = {
    face.reference for component in document.assembly.components for face in component.faces
}
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
    "face_picked": bool(picked and picked[0] in face_identities),
    "picked_values": picked,
    "face_identity_count": len(face_identities),
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
            self.assertTrue(result["face_picked"], result)
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
        import_timing = next(
            item for item in self.window.workflow.timings if item.operation == "step_import"
        )
        self.assertGreaterEqual(import_timing.elapsed_ms, 0.0)
        self.assertIn(" ms", self.window.statusBar().currentMessage())

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

    def test_blocked_export_surfaces_authoritative_gate_without_writing(self):
        self.window.project = self._project()
        with patch("fxd_qt_app.QFileDialog.getExistingDirectory") as chooser, patch(
            "fxd_qt_app.export_project_package"
        ) as export, patch("fxd_qt_app.QMessageBox.warning") as warning:
            self.window.export_package()
        chooser.assert_not_called()
        export.assert_not_called()
        warning.assert_called_once()
        self.assertIn("validation result", warning.call_args.args[2])
        self.assertIn("Export blocked", self.window.statusBar().currentMessage())

    def test_suppressed_or_corrected_project_disables_and_blocks_export(self):
        clean_validation = SimpleNamespace(
            blocked=False, status="provisional", findings=(), evidence_digest="evidence"
        )
        with patch.object(
            FxdProject, "active_validation", new_callable=PropertyMock,
            return_value=clean_validation,
        ):
            base = self._project()
            projects = (
                replace(base, suppressed_features=frozenset({"support-1"})),
                base.correct("clamp_force", "review", "engineering correction"),
            )
            for project in projects:
                state = "suppressed" if project.suppressed_features else "corrected"
                with self.subTest(state=state):
                    self.window.project = project
                    self.window._refresh_shell_state()
                    self.assertFalse(self.window._actions["export"].isEnabled())
                    with patch(
                        "fxd_qt_app.QFileDialog.getExistingDirectory"
                    ) as chooser, patch(
                        "fxd_qt_app.export_project_package"
                    ) as export, patch("fxd_qt_app.QMessageBox.warning") as warning:
                        self.window.export_package()
                    chooser.assert_not_called()
                    export.assert_not_called()
                    warning.assert_called_once()

    def test_clean_validated_project_enables_and_exports(self):
        clean_validation = SimpleNamespace(
            blocked=False, status="provisional", findings=(), evidence_digest="evidence"
        )
        self.window.project = self._project()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            FxdProject, "active_validation", new_callable=PropertyMock,
            return_value=clean_validation,
        ), patch(
            "fxd_qt_app.QFileDialog.getExistingDirectory", return_value=directory
        ), patch(
            "fxd_qt_app.export_project_package", return_value=(Path(directory) / "manifest.json",)
        ) as export:
            self.window._refresh_shell_state()
            self.assertTrue(self.window._actions["export"].isEnabled())
            self.window.export_package()
        export.assert_called_once_with(self.window.project, directory, kernel=self.window.kernel)

    def test_interactive_analysis_wires_exact_faces_to_existing_engines(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._load_and_annotate_real_product(directory)
            before = source.read_bytes()
            with patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.analyze_assembly_now()
            self.assertFalse(warning.called, warning.call_args)
            self.assertEqual(source.read_bytes(), before)
        self.assertIsNotNone(self.window.project)
        self.assertTrue(self.window.workflow.analysis_completed)
        self.assertEqual(len(self.window.workflow.geometry_annotations), 3)
        self.assertIsNotNone(self.window.project.placement)
        self.assertTrue(self.window._property_values["Evidence digest"].text())

    def test_concepts_populate_comparison_tree_and_provisional_viewport_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            self._load_and_annotate_real_product(directory)
            with patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.analyze_assembly_now()
            self.assertFalse(warning.called, warning.call_args)
            self.window.generate_concepts()
        self.assertTrue(self.window.workflow.concepts_generated)
        self.assertEqual(self.window.concept_table.rowCount(), 3)
        self.assertEqual(self.window.concept_table.columnCount(), 18)
        self.assertEqual(
            self.window.concept_table.horizontalHeaderItem(17).text(), "Why ranked"
        )
        review_calls = [item for item in self.window.viewport.scene.calls
                        if item[0] == "review_geometry"]
        self.assertTrue(review_calls)
        self.assertTrue(review_calls[-1][1])
        titles = [self.window.tree.topLevelItem(index).text(0)
                  for index in range(self.window.tree.topLevelItemCount())]
        self.assertIn("Fixture concepts", titles)
        self.assertFalse(any(
            self.window.concept_table.item(row, 1).text() == "INVALID"
            and self.window.concept_table.item(row, 2).text() == "Recommended"
            for row in range(self.window.concept_table.rowCount())
        ))

    def test_supported_workbench_edit_records_revision_and_revalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            self._load_and_annotate_real_product(directory)
            with patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.analyze_assembly_now()
            self.assertFalse(warning.called, warning.call_args)
            self.window.generate_concepts()
        before = self.window.project.revision_id
        self.window.edit_parameter_name.setCurrentText("base_thickness")
        self.window.edit_parameter_value.setValue(18.0)
        self.window.edit_reason.setText("Increase base review thickness")
        with patch("fxd_qt_app.QMessageBox.warning") as warning:
            self.window.apply_parameter_edit()
        self.assertFalse(warning.called, warning.call_args)
        self.assertNotEqual(self.window.project.revision_id, before)
        self.assertEqual(self.window.project.active.fixture.parameters.base_thickness, 18.0)
        self.assertIsNone(self.window.project.approved_revision)
        self.assertGreaterEqual(self.window.revision_list.count(), 2)
        regeneration = next(
            item for item in self.window.workflow.timings if item.operation == "regeneration"
        )
        self.assertGreaterEqual(regeneration.elapsed_ms, 0.0)

    def test_supported_feature_move_and_suppression_use_existing_revision_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            self._load_and_annotate_real_product(directory)
            with patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.analyze_assembly_now()
            self.assertFalse(warning.called, warning.call_args)
            self.window.generate_concepts()
        target = self.window.project.active.fixture.features[0].identity
        before = self.window.project.revision_id
        self.window.edit_operation.setCurrentText("Move feature")
        self.window.edit_target.setCurrentText(target)
        self.window.edit_move_x.setValue(5.0)
        self.window.edit_reason.setText("Move for deterministic access review")
        with patch("fxd_qt_app.QMessageBox.warning") as warning:
            self.window.apply_parameter_edit()
        self.assertFalse(warning.called, warning.call_args)
        self.assertNotEqual(self.window.project.revision_id, before)
        self.assertEqual(self.window.project.edit_log[-1].operation, "move")
        self.window.edit_operation.setCurrentText("Suppress or restore feature")
        self.window.edit_target.setCurrentText(target)
        with patch("fxd_qt_app.QMessageBox.warning") as warning:
            self.window.apply_parameter_edit()
        self.assertFalse(warning.called, warning.call_args)
        self.assertIn(target, self.window.project.suppressed_features)

    def test_private_tooling_import_records_engineer_supplied_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._real_step(directory)
            self.window.load_step_path(source)
            self.window.tooling_identity.setText("private-clamp-01")
            self.window.tooling_kind.setCurrentText("clamp")
            self.window.tooling_manufacturer.setText("FXD test tooling")
            self.window.tooling_part_number.setText("TC-01")
            self.window.tooling_revision.setText("B")
            self.window.tooling_mount_direction.setCurrentText("+Z")
            self.window.tooling_work_direction.setCurrentText("-Z")
            self.window.tooling_stroke.setValue(32.0)
            self.window.tooling_reach.setValue(85.0)
            self.window.tooling_force.setValue(1200.0)
            self.window.tooling_verified.setChecked(True)
            with patch(
                "fxd_qt_app.QFileDialog.getOpenFileName", return_value=(str(source), "")
            ), patch("fxd_qt_app.QMessageBox.warning") as warning:
                self.window.import_customer_tooling()
        self.assertFalse(warning.called, warning.call_args)
        record = self.window.workflow.customer_tooling[0]
        self.assertEqual(record.identity, "private-clamp-01")
        self.assertEqual(record.manufacturer, "FXD test tooling")
        self.assertEqual(record.mounting_direction, Vec3(0, 0, 1))
        self.assertEqual(record.force_n, 1200.0)
        self.assertTrue(record.verified)

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

    def test_export_passes_real_ocp_kernel_to_manufacturing_package(self):
        self.window.project = self._project()
        clean_validation = SimpleNamespace(blocked=False)
        with tempfile.TemporaryDirectory() as directory, patch.object(
            FxdProject, "active_validation", new_callable=PropertyMock,
            return_value=clean_validation,
        ):
            with patch(
                "fxd_qt_app.QFileDialog.getExistingDirectory", return_value=directory
            ), patch(
                "fxd_qt_app.export_project_package", return_value=(Path(directory) / "manifest.json",)
            ) as export:
                self.window.export_package()
        export.assert_called_once_with(self.window.project, directory, kernel=self.window.kernel)
        self.assertIsInstance(self.window.kernel, OcpKernel)


if __name__ == "__main__":
    unittest.main()
