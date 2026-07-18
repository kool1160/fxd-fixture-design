"""Reusable, domain-backed widgets from the FXD desktop branding system."""

from collections.abc import Iterable

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from .theme import icon
from .theme.tokens import DIMENSIONS


STATUS_ICON = {
    "pass": "pass",
    "valid": "pass",
    "verified": "pass",
    "complete": "pass",
    "warning": "warning",
    "provisional": "assumption",
    "stale": "stale",
    "fail": "fail",
    "error": "fail",
    "invalid": "fail",
    "blocked": "fail",
    "override": "override",
    "notevaluated": "not-evaluated",
    "not evaluated": "not-evaluated",
    "available": "right",
    "active": "right",
    "engineer modified": "edit-feature",
    "deferred": "not-evaluated",
    "not started": "not-evaluated",
}


def repolish(widget: object) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def semantic_icon(status: str):
    normalized = status.strip().lower()
    name = STATUS_ICON.get(normalized, "not-evaluated")
    return icon(name)


class StatusChip(QFrame):
    """Compact icon, text, and color status that never relies on color alone."""

    def __init__(self, status: str = "notEvaluated", text: str = "NOT EVALUATED",
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 7, 2)
        layout.setSpacing(5)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(14, 14)
        self.text_label = QLabel(self)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.setFixedHeight(24)
        self.set_status(status, text)

    def set_status(self, status: str, text: str) -> None:
        normalized = status.strip().lower()
        qss_status = {
            "valid": "pass", "verified": "pass", "complete": "pass",
            "provisional": "warning", "stale": "warning",
            "invalid": "fail", "error": "fail", "blocked": "fail",
            "not evaluated": "notEvaluated",
        }.get(normalized, status)
        self.setProperty("status", qss_status)
        self.icon_label.setProperty("status", qss_status)
        self.text_label.setProperty("status", qss_status)
        self.text_label.setText(text)
        self.icon_label.setPixmap(semantic_icon(status).pixmap(QSize(14, 14)))
        self.setAccessibleName(f"Status: {text}")
        self.setToolTip(f"Engineering status: {text}")
        repolish(self.icon_label)
        repolish(self.text_label)
        repolish(self)


class SourceCadBadge(QToolButton):
    """Read-only source identity control backed by imported STEP evidence."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sourceCadBadge")
        self.setProperty("source", "readOnly")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIcon(icon("lock-decision"))
        self.setIconSize(QSize(14, 14))
        self.setFixedHeight(24)
        self.setMinimumWidth(390)
        self.clear_source()

    def clear_source(self) -> None:
        self.setText("SOURCE CAD \u00b7 READ-ONLY  No source loaded")
        self.setToolTip("No source STEP identity is loaded.")
        self.setAccessibleName("Source CAD read-only. No source loaded.")

    def set_source(self, filename: str, sha256: str, *, verified: bool) -> None:
        evidence = "VERIFIED" if verified else "UNVERIFIED"
        short_hash = f"{sha256[:8]}...{sha256[-4:]}" if len(sha256) >= 12 else sha256
        self.setText(
            f"SOURCE CAD \u00b7 READ-ONLY  {filename}  SHA {short_hash}  {evidence}"
        )
        self.setToolTip(
            f"Immutable source: {filename}\nSHA-256: {sha256}\nGeometry evidence: {evidence}"
        )
        self.setAccessibleName(
            f"Source CAD read-only. {filename}. Geometry evidence {evidence}."
        )


WORKFLOW_STEPS = (
    "Project", "Import", "Assembly", "Manufacturing Intent", "Orientation",
    "Proposal", "Datums", "Locators & Supports", "Clamps", "Base Structure",
    "Weld & Access", "Concepts", "Validation", "Cost & Volume",
    "Review & Approval", "Export", "Component Library",
    "Rules & Preferences", "Project History",
)


class WorkflowRail(QListWidget):
    """Compact navigation rail with explicit text status in each tooltip."""

    stage_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._clicked_item: QListWidgetItem | None = None
        self.setObjectName("workflowRail")
        self.setFixedWidth(DIMENSIONS.workflow_rail)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setSpacing(0)
        for index, name in enumerate(WORKFLOW_STEPS, start=1):
            item = QListWidgetItem(f"{index}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setData(Qt.ItemDataRole.UserRole + 1, "not started")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(DIMENSIONS.workflow_rail - 2, 28))
            item.setToolTip(f"{index}. {name} - Not started")
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{name}, Not started")
            self.addItem(item)
        self.itemClicked.connect(self._select_clicked_stage)
        self.itemActivated.connect(self._activate_stage)

    def _emit_stage(self, item: QListWidgetItem) -> None:
        self.stage_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def _select_clicked_stage(self, item: QListWidgetItem) -> None:
        self._clicked_item = item
        self._emit_stage(item)
        QTimer.singleShot(0, self._clear_clicked_item)

    def _activate_stage(self, item: QListWidgetItem) -> None:
        if item is self._clicked_item:
            self._clicked_item = None
            return
        self._emit_stage(item)

    def _clear_clicked_item(self) -> None:
        self._clicked_item = None

    def set_states(self, states: dict[str, str], active: str | None) -> None:
        active_item = None
        for index in range(self.count()):
            item = self.item(index)
            name = str(item.data(Qt.ItemDataRole.UserRole))
            state = "active" if name == active else states.get(name, "not started")
            item.setData(Qt.ItemDataRole.UserRole + 1, state)
            item.setIcon(semantic_icon(state))
            item.setToolTip(f"{index + 1}. {name} - {state.title()}")
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{name}, {state}")
            if state == "active":
                active_item = item
        if active_item is not None:
            self.setCurrentItem(active_item)
        else:
            self.clearSelection()


class ApprovalGatePanel(QFrame):
    """Visible deterministic gate summary with human review actions."""

    approve_requested = Signal()
    reject_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("approvalGatePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.status = StatusChip(parent=self)
        self.summary = QLabel("No deterministic validation result is available.", self)
        self.summary.setWordWrap(True)
        self.summary.setObjectName("gateSummary")
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.reject = QPushButton("Reject", self)
        self.reject.setProperty("role", "destructive")
        self.reject.clicked.connect(self.reject_requested)
        self.approve = QPushButton("Approve for Review", self)
        self.approve.setProperty("role", "primary")
        self.approve.clicked.connect(self.approve_requested)
        actions.addWidget(self.reject)
        actions.addWidget(self.approve)
        layout.addWidget(self.status, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.summary)
        layout.addLayout(actions)
        self.set_result("not evaluated", 0, 0, can_approve=False, approved=False)

    def set_result(self, status: str, failures: int, warnings: int, *,
                   can_approve: bool, approved: bool) -> None:
        label = status.upper()
        self.status.set_status(status, label)
        if approved:
            message = (
                "Engineer review recorded for this revision. This is not production approval "
                "or physical prove-out."
            )
        elif status == "not evaluated":
            message = "Approval blocked: deterministic validation has not been run."
        elif not can_approve:
            message = (
                f"Approval blocked: {failures} deterministic failures and "
                f"{warnings} warnings require review."
            )
        elif status == "provisional":
            message = (
                f"Provisional review: {warnings} warnings or missing evidence remain visible. "
                "Qualified engineering review is required."
            )
        else:
            message = (
                "Deterministic checks do not block engineering review. Qualified human "
                "approval and physical prove-out remain separate."
            )
        self.summary.setText(message)
        self.approve.setEnabled(can_approve and not approved)
        self.reject.setEnabled(status != "not evaluated")
        self.approve.setToolTip(message)
