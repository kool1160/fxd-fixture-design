"""Presentation resources for the FXD PySide6 engineering workbench."""

from .theme import apply_fxd_theme, application_icon, asset_path, icon
from .widgets import ApprovalGatePanel, SourceCadBadge, StatusChip, WorkflowRail

__all__ = [
    "ApprovalGatePanel",
    "SourceCadBadge",
    "StatusChip",
    "WorkflowRail",
    "apply_fxd_theme",
    "application_icon",
    "asset_path",
    "icon",
]
