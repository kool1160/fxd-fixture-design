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
from time import monotonic
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from fxd_geometry import (
    AnnotationRole,
    ExportError,
    GeometryReference,
    InteractiveWorkflow,
    InteractiveWorkflowError,
    KernelOperationError,
    OcpKernel,
    OperationTiming,
    ProcessSetup,
    RenderDiagnostics,
    Vec3,
    WorkbenchDocument,
    analyze_engineering_workflow,
    compare_concepts,
    face_annotation,
    load_step_for_workbench,
    product_from_workbench_document,
    tooling_record_from_file,
)
from fxd_geometry.operations import ProjectRecovery, StructuredLog, export_project_package
from fxd_geometry.project import FxdProject, ProjectFormatError, SUPPORTED_LAYERS


logger = logging.getLogger("fxd.qt_app")
EVIDENCE_REAL = "REAL OCP source geometry"
EVIDENCE_PROVISIONAL = "Provisional - real-kernel evidence unavailable"


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


class VtkWorkerSceneProxy:
    """Control proxy for the isolated native renderer process."""

    def __init__(self, process: subprocess.Popen[str],
                 messages: Queue[dict[str, object]], ready: dict[str, object]) -> None:
        self.process = process
        self.messages = messages
        self.ready = ready
        self._request_id = 0

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
            try:
                message = self.messages.get(timeout=0.25)
            except Empty:
                if self.process.poll() is not None:
                    raise RuntimeError("native VTK worker exited during benchmark")
                continue
            if message.get("event") == "error":
                raise RuntimeError(str(message.get("message", "VTK benchmark failed")))
            if message.get("request_id") == request_id:
                return self.diagnostics(
                    average_render_ms=float(message["average_render_ms"]),
                    frames_per_second=float(message["frames_per_second"]),
                )
        raise TimeoutError("native VTK benchmark did not respond")

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
        self.render_host.setStyleSheet("background: #111820;")
        self.native_title = f"FXD Embedded VTK {os.getpid()} {id(self)}"
        self.native_window_id: int | None = None
        self.worker: subprocess.Popen[str] | None = None
        self.messages: Queue[dict[str, object]] = Queue()
        self.scene: VtkWorkerSceneProxy | None = None
        self.initialization_error: str | None = None
        self.separate_window_created = False
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
        if self.scene is not None:
            self.scene.close()
        elif self.worker is not None and self.worker.poll() is None:
            self.worker.terminate()
            self.worker.wait(timeout=5)
        self.scene = None
        self.worker = None
        self.native_window_id = None

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
            self.native_window_id, 0, 0, width, height, True
        )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._resize_native_window()
        if self.scene is not None:
            self.scene.render()


