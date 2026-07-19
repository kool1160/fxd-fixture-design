"""Unified PySide6 engineering workbench with an embedded VTK viewport."""
from __future__ import annotations

import logging
import os
import sys
import ctypes
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
import tempfile
from threading import Thread
from time import monotonic, perf_counter
from typing import Callable

from PySide6.QtCore import QObject, QPointF, QRunnable, QSettings, QSize, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from fxd_ui import (
    ApprovalGatePanel,
    SourceCadBadge,
    StatusChip,
    WorkflowRail,
    apply_fxd_theme,
    application_icon,
    asset_path,
    icon,
)
from fxd_ui.theme.tokens import COLORS
from fxd_geometry import (
    AdjustmentState,
    AiFixtureProvider,
    AnnotationRole,
    CancellationToken,
    ConstructionMethod,
    FixtureLifecycle,
    FixturePurpose,
    FixtureBuildRequirements,
    FixtureBuildError,
    ExportError,
    GeometryReference,
    InteractiveWorkflow,
    InteractiveWorkflowError,
    KernelOperationError,
    ManufacturingOrientation,
    ManufacturingOrientationError,
    MissingIntentError,
    OcpKernel,
    OperationTiming,
    ProcessSetup,
    ProviderState,
    RecommendationDecision,
    OrientationMethod,
    ReferencePlane,
    RenderDiagnostics,
    Vec3,
    author_fixture_build,
    WorkbenchDocument,
    analyze_engineering_workflow,
    apply_recommended_intent,
    compare_concepts,
    face_annotation,
    load_step_for_workbench,
    product_from_workbench_document,
    generate_fixture_build_plan as generate_m30_fixture_build_plan,
    generate_fixture_proposal,
    minimal_intent_questions,
    orientation_from_face,
    orientation_from_faces,
    orientation_from_plane,
    recommend_orientations,
    reference_plane_orientation,
    proposal_engineering_context_identity,
    tooling_record_from_file,
)
from fxd_geometry.operations import (
    ProjectRecovery,
    StructuredLog,
    export_project_package,
    project_export_block_reason,
)
from fxd_geometry.project import FxdProject, ProjectFormatError, SUPPORTED_LAYERS


logger = logging.getLogger("fxd.qt_app")
EVIDENCE_REAL = "REAL OCP source geometry"
EVIDENCE_PROVISIONAL = "Provisional - real-kernel evidence unavailable"

FIXTURE_TYPE_OPTIONS = (
    "Full weld fixture", "Tack or Location Fixture", "Assembly fixture",
    "Inspection fixture", "Profile check fixture", "Go/no-go gauge",
    "Rework fixture", "Robotic or cobot fixture", "Combined build-and-check fixture",
)
PROCESS_OPTIONS = (
    "MIG welding", "TIG welding", "Resistance welding", "Manual assembly",
    "Laser cutting", "Machining", "Unknown",
)
OPERATION_MODE_OPTIONS = ("Manual", "Cobot", "Robotic", "Unknown")
VOLUME_OPTIONS = ("Low", "Medium", "High", "Unknown")
DIRECTION_OPTIONS = ("+X", "-X", "+Y", "-Y", "+Z", "-Z", "Unknown")
BASE_STRATEGY_OPTIONS = ("Auto", "Baseplate", "Welded frame", "Hybrid", "CNC-machined", "Unknown")
CONSTRUCTION_OPTIONS = (
    "Auto-select", "Laser-cut fabricated", "CNC-machined", "Hybrid",
    "Welded tube-frame", "Shop-standard", "Tack or Location Fixture",
)
LIFECYCLE_OPTIONS = (
    "Store and reuse", "Disposable or job-run recut",
    "Reusable tooling on disposable fixture", "Full permanent fixture",
)
CLECO_STRATEGY_OPTIONS = ("None", "Separate fixture Cleco holes", "Product Cleco holes")
ADJUSTMENT_STATE_OPTIONS = (
    "Provisional adjustment", "Prove-out setting", "Locked production position",
    "Doweled production position", "Revalidation required",
)
ORIENTATION_METHOD_OPTIONS = (
    "Auto recommend", "Select planar face", "Select reference plane", "Use source orientation",
)
REFERENCE_PLANE_OPTIONS = (
    "Front Plane", "Top Plane", "Right Plane", "Selected planar face", "Custom plane",
)
ORIENTATION_ROTATION_OPTIONS = ("0 degrees", "90 degrees", "180 degrees", "270 degrees", "Custom angle")


class ScrollPassthroughComboBox(QComboBox):
    """Keep closed engineering selectors from consuming scroll-wheel input."""

    def wheelEvent(self, event) -> None:
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                target = parent.viewport()
                global_position = event.globalPosition()
                local_position = QPointF(target.mapFromGlobal(global_position.toPoint()))
                forwarded = QWheelEvent(
                    local_position,
                    global_position,
                    event.pixelDelta(),
                    event.angleDelta(),
                    event.buttons(),
                    event.modifiers(),
                    event.phase(),
                    event.inverted(),
                )
                QApplication.sendEvent(target, forwarded)
                event.accept()
                return
            parent = parent.parentWidget()
        # Preserve standard Qt propagation when the combo is not in a scroll area.
        event.ignore()


def _load_user32():
    """Load User32 with reliable thread-local Win32 error propagation."""
    return ctypes.WinDLL("user32", use_last_error=True)


class _AnalysisSignals(QObject):
    completed = Signal(object, int, bytes)
    failed = Signal(str, int)


class _AnalysisTask(QRunnable):
    """Run CAD-neutral deterministic analysis away from the Qt GUI thread."""

    def __init__(self, document: WorkbenchDocument, workflow: InteractiveWorkflow,
                 request_id: int) -> None:
        super().__init__()
        self.document = document
        self.workflow = workflow
        self.request_id = request_id
        self.signals = _AnalysisSignals()

    def run(self) -> None:
        try:
            project = analyze_engineering_workflow(self.document, self.workflow)
            self.signals.completed.emit(project, self.request_id, self.document.source_bytes)
        except Exception as exc:
            logger.exception("background deterministic engineering analysis failed")
            self.signals.failed.emit(str(exc), self.request_id)


class _ProposalSignals(QObject):
    completed = Signal(object, int)
    failed = Signal(str, int)


class _ProposalTask(QRunnable):
    """Run the provider-neutral proposal pipeline without blocking Qt."""

    def __init__(self, document: WorkbenchDocument, workflow: InteractiveWorkflow,
                 request_id: int, provider: AiFixtureProvider | None,
                 cancellation: CancellationToken, prior_proposal: object | None = None,
                 current_project: FxdProject | None = None) -> None:
        super().__init__()
        self.document = document
        self.workflow = workflow
        self.request_id = request_id
        self.provider = provider
        self.cancellation = cancellation
        self.prior_proposal = prior_proposal
        self.current_project = current_project
        self.signals = _ProposalSignals()

    def run(self) -> None:
        try:
            outcome = generate_fixture_proposal(
                self.document, self.workflow, provider=self.provider,
                cancellation=self.cancellation, prior_proposal=self.prior_proposal,
                current_project=self.current_project,
            )
            self.signals.completed.emit(outcome, self.request_id)
        except Exception as exc:
            logger.exception("background fixture proposal generation failed")
            self.signals.failed.emit(str(exc), self.request_id)


class VtkWorkerSceneProxy:
    """Control proxy for the isolated native renderer process."""

    def __init__(self, process: subprocess.Popen[str],
                 messages: Queue[dict[str, object]], ready: dict[str, object]) -> None:
        self.process = process
        self.messages = messages
        self.ready = ready
        self._request_id = 0
        self._responses: dict[int, dict[str, object]] = {}

    def _send(self, command: str, **values: object) -> None:
        if self.process.poll() is not None or self.process.stdin is None:
            raise RuntimeError("native VTK worker is not running")
        message = {"command": command, **values}
        self.process.stdin.write(json.dumps(message, sort_keys=True) + "\n")
        self.process.stdin.flush()

    def fit(self) -> None:
        self._send("fit")

    def standard_view(self, view: str) -> None:
        self._send("standard_view", view=view)

    def set_wireframe(self, enabled: bool) -> None:
        self._send("set_wireframe", enabled=enabled)

    def set_transparent(self, enabled: bool) -> None:
        self._send("set_transparent", enabled=enabled)

    def set_visible(self, enabled: bool) -> None:
        self._send("set_visible", enabled=enabled)

    def set_orbit(self, enabled: bool) -> None:
        self._send("set_orbit", enabled=enabled)

    def set_navigation_mode(self, mode: str) -> None:
        self._send("set_navigation_mode", mode=mode)

    def set_face_picking(self, enabled: bool) -> None:
        self._send("set_face_picking", enabled=enabled)

    def set_size(self, width: int, height: int) -> None:
        self._send("set_size", width=int(width), height=int(height))

    def preview_orientation(self, right, front, up) -> None:
        self._send(
            "preview_orientation", right=list(right), front=list(front), up=list(up)
        )

    def simulate_face_click_for_acceptance(self, x: int, y: int) -> None:
        """Exercise the native interactor event path in Windows acceptance tests."""
        self._send("simulate_face_click_for_acceptance", x=int(x), y=int(y))

    def select(self, identity: str) -> bool:
        self._send("select", identity=identity)
        identities = self.ready.get("selection_identities", self.ready.get("actor_identities", []))
        return identity in identities

    def set_review_geometry(self, items: list[dict[str, object]]) -> None:
        self._send("set_review_geometry", items=items)

    def render(self) -> None:
        self._send("render")

    def diagnostics(self, *, average_render_ms: float | None = None,
                    frames_per_second: float | None = None) -> RenderDiagnostics:
        return RenderDiagnostics(
            backend=str(self.ready["backend"]),
            actor_count=int(self.ready["actor_count"]),
            point_count=int(self.ready["point_count"]),
            triangle_count=int(self.ready["triangle_count"]),
            initialized=True,
            native_rendering_active=True,
            fallback_active=False,
            average_render_ms=average_render_ms,
            frames_per_second=frames_per_second,
        )

    def benchmark(self, frames: int = 20) -> RenderDiagnostics:
        self._request_id += 1
        request_id = self._request_id
        self._send("benchmark", frames=frames, request_id=request_id)
        deadline = monotonic() + 30.0
        while monotonic() < deadline:
            response = self._responses.pop(request_id, None)
            if response is not None:
                if response.get("event") == "error":
                    raise RuntimeError(str(response.get("message", "VTK benchmark failed")))
                return self.diagnostics(
                    average_render_ms=float(response["average_render_ms"]),
                    frames_per_second=float(response["frames_per_second"]),
                )
            try:
                message = self.messages.get(timeout=0.25)
            except Empty:
                if self.process.poll() is not None:
                    raise RuntimeError("native VTK worker exited during benchmark")
                continue
            self._route_message(message)
        raise TimeoutError("native VTK benchmark did not respond")

    def _route_message(self, message: dict[str, object]) -> dict[str, object] | None:
        request_id = message.get("request_id")
        if isinstance(request_id, int):
            self._responses[request_id] = message
            return None
        return message

    def poll_events(self) -> tuple[dict[str, object], ...]:
        events: list[dict[str, object]] = []
        while True:
            try:
                message = self.messages.get_nowait()
            except Empty:
                break
            event = self._route_message(message)
            if event is not None:
                events.append(event)
        return tuple(events)

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self._send("shutdown")
                self.process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.process.terminate()
                self.process.wait(timeout=5)


class EmbeddedVtkViewport(QFrame):
    """A supervised Win32 VTK render child embedded in the Qt workbench."""

    face_picked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if os.name != "nt":
            raise RuntimeError("the embedded native VTK viewport requires Windows")
        self.user32 = _load_user32()
        self.setObjectName("embeddedVtkViewport")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.render_host = QWidget(self)
        self.render_host.setObjectName("vtkNativeRenderHost")
        self.render_host.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.render_host.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.render_host.setStyleSheet(f"background: {COLORS.carbon};")
        self.native_title = f"FXD Embedded VTK {os.getpid()} {id(self)}"
        self.native_window_id: int | None = None
        self.worker: subprocess.Popen[str] | None = None
        self.messages: Queue[dict[str, object]] = Queue()
        self.scene: VtkWorkerSceneProxy | None = None
        self.initialization_error: str | None = None
        self.separate_window_created = False
        self._message_timer = QTimer(self)
        self._message_timer.setInterval(20)
        self._message_timer.timeout.connect(self._poll_worker_messages)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(16)
        self._resize_timer.timeout.connect(self._apply_native_resize)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.render_host)

    def load_document(self, document: WorkbenchDocument) -> None:
        self.clear()
        temporary_source: Path | None = None
        try:
            source = document.source_path
            if source is None:
                handle, name = tempfile.mkstemp(suffix=".step", prefix="fxd-view-")
                os.close(handle)
                temporary_source = Path(name)
                temporary_source.write_bytes(document.source_bytes)
                source = temporary_source
            elif sha256(source.read_bytes()).hexdigest() != document.source_sha256:
                raise RuntimeError("source STEP changed before viewport launch")
            self.worker = self._launch_worker(source, document.source_sha256)
            ready = self._wait_for_ready(self.worker)
            self.scene = VtkWorkerSceneProxy(self.worker, self.messages, ready)
            self._embed_native_window()
            self._message_timer.start()
            self.initialization_error = None
        except Exception as exc:
            self.clear()
            self.initialization_error = str(exc)
            logger.exception("embedded VTK initialization failed")
            raise
        finally:
            if temporary_source is not None:
                temporary_source.unlink(missing_ok=True)

    def _launch_worker(self, source: Path, expected_sha256: str) -> subprocess.Popen[str]:
        creationflags = 0x08000000 if os.name == "nt" else 0
        process = subprocess.Popen(
            [sys.executable, "-u", "-m", "fxd_geometry.vtk_worker",
             str(source), expected_sha256, self.native_title],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, creationflags=creationflags,
        )

        def read_output() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        self.messages.put(value)
                except json.JSONDecodeError:
                    logger.warning("invalid VTK worker output: %s", line.rstrip())

        def read_errors() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                logger.info("VTK worker: %s", line.rstrip())

        Thread(target=read_output, daemon=True).start()
        Thread(target=read_errors, daemon=True).start()
        return process

    def _wait_for_ready(self, process: subprocess.Popen[str]) -> dict[str, object]:
        deadline = monotonic() + 90.0
        while monotonic() < deadline:
            try:
                message = self.messages.get(timeout=0.25)
            except Empty:
                if process.poll() is not None:
                    raise RuntimeError(f"native VTK worker exited with code {process.returncode}")
                QApplication.processEvents()
                continue
            event = message.get("event")
            if event == "ready":
                return message
            if event in {"fatal", "error"}:
                raise RuntimeError(str(message.get("message", "native VTK worker failed")))
        raise TimeoutError("native VTK worker did not initialize")

    def clear(self) -> None:
        self._message_timer.stop()
        self._resize_timer.stop()
        if self.scene is not None:
            self.scene.close()
        elif self.worker is not None and self.worker.poll() is None:
            self.worker.terminate()
            self.worker.wait(timeout=5)
        self.scene = None
        self.worker = None
        self.native_window_id = None

    def _poll_worker_messages(self) -> None:
        if self.scene is None:
            return
        for message in self.scene.poll_events():
            if message.get("event") == "face_picked":
                self.face_picked.emit(str(message.get("face_identity") or ""))
            elif message.get("event") in {"error", "fatal"}:
                logger.error("VTK worker event: %s", message.get("message", "unknown error"))

    def diagnostics(self) -> RenderDiagnostics | None:
        return self.scene.diagnostics() if self.scene else None

    def close_viewport(self) -> None:
        self.clear()

    def _embed_native_window(self) -> None:
        user32 = self.user32
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user32.SetParent.restype = ctypes.c_void_p
        user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t
        ]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.MoveWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_bool,
        ]
        user32.MoveWindow.restype = ctypes.c_bool
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.ShowWindow.restype = ctypes.c_bool
        user32.SetWindowPos.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = ctypes.c_bool

        vtk_window = int(user32.FindWindowW(None, self.native_title) or 0)
        if not vtk_window:
            raise RuntimeError("VTK native render window was not created")
        host_window = int(self.render_host.winId())
        ctypes.set_last_error(0)
        previous_parent = user32.SetParent(vtk_window, host_window)
        if not previous_parent and ctypes.get_last_error():
            raise RuntimeError("VTK native render window could not be parented into Qt")
        style = int(user32.GetWindowLongPtrW(vtk_window, -16))
        remove_style = 0x80000000 | 0x00C00000 | 0x00040000 | 0x00080000
        remove_style |= 0x00020000 | 0x00010000
        style = (style & ~remove_style) | 0x40000000 | 0x10000000
        style |= 0x04000000 | 0x02000000
        ctypes.set_last_error(0)
        previous_style = user32.SetWindowLongPtrW(vtk_window, -16, style)
        if not previous_style and ctypes.get_last_error():
            raise RuntimeError("VTK child-window style could not be applied")
        self.native_window_id = vtk_window
        self._resize_native_window()
        user32.SetWindowPos(
            vtk_window, None, 0, 0, 0, 0,
            0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020,
        )
        user32.ShowWindow(vtk_window, 5)

    def _resize_native_window(self) -> None:
        if not self.native_window_id:
            return
        ratio = self.render_host.devicePixelRatioF()
        width = max(1, round(self.render_host.width() * ratio))
        height = max(1, round(self.render_host.height() * ratio))
        self.user32.MoveWindow(
            self.native_window_id, 0, 0, width, height, False
        )
        if self.scene is not None:
            self.scene.set_size(width, height)

    def _apply_native_resize(self) -> None:
        self._resize_native_window()
        if self.scene is not None:
            self.scene.render()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._resize_timer.start()


