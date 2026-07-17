"""Approved FXD UI & Branding Kit v1.1 design tokens."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    carbon: str = "#0B0D10"
    graphite: str = "#14181D"
    panel: str = "#1A1F26"
    raised: str = "#222831"
    border: str = "#323A45"
    steel: str = "#D6DBE0"
    muted: str = "#8B96A3"
    blue: str = "#0A84D7"
    orange: str = "#FF7A00"
    passed: str = "#39C98A"
    warning: str = "#F4B740"
    fail: str = "#EF6464"
    not_evaluated: str = "#7D8794"
    override: str = "#B78AF7"
    selection: str = "#153B55"
    input: str = "#101419"
    white: str = "#FFFFFF"


@dataclass(frozen=True)
class Dimensions:
    app_bar: int = 34
    menu_bar: int = 26
    toolbar: int = 40
    status_bar: int = 24
    workflow_rail: int = 48
    icon: int = 20
    min_window_width: int = 1180
    min_window_height: int = 720
    explorer_default: int = 300
    inspector_default: int = 360


COLORS = Colors()
DIMENSIONS = Dimensions()
UI_FONT = "Segoe UI"
TECHNICAL_FONT = "Consolas"