class FxdWorkbenchWindow(QMainWindow):
    """One-window desktop shell around the deterministic FXD engineering core."""

    def __init__(self, *,
                 viewport_factory: Callable[..., EmbeddedVtkViewport] = EmbeddedVtkViewport,
                 kernel: OcpKernel | None = None) -> None:
        super().__init__()
        self.setObjectName("fxdEngineeringWorkbench")
        self.setWindowTitle("FXD - Engineering Workbench - review only")
        self.resize(1500, 900)
        self.document: WorkbenchDocument | None = None
        self.project: FxdProject | None = None
        self.workflow: InteractiveWorkflow | None = None
        self.project_path: Path | None = None
        self.selected_identity: str | None = None
        self.selected_reference: GeometryReference | None = None
        self._geometry_references: dict[str, GeometryReference] = {}
        self._finding_records: dict[str, object] = {}
        self.analysis_pool = QThreadPool(self)
        self.analysis_pool.setMaxThreadCount(1)
        self._analysis_request = 0
        self._analysis_tasks: dict[int, _AnalysisTask] = {}
        self.log = StructuredLog(Path.home() / ".fxd" / "diagnostics.jsonl")
        self.kernel = kernel or OcpKernel()
        self.viewport = viewport_factory(self)
        self._property_values: dict[str, QLabel] = {}
        self._actions: dict[str, QAction] = {}

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        controls = QLabel(
            "Mouse: left drag orbit | middle drag pan | wheel or right drag zoom | F fit",
            central,
        )
        controls.setObjectName("mouseControls")
        controls.setStyleSheet("padding: 6px 10px; color: #c9d3dd; background: #202a35;")
        central_layout.addWidget(controls)
        central_layout.addWidget(self.viewport, 1)
        self.setCentralWidget(central)

        self._build_tree_dock()
        self._build_workflow_dock()
        self._build_review_dock()
        self._build_actions()
        self.statusBar().showMessage("Open a legally shareable STEP file or FXD project.")
        self._set_property("Evidence", EVIDENCE_PROVISIONAL)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QMainWindow, QMainWindow > QWidget { background: #151c24; color: #e7edf3; }"
            "QDockWidget { color: #e7edf3; font-weight: 600; }"
            "QDockWidget::title { background: #202a35; padding: 6px; }"
            "QTreeWidget, QListWidget, QTabWidget::pane {"
            " background: #1b2530; color: #e7edf3; border: 1px solid #3a4856; }"
            "QTreeWidget::item:selected, QListWidget::item:selected {"
            " background: #2f6682; color: white; }"
            "QHeaderView::section { background: #26323e; color: #e7edf3;"
            " border: 0; border-right: 1px solid #3a4856; padding: 5px; }"
            "QTabBar::tab { background: #26323e; color: #d5dee6; padding: 7px 14px; }"
            "QTabBar::tab:selected { background: #2f6682; color: white; }"
            "QLabel { color: #dbe4ec; background: transparent; }"
            "QToolBar { background: #202a35; color: #e7edf3;"
            " border-bottom: 1px solid #3a4856; spacing: 4px; }"
            "QToolButton { color: #e7edf3; padding: 4px 6px; }"
            "QToolButton:checked { background: #2f6682; }"
            "QMenuBar, QMenu { background: #202a35; color: #e7edf3; }"
            "QMenuBar::item:selected, QMenu::item:selected { background: #2f6682; }"
            "QStatusBar { background: #202a35; color: #e7edf3; }"
        )

    def _build_tree_dock(self) -> None:
        dock = QDockWidget("Engineering Explorer", self)
        dock.setObjectName("engineeringExplorerDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.tree = QTreeWidget(dock)
        self.tree.setObjectName("engineeringTree")
        self.tree.setHeaderLabels(["Item", "Status"])
        self.tree.setColumnWidth(0, 250)
        self.tree.itemSelectionChanged.connect(self._tree_selection_changed)
        dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    @staticmethod
    def _combo(values: tuple[str, ...], *, editable: bool = False) -> QComboBox:
        combo = QComboBox()
        combo.addItems(values)
        combo.setEditable(editable)
        return combo

    def _build_workflow_dock(self) -> None:
        dock = QDockWidget("Fixture Engineering Workflow", self)
        dock.setObjectName("workflowDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.workflow_tabs = QTabWidget(dock)
        self.workflow_tabs.setObjectName("workflowTabs")

        product_page = QWidget(self.workflow_tabs)
        product_layout = QVBoxLayout(product_page)
        self.workflow_source = QLabel("Import a STEP assembly to begin.")
        self.workflow_source.setWordWrap(True)
        product_layout.addWidget(self.workflow_source)
        product_layout.addStretch(1)
        self.workflow_tabs.addTab(product_page, "Product")

        process_page = QWidget(self.workflow_tabs)
        process_form = QFormLayout(process_page)
        self.process_project_name = QLineEdit()
        self.process_fixture_type = self._combo(("Weld fixture", "Assembly fixture", "Inspection fixture"), editable=True)
        self.process_method = self._combo(("MIG welding", "TIG welding", "Resistance welding", "Assembly"), editable=True)
        self.process_mode = self._combo(("Manual", "Cobot", "Robotic"))
        self.process_quantity = QSpinBox()
        self.process_quantity.setRange(1, 10_000_000)
        self.process_quantity.setValue(10)
        self.process_volume = self._combo(("Low", "Medium", "High", "Unknown"))
        self.process_build = self._combo(("+Z", "-Z", "+X", "-X", "+Y", "-Y", "Unknown"))
        self.process_load = self._combo(("+X", "-X", "+Y", "-Y", "+Z", "-Z", "Unknown"))
        self.process_unload = self._combo(("-X", "+X", "+Y", "-Y", "+Z", "-Z", "Unknown"))
        self.process_operator = QLineEdit()
        self.process_operator.setPlaceholderText("Unknown, or explicit hand/helmet access")
        self.process_automation = QLineEdit()
        self.process_automation.setPlaceholderText("Unknown, or robot/cobot assumptions")
        self.process_shop = QLineEdit()
        self.process_shop.setPlaceholderText("laser cutting, welding, machining")
        self.process_material = QLineEdit()
        self.process_material.setPlaceholderText("Unknown, or product/process assumptions")
        self.process_base = self._combo(("Auto", "Baseplate", "Welded frame", "Unknown"))
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
            ("Build orientation", self.process_build), ("Load direction", self.process_load),
            ("Unload direction", self.process_unload), ("Operator access", self.process_operator),
            ("Automation", self.process_automation), ("Shop capabilities", self.process_shop),
            ("Material/process", self.process_material), ("Base strategy", self.process_base),
            ("Repeatability (mm)", self.process_repeatability),
            ("Clearance (mm)", self.process_clearance),
        ):
            process_form.addRow(label + ":", widget)
        self.analyze_button = QPushButton("Analyze Assembly")
        self.analyze_button.clicked.connect(self.analyze_assembly)
        process_form.addRow(self.analyze_button)
        self.workflow_tabs.addTab(process_page, "Process")

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
        tabs = QTabWidget(dock)
        tabs.setObjectName("reviewTabs")

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
        dock.setWidget(tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _action(self, key: str, text: str, callback: Callable[[], None],
                *, shortcut: str | None = None, icon: QStyle.StandardPixmap | None = None,
                checkable: bool = False) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        if icon is not None:
            action.setIcon(self.style().standardIcon(icon))
        action.setCheckable(checkable)
        self._actions[key] = action
        return action

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        view_menu = self.menuBar().addMenu("&View")
        engineering_menu = self.menuBar().addMenu("&Engineering")
        help_menu = self.menuBar().addMenu("&Help")

        import_action = self._action(
            "import", "Import STEP...", self.import_step, shortcut="Ctrl+I",
            icon=QStyle.StandardPixmap.SP_DialogOpenButton,
        )
        open_action = self._action(
            "open_project", "Open FXD project...", self.open_project, shortcut="Ctrl+O",
            icon=QStyle.StandardPixmap.SP_DirOpenIcon,
        )
        save_action = self._action(
            "save_project", "Save FXD project...", self.save_project, shortcut="Ctrl+S",
            icon=QStyle.StandardPixmap.SP_DialogSaveButton,
        )
        export_action = self._action(
            "export", "Export review package...", self.export_package,
            icon=QStyle.StandardPixmap.SP_DialogApplyButton,
        )
        recover_action = self._action(
            "recover", "Recover autosave", self.recover_autosave,
            icon=QStyle.StandardPixmap.SP_BrowserReload,
        )
        file_menu.addActions([import_action, open_action, save_action, export_action])
        file_menu.addSeparator()
        file_menu.addAction(recover_action)

        fit_action = self._action(
            "fit", "Fit to view", self.fit_view, shortcut="F",
            icon=QStyle.StandardPixmap.SP_DesktopIcon,
        )
        view_menu.addAction(fit_action)
        view_menu.addSeparator()
        for view in ("front", "back", "left", "right", "top", "bottom", "isometric"):
            view_menu.addAction(self._action(
                "view_" + view, view.title(), lambda checked=False, name=view: self.set_standard_view(name)
            ))
        view_menu.addSeparator()
        wireframe = self._action(
            "wireframe", "Wireframe", self.toggle_wireframe, checkable=True
        )
        transparency = self._action(
            "transparency", "Transparency", self.toggle_transparency, checkable=True
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
                checkable=True,
            )
            navigation_group.addAction(action)
            engineering_menu.addAction(action)
        self._actions["nav_orbit"].setChecked(True)
        engineering_menu.addSeparator()
        engineering_menu.addAction(self._action(
            "approve", "Approve for engineering review", lambda: self.record_decision("approve_for_review")
        ))
        engineering_menu.addAction(self._action(
            "reject", "Reject concept", lambda: self.record_decision("reject")
        ))
        help_menu.addAction(self._action(
            "diagnostics", "Renderer diagnostics", self.show_renderer_diagnostics
        ))
        help_menu.addAction(self._action(
            "benchmark", "Run visible render benchmark", self.show_renderer_benchmark
        ))

        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addActions([import_action, open_action, save_action, export_action])
        toolbar.addSeparator()
        toolbar.addActions([fit_action, self._actions["nav_orbit"], self._actions["nav_pan"],
                            self._actions["nav_zoom"]])
        toolbar.addSeparator()
        toolbar.addActions([wireframe, transparency])
        self.addToolBar(toolbar)

    def _set_property(self, name: str, value: object) -> None:
        self._property_values[name].setText(str(value))

    def import_step(self) -> None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Import STEP", "", "STEP files (*.step *.stp);;All files (*)"
        )
        if name:
            self.load_step_path(Path(name))

    def load_step_path(self, source: Path) -> None:
        try:
            before = source.read_bytes()
            before_digest = sha256(before).hexdigest()
            import_started = monotonic()
            document = load_step_for_workbench(source)
            import_elapsed_ms = round((monotonic() - import_started) * 1000.0, 3)
            after_digest = sha256(source.read_bytes()).hexdigest()
            if before_digest != after_digest or before != document.source_bytes:
                raise RuntimeError("source STEP identity changed during import")
            self.viewport.load_document(document)
            self.document = document
            self.project = None
            self.workflow = InteractiveWorkflow(
                document.source_sha256,
                ProcessSetup(project_name=source.stem),
                timings=(OperationTiming("step_import", import_elapsed_ms),),
            )
            self.project_path = None
            self.selected_identity = None
            self.selected_reference = None
            self._refresh_all()
            self.setWindowTitle(f"FXD - {source.name} - engineering review only")
            self.statusBar().showMessage(
                f"Loaded immutable STEP through OCP in {import_elapsed_ms:.1f} ms: "
                f"{document.component_count} components."
            )
            self.log.record("step_opened", source_sha256=document.source_sha256,
                            component_count=document.component_count,
                            elapsed_ms=import_elapsed_ms)
        except Exception as exc:
            logger.exception("STEP import failed for %s", source)
            self.viewport.clear()
            self.document = None
            self.project = None
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
        self.project = FxdProject.load(source)
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
        destination = QFileDialog.getExistingDirectory(self, "Export engineering review package")
        if destination:
            try:
                paths = export_project_package(self.project, destination, kernel=self.kernel)
            except ExportError as exc:
                self.log.record(
                    "export_blocked", revision=self.project.revision_id, reason=str(exc)
                )
                QMessageBox.warning(self, "Export blocked", str(exc))
                self.statusBar().showMessage(
                    "Export blocked by deterministic validation; no review package was written."
                )
                return
            self.statusBar().showMessage(
                f"Exported {len(paths)} review artifacts; production approval is not implied."
            )

    def recover_autosave(self) -> None:
        if self.project_path is None:
            self.statusBar().showMessage("Open or save a project before recovering autosave.")
            return
        self.project = ProjectRecovery(self.project_path).recover()
        self.workflow = self.project.workflow
        self._refresh_all()
        self.statusBar().showMessage("Autosave recovered; deterministic revalidation remains required.")

    def _refresh_all(self) -> None:
        self._sync_layer_actions()
        self._populate_tree()
        self._populate_properties()
        self._populate_findings()
        self._populate_workflow()

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

        if self.project and self.workflow and self.workflow.concepts_generated:
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
            self.project = self.project.with_workflow(self.workflow)
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
    def _optional_text(widget: QLineEdit) -> str | None:
        value = widget.text().strip()
        return value or None

    def _capture_process_setup(self) -> ProcessSetup:
        project_name = self.process_project_name.text().strip()
        if not project_name and self.document:
            project_name = Path(self.document.source_name).stem
        setup = ProcessSetup(
            project_name=project_name,
            fixture_type=self.process_fixture_type.currentText().strip() or None,
            manufacturing_process=self.process_method.currentText().strip() or None,
            operation_mode=self.process_mode.currentText().strip() or None,
            production_quantity=self.process_quantity.value(),
            volume_category=self.process_volume.currentText(),
            build_orientation=self._direction(self.process_build.currentText()),
            loading_direction=self._direction(self.process_load.currentText()),
            unloading_direction=self._direction(self.process_unload.currentText()),
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
        )
        if self.workflow is not None:
            self.workflow = replace(self.workflow, setup=setup)
        return setup

    def _set_process_setup(self, setup: ProcessSetup) -> None:
        self.process_project_name.setText(setup.project_name)
        for combo, value in (
            (self.process_fixture_type, setup.fixture_type),
            (self.process_method, setup.manufacturing_process),
            (self.process_mode, setup.operation_mode),
            (self.process_volume, setup.volume_category),
            (self.process_base, setup.preferred_base_strategy or "Auto"),
        ):
            if value:
                combo.setCurrentText(value)
        if setup.production_quantity:
            self.process_quantity.setValue(setup.production_quantity)
        self.process_build.setCurrentText(self._direction_text(setup.build_orientation))
        self.process_load.setCurrentText(self._direction_text(setup.loading_direction))
        self.process_unload.setCurrentText(self._direction_text(setup.unloading_direction))
        self.process_operator.setText(setup.operator_access or "")
        self.process_automation.setText(setup.automation_assumptions or "")
        self.process_shop.setText(", ".join(setup.shop_capabilities))
        self.process_material.setText(setup.material_assumptions or "")
        self.process_repeatability.setValue(setup.required_repeatability_mm or 0.0)
        self.process_clearance.setValue(setup.required_clearance_mm or 0.0)

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
            return
        self.analyze_button.setEnabled(self.document is not None)
        self.generate_button.setEnabled(self.project is not None and self.workflow.analysis_completed)
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
            self.project = None
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
        self.project = project
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
        if self.project is None or self.workflow is None or not self.workflow.analysis_completed:
            self.statusBar().showMessage("Run deterministic assembly analysis first.")
            return
        self.workflow = replace(self.workflow, concepts_generated=True, active_stage="Concepts")
        self.project = self.project.with_workflow(self.workflow)
        self._show_active_concept_geometry()
        self._refresh_all()
        self.statusBar().showMessage(
            f"Generated {len(self.project.concepts)} deterministic review concepts; "
            "wireframe fixture geometry is provisional, not released fabrication geometry."
        )

    def _review_geometry_items(self) -> list[dict[str, object]]:
        if self.project is None or self.workflow is None or not self.workflow.concepts_generated:
            return []
        status = self.project.active_validation.status
        layers = {
            "baseplate": "fixture", "support_pad": "supports", "support": "supports",
            "hard_stop": "stops", "stop": "stops", "round_pin": "locators",
            "relieved_locator": "locators", "clamp_mount": "clamps", "clamp": "clamps",
        }
        return [{
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

    def _show_active_concept_geometry(self) -> None:
        scene = self._scene()
        if scene is not None:
            scene.set_review_geometry(self._review_geometry_items())

    def _populate_concept_comparison(self) -> None:
        self.concept_table.setRowCount(0)
        if self.project is None or self.workflow is None or not self.workflow.concepts_generated:
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
        self.project = self.project.with_concept(identity)
        if self.workflow is not None:
            self.workflow = replace(self.workflow, active_stage="Concepts")
            self.project = self.project.with_workflow(self.workflow)
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
                self.project = self.project.with_workflow(self.workflow)
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
            regeneration_started = monotonic()
            if operation == "Set parameter":
                self.project = self.project.edit_parameter(
                    self.edit_parameter_name.currentText(), self.edit_parameter_value.value(), reason,
                )
            elif operation == "Move feature":
                self.project = self.project.edit_feature(
                    target, "move",
                    Vec3(self.edit_move_x.value(), self.edit_move_y.value(), self.edit_move_z.value()),
                    reason,
                )
            elif operation == "Resize feature":
                self.project = self.project.edit_feature(
                    target, "resize",
                    {"x": self.edit_size_x.value(), "y": self.edit_size_y.value(),
                     "z": self.edit_size_z.value()},
                    reason,
                )
            elif operation == "Replace feature":
                self.project = self.project.edit_feature(
                    target, "replace", self.edit_replacement.currentText(), reason,
                )
            elif operation == "Suppress or restore feature":
                self.project = self.project.suppress(target, reason)
            else:
                raise ProjectFormatError(f"unsupported workbench edit {operation!r}")
            regeneration_elapsed_ms = round(
                (monotonic() - regeneration_started) * 1000.0, 3
            )
            timings = tuple(
                item for item in self.workflow.timings if item.operation != "regeneration"
            ) + (OperationTiming("regeneration", regeneration_elapsed_ms),)
            self.workflow = replace(
                self.workflow, active_stage="Validation", concepts_generated=True,
                timings=timings,
            )
            self.project = self.project.with_workflow(self.workflow)
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
            self.project = self.project.restore(revision_id)
            self.workflow = replace(self.workflow, active_stage="Validation", concepts_generated=True)
            self.project = self.project.with_workflow(self.workflow)
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

    def toggle_transparency(self) -> None:
        if self._scene():
            self._scene().set_transparent(self._actions["transparency"].isChecked())

    def toggle_project_layer(self, layer: str) -> None:
        action = self._actions["layer_" + layer]
        if self.project is None:
            action.setChecked(True)
            self.statusBar().showMessage("Open an FXD project to change review layers.")
            return
        visible = action.isChecked()
        currently_visible = layer not in self.project.hidden_layers
        if visible != currently_visible:
            self.project = self.project.toggle_layer(layer)
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
            self.project = self.project.decide(action, "Human review action recorded locally.")
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
        self._analysis_request += 1
        self.analysis_pool.clear()
        self.analysis_pool.waitForDone(5000)
        self.viewport.close_viewport()
        event.accept()


def create_application(argv: list[str] | None = None) -> QApplication:
    if os.environ.get("CI") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    return QApplication.instance() or QApplication(argv or sys.argv)


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
