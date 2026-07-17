"""Unified PySide6 engineering workbench with an embedded VTK viewport."""
from __future__ import annotations

import logging
import os
import sys
import ctypes
from hashlib import sha256
import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
import tempfile
from threading import Thread
from time import monotonic
from typing import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStyle,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from fxd_geometry import (
    KernelOperationError,
    OcpKernel,
    RenderDiagnostics,
    WorkbenchDocument,
    load_step_for_workbench,
)
from fxd_geometry.operations import ProjectRecovery, StructuredLog, export_project_package
from fxd_geometry.project import FxdProject, ProjectFormatError, SUPPORTED_LAYERS


logger = logging.getLogger("fxd.qt_app")
EVIDENCE_REAL = "REAL OCP source geometry"
EVIDENCE_PROVISIONAL = "Provisional - real-kernel evidence unavailable"


def _load_user32():
    """Load User32 with reliable thread-local Win32 error propagation."""
    return ctypes.WinDLL("user32", use_last_error=True)


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
        actor_identities = self.ready.get("actor_identities", [])
        return identity in actor_identities

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
        self.project_path: Path | None = None
        self.selected_identity: str | None = None
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
            "Visible FPS",
        ):
            value = QLabel("-", properties)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.properties_form.addRow(label + ":", value)
            self._property_values[label] = value
        tabs.addTab(properties, "Properties")

        self.findings = QListWidget(tabs)
        self.findings.setObjectName("engineeringFindings")
        tabs.addTab(self.findings, "Findings")
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
            document = load_step_for_workbench(source)
            after_digest = sha256(source.read_bytes()).hexdigest()
            if before_digest != after_digest or before != document.source_bytes:
                raise RuntimeError("source STEP identity changed during import")
            self.viewport.load_document(document)
            self.document = document
            self.project = None
            self.project_path = None
            self.selected_identity = None
            self._refresh_all()
            self.setWindowTitle(f"FXD - {source.name} - engineering review only")
            self.statusBar().showMessage(
                f"Loaded immutable STEP through OCP: {document.component_count} components."
            )
            self.log.record("step_opened", source_sha256=document.source_sha256,
                            component_count=document.component_count)
        except Exception as exc:
            logger.exception("STEP import failed for %s", source)
            self.viewport.clear()
            self.document = None
            self.project = None
            self.project_path = None
            self.selected_identity = None
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
            paths = export_project_package(self.project, destination, kernel=self.kernel)
            self.statusBar().showMessage(
                f"Exported {len(paths)} review artifacts; production approval is not implied."
            )

    def recover_autosave(self) -> None:
        if self.project_path is None:
            self.statusBar().showMessage("Open or save a project before recovering autosave.")
            return
        self.project = ProjectRecovery(self.project_path).recover()
        self._refresh_all()
        self.statusBar().showMessage("Autosave recovered; deterministic revalidation remains required.")

    def _refresh_all(self) -> None:
        self._sync_layer_actions()
        self._populate_tree()
        self._populate_properties()
        self._populate_findings()

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
        if self.document:
            self._add_tree_category("Imported assembly", [
                (self.document.source_name, self.document.assembly.root_reference, EVIDENCE_REAL)
            ])
            components = [
                (component.name, component.reference, "real source")
                for component in self.document.assembly.components
            ]
            if not components:
                components = [("Source geometry", "source:geometry", "real source")]
            self._add_tree_category("Components", components)
        elif self.project:
            components = [
                (component.name, component.identity, "normalized source")
                for component in self.project.product.components
            ]
            self._add_tree_category("Product geometry", components)

        if self.project:
            feature_groups: dict[str, list[tuple[str, str, str]]] = {}
            for feature in self.project.active.fixture.features:
                feature_groups.setdefault(feature.kind, []).append(
                    (feature.identity, feature.identity, "review geometry")
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
        diagnostics = self.viewport.diagnostics()
        self._set_property("Render backend", diagnostics.backend if diagnostics else "unavailable")
        self._set_property("Actors", diagnostics.actor_count if diagnostics else 0)
        self._set_property("Points", diagnostics.point_count if diagnostics else 0)
        self._set_property("Native rendering", diagnostics.native_rendering_active if diagnostics else False)
        self._set_property("Fallback", diagnostics.fallback_active if diagnostics else False)

    def _populate_findings(self) -> None:
        self.findings.clear()
        if self.project:
            for finding in self.project.active_validation.findings:
                self.findings.addItem(
                    f"{finding.severity.upper()} | {finding.subsystem} | {finding.code}\n{finding.message}"
                )
        if self.findings.count() == 0:
            self.findings.addItem("No deterministic engineering findings are available for this view.")

    def _tree_selection_changed(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            return
        identity = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not identity:
            return
        self.selected_identity = str(identity)
        mapped = bool(self.viewport.scene and self.viewport.scene.select(self.selected_identity))
        self._set_property("Selected identity", self.selected_identity)
        message = f"Selected {self.selected_identity}."
        if not mapped:
            message += " Geometry identity mapping is not available for this item."
        self.statusBar().showMessage(message)

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
