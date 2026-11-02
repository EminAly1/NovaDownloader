"""Shared desktop design tokens; QSS and custom painting use the same palette."""

from importlib.resources import files
from string import Template

COLORS = {
    "background": "#0B1020",
    "sidebar": "#111827",
    "surface": "#171F30",
    "raised": "#1E293B",
    "accent": "#6366F1",
    "hover": "#818CF8",
    "primary_hover": "#7376F4",
    "warning": "#FDE68A",
    "text": "#F8FAFC",
    "muted": "#A8B5C9",
    "success": "#86EFAC",
    "error": "#FCA5A5",
    "border": "#303C52",
    "selected": "#232C52",
    "focus": "#C7D2FE",
}
SPACE = 8
RADIUS = 16


def stylesheet() -> str:
    template = files("novadownloader.ui.themes").joinpath("dark.qss").read_text("utf-8")
    return Template(template).substitute(COLORS, radius=RADIUS)
