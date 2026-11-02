"""Small original line icons, rendered at 2x for crisp Qt high-DPI display."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from novadownloader.ui.theme import COLORS

PATHS = {
    "home": '<path d="m3 10 9-7 9 7v10H3Z M9 20v-7h6v7"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5 M4 16v5h16v-5"/>',
    "history": '<path d="M3 10a9 9 0 1 1 1 8 M3 4v6h6 M12 7v6l4 2"/>',
    "settings": (
        '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle '
        'cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>'
    ),
    "link": (
        '<path d="m10 14 4-4 M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0 M16 '
        '8l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" transform="translate(1 0) '
        'scale(.92 1)"/>'
    ),
    "paste": (
        '<rect x="5" y="5" width="14" height="16" rx="2"/><rect x="8" y="2" '
        'width="8" height="5" rx="2"/>'
    ),
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "video": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 5 3-5 3Z"/>',
    "audio": (
        '<path d="M5 16v-4a7 7 0 0 1 14 0v4"/><rect x="3" y="12" width="4" '
        'height="8" rx="2"/><rect x="17" y="12" width="4" height="8" rx="2"/>'
    ),
    "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    "check": '<path d="m5 12 4 4 10-10"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',
    "logo": '<path d="M5 20V4l14 16V4 M3 12h18"/>',
}


def icon(name: str, color: str | None = None, size: int = 24) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color or COLORS["muted"]}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    )
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
