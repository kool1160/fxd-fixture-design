"""Application-level Qt palette, stylesheet, and approved asset loading."""

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from .tokens import COLORS


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
THEME_ROOT = Path(__file__).resolve().parent


def asset_path(*parts: str) -> Path:
    """Return an approved repository asset path and fail closed if it is absent."""
    path = REPOSITORY_ROOT.joinpath(*parts)
    if not path.is_file():
        raise FileNotFoundError(f"FXD UI asset is unavailable: {path}")
    return path


def icon(name: str) -> QIcon:
    return QIcon(str(asset_path("assets", "icons", "toolbar", f"{name}.svg")))


def application_icon() -> QIcon:
    result = QIcon()
    for size in (16, 32, 48, 64, 128, 192, 256, 512):
        path = asset_path("assets", "branding", "app-icons", f"fxd-app-icon-{size}.png")
        result.addFile(str(path), QSize(size, size))
    return result


def _palette() -> QPalette:
    palette = QPalette()
    role = QPalette.ColorRole
    palette.setColor(role.Window, QColor(COLORS.carbon))
    palette.setColor(role.WindowText, QColor(COLORS.steel))
    palette.setColor(role.Base, QColor(COLORS.panel))
    palette.setColor(role.AlternateBase, QColor(COLORS.graphite))
    palette.setColor(role.ToolTipBase, QColor(COLORS.raised))
    palette.setColor(role.ToolTipText, QColor(COLORS.steel))
    palette.setColor(role.Text, QColor(COLORS.steel))
    palette.setColor(role.Button, QColor(COLORS.raised))
    palette.setColor(role.ButtonText, QColor(COLORS.steel))
    palette.setColor(role.Highlight, QColor(COLORS.blue))
    palette.setColor(role.HighlightedText, QColor(COLORS.white))
    palette.setColor(
        QPalette.ColorGroup.Disabled, role.Text, QColor(COLORS.muted)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, role.ButtonText, QColor(COLORS.muted)
    )
    return palette


def apply_fxd_theme(application: QApplication) -> None:
    """Apply the v1.1 theme once at application scope."""
    stylesheet = (THEME_ROOT / "fxd.qss").read_text(encoding="utf-8")
    application.setPalette(_palette())
    application.setStyleSheet(stylesheet)
    application.setWindowIcon(application_icon())
    application.setApplicationName("FXD Engineering Workbench")
    application.setOrganizationName("FXD")