class FxdWorkbenchWindow(QMainWindow):
    """One-window desktop shell around the deterministic FXD engineering core."""

    def __init__(self, *,
                 viewport_factory: Callable[..., EmbeddedVtkViewport] = EmbeddedVtkViewport,
                 kernel: OcpKernel | None = None,
                 ai_provider: AiFixtureProvider | None = None) -> None:
        super().__init__()
        self.setObjectName("fxdEngineeringWorkbench")
        self.setWindowTitle("FXD - Engineering Workbench - review only")
        self.resize(1500, 900)
        self.setMinimumSize(1180, 720)
        self.setWindowIcon(application_icon())
        self.document: WorkbenchDocument | None = None
        self.project: FxdProject | None = None
        self.workflow: InteractiveWorkflow | None = None
        self.authored_fixture_build = None
        self.project_path: Path | None = None
        self.selected_identity: str | None = None
        self.selected_reference: GeometryReference | None = None
        self.orientation_face_reference: GeometryReference | None = None
        self.orientation_front_reference: GeometryReference | None = None
        self.orientation_pending_reference: GeometryReference | None = None
        self.orientation_recommendation: GeometryReference | None = None
        self.orientation_guided_step = 0
        self.orientation_draft: ManufacturingOrientation | None = None
        self._setting_orientation_controls = False
        self._geometry_references: dict[str, GeometryReference] = {}
        self._finding_records: dict[str, object] = {}
        self._ui_active_stage: str | None = None
        self._settings_enabled = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
        self.settings = QSettings("FXD", "EngineeringWorkbench")
        self.analysis_pool = QThreadPool(self)
        self.analysis_pool.setMaxThreadCount(1)
        self._analysis_request = 0
        self._analysis_tasks: dict[int, _AnalysisTask] = {}
        self._proposal_request = 0
        self._proposal_tasks: dict[int, _ProposalTask] = {}
        self._proposal_contexts: dict[int, tuple[str, str | None]] = {}
        self._proposal_cancellation: CancellationToken | None = None
        self._first_successful_source_import = False
        self.ai_provider = ai_provider
        self._proposal_records: dict[str, object] = {}
        self._guided_issue_records: dict[str, object] = {}
        self._active_guided_issue: str | None = None
        self._guided_fix_signal: tuple[object, object] | None = None
        self.log = StructuredLog(Path.home() / ".fxd" / "diagnostics.jsonl")
        self.kernel = kernel or OcpKernel()
        self.viewport = viewport_factory(self)
        if hasattr(self.viewport, "face_picked"):
            self.viewport.face_picked.connect(self._viewer_face_picked)
        self._property_values: dict[str, QLabel] = {}
        self._actions: dict[str, QAction] = {}

        central = QWidget(self)
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.workflow_rail = WorkflowRail(central)
        self.workflow_rail.stage_selected.connect(self._navigate_stage)
        viewport_column = QWidget(central)
        viewport_layout = QVBoxLayout(viewport_column)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)
        self.viewport_caption = QLabel("PERSPECTIVE \u00b7 SHADED", viewport_column)
        self.viewport_caption.setObjectName("viewportCaption")
        viewport_layout.addWidget(self.viewport_caption)
        viewport_layout.addWidget(self.viewport, 1)
        central_layout.addWidget(self.workflow_rail)
        central_layout.addWidget(viewport_column, 1)
        self.setCentralWidget(central)

        self._build_tree_dock()
        self._build_workflow_dock()
        self._build_review_dock()
        self._build_actions()
        self._build_identity_bar()
        self._build_status_strip()
        self._restore_layout()
        self.statusBar().showMessage("Open a legally shareable STEP file or FXD project.")
        self._set_property("Evidence", EVIDENCE_PROVISIONAL)
        self._refresh_shell_state()

    def _replace_project(self, project: FxdProject | None) -> None:
        """Replace project state and invalidate geometry authored for the old revision."""
        self.project = project
        self.authored_fixture_build = None
        project_orientation = (
            project.workflow.setup.manufacturing_orientation
            if project is not None and project.workflow is not None else None
        )
        if (self.orientation_draft is not None and (
                project is None
                or self.orientation_draft.source_sha256 != project.product.source_sha256
                or project_orientation is None
                or self.orientation_draft.identity != project_orientation.identity)):
            self.orientation_draft = None
            self.orientation_face_reference = None
            self.orientation_front_reference = None
            self.orientation_pending_reference = None
            self.orientation_recommendation = None

    def _active_authored_fixture_build(self):
        """Return cache only when it belongs to the active source and build plan."""
        authored = self.authored_fixture_build
        if authored is None:
            return None
        if self.project is None or self.project.fixture_build is None:
            self.authored_fixture_build = None
            return None
        plan = self.project.fixture_build
        if (authored.plan_identity != plan.identity
                or authored.source_sha256 != self.project.product.source_sha256):
            self.authored_fixture_build = None
            return None
        return authored

    def _build_tree_dock(self) -> None:
        dock = QDockWidget("Engineering Explorer", self)
        dock.setObjectName("engineeringExplorerDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        dock.setMinimumWidth(380)
        dock.setMaximumWidth(560)
        self.tree = QTreeWidget(dock)
        self.tree.setObjectName("engineeringTree")
        self.tree.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.tree.setHeaderLabels(["Item", "Status"])
        self.tree.setColumnWidth(0, 180)
        self.tree.itemSelectionChanged.connect(self._tree_selection_changed)
        dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    @staticmethod
    def _combo(
        values: tuple[str, ...], *, editable: bool = False, wheel_to_parent: bool = False,
    ) -> QComboBox:
        combo = ScrollPassthroughComboBox() if wheel_to_parent else QComboBox()
        combo.addItems(values)
        combo.setEditable(editable)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMinimumContentsLength(18)
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        for index, value in enumerate(values):
            combo.setItemData(index, value, Qt.ItemDataRole.ToolTipRole)
        return combo

    def _build_orientation_page(self) -> QScrollArea:
        """Build the simple two-face workflow while retaining advanced controls."""
        scroll = QScrollArea(self.workflow_tabs)
        scroll.setObjectName("orientationWorkflow")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget(scroll)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        heading = QLabel("Manufacturing Orientation", host)
        heading.setProperty("sectionHeading", True)
        intro = QLabel(
            "Tell FXD how the part sits using two planar model faces. "
            "The imported STEP and its source coordinates remain unchanged.", host,
        )
        intro.setWordWrap(True)
        self.orientation_step_label = QLabel("STEP 1 OF 3", host)
        self.orientation_step_label.setProperty("technical", True)
        layout.addWidget(heading)
        layout.addWidget(intro)
        layout.addWidget(self.orientation_step_label)

        self.orientation_steps = QStackedWidget(host)

        bottom_page = QWidget(self.orientation_steps)
        bottom_layout = QVBoxLayout(bottom_page)
        bottom_layout.setContentsMargins(0, 4, 0, 4)
        bottom_prompt = QLabel("Select the face that sits down on the fixture.", bottom_page)
        bottom_prompt.setWordWrap(True)
        bottom_prompt.setProperty("sectionHeading", True)
        bottom_help = QLabel("Click a planar face directly on the model.", bottom_page)
        bottom_help.setWordWrap(True)
        self.orientation_bottom_status = QLabel("No bottom face selected.", bottom_page)
        self.orientation_bottom_status.setWordWrap(True)
        self.orientation_recommendation_text = QLabel(
            "FXD will show a support-face recommendation when planar evidence is available.",
            bottom_page,
        )
        self.orientation_recommendation_text.setWordWrap(True)
        self.orientation_use_recommendation = QPushButton("Use as fixture-down?", bottom_page)
        self.orientation_use_recommendation.clicked.connect(self.use_recommended_bottom_face)
        bottom_actions = QHBoxLayout()
        self.orientation_accept_bottom = QPushButton("Accept bottom face", bottom_page)
        self.orientation_accept_bottom.setProperty("role", "primary")
        self.orientation_accept_bottom.clicked.connect(self.accept_guided_bottom_face)
        self.orientation_pick_another_bottom = QPushButton("Pick another face", bottom_page)
        self.orientation_pick_another_bottom.clicked.connect(self.pick_another_bottom_face)
        self.orientation_flip_side = QPushButton("Flip side", bottom_page)
        self.orientation_flip_side.clicked.connect(self.flip_guided_bottom_side)
        bottom_actions.addWidget(self.orientation_accept_bottom)
        bottom_actions.addWidget(self.orientation_pick_another_bottom)
        bottom_actions.addWidget(self.orientation_flip_side)
        bottom_layout.addWidget(bottom_prompt)
        bottom_layout.addWidget(bottom_help)
        bottom_layout.addWidget(self.orientation_bottom_status)
        bottom_layout.addWidget(self.orientation_recommendation_text)
        bottom_layout.addWidget(self.orientation_use_recommendation)
        bottom_layout.addLayout(bottom_actions)
        bottom_layout.addStretch(1)
        self.orientation_steps.addWidget(bottom_page)

        front_page = QWidget(self.orientation_steps)
        front_layout = QVBoxLayout(front_page)
        front_layout.setContentsMargins(0, 4, 0, 4)
        front_prompt = QLabel(
            "Select the face that points toward the operator or front of the fixture.",
            front_page,
        )
        front_prompt.setWordWrap(True)
        front_prompt.setProperty("sectionHeading", True)
        front_help = QLabel("Click a second planar face directly on the model.", front_page)
        front_help.setWordWrap(True)
        self.orientation_front_status = QLabel("No front face selected.", front_page)
        self.orientation_front_status.setWordWrap(True)
        self.orientation_guided_error = QLabel("", front_page)
        self.orientation_guided_error.setWordWrap(True)
        self.orientation_guided_error.setProperty("status", "warning")
        front_actions = QHBoxLayout()
        self.orientation_preview_button = QPushButton("Preview orientation", front_page)
        self.orientation_preview_button.setProperty("role", "primary")
        self.orientation_preview_button.clicked.connect(self.preview_guided_orientation)
        self.orientation_back_to_bottom = QPushButton("Back", front_page)
        self.orientation_back_to_bottom.clicked.connect(self.back_to_guided_bottom)
        front_actions.addWidget(self.orientation_preview_button)
        front_actions.addWidget(self.orientation_back_to_bottom)
        front_layout.addWidget(front_prompt)
        front_layout.addWidget(front_help)
        front_layout.addWidget(self.orientation_front_status)
        front_layout.addWidget(self.orientation_guided_error)
        front_layout.addLayout(front_actions)
        front_layout.addStretch(1)
        self.orientation_steps.addWidget(front_page)

        preview_page = QWidget(self.orientation_steps)
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setContentsMargins(0, 4, 0, 4)
        preview_prompt = QLabel("Review the manufacturing orientation.", preview_page)
        preview_prompt.setProperty("sectionHeading", True)
        self.orientation_summary = QLabel("Select bottom and front faces to create a preview.", preview_page)
        self.orientation_summary.setWordWrap(True)
        preview_actions = QVBoxLayout()
        preview_primary_actions = QHBoxLayout()
        preview_secondary_actions = QHBoxLayout()
        self.orientation_guided_accept = QPushButton("Accept orientation", preview_page)
        self.orientation_guided_accept.setProperty("role", "primary")
        self.orientation_guided_accept.clicked.connect(self.accept_guided_orientation)
        self.orientation_back_to_front = QPushButton("Back", preview_page)
        self.orientation_back_to_front.clicked.connect(self.back_to_guided_front)
        self.orientation_guided_reset = QPushButton("Reset", preview_page)
        self.orientation_guided_reset.clicked.connect(self.reset_guided_orientation)
        self.orientation_fit_preview = QPushButton("Fit View", preview_page)
        self.orientation_fit_preview.clicked.connect(self.fit_view)
        self.orientation_advanced_toggle = QToolButton(preview_page)
        self.orientation_advanced_toggle.setText("Advanced")
        self.orientation_advanced_toggle.setCheckable(True)
        preview_primary_actions.addWidget(self.orientation_guided_accept)
        preview_primary_actions.addWidget(self.orientation_back_to_front)
        preview_primary_actions.addWidget(self.orientation_guided_reset)
        preview_secondary_actions.addWidget(self.orientation_fit_preview)
        preview_secondary_actions.addWidget(self.orientation_advanced_toggle)
        preview_actions.addLayout(preview_primary_actions)
        preview_actions.addLayout(preview_secondary_actions)
        preview_layout.addWidget(preview_prompt)
        preview_layout.addWidget(self.orientation_summary)
        preview_layout.addLayout(preview_actions)
        preview_layout.addStretch(1)
        self.orientation_steps.addWidget(preview_page)
        layout.addWidget(self.orientation_steps)

        self.orientation_advanced_group = QGroupBox("Advanced orientation settings", host)
        advanced_form = QFormLayout(self.orientation_advanced_group)
        self.orientation_method = self._combo(ORIENTATION_METHOD_OPTIONS, wheel_to_parent=True)
        self.orientation_reference_plane = self._combo(REFERENCE_PLANE_OPTIONS, wheel_to_parent=True)
        self.orientation_select_face = QPushButton("Use selected face as build-down")
        self.orientation_selected_face = QLabel("No planar model face selected.")
        self.orientation_selected_face.setWordWrap(True)
        self.orientation_flip_normal = QCheckBox("Flip normal")
        self.orientation_rotation = self._combo(ORIENTATION_ROTATION_OPTIONS, wheel_to_parent=True)
        self.orientation_custom_rotation = QDoubleSpinBox()
        self.orientation_custom_rotation.setRange(-360.0, 360.0)
        self.orientation_custom_rotation.setSuffix(" deg")
        self.orientation_custom_origin = QLineEdit()
        self.orientation_custom_origin.setPlaceholderText("x, y, z mm")
        self.orientation_custom_normal = QLineEdit()
        self.orientation_custom_normal.setPlaceholderText("x, y, z source direction")
        self.orientation_matrix = QLabel("Not defined")
        self.orientation_matrix.setWordWrap(True)
        self.orientation_inverse = QLabel("Not defined")
        self.orientation_inverse.setWordWrap(True)
        self.orientation_raw_evidence = QLabel("No orientation evidence.")
        self.orientation_raw_evidence.setWordWrap(True)
        self.orientation_explanation = QLabel(
            "Choose a source plane, exact source axes, or an exact planar face."
        )
        self.orientation_explanation.setWordWrap(True)
        self.orientation_reset = QPushButton("Reset to source orientation")
        self.orientation_accept = QPushButton("Apply advanced orientation")
        for label, widget in (
            ("Orientation method", self.orientation_method),
            ("Source reference plane", self.orientation_reference_plane),
            ("Face identity", self.orientation_selected_face),
            ("Selected face", self.orientation_select_face),
            ("Flip normal", self.orientation_flip_normal),
            ("Rotation", self.orientation_rotation),
            ("Custom angle", self.orientation_custom_rotation),
            ("Plane origin", self.orientation_custom_origin),
            ("Plane normal / source axes", self.orientation_custom_normal),
            ("Source-to-manufacturing", self.orientation_matrix),
            ("Inverse transform", self.orientation_inverse),
            ("Raw evidence", self.orientation_raw_evidence),
            ("Decision", self.orientation_explanation),
        ):
            advanced_form.addRow(label + ":", widget)
        advanced_actions = QWidget(self.orientation_advanced_group)
        advanced_actions_layout = QHBoxLayout(advanced_actions)
        advanced_actions_layout.setContentsMargins(0, 0, 0, 0)
        advanced_actions_layout.addWidget(self.orientation_reset)
        advanced_actions_layout.addWidget(self.orientation_accept)
        advanced_form.addRow(advanced_actions)
        self.orientation_advanced_group.setVisible(False)
        self.orientation_advanced_toggle.toggled.connect(self.orientation_advanced_group.setVisible)
        layout.addWidget(self.orientation_advanced_group)
        layout.addStretch(1)

        self.orientation_method.currentTextChanged.connect(self._orientation_controls_changed)
        self.orientation_reference_plane.currentTextChanged.connect(self._orientation_controls_changed)
        self.orientation_flip_normal.toggled.connect(self._orientation_controls_changed)
        self.orientation_rotation.currentTextChanged.connect(self._orientation_controls_changed)
        self.orientation_custom_rotation.valueChanged.connect(self._orientation_controls_changed)
        self.orientation_custom_origin.editingFinished.connect(self._orientation_controls_changed)
        self.orientation_custom_normal.editingFinished.connect(self._orientation_controls_changed)
        self.orientation_select_face.clicked.connect(self.select_build_down_face)
        self.orientation_reset.clicked.connect(self.reset_to_source_orientation)
        self.orientation_accept.clicked.connect(self.accept_manufacturing_orientation)
        scroll.setWidget(host)
        return scroll

    def _build_proposal_page(self) -> QScrollArea:
        scroll = QScrollArea(self.workflow_tabs)
        scroll.setObjectName("fixtureProposalWorkflow")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget(scroll)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        heading = QLabel("AI Fixture Engineer", host)
        heading.setProperty("sectionHeading", True)
        introduction = QLabel(
            "Generate one editable fixture proposal from the accepted manufacturing "
            "orientation and deterministic FXD engineering evidence. AI proposes; "
            "engineering validation remains authoritative.", host,
        )
        introduction.setWordWrap(True)
        self.proposal_status = QLabel(
            "Accept manufacturing orientation to begin.", host,
        )
        self.proposal_status.setWordWrap(True)
        self.proposal_status.setObjectName("fixtureProposalStatus")
        self.proposal_generate = QPushButton("Generate Fixture Proposal", host)
        self.proposal_generate.setObjectName("generateFixtureProposal")
        self.proposal_generate.setProperty("role", "primary")
        self.proposal_generate.clicked.connect(self.generate_fixture_proposal_action)
        self.proposal_cancel = QPushButton("Cancel generation", host)
        self.proposal_cancel.clicked.connect(self.cancel_fixture_proposal)
        self.proposal_cancel.setVisible(False)

        self.proposal_interview = QGroupBox("Essential intent confirmation", host)
        interview_layout = QVBoxLayout(self.proposal_interview)
        self.proposal_questions = QListWidget(self.proposal_interview)
        self.proposal_questions.setObjectName("proposalIntentQuestions")
        self.proposal_use_recommended = QPushButton(
            "Use these recommended answers", self.proposal_interview,
        )
        self.proposal_use_recommended.clicked.connect(self.apply_proposal_recommended_intent)
        interview_layout.addWidget(self.proposal_questions)
        interview_layout.addWidget(self.proposal_use_recommended)

        self.proposal_summary = QLabel("No fixture proposal has been generated.", host)
        self.proposal_summary.setWordWrap(True)
        self.proposal_recommendations = QListWidget(host)
        self.proposal_recommendations.setObjectName("fixtureProposalRecommendations")
        self.proposal_recommendations.itemSelectionChanged.connect(
            self._proposal_selection_changed
        )
        self.proposal_explanation = QLabel(
            "Select a recommendation to review why it was proposed, its assumptions, "
            "confidence, deterministic checks, and unresolved risk.", host,
        )
        self.proposal_explanation.setWordWrap(True)

        review_actions = QHBoxLayout()
        self.proposal_accept_recommendation = QPushButton("Accept", host)
        self.proposal_reject_recommendation = QPushButton("Reject", host)
        self.proposal_suppress_recommendation = QPushButton("Suppress", host)
        self.proposal_accept_recommendation.clicked.connect(
            lambda: self._decide_selected_recommendation(RecommendationDecision.ACCEPTED)
        )
        self.proposal_reject_recommendation.clicked.connect(
            lambda: self._decide_selected_recommendation(RecommendationDecision.REJECTED)
        )
        self.proposal_suppress_recommendation.clicked.connect(
            lambda: self._decide_selected_recommendation(RecommendationDecision.SUPPRESSED)
        )
        review_actions.addWidget(self.proposal_accept_recommendation)
        review_actions.addWidget(self.proposal_reject_recommendation)
        review_actions.addWidget(self.proposal_suppress_recommendation)

        edit_form = QFormLayout()
        self.proposal_edit_parameter = self._combo((), editable=False)
        self.proposal_edit_value = QLineEdit(host)
        self.proposal_edit_note = QLineEdit(host)
        self.proposal_edit_note.setPlaceholderText("Engineer reason for the proposal revision")
        self.proposal_apply_edit = QPushButton("Edit recommendation", host)
        self.proposal_apply_edit.clicked.connect(self._edit_selected_recommendation)
        edit_form.addRow("Editable parameter:", self.proposal_edit_parameter)
        edit_form.addRow("New value:", self.proposal_edit_value)
        edit_form.addRow("Reason:", self.proposal_edit_note)
        edit_form.addRow(self.proposal_apply_edit)

        decision_actions = QHBoxLayout()
        self.proposal_accept = QPushButton("Accept for Engineering Review", host)
        self.proposal_reject = QPushButton("Reject Proposal", host)
        self.proposal_accept.clicked.connect(
            lambda: self._decide_fixture_proposal("accepted_for_engineering_review")
        )
        self.proposal_reject.clicked.connect(
            lambda: self._decide_fixture_proposal("rejected")
        )
        decision_actions.addWidget(self.proposal_accept)
        decision_actions.addWidget(self.proposal_reject)

        self.proposal_technical_toggle = QToolButton(host)
        self.proposal_technical_toggle.setText("Technical proposal details")
        self.proposal_technical_toggle.setCheckable(True)
        self.proposal_technical_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.proposal_technical_details = QLabel("", host)
        self.proposal_technical_details.setWordWrap(True)
        self.proposal_technical_details.setProperty("technical", True)
        self.proposal_technical_details.setVisible(False)
        self.proposal_technical_toggle.toggled.connect(
            lambda shown: (
                self.proposal_technical_toggle.setArrowType(
                    Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow
                ),
                self.proposal_technical_details.setVisible(shown),
            )
        )

        layout.addWidget(heading)
        layout.addWidget(introduction)
        layout.addWidget(self.proposal_status)
        layout.addWidget(self.proposal_generate)
        layout.addWidget(self.proposal_cancel)
        layout.addWidget(self.proposal_interview)
        layout.addWidget(self.proposal_summary)
        layout.addWidget(self.proposal_recommendations, 1)
        layout.addWidget(self.proposal_explanation)
        layout.addLayout(review_actions)
        layout.addLayout(edit_form)
        layout.addLayout(decision_actions)
        layout.addWidget(self.proposal_technical_toggle)
        layout.addWidget(self.proposal_technical_details)
        scroll.setWidget(host)
        return scroll

    def _build_workflow_dock(self) -> None:
        dock = QDockWidget("Fixture Engineering Workflow", self)
        dock.setObjectName("workflowDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        dock.setMinimumWidth(380)
        dock.setMaximumWidth(560)
        self.workflow_dock = dock
        self.workflow_tabs = QTabWidget(dock)
        self.workflow_tabs.setObjectName("workflowTabs")
        self.workflow_tabs.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        self.workflow_tabs.setMinimumWidth(0)

        product_page = QWidget(self.workflow_tabs)
        product_layout = QVBoxLayout(product_page)
        self.workflow_source = QLabel("Import a STEP assembly to begin.")
        self.workflow_source.setWordWrap(True)
        product_layout.addWidget(self.workflow_source)
        product_layout.addStretch(1)
        self.workflow_tabs.addTab(product_page, "Product")

        self.orientation_page = self._build_orientation_page()
        self.workflow_tabs.addTab(self.orientation_page, "Orientation")

        self.proposal_page = self._build_proposal_page()
        self.workflow_tabs.addTab(self.proposal_page, "Proposal")

        # M30 adds governed construction inputs; keep the complete review form
        # reachable at the supported 1366 x 768 desktop size.
        self.process_scroll = QScrollArea(self.workflow_tabs)
        self.process_scroll.setWidgetResizable(True)
        self.process_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.process_scroll.setMinimumWidth(0)
        self.process_form_widget = QWidget(self.process_scroll)
        self.process_form_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.process_form_widget.setMinimumWidth(0)
        process_form = QFormLayout(self.process_form_widget)
        process_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        process_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        process_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        process_form.setContentsMargins(12, 12, 12, 12)
        process_form.setHorizontalSpacing(10)
        process_form.setVerticalSpacing(8)
        self.process_project_name = QLineEdit()
        self.process_fixture_type = self._combo(FIXTURE_TYPE_OPTIONS, wheel_to_parent=True)
        self.process_method = self._combo(PROCESS_OPTIONS, wheel_to_parent=True)
        self.process_mode = self._combo(OPERATION_MODE_OPTIONS, wheel_to_parent=True)
        self.process_quantity = QSpinBox()
        self.process_quantity.setRange(1, 10_000_000)
        self.process_quantity.setValue(10)
        self.process_volume = self._combo(VOLUME_OPTIONS, wheel_to_parent=True)
        self.process_build = self._combo(DIRECTION_OPTIONS, wheel_to_parent=True)
        self.process_load = self._combo(DIRECTION_OPTIONS, wheel_to_parent=True)
        self.process_unload = self._combo(DIRECTION_OPTIONS, wheel_to_parent=True)
        self.process_build.setCurrentText("+Z")
        self.process_unload.setCurrentText("-X")
        self.process_operator = QLineEdit()
        self.process_operator.setPlaceholderText("Unknown, or explicit hand/helmet access")
        self.process_automation = QLineEdit()
        self.process_automation.setPlaceholderText("Unknown, or robot/cobot assumptions")
        self.process_shop = QLineEdit()
        self.process_shop.setPlaceholderText("laser cutting, welding, machining")
        self.process_material = QLineEdit()
        self.process_material.setPlaceholderText("Unknown, or product/process assumptions")
        self.process_base = self._combo(BASE_STRATEGY_OPTIONS, wheel_to_parent=True)
        self.process_construction = self._combo(CONSTRUCTION_OPTIONS, wheel_to_parent=True)
        self.process_lifecycle = self._combo(LIFECYCLE_OPTIONS, wheel_to_parent=True)
        self.process_repeat_frequency = QLineEdit()
        self.process_repeat_frequency.setPlaceholderText("Unknown, or repeat frequency")
        self.process_job_revision = QLineEdit()
        self.process_job_revision.setPlaceholderText("Required for disposable or recut fixture")
        self.process_cleco_strategy = self._combo(CLECO_STRATEGY_OPTIONS, wheel_to_parent=True)
        self.process_adjustment_state = self._combo(ADJUSTMENT_STATE_OPTIONS, wheel_to_parent=True)
        self.process_product_hole_approval = QCheckBox("Recorded")
        self.process_product_hole_justification = QLineEdit()
        self.process_product_hole_justification.setPlaceholderText("Cost, process, or customer justification")
        self.process_tack_access = QCheckBox("Reviewed")
        self.process_unload_clearance = QCheckBox("Reviewed")
        self.process_repeatability = QDoubleSpinBox()
        self.process_repeatability.setRange(0.0, 1000.0)
        self.process_repeatability.setDecimals(3)
        self.process_repeatability.setSpecialValueText("Unknown")
        self.process_clearance = QDoubleSpinBox()
        self.process_clearance.setRange(0.0, 1000.0)
        self.process_clearance.setDecimals(3)
        self.process_clearance.setValue(2.0)
        for label, widget in (
            ("Project", self.process_project_name), ("Fixture type", self.process_fixture_type),
            ("Process", self.process_method), ("Operation", self.process_mode),
            ("Quantity", self.process_quantity), ("Volume", self.process_volume),
            ("Build-up axis (Mfg)", self.process_build), ("Load direction (Mfg)", self.process_load),
            ("Unload direction (Mfg)", self.process_unload), ("Operator access", self.process_operator),
            ("Automation", self.process_automation), ("Shop capabilities", self.process_shop),
            ("Material/process", self.process_material), ("Base strategy", self.process_base),
            ("Construction", self.process_construction), ("Lifecycle", self.process_lifecycle),
            ("Repeat frequency", self.process_repeat_frequency), ("Job revision", self.process_job_revision),
            ("Cleco strategy", self.process_cleco_strategy),
            ("Adjustment state", self.process_adjustment_state),
            ("Product-hole approval", self.process_product_hole_approval),
            ("Product-hole justification", self.process_product_hole_justification),
            ("Tack access", self.process_tack_access), ("Unload clearance", self.process_unload_clearance),
            ("Repeatability (mm)", self.process_repeatability),
            ("Clearance (mm)", self.process_clearance),
        ):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            widget.setMinimumWidth(220)
            widget.setToolTip(f"{label}: select a supported value or record explicit engineer evidence.")
            process_form.addRow(label + ":", widget)
        self.process_product_hole_approval.setToolTip(
            "Customer or process approval is recorded for Cleco holes in the production part."
        )
        self.process_tack_access.setToolTip(
            "Engineer-reviewed evidence that tack access is available; full-weld access is not implied."
        )
        self.process_unload_clearance.setToolTip(
            "Engineer-reviewed welded-shape unload clearance evidence."
        )
        self.analyze_button = QPushButton("Analyze Assembly")
        self.analyze_button.clicked.connect(self.analyze_assembly)
        process_form.addRow(self.analyze_button)
        for row in range(process_form.rowCount()):
            item = process_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel):
                label.setWordWrap(True)
                label.setMinimumWidth(0)
                label.setMaximumWidth(160)
                label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.process_scroll.setWidget(self.process_form_widget)
        self.workflow_tabs.addTab(self.process_scroll, "Process")

        annotation_page = QWidget(self.workflow_tabs)
        annotation_layout = QVBoxLayout(annotation_page)
        self.annotation_selection = QLabel("Select an exact face in the engineering explorer.")
        self.annotation_selection.setWordWrap(True)
        self.annotation_role = self._combo(tuple(role.value.replace("_", " ").title()
                                                  for role in AnnotationRole))
        self.annotation_role.setObjectName("annotationRole")
        self.annotation_apply = QPushButton("Assign selected face role")
        self.annotation_apply.clicked.connect(self.assign_selected_annotation)
        self.annotation_list = QListWidget()
        annotation_layout.addWidget(self.annotation_selection)
        annotation_layout.addWidget(self.annotation_role)
        annotation_layout.addWidget(self.annotation_apply)
        annotation_layout.addWidget(self.annotation_list, 1)
        self.workflow_tabs.addTab(annotation_page, "Datums and intent")

        concepts_page = QWidget(self.workflow_tabs)
        concepts_layout = QVBoxLayout(concepts_page)
        self.generate_button = QPushButton("Generate Fixture Concepts")
        self.generate_button.clicked.connect(self.generate_concepts)
        self.concept_table = QTableWidget(0, 18)
        self.concept_table.setHorizontalHeaderLabels((
            "Concept", "Status", "Recommended", "Score", "Cost evidence",
            "Loading", "Unloading", "Repeatability", "Fixture complexity",
            "Fabricated", "Purchased", "Operator access", "Weld access",
            "Automation access", "Manufacturability", "Maintainability",
            "Unresolved", "Why ranked",
        ))
        self.concept_table.itemSelectionChanged.connect(self._concept_selection_changed)
        concepts_layout.addWidget(self.generate_button)
        concepts_layout.addWidget(self.concept_table, 1)
        self.workflow_tabs.addTab(concepts_page, "Concepts")

        fabrication_page = QWidget(self.workflow_tabs)
        fabrication_layout = QVBoxLayout(fabrication_page)
        self.fabrication_status = QLabel(
            "Build a deterministic manufacturing plan after selecting an active fixture concept."
        )
        self.fabrication_status.setWordWrap(True)
        self.fabrication_components = QListWidget(fabrication_page)
        self.fabrication_plan_button = QPushButton("Generate Fixture Build Plan")
        self.fabrication_plan_button.clicked.connect(self.generate_fixture_build_plan)
        self.fabrication_author_button = QPushButton("Author Real Manufacturing Geometry")
        self.fabrication_author_button.clicked.connect(self.author_real_fixture_geometry)
        fabrication_layout.addWidget(self.fabrication_status)
        fabrication_layout.addWidget(self.fabrication_components, 1)
        fabrication_layout.addWidget(self.fabrication_plan_button)
        fabrication_layout.addWidget(self.fabrication_author_button)
        self.workflow_tabs.addTab(fabrication_page, "Manufacturing")

        tooling_page = QWidget(self.workflow_tabs)
        tooling_layout = QVBoxLayout(tooling_page)
        tooling_notice = QLabel(
            "Generic vendor-neutral tools are preferred. Customer files remain local and unverified until required metadata is supplied."
        )
        tooling_notice.setWordWrap(True)
        self.tooling_list = QListWidget()
        tooling_metadata = QFormLayout()
        self.tooling_identity = QLineEdit()
        self.tooling_identity.setPlaceholderText("Stable private-library identity (optional)")
        self.tooling_kind = self._combo(("clamp", "locator", "support", "stop", "custom_tool"))
        self.tooling_manufacturer = QLineEdit()
        self.tooling_part_number = QLineEdit()
        self.tooling_revision = QLineEdit()
        directions = ("Unknown", "+X", "-X", "+Y", "-Y", "+Z", "-Z")
        self.tooling_mount_direction = self._combo(directions)
        self.tooling_work_direction = self._combo(directions)
        self.tooling_stroke = QDoubleSpinBox()
        self.tooling_reach = QDoubleSpinBox()
        self.tooling_force = QDoubleSpinBox()
        for control in (self.tooling_stroke, self.tooling_reach, self.tooling_force):
            control.setRange(0.0, 1000000.0)
            control.setDecimals(3)
            control.setSpecialValueText("Unknown")
        self.tooling_verified = QCheckBox("Required metadata checked by the engineer")
        for label, widget in (
            ("Identity", self.tooling_identity), ("Role", self.tooling_kind),
            ("Manufacturer", self.tooling_manufacturer), ("Part number", self.tooling_part_number),
            ("Revision", self.tooling_revision), ("Mount direction", self.tooling_mount_direction),
            ("Working direction", self.tooling_work_direction), ("Stroke (mm)", self.tooling_stroke),
            ("Reach (mm)", self.tooling_reach), ("Force (N)", self.tooling_force),
            ("Verification", self.tooling_verified),
        ):
            tooling_metadata.addRow(label + ":", widget)
        self.tooling_import = QPushButton("Import customer-owned tooling reference...")
        self.tooling_import.clicked.connect(self.import_customer_tooling)
        tooling_layout.addWidget(tooling_notice)
        tooling_layout.addWidget(self.tooling_list, 1)
        tooling_layout.addLayout(tooling_metadata)
        tooling_layout.addWidget(self.tooling_import)
        self.workflow_tabs.addTab(tooling_page, "Tooling")

        edit_page = QWidget(self.workflow_tabs)
        edit_layout = QFormLayout(edit_page)
        self.edit_operation = self._combo((
            "Set parameter", "Move feature", "Resize feature", "Replace feature",
            "Suppress or restore feature",
        ))
        self.edit_target = self._combo((), editable=True)
        self.edit_parameter_name = self._combo((
            "base_thickness", "pin_diameter", "support_height", "clearance",
        ))
        self.edit_parameter_value = QDoubleSpinBox()
        self.edit_parameter_value.setRange(0.01, 10000.0)
        self.edit_parameter_value.setDecimals(3)
        self.edit_parameter_value.setValue(12.0)
        self.edit_move_x = QDoubleSpinBox()
        self.edit_move_y = QDoubleSpinBox()
        self.edit_move_z = QDoubleSpinBox()
        for control in (self.edit_move_x, self.edit_move_y, self.edit_move_z):
            control.setRange(-10000.0, 10000.0)
            control.setDecimals(3)
        self.edit_size_x = QDoubleSpinBox()
        self.edit_size_y = QDoubleSpinBox()
        self.edit_size_z = QDoubleSpinBox()
        for control in (self.edit_size_x, self.edit_size_y, self.edit_size_z):
            control.setRange(0.01, 10000.0)
            control.setDecimals(3)
            control.setValue(10.0)
        self.edit_replacement = self._combo((
            "round_pin", "relieved_locator", "support_pad", "hard_stop", "clamp_mount",
        ))
        self.edit_reason = QLineEdit()
        self.edit_reason.setPlaceholderText("Engineering reason for the revision")
        self.edit_apply = QPushButton("Regenerate and revalidate")
        self.edit_apply.clicked.connect(self.apply_parameter_edit)
        self.revision_list = QListWidget()
        self.edit_restore = QPushButton("Restore selected revision")
        self.edit_restore.clicked.connect(self.restore_selected_revision)
        edit_layout.addRow("Operation:", self.edit_operation)
        edit_layout.addRow("Fixture feature:", self.edit_target)
        edit_layout.addRow("Parameter:", self.edit_parameter_name)
        edit_layout.addRow("Value (mm):", self.edit_parameter_value)
        edit_layout.addRow("Move X (mm):", self.edit_move_x)
        edit_layout.addRow("Move Y (mm):", self.edit_move_y)
        edit_layout.addRow("Move Z (mm):", self.edit_move_z)
        edit_layout.addRow("Size X (mm):", self.edit_size_x)
        edit_layout.addRow("Size Y (mm):", self.edit_size_y)
        edit_layout.addRow("Size Z (mm):", self.edit_size_z)
        edit_layout.addRow("Replacement:", self.edit_replacement)
        edit_layout.addRow("Reason:", self.edit_reason)
        edit_layout.addRow(self.edit_apply)
        edit_layout.addRow("Revision history:", self.revision_list)
        edit_layout.addRow(self.edit_restore)
        self.workflow_tabs.addTab(edit_page, "Edit and revisions")

        dock.setWidget(self.workflow_tabs)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        explorer = self.findChild(QDockWidget, "engineeringExplorerDock")
        if explorer is not None:
            self.tabifyDockWidget(explorer, dock)
            explorer.raise_()

    def _build_review_dock(self) -> None:
        dock = QDockWidget("Properties and Findings", self)
        dock.setObjectName("reviewDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        dock.setMinimumWidth(300)
        dock.setMaximumWidth(440)
        tabs = QTabWidget(dock)
        tabs.setObjectName("reviewTabs")
        tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.review_tabs = tabs

        properties = QWidget(tabs)
        self.properties_form = QFormLayout(properties)
        for label in (
            "Source file", "Source SHA-256", "Components", "Faces", "Triangles",
            "Selected identity", "Evidence", "Validation", "Render backend",
            "Actors", "Points", "Native rendering", "Fallback", "Average render",
            "Visible FPS", "Project revision", "Evidence digest", "Workflow stage",
        ):
            value = QLabel("-", properties)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            if label in {
                "Source SHA-256", "Selected identity", "Faces", "Triangles",
                "Project revision", "Evidence digest", "Average render", "Visible FPS",
            }:
                value.setProperty("technical", True)
            self.properties_form.addRow(label + ":", value)
            self._property_values[label] = value
        tabs.addTab(properties, "Properties")

        findings_page = QWidget(tabs)
        findings_layout = QVBoxLayout(findings_page)
        filters = QHBoxLayout()
        self.finding_severity = self._combo(("All severities", "error", "warning", "info"))
        self.finding_category = self._combo(("All categories",), editable=False)
        self.finding_severity.currentTextChanged.connect(self._populate_findings)
        self.finding_category.currentTextChanged.connect(self._populate_findings)
        filters.addWidget(self.finding_severity)
        filters.addWidget(self.finding_category)
        self.findings = QListWidget(findings_page)
        self.findings.setObjectName("engineeringFindings")
        self.findings.itemSelectionChanged.connect(self._finding_selection_changed)
        self.finding_reviewed = QPushButton("Mark selected finding reviewed")
        self.finding_reviewed.clicked.connect(self.mark_selected_finding_reviewed)
        findings_layout.addLayout(filters)
        findings_layout.addWidget(self.findings, 1)
        findings_layout.addWidget(self.finding_reviewed)
        tabs.addTab(findings_page, "Findings")

        validation_page = QWidget(tabs)
        validation_layout = QVBoxLayout(validation_page)
        self.approval_gate = ApprovalGatePanel(validation_page)
        self.approval_gate.approve_requested.connect(
            lambda: self.record_decision("approve_for_review")
        )
        self.approval_gate.reject_requested.connect(
            lambda: self.record_decision("reject")
        )
        validation_layout.addWidget(self.approval_gate)
        self.guided_validation_summary = QLabel(
            "Generate a fixture proposal to see guided validation findings.", validation_page,
        )
        self.guided_validation_summary.setObjectName("guidedValidationSummary")
        self.guided_validation_summary.setWordWrap(True)
        self.guided_issues = QListWidget(validation_page)
        self.guided_issues.setObjectName("guidedValidationIssues")
        self.guided_issues.itemSelectionChanged.connect(self._guided_issue_selection_changed)
        self.guided_issue_explanation = QLabel("", validation_page)
        self.guided_issue_explanation.setWordWrap(True)
        guided_actions = QHBoxLayout()
        self.guided_fix = QPushButton("Fix this", validation_page)
        self.guided_fix.clicked.connect(self.fix_selected_guided_issue)
        self.guided_more = QToolButton(validation_page)
        self.guided_more.setText("More details")
        self.guided_more.setCheckable(True)
        guided_actions.addWidget(self.guided_fix)
        guided_actions.addWidget(self.guided_more)
        self.guided_technical_details = QLabel("", validation_page)
        self.guided_technical_details.setWordWrap(True)
        self.guided_technical_details.setProperty("technical", True)
        self.guided_technical_details.setVisible(False)
        self.guided_more.toggled.connect(self.guided_technical_details.setVisible)
        validation_layout.addWidget(self.guided_validation_summary)
        validation_layout.addWidget(self.guided_issues, 1)
        validation_layout.addWidget(self.guided_issue_explanation)
        validation_layout.addLayout(guided_actions)
        validation_layout.addWidget(self.guided_technical_details)
        validation_layout.addStretch(1)
        tabs.addTab(validation_page, "Validation")
        dock.setWidget(tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _build_identity_bar(self) -> None:
        host = QWidget(self)
        host.setObjectName("fxdMenuHost")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)

        bar = QWidget(host)
        bar.setObjectName("fxdIdentityBar")
        bar.setFixedHeight(34)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)
        logo = QLabel(bar)
        logo.setPixmap(application_icon().pixmap(20, 20))
        logo.setFixedSize(22, 22)
        logo.setAccessibleName("FXD application icon")
        brand = QLabel("FXD", bar)
        brand.setObjectName("fxdBrandMark")
        self.project_title = QLabel("Engineering Workbench", bar)
        self.project_title.setObjectName("fxdProjectTitle")
        self.source_badge = SourceCadBadge(bar)
        self.source_badge.clicked.connect(self.show_source_identity)
        self.kernel_health = StatusChip("pass", "OCP", bar)
        self.renderer_health = StatusChip("notEvaluated", "VTK", bar)
        layout.addWidget(logo)
        layout.addWidget(brand)
        layout.addWidget(self.project_title)
        layout.addStretch(1)
        layout.addWidget(self.source_badge)
        layout.addStretch(1)
        layout.addWidget(self.kernel_health)
        layout.addWidget(self.renderer_health)
        host_layout.addWidget(bar)
        host_layout.addWidget(self.menuBar())
        self.setMenuWidget(host)

    def _build_status_strip(self) -> None:
        self.status_units = QLabel("Units: mm", self)
        self.status_units.setProperty("technical", True)
        self.status_coordinates = QLabel("Coordinate: Project", self)
        self.status_coordinates.setProperty("technical", True)
        self.status_selection = QLabel("Selection: -", self)
        self.status_selection.setProperty("technical", True)
        self.status_validation = StatusChip("notEvaluated", "NOT EVALUATED", self)
        self.statusBar().addPermanentWidget(self.status_units)
        self.statusBar().addPermanentWidget(self.status_coordinates)
        self.statusBar().addPermanentWidget(self.status_selection, 1)
        self.statusBar().addPermanentWidget(self.status_validation)

    def show_source_identity(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("FXD Source CAD Identity")
        dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog)
        header = SourceCadBadge(dialog)
        header.setEnabled(False)
        if self.document:
            filename = self.document.source_name
            digest = self.document.source_sha256
            components = self.document.component_count
            faces = len(self.document.meshes)
            triangles = sum(len(mesh.triangles) for mesh in self.document.meshes)
            verified = True
        elif self.project:
            filename = self.project.product.source_name
            digest = self.project.product.source_sha256
            components = len(self.project.product.components)
            faces = triangles = 0
            verified = False
        else:
            filename = "No source loaded"
            digest = "-"
            components = faces = triangles = 0
            verified = False
        if digest != "-":
            header.set_source(filename, digest, verified=verified)
        form_host = QWidget(dialog)
        form = QFormLayout(form_host)
        for label, value in (
            ("Filename", filename), ("SHA-256", digest),
            ("Geometry evidence", "Verified OCP geometry" if verified else "Unavailable"),
            ("Components", components), ("Faces", faces), ("Triangles", triangles),
            ("Source policy", "Immutable; annotations and generated geometry are separate"),
        ):
            row = QLabel(str(value), form_host)
            row.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.setWordWrap(True)
            if label in {"SHA-256", "Components", "Faces", "Triangles"}:
                row.setProperty("technical", True)
            form.addRow(label + ":", row)
        boundary = QLabel(
            "Engineering review only. Source bytes are never rewritten by the workbench.",
            dialog,
        )
        boundary.setWordWrap(True)
        boundary.setProperty("status", "warning")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(header)
        layout.addWidget(form_host)
        layout.addWidget(boundary)
        layout.addWidget(buttons)
        dialog.exec()

    def _action(self, key: str, text: str, callback: Callable[[], None],
                *, shortcut: str | None = None, icon_name: str | None = None,
                checkable: bool = False) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        if icon_name is not None:
            action.setIcon(icon(icon_name))
        action.setCheckable(checkable)
        action.setToolTip(f"{text}{f' ({shortcut})' if shortcut else ''}")
        self._actions[key] = action
        return action

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        project_menu = self.menuBar().addMenu("&Project")
        view_menu = self.menuBar().addMenu("&View")
        engineering_menu = self.menuBar().addMenu("&Engineering")
        validation_menu = self.menuBar().addMenu("&Validation")
        tools_menu = self.menuBar().addMenu("&Tools")
        window_menu = self.menuBar().addMenu("&Window")
        help_menu = self.menuBar().addMenu("&Help")

        import_action = self._action(
            "import", "Import STEP...", self.import_step, shortcut="Ctrl+I", icon_name="import-step",
        )
        open_action = self._action(
            "open_project", "Open FXD project...", self.open_project, shortcut="Ctrl+O",
            icon_name="open-project",
        )
        save_action = self._action(
            "save_project", "Save FXD project...", self.save_project, shortcut="Ctrl+S",
            icon_name="save",
        )
        export_action = self._action(
            "export", "Export review package...", self.export_package,
            icon_name="export-review",
        )
        recover_action = self._action(
            "recover", "Recover autosave", self.recover_autosave,
            icon_name="recover-autosave",
        )
        file_menu.addActions([import_action, open_action, save_action, export_action])
        file_menu.addSeparator()
        file_menu.addAction(recover_action)

        source_identity = self._action(
            "source_identity", "Source CAD identity...", self.show_source_identity,
            icon_name="lock-decision",
        )
        project_menu.addAction(source_identity)

        fit_action = self._action(
            "fit", "Fit to view", self.fit_view, shortcut="F", icon_name="fit-view",
        )
        view_menu.addAction(fit_action)
        view_menu.addSeparator()
        for view in ("front", "back", "left", "right", "top", "bottom", "isometric"):
            view_menu.addAction(self._action(
                "view_" + view, view.title(),
                lambda checked=False, name=view: self.set_standard_view(name), icon_name=view,
            ))
        view_menu.addSeparator()
        wireframe = self._action(
            "wireframe", "Wireframe", self.toggle_wireframe,
            icon_name="wireframe", checkable=True,
        )
        transparency = self._action(
            "transparency", "Transparency", self.toggle_transparency,
            icon_name="transparency", checkable=True,
        )
        view_menu.addActions([wireframe, transparency])
        layer_menu = view_menu.addMenu("Project layers")
        for layer in sorted(SUPPORTED_LAYERS):
            action = self._action(
                "layer_" + layer, layer.title(),
                lambda checked=False, name=layer: self.toggle_project_layer(name),
                checkable=True,
            )
            action.setChecked(True)
            action.setEnabled(False)
            layer_menu.addAction(action)

        navigation_group = QActionGroup(self)
        navigation_group.setExclusive(True)
        for mode in ("orbit", "pan", "zoom"):
            action = self._action(
                "nav_" + mode, mode.title(),
                lambda checked=False, name=mode: self.set_navigation_mode(name),
                icon_name=mode, checkable=True,
            )
            navigation_group.addAction(action)
            engineering_menu.addAction(action)
        self._actions["nav_orbit"].setChecked(True)
        engineering_menu.addSeparator()
        edit_orientation_action = self._action(
            "edit_orientation", "Edit orientation", self.edit_orientation,
            icon_name="manufacturing-intent",
        )
        analyze_action = self._action(
            "analyze", "Analyze assembly", self.analyze_assembly,
            icon_name="analyze-assembly",
        )
        generate_action = self._action(
            "generate", "Generate concepts", self.generate_concepts,
            icon_name="generate-concepts",
        )
        proposal_action = self._action(
            "generate_proposal", "Generate Fixture Proposal",
            self.generate_fixture_proposal_action, icon_name="generate-concepts",
        )
        engineering_menu.addActions([
            edit_orientation_action, proposal_action, analyze_action, generate_action,
        ])

        findings_action = self._action(
            "findings", "Review findings", self.focus_findings,
            icon_name="review-findings",
        )
        approve_action = self._action(
            "approve", "Approve for engineering review",
            lambda: self.record_decision("approve_for_review"), icon_name="approve",
        )
        reject_action = self._action(
            "reject", "Reject concept", lambda: self.record_decision("reject"),
            icon_name="reject",
        )
        validation_menu.addActions([findings_action, approve_action, reject_action])

        tooling_action = self._action(
            "tooling", "Customer tooling", lambda: self._navigate_stage("Component Library"),
            icon_name="external-link",
        )
        tools_menu.addAction(tooling_action)

        reset_layout = self._action(
            "reset_layout", "Reset workbench layout", self.reset_workbench_layout,
        )
        window_menu.addAction(reset_layout)
        for dock_name in ("engineeringExplorerDock", "workflowDock", "reviewDock"):
            dock = self.findChild(QDockWidget, dock_name)
            if dock is not None:
                window_menu.addAction(dock.toggleViewAction())

        help_menu.addAction(self._action(
            "diagnostics", "Renderer diagnostics", self.show_renderer_diagnostics,
            icon_name="review-findings",
        ))
        help_menu.addAction(self._action(
            "benchmark", "Run visible render benchmark", self.show_renderer_benchmark
        ))
        help_menu.addSeparator()
        help_menu.addAction(self._action(
            "first_run_guide", "Fixture proposal guide", lambda: self.show_first_run_guide(True)
        ))
        help_menu.addAction(self._action("about", "About FXD", self.show_about))

        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.addActions([import_action, open_action, save_action, export_action])
        toolbar.addSeparator()
        toolbar.addActions([fit_action, self._actions["nav_orbit"], self._actions["nav_pan"],
                            self._actions["nav_zoom"]])
        toolbar.addSeparator()
        toolbar.addActions([
            self._actions["view_isometric"], self._actions["view_front"],
            self._actions["view_top"], wireframe, transparency,
        ])
        toolbar.addSeparator()
        toolbar.addActions([
            edit_orientation_action, proposal_action, analyze_action, generate_action, findings_action,
        ])
        toolbar.addSeparator()
        toolbar.addActions([approve_action, reject_action])
        self.addToolBar(toolbar)

    def _set_property(self, name: str, value: object) -> None:
        self._property_values[name].setText(str(value))

    def _navigate_stage(self, stage: str) -> None:
        self._ui_active_stage = stage
        tab_for_stage = {
            "Project": 0, "Import": 0, "Assembly": 0,
            "Manufacturing Intent": 3, "Orientation": 1, "Proposal": 2,
            "Datums": 4, "Locators & Supports": 4, "Clamps": 4,
            "Base Structure": 5, "Weld & Access": 5, "Concepts": 5,
            "Cost & Volume": 5, "Component Library": 7,
            "Rules & Preferences": 7, "Project History": 8,
        }
        if stage in {"Validation", "Review & Approval", "Export"}:
            review = self.findChild(QDockWidget, "reviewDock")
            if review is not None:
                review.show()
                review.raise_()
            self.review_tabs.setCurrentIndex(2 if stage != "Review & Approval" else 2)
        else:
            workflow_dock = self.findChild(QDockWidget, "workflowDock")
            if workflow_dock is not None:
                workflow_dock.show()
                workflow_dock.raise_()
            self.workflow_tabs.setCurrentIndex(tab_for_stage.get(stage, 0))
        state = self._workflow_states().get(stage)
        if state in {"blocked", "stale"} and self.project is not None:
            matching = [
                index for index in range(self.guided_issues.count())
                if (issue := self._guided_issue_records.get(str(
                    self.guided_issues.item(index).data(Qt.ItemDataRole.UserRole)
                ))) is not None and issue.workflow_section == stage
            ]
            if matching:
                review = self.findChild(QDockWidget, "reviewDock")
                if review is not None:
                    review.show()
                    review.raise_()
                self.review_tabs.setCurrentIndex(2)
                self.guided_issues.setCurrentRow(matching[0])
        self._set_orientation_pick_mode(
            stage == "Orientation" and self.orientation_guided_step in {0, 1}
        )
        self._populate_workflow_rail()
        self.statusBar().showMessage(f"Workflow view: {stage}.")

    def edit_orientation(self) -> None:
        if self.workflow is None:
            self.statusBar().showMessage("Import a STEP model before editing orientation.")
            return
        orientation = self.workflow.setup.manufacturing_orientation
        if orientation is not None and orientation.front_reference is not None:
            self.orientation_face_reference = orientation.selected_reference
            self.orientation_front_reference = orientation.front_reference
            self.orientation_draft = orientation.with_acceptance(False)
            self.orientation_guided_step = 2
        elif orientation is not None and orientation.selected_reference is not None:
            self.orientation_face_reference = orientation.selected_reference
            self.orientation_front_reference = None
            self.orientation_guided_step = 1
        else:
            self.orientation_guided_step = 0
        self._navigate_stage("Orientation")
        self._set_orientation_pick_mode(True)
        self._refresh_guided_orientation()

    def focus_findings(self) -> None:
        review = self.findChild(QDockWidget, "reviewDock")
        if review is not None:
            review.show()
            review.raise_()
        self.review_tabs.setCurrentIndex(1)

    def generate_fixture_proposal_now(self, provider: AiFixtureProvider | None = None):
        """Synchronous seam used by focused tests and non-threaded integrations."""
        if self.document is None or self.workflow is None:
            raise InteractiveWorkflowError("import a STEP model before generating a proposal")
        self._persist_process_setup_from_controls()
        outcome = generate_fixture_proposal(
            self.document, self.workflow,
            provider=provider if provider is not None else self.ai_provider,
            prior_proposal=self.project.fixture_proposal if self.project else None,
            current_project=self.project,
        )
        self.workflow = outcome.project.workflow
        self._replace_project(outcome.project)
        self._show_active_concept_geometry()
        self._refresh_all()
        return outcome

    def generate_fixture_proposal_action(self) -> None:
        if self.document is None or self.workflow is None:
            self.statusBar().showMessage("Import a STEP model before generating a fixture proposal.")
            return
        if not self.workflow.has_accepted_manufacturing_orientation():
            self.statusBar().showMessage(
                "Accept manufacturing orientation before generating a fixture proposal."
            )
            self._navigate_stage("Orientation")
            return
        questions = minimal_intent_questions(self.workflow)
        if questions:
            self._populate_proposal()
            self.proposal_status.setText(
                "Confirm the essential manufacturing intent below before generation."
            )
            self.proposal_interview.setVisible(True)
            return
        self._persist_process_setup_from_controls()
        self._proposal_request += 1
        request_id = self._proposal_request
        cancellation = CancellationToken.create()
        self._proposal_cancellation = cancellation
        task = _ProposalTask(
            self.document, self.workflow, request_id, self.ai_provider, cancellation,
            self.project.fixture_proposal if self.project else None,
            self.project,
        )
        self._proposal_tasks[request_id] = task
        self._proposal_contexts[request_id] = (
            self._proposal_workflow_identity(self.workflow),
            self._proposal_project_identity(self.project),
        )
        task.signals.completed.connect(self._proposal_completed)
        task.signals.failed.connect(self._proposal_failed)
        self.proposal_generate.setEnabled(False)
        self.proposal_cancel.setVisible(True)
        self.proposal_status.setText(
            "Generating proposal. Source geometry remains local and unchanged."
        )
        self.analysis_pool.start(task)

    def cancel_fixture_proposal(self) -> None:
        if self._proposal_cancellation is not None:
            self._proposal_cancellation.cancel()
            self.proposal_status.setText("Cancelling fixture proposal generation safely...")

    @staticmethod
    def _proposal_workflow_identity(workflow: InteractiveWorkflow) -> str:
        encoded = json.dumps(
            workflow.to_dict(), sort_keys=True, separators=(",", ":"),
        )
        return sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _proposal_project_identity(project: FxdProject | None) -> str | None:
        if project is None:
            return None
        payload = {
            "revision_id": project.revision_id,
            "hidden_layers": sorted(project.hidden_layers),
            "decisions": [item.__dict__ for item in project.decisions],
            "revisions": [{
                "revision_id": item.revision_id,
                "parent_id": item.parent_id,
                "active_concept": item.active_concept,
                "edit_count": item.edit_count,
                "validation_status": item.validation_status,
                "evidence_digest": item.evidence_digest,
                "suppressed_features": sorted(item.suppressed_features),
            } for item in project.revisions],
            "approved_revision": project.approved_revision,
            "drawing_intent": project.drawing_intent,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _invalidate_pending_proposal_generation(self) -> None:
        """Discard completions tied to a source or project being replaced."""
        self._proposal_request += 1
        if self._proposal_cancellation is not None:
            self._proposal_cancellation.cancel()
        self._proposal_cancellation = None
        self._proposal_tasks.clear()
        self._proposal_contexts.clear()
        self.proposal_cancel.setVisible(False)

    def _proposal_completed(self, outcome: object, request_id: int) -> None:
        self._proposal_tasks.pop(request_id, None)
        request_context = self._proposal_contexts.pop(request_id, None)
        if request_id != self._proposal_request:
            return
        self._persist_process_setup_from_controls()
        if (self.workflow is None or request_context is None
                or request_context[0] != self._proposal_workflow_identity(self.workflow)
                or request_context[1] != self._proposal_project_identity(self.project)
                or self.document is None
                or outcome.project.product.source_sha256 != self.document.source_sha256
                or outcome.project.product.source_bytes != self.document.source_bytes
                or (self.project is not None
                    and outcome.project.product.source_sha256
                    != self.project.product.source_sha256)):
            self._proposal_cancellation = None
            self.proposal_cancel.setVisible(False)
            self.proposal_generate.setEnabled(True)
            self.statusBar().showMessage(
                "Discarded fixture proposal generated for replaced source, workflow, or project evidence."
            )
            return
        self._proposal_cancellation = None
        self.proposal_cancel.setVisible(False)
        self.proposal_generate.setEnabled(True)
        self.workflow = outcome.project.workflow
        self._replace_project(outcome.project)
        self._show_active_concept_geometry()
        self._refresh_all()
        self.statusBar().showMessage(outcome.message)

    def _proposal_failed(self, message: str, request_id: int) -> None:
        self._proposal_tasks.pop(request_id, None)
        self._proposal_contexts.pop(request_id, None)
        if request_id != self._proposal_request:
            return
        self._proposal_cancellation = None
        self.proposal_cancel.setVisible(False)
        self.proposal_generate.setEnabled(True)
        if "cancel" in message.lower():
            self.proposal_status.setText(
                "Proposal generation cancelled; existing project state was not changed."
            )
            self.statusBar().showMessage("Fixture proposal generation cancelled safely.")
        else:
            self.proposal_status.setText(f"Proposal generation failed: {message}")
            self.statusBar().showMessage("Fixture proposal generation failed safely.")

    def apply_proposal_recommended_intent(self) -> None:
        if self.workflow is None:
            return
        self.workflow = apply_recommended_intent(self.workflow)
        self._set_process_setup(self.workflow.setup)
        if self.project is not None:
            self._replace_project(self.project.with_workflow(self.workflow))
        self._populate_proposal()
        self.proposal_status.setText(
            "Recommended answers applied visibly. Review them, then generate the proposal."
        )

    def _populate_proposal(self) -> None:
        self.proposal_questions.clear()
        questions = minimal_intent_questions(self.workflow) if self.workflow else ()
        for question in questions:
            answer = json.dumps(question.recommended_answer, sort_keys=True)
            self.proposal_questions.addItem(
                f"{question.prompt}\nWhy: {question.why_it_matters}\n"
                f"Recommended: {answer}{' ' + question.units if question.units else ''}"
            )
        self.proposal_interview.setVisible(bool(questions))
        self._proposal_records.clear()
        self.proposal_recommendations.clear()
        proposal = self.project.fixture_proposal if self.project else None
        orientation = self.workflow.setup.manufacturing_orientation if self.workflow else None
        orientation_identity = orientation.identity if orientation else None
        orientation_ready = bool(
            self.workflow and self.workflow.has_accepted_manufacturing_orientation()
        )
        self.proposal_generate.setEnabled(orientation_ready and not self._proposal_tasks)
        if proposal is None:
            self.proposal_summary.setText("No fixture proposal has been generated.")
            self.proposal_status.setText(
                "Ready to generate from accepted manufacturing orientation."
                if orientation_ready else "Accept manufacturing orientation to begin."
            )
            self.proposal_accept.setEnabled(False)
            self.proposal_reject.setEnabled(False)
            self.proposal_technical_details.setText("")
            return
        stale = proposal.stale_reason(
            self.project.product.source_sha256, orientation_identity,
            proposal_engineering_context_identity(self.project)
            if self.workflow and self.workflow.has_accepted_manufacturing_orientation()
            else None,
        )
        state = "STALE - " + stale if stale else proposal.validation_status.upper()
        ai_assisted = proposal.provenance.source.value == "ai"
        source_label = (
            "AI-assisted fixture proposal; deterministic validation remains authoritative"
            if ai_assisted else "Deterministic baseline proposal; AI assistance unavailable"
        )
        self.proposal_status.setText(
            f"{source_label}. Provider state: {proposal.provenance.provider_state.value}."
        )
        self.proposal_summary.setText(
            f"{proposal.concept_name}\nPurpose: {proposal.fixture_purpose}\n"
            f"Base: {proposal.base_strategy} | Lifecycle: {proposal.lifecycle}\n"
            f"Validation: {state} | {proposal.blocker_count} blockers | "
            f"{proposal.warning_count} warnings\nDecision: {proposal.proposal_decision}"
        )
        for recommendation in proposal.recommendations:
            self._proposal_records[recommendation.recommendation_id] = recommendation
            item = QListWidgetItem(
                f"{recommendation.recommendation_type.value.replace('_', ' ').title()} | "
                f"{recommendation.title}\n{recommendation.decision.value.replace('_', ' ').title()} | "
                f"{recommendation.validation_status.value.replace('_', ' ').title()}"
            )
            item.setData(Qt.ItemDataRole.UserRole, recommendation.recommendation_id)
            self.proposal_recommendations.addItem(item)
        self.proposal_accept.setEnabled(not stale and proposal.blocker_count == 0)
        self.proposal_reject.setEnabled(not stale)
        self.proposal_technical_details.setText(
            f"Proposal identity: {proposal.proposal_identity}\n"
            f"Source SHA-256: {proposal.source_sha256}\n"
            f"Orientation identity: {proposal.manufacturing_orientation_identity}\n"
            f"Provider: {proposal.provenance.provider_identity}\n"
            f"Mode: {'AI-assisted' if ai_assisted else 'Deterministic baseline'}\n"
            f"Model: {proposal.provenance.engine_identifier}\n"
            f"Fallback used: {'No' if ai_assisted else 'Yes'}\n"
            f"Prompt contract: {proposal.provenance.prompt_contract_version}\n"
            f"Response contract: {proposal.provenance.response_contract_version}"
            + (
                f"\nProvider failure: {proposal.provenance.provider_message}"
                if proposal.provenance.provider_state == ProviderState.FAILED
                else ""
            )
        )

    def _selected_proposal_recommendation(self):
        selected = self.proposal_recommendations.selectedItems()
        if not selected:
            return None
        return self._proposal_records.get(str(selected[0].data(Qt.ItemDataRole.UserRole)))

    def _proposal_selection_changed(self) -> None:
        recommendation = self._selected_proposal_recommendation()
        self.proposal_edit_parameter.clear()
        if recommendation is None:
            return
        assumptions = "; ".join(recommendation.assumptions) or "None recorded"
        risks = "; ".join(recommendation.unresolved_risks) or "None recorded"
        checks = "; ".join(recommendation.deterministic_checks)
        self.proposal_explanation.setText(
            f"Why proposed: {recommendation.engineering_reason}\n"
            f"Confidence: {recommendation.confidence:.0%}\n"
            f"Assumptions: {assumptions}\nDeterministic checks: {checks}\n"
            f"Unresolved risk: {risks}"
        )
        for parameter in recommendation.editable_parameters:
            self.proposal_edit_parameter.addItem(parameter.name)
        if recommendation.editable_parameters:
            self.proposal_edit_value.setText(json.dumps(
                recommendation.editable_parameters[0].value, sort_keys=True,
            ))
        identity = recommendation.fixture_feature_identity
        if identity is None and recommendation.geometry_reference is not None:
            identity = recommendation.geometry_reference.face_identity
        if identity and self._scene() is not None:
            self._scene().select(identity)

    def _decide_selected_recommendation(self, decision: RecommendationDecision) -> None:
        recommendation = self._selected_proposal_recommendation()
        if recommendation is None or self.project is None:
            self.statusBar().showMessage("Select a proposal recommendation first.")
            return
        try:
            self._replace_project(self.project.decide_proposal_recommendation(
                recommendation.recommendation_id, decision,
                "Engineer decision recorded in proposal review.",
            ))
        except (ProjectFormatError, ValueError) as exc:
            self.statusBar().showMessage(str(exc))
            return
        self.workflow = self.project.workflow
        self._refresh_all()

    def _edit_selected_recommendation(self) -> None:
        recommendation = self._selected_proposal_recommendation()
        if recommendation is None or self.project is None:
            self.statusBar().showMessage("Select an editable proposal recommendation first.")
            return
        name = self.proposal_edit_parameter.currentText()
        if not name:
            self.statusBar().showMessage("Selected recommendation has no editable parameters.")
            return
        raw = self.proposal_edit_value.text().strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        try:
            self._replace_project(self.project.edit_proposal_recommendation(
                recommendation.recommendation_id, {name: value},
                self.proposal_edit_note.text().strip() or "Engineer edited proposal parameter.",
            ))
        except (ProjectFormatError, ValueError) as exc:
            self.statusBar().showMessage(str(exc))
            return
        self.workflow = self.project.workflow
        self._refresh_all()

    def _decide_fixture_proposal(self, decision: str) -> None:
        if self.project is None or self.project.fixture_proposal is None:
            return
        try:
            self._replace_project(self.project.decide_fixture_proposal(decision))
        except (ProjectFormatError, ValueError) as exc:
            self.statusBar().showMessage(str(exc))
            return
        self.workflow = self.project.workflow
        self._refresh_all()

    def _populate_guided_validation(self) -> None:
        self.guided_issues.clear()
        self._guided_issue_records.clear()
        proposal = self.project.fixture_proposal if self.project else None
        if proposal is None:
            self.guided_validation_summary.setText(
                "Generate a fixture proposal to see guided validation findings."
            )
            self.guided_fix.setEnabled(False)
            return
        if proposal.blocker_count:
            title = "Validation failed"
        elif proposal.warning_count:
            title = "Validation requires engineering review"
        else:
            title = "Validation passed"
        self.guided_validation_summary.setText(
            f"{title}\n{proposal.blocker_count} blocking issues\n"
            f"{proposal.warning_count} warnings requiring review"
        )
        for issue in proposal.guided_issues:
            self._guided_issue_records[issue.issue_id] = issue
            item = QListWidgetItem(
                f"{issue.severity.upper()} | {issue.title}\n"
                f"{issue.what_is_wrong}"
            )
            item.setData(Qt.ItemDataRole.UserRole, issue.issue_id)
            self.guided_issues.addItem(item)
        self.guided_fix.setEnabled(bool(proposal.guided_issues))

    def _selected_guided_issue(self):
        selected = self.guided_issues.selectedItems()
        if not selected:
            return None
        return self._guided_issue_records.get(str(selected[0].data(Qt.ItemDataRole.UserRole)))

    def _guided_issue_selection_changed(self) -> None:
        issue = self._selected_guided_issue()
        if issue is None:
            return
        self._active_guided_issue = issue.issue_id
        self.guided_issue_explanation.setText(
            f"What is wrong: {issue.what_is_wrong}\n"
            f"Why it matters: {issue.why_it_matters}\n"
            f"Affected item: {issue.affected_identity or 'workflow evidence'}\n"
            f"Where to fix it: {issue.workflow_section}"
        )
        self.guided_technical_details.setText(
            f"Rule: {issue.rule_id}\n" + "\n".join(issue.technical_details)
        )
        if issue.affected_identity and self._scene() is not None:
            self._scene().select(issue.affected_identity)

    def fix_selected_guided_issue(self) -> None:
        issue = self._selected_guided_issue()
        if issue is None:
            self.statusBar().showMessage("Select a guided validation issue first.")
            return
        self._navigate_stage(issue.workflow_section)
        control = getattr(self, issue.fix_target, None)
        if isinstance(control, QWidget):
            control.setFocus(Qt.FocusReason.OtherFocusReason)
            scroll = control.parentWidget()
            while scroll is not None and not isinstance(scroll, QScrollArea):
                scroll = scroll.parentWidget()
            if isinstance(scroll, QScrollArea):
                scroll.ensureWidgetVisible(control)
            signal = None
            if isinstance(control, QComboBox):
                signal = control.currentTextChanged
            elif isinstance(control, QLineEdit):
                signal = control.editingFinished
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                signal = control.valueChanged
            elif isinstance(control, QCheckBox):
                signal = control.toggled
            if signal is not None:
                if self._guided_fix_signal is not None:
                    old_signal, old_callback = self._guided_fix_signal
                    try:
                        old_signal.disconnect(old_callback)
                    except (RuntimeError, TypeError):
                        pass
                callback = lambda *_args, identity=issue.issue_id: self._guided_correction_changed(identity)
                signal.connect(callback)
                self._guided_fix_signal = (signal, callback)
        if issue.affected_identity and self._scene() is not None:
            self._scene().select(issue.affected_identity)
        self.statusBar().showMessage(
            f"Fix {issue.title} in {issue.workflow_section}; validation re-evaluates after the change."
        )

    def _guided_correction_changed(self, issue_identity: str) -> None:
        if self._guided_fix_signal is not None:
            signal, callback = self._guided_fix_signal
            self._guided_fix_signal = None
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        if self.workflow is None or self.project is None or self.project.fixture_proposal is None:
            return
        setup = self._capture_process_setup(persist=False)
        self.workflow = replace(self.workflow, setup=setup)
        self._replace_project(self.project.with_workflow(self.workflow))
        self._refresh_all()
        remaining = [
            index for index in range(self.guided_issues.count())
            if self.guided_issues.item(index).data(Qt.ItemDataRole.UserRole) == issue_identity
        ]
        if remaining:
            self.guided_issues.setCurrentRow(remaining[0])
        elif self.guided_issues.count():
            self.guided_issues.setCurrentRow(0)
        self.statusBar().showMessage(
            "Deterministic proposal validation re-evaluated; next unresolved issue selected."
        )

    def _restore_layout(self) -> None:
        if not self._settings_enabled:
            self.reset_workbench_layout(persist=False)
            return
        geometry = self.settings.value("workbench/geometry")
        state = self.settings.value("workbench/state")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            self.restoreState(state)
        else:
            self.reset_workbench_layout(persist=False)

    def reset_workbench_layout(self, *, persist: bool = True) -> None:
        self.resize(1500, 900)
        explorer = self.findChild(QDockWidget, "engineeringExplorerDock")
        workflow = self.findChild(QDockWidget, "workflowDock")
        review = self.findChild(QDockWidget, "reviewDock")
        for dock in (explorer, workflow, review):
            if dock is not None:
                dock.show()
        if explorer is not None and workflow is not None:
            self.tabifyDockWidget(explorer, workflow)
            explorer.raise_()
        docks = [dock for dock in (explorer, review) if dock is not None]
        if docks:
            self.resizeDocks(docks, [250, 320][:len(docks)], Qt.Orientation.Horizontal)
        if persist and self._settings_enabled:
            self.settings.remove("workbench/geometry")
            self.settings.remove("workbench/state")
        self.statusBar().showMessage("Workbench layout restored; project data was not changed.")

    def _workflow_states(self) -> dict[str, str]:
        states = {name: "not started" for name in (
            "Project", "Import", "Assembly", "Manufacturing Intent", "Orientation", "Proposal",
            "Datums", "Locators & Supports", "Clamps", "Base Structure",
            "Weld & Access", "Concepts", "Validation", "Cost & Volume",
            "Review & Approval", "Export", "Component Library",
            "Rules & Preferences", "Project History",
        )}
        has_source = self.document is not None or self.project is not None
        if not has_source:
            states["Project"] = "available"
            states["Import"] = "available"
            states["Rules & Preferences"] = "deferred"
            return states
        for name in ("Project", "Import", "Assembly"):
            states[name] = "complete"
        states["Manufacturing Intent"] = "complete" if self.workflow else "available"
        orientation = self.workflow.setup.manufacturing_orientation if self.workflow else None
        source_sha256 = self.document.source_sha256 if self.document else (
            self.project.product.source_sha256 if self.project else None
        )
        states["Orientation"] = (
            "complete" if orientation and source_sha256 and orientation.accepted
            and not orientation.is_stale_for(source_sha256) else "warning"
        )
        proposal = self.project.fixture_proposal if self.project else None
        if proposal is None:
            states["Proposal"] = "available" if states["Orientation"] == "complete" else "not started"
        else:
            proposal_stale = proposal.stale_reason(
                self.project.product.source_sha256, orientation.identity if orientation else None,
                proposal_engineering_context_identity(self.project)
                if self.workflow and self.workflow.has_accepted_manufacturing_orientation()
                else None,
            )
            states["Proposal"] = (
                "stale" if proposal_stale else "blocked" if proposal.blocker_count else
                "warning" if proposal.warning_count else "complete"
            )
        has_annotations = bool(self.workflow and self.workflow.geometry_annotations)
        states["Datums"] = "complete" if has_annotations else "available"
        analyzed = bool(self.workflow and self.workflow.analysis_completed
                        and self.workflow.has_accepted_manufacturing_orientation())
        for name in ("Locators & Supports", "Clamps", "Base Structure", "Weld & Access"):
            states[name] = "complete" if analyzed else "available"
        concepts = bool(self.workflow and self.workflow.concepts_generated
                        and self.workflow.has_accepted_manufacturing_orientation())
        states["Concepts"] = "complete" if concepts else ("available" if analyzed else "not started")
        states["Cost & Volume"] = "complete" if concepts else "not started"
        if self.project is not None:
            validation = self.project.active_validation.status
            states["Validation"] = {
                "valid": "complete", "provisional": "warning", "invalid": "blocked",
            }.get(validation, "not evaluated")
            if self.project.suppressed_features or self.project.active.corrections:
                states["Concepts"] = "engineer modified"
                states["Validation"] = "stale"
            states["Review & Approval"] = (
                "complete" if self.project.approved_revision else
                "blocked" if (
                    self.project.active_validation.blocked
                    or self.project.suppressed_features
                    or self.project.active.corrections
                    or project_export_block_reason(self.project) is not None
                ) else "available"
            )
            states["Export"] = (
                "blocked" if (
                    self.project.active_validation.blocked
                    or self.project.suppressed_features
                    or self.project.active.corrections
                    or project_export_block_reason(self.project) is not None
                ) else "available"
            )
            states["Project History"] = "complete" if self.project.revisions else "available"
            if proposal is not None:
                for issue in proposal.guided_issues:
                    section = issue.workflow_section
                    if section not in states:
                        continue
                    if issue.severity == "error":
                        states[section] = "blocked"
                    elif issue.severity == "warning" and states[section] != "blocked":
                        states[section] = "warning"
        states["Component Library"] = (
            "complete" if self.workflow and self.workflow.customer_tooling else "available"
        )
        states["Rules & Preferences"] = "deferred"
        return states

    def _populate_workflow_rail(self) -> None:
        stage_map = {
            "Product": "Project", "Datums and intent": "Datums",
            "Concepts": "Concepts", "Proposal": "Proposal", "Validation": "Validation",
        }
        active = self._ui_active_stage
        if active is None and self.workflow is not None:
            active = stage_map.get(self.workflow.active_stage, self.workflow.active_stage)
        if active is None:
            active = "Project"
        self.workflow_rail.set_states(self._workflow_states(), active)

    def _refresh_shell_state(self) -> None:
        if self.document is not None:
            self.source_badge.set_source(
                self.document.source_name, self.document.source_sha256, verified=True
            )
            self.project_title.setText(self.document.source_name)
        elif self.project is not None:
            self.source_badge.set_source(
                self.project.product.source_name,
                self.project.product.source_sha256,
                verified=False,
            )
            self.project_title.setText(self.project.product.source_name)
        else:
            self.source_badge.clear_source()
            self.project_title.setText("Engineering Workbench")
        orientation = self.workflow.setup.manufacturing_orientation if self.workflow else None
        if orientation and orientation.accepted and not orientation.is_stale_for(
                self.document.source_sha256 if self.document else self.project.product.source_sha256 if self.project else ""):
            self.status_coordinates.setText("Coordinate: Manufacturing XYZ (accepted)")
        elif self.document is not None or self.project is not None:
            self.status_coordinates.setText("Coordinate: Source CAD (orientation required)")
        else:
            self.status_coordinates.setText("Coordinate: Project")

        diagnostics = self.viewport.diagnostics()
        if diagnostics and diagnostics.native_rendering_active and not diagnostics.fallback_active:
            self.renderer_health.set_status("pass", "VTK")
        elif self.document is not None:
            self.renderer_health.set_status("warning", "VTK WARNING")
        else:
            self.renderer_health.set_status("notEvaluated", "VTK")

        export_block_reason = (
            project_export_block_reason(self.project) if self.project is not None else None
        )
        if self.project is None:
            status = "not evaluated"
            failures = warnings = 0
            can_approve = approved = False
        else:
            status = self.project.active_validation.status
            failures = sum(
                finding.severity == "error" for finding in self.project.active_validation.findings
            )
            warnings = sum(
                finding.severity == "warning" for finding in self.project.active_validation.findings
            )
            can_approve = (
                not self.project.active_validation.blocked
                and not self.project.suppressed_features
                and not self.project.active.corrections
                and export_block_reason is None
            )
            approved = self.project.approved_revision == self.project.revision_id
        self.status_validation.set_status(status, status.upper())
        self.approval_gate.set_result(
            status, failures, warnings, can_approve=can_approve, approved=approved
        )
        self.status_selection.setText(f"Selection: {self.selected_identity or '-'}")

        action_state = {
            "save_project": self.project is not None,
            "export": self.project is not None and export_block_reason is None,
            "recover": self.project_path is not None,
            "fit": self.document is not None,
            "edit_orientation": self.document is not None and self.workflow is not None,
            "generate_proposal": bool(
                self.document is not None and self.workflow is not None
                and self.workflow.has_accepted_manufacturing_orientation()
            ),
            "analyze": self.document is not None and self.workflow is not None
            and self.workflow.setup.manufacturing_orientation is not None
            and self.workflow.setup.manufacturing_orientation.accepted
            and not self.workflow.setup.manufacturing_orientation.is_stale_for(self.document.source_sha256),
            "generate": bool(self.project and self.workflow and self.workflow.analysis_completed
                              and self.workflow.has_accepted_manufacturing_orientation()),
            "findings": self.project is not None,
            "approve": can_approve and not approved,
            "reject": self.project is not None,
        }
        for key, enabled in action_state.items():
            if key in self._actions:
                self._actions[key].setEnabled(enabled)
        if "export" in self._actions:
            self._actions["export"].setToolTip(
                f"Export disabled: {export_block_reason}." if export_block_reason else
                "Export the current engineering review package"
            )
        self._populate_workflow_rail()

    def show_first_run_guide(self, force: bool = False) -> None:
        if not force and bool(self.settings.value("guide/fixture_proposal_dismissed", False, type=bool)):
            return
        existing = getattr(self, "_first_run_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        dialog = QDialog(self)
        dialog.setObjectName("fixtureProposalFirstRunGuide")
        dialog.setWindowTitle("FXD Fixture Proposal Guide")
        dialog.setModal(False)
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        pages = QStackedWidget(dialog)
        for title, message in (
            ("1. Orient the product",
             "Select fixture-down and operator-front faces. FXD stores manufacturing XYZ separately; source CAD remains unchanged."),
            ("2. Generate one proposal",
             "Confirm only missing essential intent, then generate. A configured AI provider may propose; the deterministic baseline remains available offline."),
            ("3. Review and validate",
             "Accept, reject, suppress, or edit each recommendation. Fix blockers through guided navigation before approval or export."),
        ):
            page = QWidget(pages)
            page_layout = QVBoxLayout(page)
            heading = QLabel(title, page)
            heading.setProperty("sectionHeading", True)
            body = QLabel(message, page)
            body.setWordWrap(True)
            page_layout.addWidget(heading)
            page_layout.addWidget(body)
            page_layout.addStretch(1)
            pages.addWidget(page)
        controls = QHBoxLayout()
        back = QPushButton("Back", dialog)
        next_button = QPushButton("Next", dialog)
        dismiss = QPushButton("Dismiss", dialog)
        never = QCheckBox("Don't show this again", dialog)

        def update_buttons() -> None:
            back.setEnabled(pages.currentIndex() > 0)
            next_button.setText("Finish" if pages.currentIndex() == pages.count() - 1 else "Next")

        def advance() -> None:
            if pages.currentIndex() == pages.count() - 1:
                close_guide()
            else:
                pages.setCurrentIndex(pages.currentIndex() + 1)
                update_buttons()

        def close_guide() -> None:
            if never.isChecked():
                self.settings.setValue("guide/fixture_proposal_dismissed", True)
            dialog.close()

        back.clicked.connect(lambda: (pages.setCurrentIndex(pages.currentIndex() - 1), update_buttons()))
        next_button.clicked.connect(advance)
        dismiss.clicked.connect(close_guide)
        controls.addWidget(never)
        controls.addStretch(1)
        controls.addWidget(back)
        controls.addWidget(next_button)
        controls.addWidget(dismiss)
        layout.addWidget(pages)
        layout.addLayout(controls)
        update_buttons()
        self._first_run_dialog = dialog
        dialog.show()

    def show_about(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("About FXD")
        dialog.setMinimumWidth(640)
        layout = QVBoxLayout(dialog)
        artwork = QLabel(dialog)
        pixmap = QPixmap(str(asset_path(
            "assets", "branding", "logos", "fxd-logo-approved-dark-1600x900.png"
        )))
        artwork.setPixmap(pixmap.scaled(
            600, 338, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message = QLabel(
            "FXD - Intelligent Industrial Fixture Design\n"
            "AI proposes. Engineering validates.\n"
            "Engineering review only; no automatic production approval.",
            dialog,
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(artwork)
        layout.addWidget(message)
        layout.addWidget(buttons)
        dialog.exec()

    def import_step(self) -> None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Import STEP", "", "STEP files (*.step *.stp);;All files (*)"
        )
        if name:
            self.load_step_path(Path(name))

    def load_step_path(self, source: Path) -> None:
        self._invalidate_pending_proposal_generation()
        try:
            before = source.read_bytes()
            before_digest = sha256(before).hexdigest()
            import_started = perf_counter()
            document = load_step_for_workbench(source)
            import_elapsed_ms = round((perf_counter() - import_started) * 1000.0, 3)
            after_digest = sha256(source.read_bytes()).hexdigest()
            if before_digest != after_digest or before != document.source_bytes:
                raise RuntimeError("source STEP identity changed during import")
            self.viewport.load_document(document)
            self.document = document
            self._replace_project(None)
            self.workflow = InteractiveWorkflow(
                document.source_sha256,
                ProcessSetup(project_name=source.stem),
                timings=(OperationTiming("step_import", import_elapsed_ms),),
            )
            self.project_path = None
            self.selected_identity = None
            self.selected_reference = None
            self._refresh_all()
            self._prepare_guided_orientation()
            self._navigate_stage("Orientation")
            self.setWindowTitle(f"FXD - {source.name} - engineering review only")
            self.statusBar().showMessage(
                f"Loaded immutable STEP through OCP in {import_elapsed_ms:.1f} ms: "
                f"{document.component_count} components."
            )
            self.log.record("step_opened", source_sha256=document.source_sha256,
                            component_count=document.component_count,
                            elapsed_ms=import_elapsed_ms)
            if self._settings_enabled and not self._first_successful_source_import:
                self._first_successful_source_import = True
                QTimer.singleShot(0, self.show_first_run_guide)
        except Exception as exc:
            logger.exception("STEP import failed for %s", source)
            self.viewport.clear()
            self.document = None
            self._replace_project(None)
            self.workflow = None
            self.project_path = None
            self.selected_identity = None
            self.selected_reference = None
            self._refresh_all()
            self.setWindowTitle("FXD - Engineering Workbench - review only")
            self.statusBar().showMessage(f"STEP import failed closed: {exc}")
            QMessageBox.critical(self, "STEP import failed", str(exc))
            raise

    def open_project(self) -> None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Open FXD project", "", "FXD projects (*.fxd.json)"
        )
        if name:
            self.load_project_path(Path(name))

    def load_project_path(self, source: Path) -> None:
        self._invalidate_pending_proposal_generation()
        self._replace_project(FxdProject.load(source))
        self.workflow = self.project.workflow
        self.project_path = source
        self.document = None
        try:
            self.document = load_step_for_workbench(
                self.project.product.source_bytes,
                source_name=self.project.product.source_name,
            )
            self.viewport.load_document(self.document)
        except Exception:
            # A renderer failure cannot invalidate an otherwise readable project.
            logger.exception("project source has no authoritative real-kernel display evidence")
            self.viewport.clear()
            self.document = None
        self._refresh_all()
        self._show_active_concept_geometry()
        if self.workflow is not None and not self.workflow.has_accepted_manufacturing_orientation():
            self._prepare_guided_orientation()
            self._navigate_stage("Orientation")
        self.log.record("project_opened", source_sha256=self.project.product.source_sha256,
                        revision=self.project.revision_id)
        self.statusBar().showMessage(
            "Project opened; deterministic validation remains authoritative."
        )

    def save_project(self) -> None:
        if self.project is None:
            self.statusBar().showMessage("No FXD project is open.")
            return
        name, _ = QFileDialog.getSaveFileName(
            self, "Save FXD project", "", "FXD projects (*.fxd.json)"
        )
        if name:
            self.save_project_path(Path(name))

    def save_project_path(self, destination: Path) -> None:
        if self.project is None:
            raise ProjectFormatError("no FXD project is open")
        self.project.save(destination)
        self.project_path = destination
        ProjectRecovery(destination).autosave(self.project)
        self.log.record("project_saved", revision=self.project.revision_id)
        self.statusBar().showMessage("Project saved; production approval is not implied.")

    def export_package(self) -> None:
        if self.project is None:
            self.statusBar().showMessage("No validated FXD project is open.")
            return
        block_reason = project_export_block_reason(self.project)
        if block_reason is not None:
            self.log.record(
                "export_blocked", revision=self.project.revision_id, reason=block_reason
            )
            QMessageBox.warning(self, "Export blocked", block_reason)
            self.statusBar().showMessage(
                "Export blocked by deterministic validation or stale review state; "
                "no review package was written."
            )
            return
        destination = QFileDialog.getExistingDirectory(self, "Export engineering review package")
        if destination:
            try:
                paths = export_project_package(self.project, destination, kernel=self.kernel)
                if self.project.fixture_build is not None:
                    authored = self._active_authored_fixture_build()
                    if authored is None:
                        authored = author_fixture_build(
                            self.project.fixture_build, self.project.product, self.kernel,
                        )
                    self.authored_fixture_build = authored
            except ExportError as exc:
                self.log.record(
                    "export_blocked", revision=self.project.revision_id, reason=str(exc)
                )
                QMessageBox.warning(self, "Export blocked", str(exc))
                self.statusBar().showMessage(
                    "Export blocked by deterministic validation; no review package was written."
                )
                return
            except (FixtureBuildError, KernelOperationError) as exc:
                self.log.record("export_blocked", revision=self.project.revision_id, reason=str(exc))
                QMessageBox.warning(self, "Manufacturing export blocked", str(exc))
                self.statusBar().showMessage("Manufacturing export blocked; no M30 package was written.")
                return
            self.statusBar().showMessage(
                f"Exported {len(paths)} review artifacts; production approval is not implied."
            )

    def recover_autosave(self) -> None:
        if self.project_path is None:
            self.statusBar().showMessage("Open or save a project before recovering autosave.")
            return
        self._replace_project(ProjectRecovery(self.project_path).recover())
        self.workflow = self.project.workflow
        self._refresh_all()
        self.statusBar().showMessage("Autosave recovered; deterministic revalidation remains required.")

    def _refresh_all(self) -> None:
        self._sync_layer_actions()
        self._populate_tree()
        self._populate_properties()
        self._populate_findings()
        self._populate_proposal()
        self._populate_guided_validation()
        self._populate_workflow()
        self._refresh_shell_state()

    def _sync_layer_actions(self) -> None:
        for layer in sorted(SUPPORTED_LAYERS):
            action = self._actions.get("layer_" + layer)
            if action is None:
                continue
            action.setEnabled(self.project is not None)
            action.setChecked(
                self.project is None or layer not in self.project.hidden_layers
            )
        if self.project is not None and self._scene() is not None:
            self._scene().set_visible("product" not in self.project.hidden_layers)

    def _add_tree_category(self, title: str, items: list[tuple[str, str, str]]) -> None:
        if not items:
            return
        category = QTreeWidgetItem([title, ""])
        self.tree.addTopLevelItem(category)
        for label, identity, status in items:
            child = QTreeWidgetItem([label, status])
            child.setData(0, Qt.ItemDataRole.UserRole, identity)
            category.addChild(child)
        category.setExpanded(True)

    def _populate_tree(self) -> None:
        self.tree.clear()
        self._geometry_references.clear()
        if self.document:
            self._add_tree_category("Imported assembly", [
                (self.document.source_name, self.document.assembly.root_reference, EVIDENCE_REAL)
            ])
            product = self.project.product if self.project else product_from_workbench_document(self.document)
            component_models = {item.identity: item for item in product.components}
            category = QTreeWidgetItem(["Components", ""])
            self.tree.addTopLevelItem(category)
            if self.document.assembly.components:
                for component in self.document.assembly.components:
                    node = QTreeWidgetItem([component.name, "real OCP component"])
                    node.setData(0, Qt.ItemDataRole.UserRole, component.reference)
                    category.addChild(node)
                    model = component_models[component.reference]
                    body_identity = model.bodies[0].identity
                    for face in component.faces:
                        reference = GeometryReference(component.reference, body_identity, face.reference)
                        self._geometry_references[face.reference] = reference
                        child = QTreeWidgetItem([
                            f"Face {face.reference.removeprefix('face:')[:12]}",
                            f"{face.area_mm2:.2f} mm2",
                        ])
                        child.setData(0, Qt.ItemDataRole.UserRole, face.reference)
                        node.addChild(child)
            else:
                model = product.components[0]
                body_identity = model.bodies[0].identity
                node = QTreeWidgetItem(["Source geometry", "real OCP shape"])
                node.setData(0, Qt.ItemDataRole.UserRole, "source:geometry")
                category.addChild(node)
                for mesh in self.document.meshes:
                    reference = GeometryReference("source:geometry", body_identity, mesh.face_reference)
                    self._geometry_references[mesh.face_reference] = reference
                    child = QTreeWidgetItem([
                        f"Face {mesh.face_reference.removeprefix('face:')[:12]}",
                        "normal unavailable",
                    ])
                    child.setData(0, Qt.ItemDataRole.UserRole, mesh.face_reference)
                    node.addChild(child)
            category.setExpanded(True)
        elif self.project:
            components = [
                (component.name, component.identity, "normalized source")
                for component in self.project.product.components
            ]
            self._add_tree_category("Product geometry", components)

        if (self.project and self.workflow and self.workflow.concepts_generated
                and self.workflow.has_accepted_manufacturing_orientation()):
            concepts = [(item.identity, item.identity,
                         self.project.validation_for(item).status)
                        for item in self.project.concepts]
            self._add_tree_category("Fixture concepts", concepts)
            feature_groups: dict[str, list[tuple[str, str, str]]] = {}
            for feature in self.project.active.fixture.features:
                feature_groups.setdefault(feature.kind, []).append(
                    (feature.identity, feature.identity,
                     f"{self.project.active_validation.status} provisional review geometry")
                )
            titles = {
                "datum": "Datums", "locator": "Locators", "round_pin": "Locators",
                "relieved_locator": "Locators", "support": "Supports", "stop": "Stops",
                "clamp": "Clamps", "baseplate": "Fixture geometry",
            }
            combined: dict[str, list[tuple[str, str, str]]] = {}
            for kind, items in feature_groups.items():
                combined.setdefault(titles.get(kind, "Fixture geometry"), []).extend(items)
            for title, items in sorted(combined.items()):
                self._add_tree_category(title, items)
            welds = [
                (joint.identity, joint.identity, "engineering annotation")
                for joint in self.project.annotations.weld_joints
            ]
            self._add_tree_category("Welds", welds)
        if self.project and self.project.fixture_build:
            active_authored = self._active_authored_fixture_build()
            authored = {item.component.identity for item in (active_authored.components if active_authored else ())}
            self._add_tree_category("Manufacturing fixture components", [
                (f"{item.part_number} | {item.role.value}", item.identity,
                 "authored OCP B-Rep" if item.identity in authored else item.geometry_authority.value)
                for item in self.project.fixture_build.components
            ])
        self.tree.resizeColumnToContents(1)

    def _populate_properties(self) -> None:
        source_name = "-"
        source_hash = "-"
        components = faces = triangles = 0
        evidence = EVIDENCE_PROVISIONAL
        validation = "Not evaluated"
        if self.document:
            source_name = self.document.source_name
            source_hash = self.document.source_sha256
            components = self.document.component_count
            faces = len(self.document.meshes)
            triangles = sum(len(mesh.triangles) for mesh in self.document.meshes)
            evidence = EVIDENCE_REAL
        elif self.project:
            source_name = self.project.product.source_name
            source_hash = self.project.product.source_sha256
            components = len(self.project.product.components)
        if self.project:
            validation = self.project.active_validation.status.upper()

        self._set_property("Source file", source_name)
        self._set_property("Source SHA-256", source_hash)
        self._set_property("Components", components)
        self._set_property("Faces", faces)
        self._set_property("Triangles", triangles)
        self._set_property("Selected identity", self.selected_identity or "-")
        self._set_property("Evidence", evidence)
        self._set_property("Validation", validation)
        self._set_property("Project revision", self.project.revision_id if self.project else "-")
        self._set_property("Evidence digest", self.project.active_validation.evidence_digest if self.project else "-")
        self._set_property("Workflow stage", self.workflow.active_stage if self.workflow else "Not started")
        diagnostics = self.viewport.diagnostics()
        self._set_property("Render backend", diagnostics.backend if diagnostics else "unavailable")
        self._set_property("Actors", diagnostics.actor_count if diagnostics else 0)
        self._set_property("Points", diagnostics.point_count if diagnostics else 0)
        self._set_property("Native rendering", diagnostics.native_rendering_active if diagnostics else False)
        self._set_property("Fallback", diagnostics.fallback_active if diagnostics else False)

    @staticmethod
    def _finding_identity(finding: object) -> str:
        payload = "|".join((
            str(getattr(finding, "code", "")), str(getattr(finding, "subsystem", "")),
            str(getattr(finding, "message", "")),
        ))
        return "finding-" + sha256(payload.encode()).hexdigest()[:16]

    def _populate_findings(self, *_args: object) -> None:
        self.findings.clear()
        self._finding_records.clear()
        if self.project:
            all_findings = self.project.active_validation.findings
            categories = sorted({finding.subsystem for finding in all_findings})
            current_category = self.finding_category.currentText()
            self.finding_category.blockSignals(True)
            self.finding_category.clear()
            self.finding_category.addItems(("All categories", *categories))
            if current_category in {"All categories", *categories}:
                self.finding_category.setCurrentText(current_category)
            self.finding_category.blockSignals(False)
            severity = self.finding_severity.currentText()
            category = self.finding_category.currentText()
            for finding in all_findings:
                if severity != "All severities" and finding.severity != severity:
                    continue
                if category != "All categories" and finding.subsystem != category:
                    continue
                identity = self._finding_identity(finding)
                self._finding_records[identity] = finding
                reviewed = bool(self.workflow and identity in self.workflow.reviewed_findings)
                row = QListWidgetItem(
                    f"{'REVIEWED | ' if reviewed else ''}{finding.severity.upper()} | "
                    f"{finding.subsystem} | {finding.code}\n{finding.message}"
                )
                row.setData(Qt.ItemDataRole.UserRole, identity)
                self.findings.addItem(row)
        if self.findings.count() == 0:
            self.findings.addItem("No deterministic engineering findings are available for this view.")

    def _finding_selection_changed(self) -> None:
        selected = self.findings.selectedItems()
        if not selected:
            return
        identity = selected[0].data(Qt.ItemDataRole.UserRole)
        finding = self._finding_records.get(str(identity))
        if finding is None:
            return
        for evidence in getattr(finding, "evidence", ()):
            candidate = str(evidence).split("=", 1)[-1]
            if self._scene() and self._scene().select(candidate):
                self.selected_identity = candidate
                self._set_property("Selected identity", candidate)
                self.statusBar().showMessage(
                    f"Finding {getattr(finding, 'code', '')} linked to {candidate}."
                )
                return
        self.statusBar().showMessage(
            f"Finding {getattr(finding, 'code', '')} has no supported viewport identity mapping."
        )

    def mark_selected_finding_reviewed(self) -> None:
        selected = self.findings.selectedItems()
        if not selected or self.workflow is None:
            self.statusBar().showMessage("Select a deterministic finding first.")
            return
        identity = selected[0].data(Qt.ItemDataRole.UserRole)
        if not identity:
            return
        self.workflow = self.workflow.mark_finding_reviewed(str(identity))
        if self.project is not None:
            self._replace_project(self.project.with_workflow(self.workflow))
        self._refresh_all()
        self.statusBar().showMessage("Finding marked reviewed; validation status was not changed.")

    def _tree_selection_changed(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            return
        identity = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not identity:
            return
        self.selected_identity = str(identity)
        self.selected_reference = self._geometry_references.get(self.selected_identity)
        mapped = bool(self.viewport.scene and self.viewport.scene.select(self.selected_identity))
        self._set_property("Selected identity", self.selected_identity)
        self.status_selection.setText(f"Selection: {self.selected_identity}")
        if self.selected_reference is not None:
            self.annotation_selection.setText(
                f"Exact OCP face selected: {self.selected_reference.face_identity}"
            )
        if self.project and self.selected_identity in {item.identity for item in self.project.concepts}:
            self.select_concept(self.selected_identity)
        message = f"Selected {self.selected_identity}."
        if not mapped:
            message += " Geometry identity mapping is not available for this item."
        self.statusBar().showMessage(message)

    def _set_orientation_pick_mode(self, enabled: bool) -> None:
        scene = self._scene()
        method = getattr(scene, "set_face_picking", None) if scene is not None else None
        if callable(method):
            method(enabled)

    def _reference_for_face_identity(self, face_identity: str) -> GeometryReference | None:
        for reference in self._geometry_references.values():
            if reference.face_identity == face_identity:
                return reference
        return None

    def _face_summary(self, reference: GeometryReference | None, role: str) -> str:
        if self.document is None or reference is None:
            return f"No {role} face selected."
        face = next((face for component in self.document.assembly.components
                     if component.reference == reference.component_identity
                     for face in component.faces if face.reference == reference.face_identity), None)
        if face is None:
            return f"The selected {role} face is no longer available for this source."
        surface = "planar" if face.is_planar else "not planar"
        return f"{role.title()} face selected · {surface} · area {face.area_mm2:.2f} mm²"

    def _viewer_face_picked(self, face_identity: str) -> None:
        if self.workflow is None or self.orientation_guided_step not in {0, 1}:
            return
        if not face_identity:
            self.orientation_guided_error.setText(
                "No model face was found at that point. Rotate or zoom, then click a planar face."
            )
            return
        reference = self._reference_for_face_identity(face_identity)
        if reference is None:
            self.orientation_guided_error.setText(
                "That tessellation cell is not linked to exact source-face evidence. Pick another face."
            )
            return
        self.selected_reference = reference
        self.selected_identity = face_identity
        self._select_guided_face(reference)

    def _select_guided_face(self, reference: GeometryReference) -> None:
        if self.document is None:
            return
        if self.orientation_guided_step == 0:
            try:
                draft = orientation_from_face(
                    self.document, reference,
                    flip_normal=self.orientation_flip_normal.isChecked(),
                )
            except ManufacturingOrientationError as exc:
                self.orientation_guided_error.setText(str(exc))
                return
            self.orientation_face_reference = reference
            self.orientation_front_reference = None
            self.orientation_pending_reference = reference
            self.orientation_guided_error.setText("")
            self._commit_orientation(draft)
            self._preview_orientation_camera(draft)
        else:
            self.orientation_front_reference = reference
            self.orientation_pending_reference = reference
            try:
                draft = self._guided_orientation(accepted=False)
            except ManufacturingOrientationError as exc:
                invalid_front = reference
                bottom_draft = orientation_from_face(
                    self.document, self.orientation_face_reference,
                    flip_normal=self.orientation_flip_normal.isChecked(),
                )
                self._commit_orientation(bottom_draft)
                self.orientation_front_reference = invalid_front
                self.orientation_guided_error.setText(str(exc))
                self._show_active_concept_geometry()
                self._refresh_guided_orientation()
                return
            self.orientation_guided_error.setText("")
            self._commit_orientation(draft)
            self._preview_orientation_camera(draft)
        self._refresh_guided_orientation()

    def _guided_orientation(self, *, accepted: bool) -> ManufacturingOrientation:
        if self.document is None or self.orientation_face_reference is None:
            raise ManufacturingOrientationError("select and accept a planar bottom face first")
        if self.orientation_front_reference is None:
            raise ManufacturingOrientationError("select a planar operator/front face")
        return orientation_from_faces(
            self.document, self.orientation_face_reference, self.orientation_front_reference,
            flip_bottom=self.orientation_flip_normal.isChecked(), accepted=accepted,
        )

    def _preview_orientation_camera(self, orientation: ManufacturingOrientation) -> None:
        scene = self._scene()
        method = getattr(scene, "preview_orientation", None) if scene is not None else None
        if callable(method):
            method(
                tuple(orientation.manufacturing_x_source.__dict__.values()),
                tuple(orientation.manufacturing_y_source.__dict__.values()),
                tuple(orientation.manufacturing_z_source.__dict__.values()),
            )

    def _prepare_guided_orientation(self) -> None:
        self.orientation_face_reference = None
        self.orientation_front_reference = None
        self.orientation_pending_reference = None
        self.orientation_guided_step = 0
        self.orientation_recommendation = None
        if self.document is not None:
            try:
                recommendations = recommend_orientations(self.document)
            except ManufacturingOrientationError:
                recommendations = ()
            if recommendations:
                self.orientation_recommendation = recommendations[0].orientation.selected_reference
        self._set_orientation_pick_mode(True)
        self._refresh_guided_orientation()

    def use_recommended_bottom_face(self) -> None:
        if self.orientation_recommendation is None:
            return
        self._select_guided_face(self.orientation_recommendation)
        if self.orientation_face_reference is not None:
            self.accept_guided_bottom_face()

    def accept_guided_bottom_face(self) -> None:
        if self.orientation_face_reference is None:
            self.orientation_guided_error.setText("Click a planar bottom face before continuing.")
            return
        self.orientation_pending_reference = None
        self.orientation_front_reference = None
        self.orientation_guided_step = 1
        self._set_orientation_pick_mode(True)
        self._refresh_guided_orientation()

    def pick_another_bottom_face(self) -> None:
        self.orientation_face_reference = None
        self.orientation_front_reference = None
        self.orientation_pending_reference = None
        self.orientation_guided_step = 0
        self._commit_orientation(None)
        self._set_orientation_pick_mode(True)
        self._refresh_guided_orientation()

    def flip_guided_bottom_side(self) -> None:
        if self.orientation_face_reference is None or self.document is None:
            self.orientation_guided_error.setText("Select a bottom face before flipping its side.")
            return
        self._setting_orientation_controls = True
        self.orientation_flip_normal.setChecked(not self.orientation_flip_normal.isChecked())
        self._setting_orientation_controls = False
        if self.orientation_front_reference is not None:
            try:
                draft = self._guided_orientation(accepted=False)
            except ManufacturingOrientationError as exc:
                self.orientation_guided_error.setText(str(exc))
                return
        else:
            draft = orientation_from_face(
                self.document, self.orientation_face_reference,
                flip_normal=self.orientation_flip_normal.isChecked(),
            )
        self._commit_orientation(draft)
        self._preview_orientation_camera(draft)
        self._refresh_guided_orientation()

    def preview_guided_orientation(self) -> None:
        try:
            draft = self._guided_orientation(accepted=False)
        except ManufacturingOrientationError as exc:
            self.orientation_guided_error.setText(str(exc))
            self._refresh_guided_orientation()
            return
        self._commit_orientation(draft)
        self.orientation_guided_step = 2
        self._set_orientation_pick_mode(False)
        self._preview_orientation_camera(draft)
        self._refresh_guided_orientation()

    def back_to_guided_bottom(self) -> None:
        self.orientation_front_reference = None
        self.orientation_guided_step = 0
        if self.document is not None and self.orientation_face_reference is not None:
            self._commit_orientation(orientation_from_face(
                self.document, self.orientation_face_reference,
                flip_normal=self.orientation_flip_normal.isChecked(),
            ))
        self._set_orientation_pick_mode(True)
        self._refresh_guided_orientation()

    def back_to_guided_front(self) -> None:
        self.orientation_guided_step = 1
        self._set_orientation_pick_mode(True)
        self._refresh_guided_orientation()

    def reset_guided_orientation(self) -> None:
        self._setting_orientation_controls = True
        self.orientation_flip_normal.setChecked(False)
        self._setting_orientation_controls = False
        self._commit_orientation(None)
        self._prepare_guided_orientation()

    def accept_guided_orientation(self) -> None:
        try:
            orientation = self._guided_orientation(accepted=True)
        except ManufacturingOrientationError as exc:
            self.orientation_guided_error.setText(str(exc))
            return
        self._commit_orientation(orientation)
        self.orientation_guided_step = 2
        self._set_orientation_pick_mode(False)
        self._preview_orientation_camera(orientation)
        self._refresh_guided_orientation()
        self.statusBar().showMessage(
            "Manufacturing orientation accepted. Generate a fixture proposal next."
        )
        self._navigate_stage("Proposal")

    def _refresh_guided_orientation(self) -> None:
        if not hasattr(self, "orientation_steps"):
            return
        self.orientation_steps.setCurrentIndex(self.orientation_guided_step)
        self.orientation_step_label.setText(f"STEP {self.orientation_guided_step + 1} OF 3")
        self.orientation_bottom_status.setText(
            self._face_summary(self.orientation_face_reference, "bottom")
        )
        self.orientation_front_status.setText(
            self._face_summary(self.orientation_front_reference, "front")
        )
        self.orientation_accept_bottom.setEnabled(self.orientation_face_reference is not None)
        self.orientation_flip_side.setEnabled(self.orientation_face_reference is not None)
        self.orientation_preview_button.setEnabled(self.orientation_front_reference is not None)
        self.orientation_use_recommendation.setEnabled(self.orientation_recommendation is not None)
        self.orientation_recommendation_text.setText(
            "This appears to be the primary support face. Use as fixture-down?"
            if self.orientation_recommendation is not None else
            "No confirmed planar support-face recommendation is available."
        )
        orientation = self.orientation_draft or (
            self.workflow.setup.manufacturing_orientation if self.workflow else None
        )
        self.orientation_guided_accept.setEnabled(
            orientation is not None and orientation.front_reference is not None
        )
        if orientation is not None and orientation.front_reference is not None:
            def vector(value: Vec3) -> str:
                return f"({value.x:.3f}, {value.y:.3f}, {value.z:.3f})"
            state = "Accepted" if orientation.accepted else "Preview - confirmation required"
            self.orientation_summary.setText(
                f"{state}\n"
                f"Bottom face: selected planar support face\n"
                f"Front direction / operator side: {vector(orientation.operator_front_source)}\n"
                f"Up direction: {vector(orientation.manufacturing_z_source)}\n"
                f"Manufacturing X (right): {vector(orientation.manufacturing_x_source)}\n"
                "Manufacturing Y points toward the operator; Z points up.\n"
                "Source CAD remains unchanged."
            )
        else:
            self.orientation_summary.setText(
                "Select bottom and front faces to create a manufacturing XYZ preview."
            )

    @staticmethod
    def _direction(text: str) -> Vec3 | None:
        return {
            "+X": Vec3(1.0, 0.0, 0.0), "-X": Vec3(-1.0, 0.0, 0.0),
            "+Y": Vec3(0.0, 1.0, 0.0), "-Y": Vec3(0.0, -1.0, 0.0),
            "+Z": Vec3(0.0, 0.0, 1.0), "-Z": Vec3(0.0, 0.0, -1.0),
        }.get(text)

    @staticmethod
    def _direction_text(value: Vec3 | None) -> str:
        mapping = {
            Vec3(1.0, 0.0, 0.0): "+X", Vec3(-1.0, 0.0, 0.0): "-X",
            Vec3(0.0, 1.0, 0.0): "+Y", Vec3(0.0, -1.0, 0.0): "-Y",
            Vec3(0.0, 0.0, 1.0): "+Z", Vec3(0.0, 0.0, -1.0): "-Z",
        }
        return mapping.get(value, "Unknown")

    @staticmethod
    def _orientation_method(text: str) -> OrientationMethod:
        return {
            "Auto recommend": OrientationMethod.AUTO_RECOMMEND,
            "Select planar face": OrientationMethod.SELECT_PLANAR_FACE,
            "Select reference plane": OrientationMethod.SELECT_REFERENCE_PLANE,
            "Use source orientation": OrientationMethod.SOURCE_ORIENTATION,
        }[text]

    @staticmethod
    def _orientation_method_text(value: OrientationMethod) -> str:
        return {
            OrientationMethod.AUTO_RECOMMEND: "Auto recommend",
            OrientationMethod.SELECT_PLANAR_FACE: "Select planar face",
            OrientationMethod.SELECT_REFERENCE_PLANE: "Select reference plane",
            OrientationMethod.SOURCE_ORIENTATION: "Use source orientation",
        }[value]

    @staticmethod
    def _reference_plane(text: str) -> ReferencePlane:
        return {
            "Front Plane": ReferencePlane.FRONT,
            "Top Plane": ReferencePlane.TOP,
            "Right Plane": ReferencePlane.RIGHT,
            "Selected planar face": ReferencePlane.SELECTED_PLANAR_FACE,
            "Custom plane": ReferencePlane.CUSTOM,
        }[text]

    @staticmethod
    def _reference_plane_text(value: ReferencePlane) -> str:
        return {
            ReferencePlane.FRONT: "Front Plane",
            ReferencePlane.TOP: "Top Plane",
            ReferencePlane.RIGHT: "Right Plane",
            ReferencePlane.SELECTED_PLANAR_FACE: "Selected planar face",
            ReferencePlane.CUSTOM: "Custom plane",
        }[value]

    def _orientation_rotation_degrees(self) -> float:
        text = self.orientation_rotation.currentText()
        if text == "Custom angle":
            return self.orientation_custom_rotation.value()
        return float(text.split(" ", 1)[0])

    @staticmethod
    def _parse_vector(text: str, label: str) -> Vec3:
        try:
            values = tuple(float(item.strip()) for item in text.split(","))
        except ValueError as exc:
            raise ManufacturingOrientationError(f"{label} must be three comma-separated numbers") from exc
        if len(values) != 3:
            raise ManufacturingOrientationError(f"{label} must be three comma-separated numbers")
        return Vec3(*values)

    def _manufacturing_direction_inputs(self, *, required: bool = True) -> tuple[Vec3 | None, Vec3 | None, Vec3 | None]:
        build = self._direction(self.process_build.currentText())
        load = self._direction(self.process_load.currentText())
        unload = self._direction(self.process_unload.currentText())
        if required and (build is None or load is None or unload is None):
            raise InteractiveWorkflowError("manufacturing build, load, and unload directions must be explicit")
        return build, load, unload

    def _orientation_from_controls(self, *, accepted: bool = False) -> ManufacturingOrientation:
        source_sha256 = self.document.source_sha256 if self.document else (
            self.project.product.source_sha256 if self.project else None
        )
        if source_sha256 is None:
            raise ManufacturingOrientationError("import a source STEP before defining manufacturing orientation")
        method = self._orientation_method(self.orientation_method.currentText())
        reference_plane = self._reference_plane(self.orientation_reference_plane.currentText())
        flip = self.orientation_flip_normal.isChecked()
        rotation = self._orientation_rotation_degrees()
        if method == OrientationMethod.AUTO_RECOMMEND:
            if self.document is None:
                raise ManufacturingOrientationError("auto orientation recommendation requires loaded OCP face evidence")
            recommendations = recommend_orientations(self.document)
            if not recommendations:
                raise ManufacturingOrientationError("auto orientation found no confirmed planar-face candidates")
            recommended = recommendations[0]
            self.orientation_explanation.setText(
                "Auto recommendation: " + " ".join(recommended.reasons)
            )
            return orientation_from_face(
                self.document, recommended.orientation.selected_reference,
                method=OrientationMethod.AUTO_RECOMMEND,
                flip_normal=(recommended.orientation.flip_normal != flip),
                rotation_degrees=rotation, accepted=accepted,
            )
        if method == OrientationMethod.SELECT_PLANAR_FACE or reference_plane == ReferencePlane.SELECTED_PLANAR_FACE:
            if self.document is None or self.orientation_face_reference is None:
                raise ManufacturingOrientationError("select a confirmed planar build-down face in the engineering explorer")
            return orientation_from_face(
                self.document, self.orientation_face_reference, method=method,
                flip_normal=flip, rotation_degrees=rotation, accepted=accepted,
            )
        if method == OrientationMethod.SOURCE_ORIENTATION:
            return orientation_from_plane(
                source_sha256=source_sha256, method=OrientationMethod.SOURCE_ORIENTATION,
                reference_plane=ReferencePlane.TOP, plane_origin_mm=Vec3(0.0, 0.0, 0.0),
                plane_normal_source=Vec3(0.0, 0.0, 1.0), flip_normal=flip,
                rotation_degrees=rotation, accepted=accepted,
                explanation=(
                    "Source orientation is a deliberate manufacturing-frame proposal, not an implicit assumption.",
                    "Engineer acceptance is required before analysis.",
                ), evidence=("reference_plane=source_xy",),
            )
        custom_origin = custom_normal = None
        if reference_plane == ReferencePlane.CUSTOM:
            custom_origin = self._parse_vector(self.orientation_custom_origin.text(), "custom plane origin")
            custom_normal = self._parse_vector(self.orientation_custom_normal.text(), "custom plane normal")
        return reference_plane_orientation(
            source_sha256, reference_plane, custom_origin_mm=custom_origin,
            custom_normal_source=custom_normal, flip_normal=flip,
            rotation_degrees=rotation, accepted=accepted,
        )

    def _commit_orientation(self, orientation: ManufacturingOrientation | None) -> None:
        """Persist a draft or accepted orientation and revoke dependent engineering evidence."""
        prior_project = self.project
        self.orientation_draft = orientation
        if self.workflow is None:
            return
        prior_setup = self.workflow.setup
        to_source = lambda value: (
            orientation.manufacturing_vector_to_source(value)
            if orientation is not None and value is not None else None
        )
        setup = replace(
            prior_setup,
            manufacturing_orientation=orientation,
            build_orientation=to_source(prior_setup.manufacturing_build_direction),
            loading_direction=to_source(prior_setup.manufacturing_loading_direction),
            unloading_direction=to_source(prior_setup.manufacturing_unloading_direction),
        )
        self.workflow = replace(
            self.workflow, setup=setup, analysis_completed=False, concepts_generated=False,
            active_stage="Orientation", timings=(),
        )
        if prior_project is not None and prior_project.fixture_proposal is not None:
            self._replace_project(prior_project.with_workflow(self.workflow))
        else:
            self._replace_project(None)
        self._show_active_concept_geometry()
        self._refresh_all()

    def _orientation_controls_changed(self, *_: object) -> None:
        if self._setting_orientation_controls or self.workflow is None:
            return
        self.orientation_custom_rotation.setEnabled(
            self.orientation_rotation.currentText() == "Custom angle"
        )
        try:
            self._commit_orientation(self._orientation_from_controls(accepted=False))
            self.statusBar().showMessage(
                "Manufacturing orientation changed; downstream analysis and authored geometry are stale."
            )
        except ManufacturingOrientationError as exc:
            self.orientation_explanation.setText(str(exc))
            self._commit_orientation(None)

    def select_build_down_face(self) -> None:
        if self.selected_reference is None or not self.selected_reference.face_identity:
            QMessageBox.warning(self, "Build-down face unavailable",
                                "Select an exact confirmed planar face in the engineering explorer first.")
            return
        self.orientation_face_reference = self.selected_reference
        self._setting_orientation_controls = True
        self.orientation_method.setCurrentText("Select planar face")
        self.orientation_reference_plane.setCurrentText("Selected planar face")
        self._setting_orientation_controls = False
        try:
            orientation = self._orientation_from_controls(accepted=False)
            self.orientation_selected_face.setText(
                f"Selected planar OCP face: {self.orientation_face_reference.face_identity}"
            )
            self.orientation_explanation.setText(" ".join(orientation.explanation))
            self._commit_orientation(orientation)
        except ManufacturingOrientationError as exc:
            self.orientation_explanation.setText(str(exc))
            self._commit_orientation(None)

    def reset_to_source_orientation(self) -> None:
        if self.workflow is None:
            self.statusBar().showMessage("Import a STEP model before defining manufacturing orientation.")
            return
        self._setting_orientation_controls = True
        self.orientation_method.setCurrentText("Use source orientation")
        self.orientation_reference_plane.setCurrentText("Top Plane")
        self.orientation_flip_normal.setChecked(False)
        self.orientation_rotation.setCurrentText("0 degrees")
        self.orientation_custom_rotation.setValue(0.0)
        self._setting_orientation_controls = False
        try:
            self._commit_orientation(self._orientation_from_controls(accepted=False))
            self.orientation_explanation.setText(
                "Source orientation restored as an unaccepted manufacturing-frame proposal."
            )
        except ManufacturingOrientationError as exc:
            QMessageBox.warning(self, "Orientation blocked", str(exc))

    def accept_manufacturing_orientation(self) -> None:
        try:
            orientation = self._orientation_from_controls(accepted=True)
            self._commit_orientation(orientation)
            self.orientation_explanation.setText(
                "Accepted manufacturing coordinate system. Analysis uses this frame; source CAD remains unchanged."
            )
            self.statusBar().showMessage("Manufacturing orientation accepted; deterministic analysis is available.")
        except ManufacturingOrientationError as exc:
            QMessageBox.warning(self, "Orientation blocked", str(exc))

    def _set_orientation_controls(self, orientation: ManufacturingOrientation | None) -> None:
        self._setting_orientation_controls = True
        try:
            self.orientation_draft = orientation
            if orientation is None:
                self.orientation_selected_face.setText("No accepted manufacturing orientation.")
                self.orientation_matrix.setText("Not defined")
                self.orientation_inverse.setText("Not defined")
                self.orientation_raw_evidence.setText("No orientation evidence.")
                self.orientation_explanation.setText(
                    "Choose a familiar plane or confirmed planar face. Source CAD stays unchanged."
                )
                return
            self.orientation_method.setCurrentText(self._orientation_method_text(orientation.method))
            self.orientation_reference_plane.setCurrentText(
                self._reference_plane_text(orientation.reference_plane)
            )
            self.orientation_flip_normal.setChecked(orientation.flip_normal)
            rotation = round(orientation.rotation_degrees, 9)
            label = f"{int(rotation)} degrees" if rotation in {0.0, 90.0, 180.0, 270.0} else "Custom angle"
            self.orientation_rotation.setCurrentText(label)
            self.orientation_custom_rotation.setValue(orientation.rotation_degrees)
            self.orientation_custom_rotation.setEnabled(label == "Custom angle")
            if orientation.reference_plane == ReferencePlane.CUSTOM:
                self.orientation_custom_origin.setText(
                    f"{orientation.plane_origin_mm.x}, {orientation.plane_origin_mm.y}, {orientation.plane_origin_mm.z}"
                )
                self.orientation_custom_normal.setText(
                    f"{orientation.plane_normal_source.x}, {orientation.plane_normal_source.y}, {orientation.plane_normal_source.z}"
                )
            self.orientation_face_reference = orientation.selected_reference
            self.orientation_front_reference = orientation.front_reference
            self.orientation_selected_face.setText(
                ("Bottom: " + orientation.selected_reference.face_identity
                 + ("\nFront: " + orientation.front_reference.face_identity
                    if orientation.front_reference else "")
                 if orientation.selected_reference else "CAD reference plane selected.")
            )
            matrix = lambda values: "\n".join(
                "  ".join(f"{value: .6g}" for value in values[row:row + 4])
                for row in range(0, 16, 4)
            )
            self.orientation_matrix.setText(matrix(orientation.source_to_manufacturing))
            self.orientation_inverse.setText(matrix(orientation.manufacturing_to_source))
            self.orientation_raw_evidence.setText("\n".join(orientation.evidence))
            state = "ACCEPTED" if orientation.accepted else "DRAFT - engineer acceptance required"
            self.orientation_explanation.setText(state + ": " + " ".join(orientation.explanation))
        finally:
            self._setting_orientation_controls = False
        self._refresh_guided_orientation()

    @staticmethod
    def _optional_text(widget: QLineEdit) -> str | None:
        value = widget.text().strip()
        return value or None

    def _capture_process_setup(self, *, persist: bool = True,
                               orientation: ManufacturingOrientation | None = None) -> ProcessSetup:
        project_name = self.process_project_name.text().strip()
        if not project_name and self.document:
            project_name = Path(self.document.source_name).stem
        if not project_name and self.project:
            project_name = Path(self.project.product.source_name).stem
        active_orientation = orientation if orientation is not None else self.orientation_draft
        if active_orientation is None and self.workflow is not None:
            active_orientation = self.workflow.setup.manufacturing_orientation
        build_axis, load_axis, unload_axis = self._manufacturing_direction_inputs(required=False)
        build_source = load_source = unload_source = None
        if active_orientation is not None and build_axis is not None and load_axis is not None and unload_axis is not None:
            build_source = active_orientation.manufacturing_vector_to_source(build_axis)
            load_source = active_orientation.manufacturing_vector_to_source(load_axis)
            unload_source = active_orientation.manufacturing_vector_to_source(unload_axis)
        setup = ProcessSetup(
            project_name=project_name,
            fixture_type=self.process_fixture_type.currentText().strip() or None,
            manufacturing_process=self.process_method.currentText().strip() or None,
            operation_mode=self.process_mode.currentText().strip() or None,
            production_quantity=self.process_quantity.value(),
            volume_category=self.process_volume.currentText(),
            build_orientation=build_source,
            loading_direction=load_source,
            unloading_direction=unload_source,
            operator_access=self._optional_text(self.process_operator),
            automation_assumptions=self._optional_text(self.process_automation),
            shop_capabilities=tuple(sorted(filter(None, (
                value.strip() for value in self.process_shop.text().split(",")
            )))),
            material_assumptions=self._optional_text(self.process_material),
            preferred_base_strategy=(None if self.process_base.currentText() in {"Auto", "Unknown"}
                                     else self.process_base.currentText()),
            required_repeatability_mm=(self.process_repeatability.value()
                                       if self.process_repeatability.value() > 0 else None),
            required_clearance_mm=self.process_clearance.value(),
            fixture_purpose=self.process_fixture_type.currentText().strip() or None,
            construction_method=self.process_construction.currentText(),
            fixture_lifecycle=self.process_lifecycle.currentText(),
            repeat_frequency=self._optional_text(self.process_repeat_frequency),
            job_revision=self._optional_text(self.process_job_revision),
            cleco_strategy=self.process_cleco_strategy.currentText(),
            manufacturing_orientation=active_orientation,
            manufacturing_build_direction=build_axis,
            manufacturing_loading_direction=load_axis,
            manufacturing_unloading_direction=unload_axis,
        )
        if persist and self.workflow is not None:
            self.workflow = replace(self.workflow, setup=setup)
        return setup

    def _persist_process_setup_from_controls(self) -> None:
        """Bind visible manufacturing-intent controls to governed project state."""
        if self.workflow is None:
            return
        setup = self._capture_process_setup(persist=False)
        if setup == self.workflow.setup:
            return
        self.workflow = replace(
            self.workflow, setup=setup, analysis_completed=False,
            concepts_generated=False, timings=(),
        )
        if self.project is not None:
            self._replace_project(self.project.with_workflow(self.workflow))

    def _set_process_setup(self, setup: ProcessSetup) -> None:
        self.process_project_name.setText(setup.project_name)
        for combo, value in (
            (self.process_fixture_type, {
                "Weld fixture": "Full weld fixture",
            }.get(setup.fixture_type, setup.fixture_type)),
            (self.process_method, {
                "Assembly": "Manual assembly",
            }.get(setup.manufacturing_process, setup.manufacturing_process)),
            (self.process_mode, setup.operation_mode),
            (self.process_volume, setup.volume_category),
            (self.process_base, setup.preferred_base_strategy or "Auto"),
            (self.process_construction, setup.construction_method or "Auto-select"),
            (self.process_lifecycle, setup.fixture_lifecycle or "Store and reuse"),
            (self.process_cleco_strategy, setup.cleco_strategy or "None"),
        ):
            if value:
                combo.setCurrentText(value)
        if setup.production_quantity:
            self.process_quantity.setValue(setup.production_quantity)
        self.process_build.setCurrentText(self._direction_text(setup.manufacturing_build_direction or setup.build_orientation))
        self.process_load.setCurrentText(self._direction_text(setup.manufacturing_loading_direction or setup.loading_direction))
        self.process_unload.setCurrentText(self._direction_text(setup.manufacturing_unloading_direction or setup.unloading_direction))
        self.process_operator.setText(setup.operator_access or "")
        self.process_automation.setText(setup.automation_assumptions or "")
        self.process_shop.setText(", ".join(setup.shop_capabilities))
        self.process_material.setText(setup.material_assumptions or "")
        self.process_repeat_frequency.setText(setup.repeat_frequency or "")
        self.process_job_revision.setText(setup.job_revision or "")
        self.process_repeatability.setValue(setup.required_repeatability_mm or 0.0)
        self.process_clearance.setValue(setup.required_clearance_mm or 0.0)
        self._set_orientation_controls(setup.manufacturing_orientation)

    def _populate_workflow(self) -> None:
        self.annotation_list.clear()
        self.tooling_list.clear()
        self.revision_list.clear()
        self.edit_target.clear()
        if self.document:
            self.workflow_source.setText(
                f"{self.document.source_name}\nSHA-256: {self.document.source_sha256}\n"
                "Source CAD is immutable; all intent is stored in the FXD project."
            )
        else:
            self.workflow_source.setText("Import a STEP assembly to begin.")
        if self.workflow is None:
            self.analyze_button.setEnabled(False)
            self.generate_button.setEnabled(False)
            self.fabrication_plan_button.setEnabled(False)
            self.fabrication_author_button.setEnabled(False)
            self.fabrication_components.clear()
            return
        orientation = self.workflow.setup.manufacturing_orientation
        self.analyze_button.setEnabled(
            self.document is not None and orientation is not None and orientation.accepted
            and not orientation.is_stale_for(self.document.source_sha256)
        )
        self.generate_button.setEnabled(
            self.project is not None and self.workflow.analysis_completed
            and self.workflow.has_accepted_manufacturing_orientation()
        )
        self.fabrication_plan_button.setEnabled(
            self.project is not None and self.workflow.concepts_generated
            and self.workflow.has_accepted_manufacturing_orientation()
        )
        self.fabrication_author_button.setEnabled(
            self.project is not None and self.project.fixture_build is not None
            and self.workflow.has_accepted_manufacturing_orientation()
        )
        self._set_process_setup(self.workflow.setup)
        for annotation in self.workflow.geometry_annotations:
            self.annotation_list.addItem(
                f"{annotation.role.value} | {annotation.reference.face_identity} | exact OCP face"
            )
        self.tooling_list.addItem("generic-toggle-clamp | vendor-neutral | metadata review required")
        self.tooling_list.addItem("generic-round-pin | vendor-neutral | metadata review required")
        self.tooling_list.addItem("generic-support-rest | vendor-neutral | metadata review required")
        for tooling in self.workflow.customer_tooling:
            state = "VERIFIED" if tooling.verified else "UNVERIFIED"
            self.tooling_list.addItem(
                f"{tooling.identity} | {state} | {tooling.manufacturer or 'manufacturer unknown'} | "
                f"{tooling.part_number or 'part number unknown'}"
            )
        if self.project:
            self.edit_target.addItems(tuple(
                feature.identity for feature in self.project.active.fixture.features
            ))
            for revision in reversed(self.project.revisions):
                item = QListWidgetItem(
                    f"{revision.revision_id} | {revision.validation_status} | {revision.edit_count} edits"
                )
                item.setData(Qt.ItemDataRole.UserRole, revision.revision_id)
                self.revision_list.addItem(item)
        self.fabrication_components.clear()
        if self.project and self.project.fixture_build:
            build = self.project.fixture_build
            validation = self.project.active_validation
            self.fabrication_status.setText(
                f"{build.requirements.fixture_purpose.value} | {build.requirements.construction_method.value}\n"
                f"Geometry authority: authored manufacturing geometry only after OCP authoring.\n"
                f"Validation: {validation.status.upper()} | job revision: {build.requirements.job_revision or 'missing'}"
            )
            active_authored = self._active_authored_fixture_build()
            authored = {item.component.identity for item in (active_authored.components if active_authored else ())}
            for component in build.components:
                state = "REAL OCP B-REP" if component.identity in authored else component.geometry_authority.value
                self.fabrication_components.addItem(
                    f"{component.part_number} | {component.role.value} | {state} | {component.nest_classification.value}"
                )
            self.process_tack_access.setChecked(build.requirements.tack_access_available is True)
            self.process_unload_clearance.setChecked(build.requirements.unload_clearance_evaluated is True)
            self.process_product_hole_approval.setChecked(build.requirements.product_hole_approved)
            self.process_product_hole_justification.setText(build.requirements.product_hole_justification or "")
            self.process_adjustment_state.setCurrentText({
                AdjustmentState.PROVISIONAL: "Provisional adjustment",
                AdjustmentState.PROVE_OUT: "Prove-out setting",
                AdjustmentState.LOCKED: "Locked production position",
                AdjustmentState.DOWELED: "Doweled production position",
                AdjustmentState.REVALIDATION_REQUIRED: "Revalidation required",
            }[build.requirements.adjustment_state])
        else:
            self.fabrication_status.setText(
                "Build a deterministic manufacturing plan after selecting an active fixture concept."
            )
        self._populate_concept_comparison()

    def assign_selected_annotation(self) -> None:
        if self.document is None or self.workflow is None or self.selected_reference is None:
            QMessageBox.warning(self, "Annotation unavailable",
                                "Select an exact OCP face in the engineering explorer first.")
            return
        try:
            self._capture_process_setup()
            role = tuple(AnnotationRole)[self.annotation_role.currentIndex()]
            annotation = face_annotation(self.document, self.selected_reference, role)
            self.workflow = self.workflow.with_annotation(annotation)
            self._replace_project(None)
            self._refresh_all()
            self.statusBar().showMessage(
                f"Assigned {role.value}; prior analysis is now stale and must be rerun."
            )
        except InteractiveWorkflowError as exc:
            QMessageBox.warning(self, "Annotation blocked", str(exc))

    def _analysis_snapshot(self) -> tuple[WorkbenchDocument, InteractiveWorkflow]:
        if self.document is None or self.workflow is None:
            raise InteractiveWorkflowError("import a real STEP assembly before analysis")
        self._capture_process_setup()
        orientation = self.workflow.setup.manufacturing_orientation
        if orientation is None:
            raise InteractiveWorkflowError("analysis requires an accepted manufacturing orientation")
        try:
            orientation.require_accepted_for(self.document.source_sha256)
        except ManufacturingOrientationError as exc:
            raise InteractiveWorkflowError(str(exc)) from exc
        return self.document, self.workflow

    def analyze_assembly(self) -> None:
        try:
            document, workflow = self._analysis_snapshot()
            self._analysis_request += 1
            request_id = self._analysis_request
            self.statusBar().showMessage("Running deterministic engineering analysis...")
            self.analyze_button.setEnabled(False)
            task = _AnalysisTask(document, workflow, request_id)
            task.signals.completed.connect(self._analysis_completed)
            task.signals.failed.connect(self._analysis_failed)
            self._analysis_tasks[request_id] = task
            self.analysis_pool.start(task)
        except Exception as exc:
            logger.exception("deterministic engineering analysis failed")
            self.statusBar().showMessage(f"Engineering analysis failed closed: {exc}")
            QMessageBox.warning(self, "Analysis blocked", str(exc))

    def analyze_assembly_now(self) -> FxdProject:
        """Synchronous test and automation boundary using the same core command."""
        document, workflow = self._analysis_snapshot()
        project = analyze_engineering_workflow(document, workflow)
        self._accept_analysis(project, document.source_bytes)
        return project

    def _analysis_completed(self, project: FxdProject, request_id: int, source_bytes: bytes) -> None:
        self._analysis_tasks.pop(request_id, None)
        if request_id != self._analysis_request:
            return
        try:
            self._accept_analysis(project, source_bytes)
        except Exception as exc:
            self._analysis_failed(str(exc), request_id)

    def _analysis_failed(self, message: str, request_id: int) -> None:
        self._analysis_tasks.pop(request_id, None)
        if request_id != self._analysis_request:
            return
        self.analyze_button.setEnabled(self.document is not None)
        self.statusBar().showMessage(f"Engineering analysis failed closed: {message}")
        QMessageBox.warning(self, "Analysis blocked", message)

    def _accept_analysis(self, project: FxdProject, source_bytes: bytes) -> None:
        if self.document is None:
            raise RuntimeError("source document closed before analysis completed")
        if self.document.source_bytes != source_bytes or sha256(source_bytes).hexdigest() != self.document.source_sha256:
            raise RuntimeError("source STEP identity changed during engineering analysis")
        if self.document.source_path and self.document.source_path.read_bytes() != source_bytes:
            raise RuntimeError("source STEP file changed during engineering analysis")
        self._replace_project(project)
        self.workflow = project.workflow
        self.project_path = None
        self._refresh_all()
        elapsed = next(item.elapsed_ms for item in self.workflow.timings
                       if item.operation == "total_analysis")
        self.log.record("engineering_analysis_completed", revision=project.revision_id,
                        elapsed_ms=elapsed, validation=project.active_validation.status)
        self.statusBar().showMessage(
            f"Analysis completed in {elapsed:.1f} ms: {project.active_validation.status}. "
            "Generate concepts to expose review geometry."
        )

    def generate_concepts(self) -> None:
        if (self.project is None or self.workflow is None or not self.workflow.analysis_completed
                or not self.workflow.has_accepted_manufacturing_orientation()):
            self.statusBar().showMessage("Run deterministic assembly analysis first.")
            return
        self.workflow = replace(self.workflow, concepts_generated=True, active_stage="Concepts")
        self._replace_project(self.project.with_workflow(self.workflow))
        self._show_active_concept_geometry()
        self._refresh_all()
        self.statusBar().showMessage(
            f"Generated {len(self.project.concepts)} deterministic review concepts; "
            "wireframe fixture geometry is provisional, not released fabrication geometry."
        )

    @staticmethod
    def _fixture_purpose_from_ui(value: str) -> FixturePurpose:
        return {
            "Full weld fixture": FixturePurpose.FULL_WELD,
            "Weld fixture": FixturePurpose.FULL_WELD,
            "Tack or Location Fixture": FixturePurpose.TACK_LOCATION,
            "Assembly fixture": FixturePurpose.ASSEMBLY,
            "Inspection fixture": FixturePurpose.INSPECTION,
            "Profile check fixture": FixturePurpose.PROFILE_CHECK,
            "Go/no-go gauge": FixturePurpose.GO_NO_GO,
            "Rework fixture": FixturePurpose.REWORK,
            "Robotic or cobot fixture": FixturePurpose.ROBOTIC,
            "Combined build-and-check fixture": FixturePurpose.COMBINED_BUILD_CHECK,
        }.get(value, FixturePurpose.FULL_WELD)

    @staticmethod
    def _construction_from_ui(value: str) -> ConstructionMethod:
        return {
            "Auto-select": ConstructionMethod.AUTO,
            "Laser-cut fabricated": ConstructionMethod.LASER_CUT_FABRICATED,
            "CNC-machined": ConstructionMethod.CNC_MACHINED,
            "Hybrid": ConstructionMethod.HYBRID,
            "Welded tube-frame": ConstructionMethod.WELDED_TUBE_FRAME,
            "Shop-standard": ConstructionMethod.SHOP_STANDARD,
            "Tack or Location Fixture": ConstructionMethod.TACK_LOCATION,
        }[value]

    @staticmethod
    def _lifecycle_from_ui(value: str) -> FixtureLifecycle:
        return {
            "Store and reuse": FixtureLifecycle.STORE_AND_REUSE,
            "Disposable or job-run recut": FixtureLifecycle.DISPOSABLE_RECUT,
            "Reusable tooling on disposable fixture": FixtureLifecycle.REUSABLE_TOOLING_ON_DISPOSABLE,
            "Full permanent fixture": FixtureLifecycle.PERMANENT,
        }[value]

    @staticmethod
    def _adjustment_state_from_ui(value: str) -> AdjustmentState:
        return {
            "Provisional adjustment": AdjustmentState.PROVISIONAL,
            "Prove-out setting": AdjustmentState.PROVE_OUT,
            "Locked production position": AdjustmentState.LOCKED,
            "Doweled production position": AdjustmentState.DOWELED,
            "Revalidation required": AdjustmentState.REVALIDATION_REQUIRED,
        }[value]

    @staticmethod
    def _cleco_strategy_from_ui(value: str):
        from fxd_geometry import ClecoStrategy
        return {
            "None": ClecoStrategy.NONE,
            "Separate fixture Cleco holes": ClecoStrategy.SEPARATE_FIXTURE_HOLES,
            "Product Cleco holes": ClecoStrategy.PRODUCT_HOLES,
        }[value]

    def _fixture_build_requirements(self) -> FixtureBuildRequirements:
        if self.project is None:
            raise ProjectFormatError("generate a fixture concept before creating manufacturing build evidence")
        setup = self._capture_process_setup()
        purpose = self._fixture_purpose_from_ui(self.process_fixture_type.currentText())
        return FixtureBuildRequirements(
            self.project.product.source_sha256, purpose,
            self._construction_from_ui(self.process_construction.currentText()),
            self._lifecycle_from_ui(self.process_lifecycle.currentText()),
            self._optional_text(self.process_job_revision), "A", setup.production_quantity,
            self._optional_text(self.process_repeat_frequency), setup.manufacturing_process,
            setup.shop_capabilities, self.process_tack_access.isChecked() if purpose == FixturePurpose.TACK_LOCATION else None,
            None if purpose == FixturePurpose.TACK_LOCATION else None,
            self.process_unload_clearance.isChecked(), self._adjustment_state_from_ui(self.process_adjustment_state.currentText()),
            ("All M30 selections are engineer-editable review inputs.",),
            ("Generated through the local FXD workbench from immutable source identity.",),
            self._cleco_strategy_from_ui(self.process_cleco_strategy.currentText()),
            self.process_product_hole_approval.isChecked(),
            self._optional_text(self.process_product_hole_justification),
        )

    def generate_fixture_build_plan(self) -> None:
        if (self.project is None or self.workflow is None or not self.workflow.concepts_generated
                or not self.workflow.has_accepted_manufacturing_orientation()):
            self.statusBar().showMessage("Generate and select a fixture concept before creating a build plan.")
            return
        try:
            plan = generate_m30_fixture_build_plan(self.project.product, self.project.active, self._fixture_build_requirements())
            self._replace_project(
                self.project.with_workflow(self.workflow).with_fixture_build(plan)
            )
            self.workflow = self.project.workflow
            self._refresh_all()
            self.statusBar().showMessage(
                f"Fixture build plan {plan.identity} generated; deterministic findings remain authoritative."
            )
        except (FixtureBuildError, ProjectFormatError) as exc:
            QMessageBox.warning(self, "Fixture build blocked", str(exc))

    def author_real_fixture_geometry(self) -> None:
        if (self.project is None or self.workflow is None or self.project.fixture_build is None
                or not self.workflow.has_accepted_manufacturing_orientation()):
            self.statusBar().showMessage("Generate a valid fixture build plan before OCP authoring.")
            return
        try:
            self.authored_fixture_build = author_fixture_build(
                self.project.fixture_build, self.project.product, self.kernel,
            )
            self._show_active_concept_geometry()
            self._refresh_all()
            self.statusBar().showMessage(
                f"Authored {len(self.authored_fixture_build.components)} real OCP manufacturing components; engineering review remains required."
            )
        except (FixtureBuildError, KernelOperationError) as exc:
            QMessageBox.warning(self, "Manufacturing geometry blocked", str(exc))

    def _review_geometry_items(self) -> list[dict[str, object]]:
        orientation_items = self._orientation_review_items()
        if (self.project is None or self.workflow is None or not self.workflow.concepts_generated
                or not self.workflow.has_accepted_manufacturing_orientation()):
            return orientation_items
        status = self.project.active_validation.status
        layers = {
            "baseplate": "fixture", "support_pad": "supports", "support": "supports",
            "hard_stop": "stops", "stop": "stops", "round_pin": "locators",
            "relieved_locator": "locators", "clamp_mount": "clamps", "clamp": "clamps",
        }
        items = [{
            "identity": feature.identity,
            "kind": feature.kind,
            "minimum": list(feature.bounds.minimum.__dict__.values()),
            "maximum": list(feature.bounds.maximum.__dict__.values()),
            "status": status,
            "evidence": "provisional deterministic fixture review geometry",
        } for feature in self.project.active.fixture.features
                if feature.identity not in self.project.suppressed_features
                and layers.get(feature.kind, "fixture") not in self.project.hidden_layers
                and "provisional" not in self.project.hidden_layers]
        active_authored = self._active_authored_fixture_build()
        if active_authored is not None:
            for authored in active_authored.components:
                bounds = authored.component.bounds
                items.append({
                    "identity": "manufacturing:" + authored.component.identity,
                    "kind": "authored_manufacturing_component",
                    "minimum": list(bounds.minimum.__dict__.values()),
                    "maximum": list(bounds.maximum.__dict__.values()),
                    "status": self.project.active_validation.status,
                    "evidence": "authored manufacturing OCP B-Rep review proxy; never source CAD",
                })
        return items + orientation_items

    def _orientation_review_items(self) -> list[dict[str, object]]:
        """Create review-only orientation overlays in source coordinates."""
        orientation = self.orientation_draft or (
            self.workflow.setup.manufacturing_orientation if self.workflow else None
        )
        if self.document is None or orientation is None or orientation.is_stale_for(self.document.source_sha256):
            return []
        points = tuple(point for mesh in self.document.meshes for point in mesh.vertices_mm)
        if not points:
            return []
        span = max(
            max(point[index] for point in points) - min(point[index] for point in points)
            for index in range(3)
        )
        scale = max(span * 0.18, 10.0)
        origin = list(orientation.plane_origin_mm.__dict__.values())
        x_axis = list(orientation.manufacturing_x_source.__dict__.values())
        y_axis = list(orientation.manufacturing_y_source.__dict__.values())
        z_axis = list(orientation.manufacturing_z_source.__dict__.values())
        items: list[dict[str, object]] = [{
            "identity": "orientation:build-plane", "kind": "orientation_plane",
            "origin": origin, "x_axis": x_axis, "y_axis": y_axis,
            "half_width": scale * 1.5, "status": "provisional", "color": [0.04, 0.52, 0.84],
            "opacity": 0.18, "representation": "surface",
            "evidence": "manufacturing build plane overlay; source CAD is unmodified",
        }]
        highlighted_faces = (
            ("bottom-face", self.orientation_face_reference or orientation.selected_reference,
             [1.0, 0.48, 0.0], "selected fixture-down face"),
            ("front-face", self.orientation_front_reference or orientation.front_reference,
             [0.05, 0.80, 0.82], "selected operator/front face"),
        )
        for suffix, reference, color, evidence in highlighted_faces:
            if reference is None:
                continue
            mesh = next((item for item in self.document.meshes
                         if item.face_reference == reference.face_identity), None)
            if mesh is None:
                continue
            items.append({
                "identity": "orientation:" + suffix, "kind": "orientation_face_highlight",
                "vertices": [list(point) for point in mesh.vertices_mm],
                "triangles": [list(triangle) for triangle in mesh.triangles],
                "status": "provisional", "color": color, "opacity": 0.68,
                "representation": "surface",
                "evidence": evidence + "; exact source face overlay; source CAD is unmodified",
            })
        directions = (
            ("manufacturing-x", x_axis, [0.92, 0.24, 0.24], "Manufacturing +X"),
            ("manufacturing-y", y_axis, [0.24, 0.82, 0.42], "Manufacturing +Y / operator front"),
            ("manufacturing-z", z_axis, [0.12, 0.47, 0.95], "Manufacturing +Z / build-up"),
            ("gravity", [-value for value in z_axis], [0.96, 0.88, 0.20], "Gravity / build-down"),
        )
        try:
            _, load_axis, unload_axis = self._manufacturing_direction_inputs()
            assert load_axis is not None and unload_axis is not None
            directions += (
                ("load", list(orientation.manufacturing_vector_to_source(load_axis).__dict__.values()),
                 [1.0, 0.48, 0.0], "Load direction"),
                ("unload", list(orientation.manufacturing_vector_to_source(unload_axis).__dict__.values()),
                 [0.72, 0.54, 0.97], "Unload direction"),
            )
        except ValueError:
            pass
        for suffix, direction, color, label in directions:
            items.append({
                "identity": "orientation:" + suffix, "kind": "orientation_arrow",
                "origin": origin, "direction": direction, "length": scale,
                "status": "provisional", "color": color, "opacity": 0.95,
                "representation": "surface",
                "evidence": label + "; manufacturing-frame overlay only",
            })
        return items

    def _show_active_concept_geometry(self) -> None:
        scene = self._scene()
        if scene is not None:
            scene.set_review_geometry(self._review_geometry_items())

    def _populate_concept_comparison(self) -> None:
        self.concept_table.setRowCount(0)
        if (self.project is None or self.workflow is None or not self.workflow.concepts_generated
                or not self.workflow.has_accepted_manufacturing_orientation()):
            return
        rows = compare_concepts(self.project)
        self.concept_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.concept_identity, row.validation_status.upper(),
                "Recommended" if row.recommended else "Review alternative",
                f"{row.preference_score:.2f}", row.cost_evidence,
                row.loading_evidence, row.unloading_evidence, row.repeatability_evidence,
                str(row.fixture_feature_count), str(row.fabricated_component_count),
                str(row.purchased_tooling_count), row.operator_access_evidence,
                row.weld_access_evidence, row.automation_access_evidence,
                row.manufacturability_evidence, row.maintainability_evidence,
                str(row.unresolved_assumptions), "; ".join(row.rationale),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.concept_identity)
                self.concept_table.setItem(row_index, column, item)
        self.concept_table.resizeColumnsToContents()

    def _concept_selection_changed(self) -> None:
        selected = self.concept_table.selectedItems()
        if selected:
            self.select_concept(str(selected[0].data(Qt.ItemDataRole.UserRole)))

    def select_concept(self, identity: str) -> None:
        if self.project is None or identity not in {item.identity for item in self.project.concepts}:
            return
        self._replace_project(self.project.with_concept(identity))
        if self.workflow is not None:
            self.workflow = replace(self.workflow, active_stage="Concepts")
            self._replace_project(self.project.with_workflow(self.workflow))
        self._show_active_concept_geometry()
        self._refresh_all()
        self.statusBar().showMessage(
            f"Active concept: {identity}. Deterministic validation remains authoritative."
        )

    def import_customer_tooling(self) -> None:
        if self.workflow is None:
            self.statusBar().showMessage("Import a product before adding private tooling metadata.")
            return
        name, _ = QFileDialog.getOpenFileName(
            self, "Import customer-owned tooling reference", "",
            "CAD files (*.step *.stp);;All files (*)",
        )
        if not name:
            return
        try:
            # A private tooling reference must itself be readable real OCP geometry.
            load_step_for_workbench(Path(name))
            digest = sha256(Path(name).read_bytes()).hexdigest()
            direction_vectors = {
                "+X": Vec3(1, 0, 0), "-X": Vec3(-1, 0, 0),
                "+Y": Vec3(0, 1, 0), "-Y": Vec3(0, -1, 0),
                "+Z": Vec3(0, 0, 1), "-Z": Vec3(0, 0, -1),
            }
            record = tooling_record_from_file(
                name,
                identity=self.tooling_identity.text().strip() or "customer-tool-" + digest[:12],
                kind=self.tooling_kind.currentText(),
                manufacturer=self.tooling_manufacturer.text().strip() or None,
                part_number=self.tooling_part_number.text().strip() or None,
                revision=self.tooling_revision.text().strip() or None,
                mounting_direction=direction_vectors.get(self.tooling_mount_direction.currentText()),
                working_direction=direction_vectors.get(self.tooling_work_direction.currentText()),
                stroke_mm=self.tooling_stroke.value() or None,
                reach_mm=self.tooling_reach.value() or None,
                force_n=self.tooling_force.value() or None,
                verified=self.tooling_verified.isChecked(),
            )
            self.workflow = self.workflow.with_tooling(record)
            if self.project is not None:
                self._replace_project(self.project.with_workflow(self.workflow))
            self._refresh_all()
            state = "VERIFIED" if record.verified else "UNVERIFIED"
            self.statusBar().showMessage(
                f"Customer tooling reference retained locally as {state}; no supplier download occurred."
            )
        except (InteractiveWorkflowError, KernelOperationError) as exc:
            QMessageBox.warning(self, "Tooling import blocked", str(exc))

    def apply_parameter_edit(self) -> None:
        if self.project is None or self.workflow is None:
            self.statusBar().showMessage("Generate a fixture concept before editing it.")
            return
        try:
            old_revision = self.project.revision_id
            old_approval = self.project.approved_revision
            reason = self.edit_reason.text().strip() or "Engineer fixture correction"
            operation = self.edit_operation.currentText()
            target = self.edit_target.currentText().strip()
            regeneration_started = perf_counter()
            if operation == "Set parameter":
                self._replace_project(self.project.edit_parameter(
                    self.edit_parameter_name.currentText(), self.edit_parameter_value.value(), reason,
                ))
            elif operation == "Move feature":
                self._replace_project(self.project.edit_feature(
                    target, "move",
                    Vec3(self.edit_move_x.value(), self.edit_move_y.value(), self.edit_move_z.value()),
                    reason,
                ))
            elif operation == "Resize feature":
                self._replace_project(self.project.edit_feature(
                    target, "resize",
                    {"x": self.edit_size_x.value(), "y": self.edit_size_y.value(),
                     "z": self.edit_size_z.value()},
                    reason,
                ))
            elif operation == "Replace feature":
                self._replace_project(self.project.edit_feature(
                    target, "replace", self.edit_replacement.currentText(), reason,
                ))
            elif operation == "Suppress or restore feature":
                self._replace_project(self.project.suppress(target, reason))
            else:
                raise ProjectFormatError(f"unsupported workbench edit {operation!r}")
            regeneration_elapsed_ms = round(
                (perf_counter() - regeneration_started) * 1000.0, 3
            )
            timings = tuple(
                item for item in self.workflow.timings if item.operation != "regeneration"
            ) + (OperationTiming("regeneration", regeneration_elapsed_ms),)
            self.workflow = replace(
                self.workflow, active_stage="Validation", concepts_generated=True,
                timings=timings,
            )
            self._replace_project(self.project.with_workflow(self.workflow))
            self._show_active_concept_geometry()
            self._refresh_all()
            self.statusBar().showMessage(
                f"Revision {old_revision} replaced by {self.project.revision_id}; "
                f"approval {'revoked' if old_approval else 'remains absent'} and validation reran "
                f"in {regeneration_elapsed_ms:.1f} ms."
            )
            self.log.record(
                "engineering_regeneration_completed", revision=self.project.revision_id,
                operation=operation, elapsed_ms=regeneration_elapsed_ms,
                validation=self.project.active_validation.status,
            )
        except ProjectFormatError as exc:
            QMessageBox.warning(self, "Edit blocked", str(exc))

    def restore_selected_revision(self) -> None:
        if self.project is None or self.workflow is None:
            self.statusBar().showMessage("Generate a fixture concept before restoring a revision.")
            return
        selected = self.revision_list.currentItem()
        if selected is None:
            self.statusBar().showMessage("Select a saved revision to restore.")
            return
        revision_id = str(selected.data(Qt.ItemDataRole.UserRole))
        try:
            old_revision = self.project.revision_id
            self._replace_project(self.project.restore(revision_id))
            self.workflow = replace(self.workflow, active_stage="Validation", concepts_generated=True)
            self._replace_project(self.project.with_workflow(self.workflow))
            self._show_active_concept_geometry()
            self._refresh_all()
            self.statusBar().showMessage(
                f"Restored {revision_id} from {old_revision}; approval remains absent and validation reran."
            )
        except ProjectFormatError as exc:
            QMessageBox.warning(self, "Revision restore blocked", str(exc))

    def _scene(self) -> VtkWorkerSceneProxy | None:
        return self.viewport.scene

    def fit_view(self) -> None:
        if self._scene():
            self._scene().fit()

    def set_standard_view(self, view: str) -> None:
        if self._scene():
            self._scene().standard_view(view)
            self.statusBar().showMessage(f"Standard view: {view.title()}")

    def set_navigation_mode(self, mode: str) -> None:
        if self._scene():
            self._scene().set_navigation_mode(mode)
        self.statusBar().showMessage(
            f"{mode.title()} selected. Trackball controls remain: LMB orbit, MMB pan, wheel/RMB zoom."
        )

    def toggle_wireframe(self) -> None:
        if self._scene():
            self._scene().set_wireframe(self._actions["wireframe"].isChecked())
        self.viewport_caption.setText(
            "PERSPECTIVE \u00b7 WIREFRAME"
            if self._actions["wireframe"].isChecked() else "PERSPECTIVE \u00b7 SHADED"
        )

    def toggle_transparency(self) -> None:
        if self._scene():
            self._scene().set_transparent(self._actions["transparency"].isChecked())
        suffix = " \u00b7 TRANSPARENT" if self._actions["transparency"].isChecked() else ""
        base = "WIREFRAME" if self._actions["wireframe"].isChecked() else "SHADED"
        self.viewport_caption.setText(f"PERSPECTIVE \u00b7 {base}{suffix}")

    def toggle_project_layer(self, layer: str) -> None:
        action = self._actions["layer_" + layer]
        if self.project is None:
            action.setChecked(True)
            self.statusBar().showMessage("Open an FXD project to change review layers.")
            return
        visible = action.isChecked()
        currently_visible = layer not in self.project.hidden_layers
        if visible != currently_visible:
            self._replace_project(self.project.toggle_layer(layer))
        if layer == "product" and self._scene() is not None:
            self._scene().set_visible(visible)
        elif self._scene() is not None:
            self._show_active_concept_geometry()
        self.statusBar().showMessage(
            f"{layer.title()} layer {'shown' if visible else 'hidden'}; "
            "the project visibility state will be preserved on save."
        )

    def record_decision(self, action: str) -> None:
        if self.project is None:
            self.statusBar().showMessage("Open an FXD project before recording a review decision.")
            return
        try:
            self._replace_project(self.project.decide(action, "Human review action recorded locally."))
            self._refresh_all()
            self.statusBar().showMessage(f"Recorded {action}; this is not production approval.")
        except ProjectFormatError as exc:
            QMessageBox.warning(self, "Review decision blocked", str(exc))

    def show_renderer_diagnostics(self) -> None:
        diagnostics = self.viewport.diagnostics()
        if diagnostics is None:
            text = "Embedded VTK is not initialized. No fallback geometry is active."
        else:
            text = "\n".join(f"{key}: {value}" for key, value in diagnostics.__dict__.items())
        QMessageBox.information(self, "Renderer diagnostics", text)

    def benchmark_renderer(self, frames: int = 20) -> RenderDiagnostics:
        if self._scene() is None:
            raise RuntimeError("embedded VTK is not initialized")
        result = self._scene().benchmark(frames)
        self.statusBar().showMessage(
            f"Visible render benchmark: {result.average_render_ms:.2f} ms/frame, "
            f"{result.frames_per_second:.1f} FPS."
        )
        self._set_property("Average render", f"{result.average_render_ms:.2f} ms")
        self._set_property("Visible FPS", f"{result.frames_per_second:.1f}")
        return result

    def show_renderer_benchmark(self) -> None:
        try:
            result = self.benchmark_renderer()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Visible render benchmark", str(exc))
            return
        QMessageBox.information(
            self, "Visible render benchmark",
            f"{result.average_render_ms:.2f} ms/frame\n"
            f"{result.frames_per_second:.1f} FPS\n\n"
            "Measured on the mapped local VTK viewport.",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API name
        if self._settings_enabled:
            self.settings.setValue("workbench/geometry", self.saveGeometry())
            self.settings.setValue("workbench/state", self.saveState())
        self._analysis_request += 1
        self.analysis_pool.clear()
        self.analysis_pool.waitForDone(5000)
        self.viewport.close_viewport()
        event.accept()


def create_application(argv: list[str] | None = None) -> QApplication:
    if os.environ.get("CI") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application = QApplication.instance() or QApplication(argv or sys.argv)
    apply_fxd_theme(application)
    return application


def main(step_path: Path | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    application = create_application()
    window = FxdWorkbenchWindow()
    window.show()
    if step_path is not None:
        QTimer.singleShot(0, lambda: window.load_step_path(step_path))
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
