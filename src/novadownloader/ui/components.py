"""Reusable Qt input, preview and empty-state components."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from novadownloader.ui.icons import icon
from novadownloader.ui.theme import COLORS, SPACE
from novadownloader.ui.thumbnail import ThumbnailLabel


def text_label(text: str = "", name: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def restyle(widget, **properties) -> None:
    for key, value in properties.items():
        widget.setProperty(key, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ClampedLabel(QLabel):
    """Keep full plain text for accessibility, elide painting to a bounded line count."""

    def __init__(self, lines=3, parent=None):
        super().__init__(parent)
        self.lines = lines
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def setText(self, value):
        super().setText(value)
        self.setToolTip(value)
        self.setAccessibleName(value)
        self.updateGeometry()

    def sizeHint(self):
        return QSize(240, self.fontMetrics().lineSpacing() * self.lines)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        layout = QTextLayout(self.text(), self.font())
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        y = 0
        for index in range(self.lines):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(self.width())
            value = self.text()[line.textStart() : line.textStart() + line.textLength()]
            if index == self.lines - 1:
                value = self.fontMetrics().elidedText(
                    self.text()[line.textStart() :], Qt.TextElideMode.ElideRight, self.width()
                )
            painter.drawText(0, y + self.fontMetrics().ascent(), value)
            y += self.fontMetrics().lineSpacing()
        layout.endLayout()
        painter.end()


class UrlInputWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("urlCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(SPACE)
        layout.addWidget(text_label("Bir bağlantıyla başlayın", "cardTitle"))
        self.url_input = QLineEdit()
        self.url_input.setAccessibleName("YouTube video bağlantısı")
        self.url_input.setPlaceholderText("YouTube bağlantısını buraya yapıştırın…")
        self.url_input.setMaxLength(4096)
        self.url_input.addAction(icon("link"), QLineEdit.ActionPosition.LeadingPosition)
        self.url_input.setMinimumWidth(0)
        layout.addWidget(self.url_input)
        actions = QHBoxLayout()
        actions.setSpacing(SPACE)
        self.paste_button = QPushButton("Yapıştır")
        self.paste_button.setIcon(icon("paste"))
        self.clear_button = QPushButton("Temizle")
        self.clear_button.setAccessibleName("Bağlantıyı ve analiz sonucunu temizle")
        self.cancel_button = QPushButton("İptal et")
        self.cancel_button.setEnabled(False)
        self.analyze_button = QPushButton("Analiz et")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.setIcon(icon("arrow", COLORS["text"]))
        for button in (self.paste_button, self.clear_button, self.cancel_button):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self.analyze_button)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Video analizi sürüyor")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.status_label = text_label(
            "YouTube, Shorts ve YouTube Music bağlantıları desteklenir.", "subtitle"
        )
        layout.addWidget(self.status_label)

    def set_state(self, state: str, message: str):
        restyle(self, state=state)
        restyle(self.status_label, state=state)
        self.status_label.setText(message)
        self.progress.setVisible(state == "loading")
        self.analyze_button.setText("Analiz ediliyor…" if state == "loading" else "Analiz et")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 520
        self.paste_button.setText("" if compact else "Yapıştır")
        self.paste_button.setAccessibleName("Yapıştır")
        self.paste_button.setToolTip("Panodaki bağlantıyı yapıştır")
        self.clear_button.setText("" if compact else "Temizle")
        self.clear_button.setIcon(icon("close"))
        self.clear_button.setToolTip("Bağlantıyı ve sonucu temizle")


class VideoPreviewCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(24)
        self.thumbnail = ThumbnailLabel(self)
        self.thumbnail.setObjectName("thumbnail")
        layout.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignTop)
        details = QVBoxLayout()
        details.setSpacing(SPACE)
        details.addWidget(text_label("YOUTUBE  /  VİDEO", "eyebrow"))
        self.title_label = ClampedLabel(3)
        self.title_label.setObjectName("cardTitle")
        details.addWidget(self.title_label)
        self.channel_label = ClampedLabel(1)
        self.channel_label.setObjectName("subtitle")
        details.addWidget(self.channel_label)
        row = QHBoxLayout()
        self.duration_label = text_label("", "badge")
        self.duration_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        row.addWidget(self.duration_label)
        self.source_label = ClampedLabel(1)
        self.source_label.setObjectName("footer")
        row.addWidget(self.source_label, 1)
        details.addLayout(row)
        layout.addLayout(details, 1)

    def show_metadata(self, metadata):
        self.title_label.setText(metadata.title)
        self.channel_label.setText(metadata.channel)
        self.duration_label.setText(metadata.readable_duration)
        self.source_label.setText(metadata.source_url)
        self.thumbnail.load_url(metadata.thumbnail_url)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.thumbnail.setFixedSize(QSize(224, 126) if self.width() >= 640 else QSize(160, 90))


class EmptyStateWidget(QFrame):
    def __init__(
        self,
        title="Bir sonraki videonuz burada.",
        description="Bağlantıyı yapıştırın; video bilgileri ve mevcut kaliteler burada görünsün.",
        symbol="video",
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(16)
        symbol_label = QLabel()
        symbol_label.setPixmap(icon(symbol, COLORS["hover"], 40).pixmap(QSize(40, 40)))
        symbol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(symbol_label)
        self.title = text_label(title, "sectionHeading")
        self.description = text_label(description, "subtitle")
        for label in (self.title, self.description):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
