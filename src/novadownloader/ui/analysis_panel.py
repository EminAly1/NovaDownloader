from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from novadownloader.core.exceptions import AnalysisError
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.ui.thumbnail import ThumbnailLabel
from novadownloader.workers.analysis_worker import AnalysisWorker


def text_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class AnalysisPanel(QFrame):
    idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusCard")
        self.request_id = 0
        self.worker = None
        self.pending = None
        self.closing = False
        self.active_input = ""
        self.metadata: VideoMetadata | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        heading = text_label("Video bağlantısını analiz et")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        self.url_input = QLineEdit()
        self.url_input.setAccessibleName("YouTube video bağlantısı")
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setMaxLength(4096)
        self.url_input.returnPressed.connect(self.start_analysis)
        self.url_input.textChanged.connect(self._input_changed)
        layout.addWidget(self.url_input)
        actions = QHBoxLayout()
        self.analyze_button = QPushButton("Analiz et")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.clicked.connect(self.start_analysis)
        paste = QPushButton("Yapıştır")
        paste.clicked.connect(lambda: self.url_input.setText(QApplication.clipboard().text()))
        self.cancel_button = QPushButton("İptal et")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        for button in (self.analyze_button, paste, self.cancel_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Video analizi sürüyor")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.status_label = text_label("Tek bir YouTube bağlantısı girin. İndirme yapılmaz.")
        layout.addWidget(self.status_label)
        self.preview = QFrame()
        preview_layout = QHBoxLayout(self.preview)
        preview_layout.setContentsMargins(0, 8, 0, 0)
        self.thumbnail = ThumbnailLabel(self)
        preview_layout.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignTop)
        details = QVBoxLayout()
        self.title_label = text_label()
        self.channel_label = text_label()
        self.duration_label = text_label()
        self.source_label = text_label()
        for label in (self.title_label, self.channel_label, self.duration_label, self.source_label):
            details.addWidget(label)
        preview_layout.addLayout(details, 1)
        layout.addWidget(self.preview)
        self.preview.hide()

    def _input_changed(self) -> None:
        self.analyze_button.setEnabled(
            not self.closing and (self.worker is None or self.url_input.text() != self.active_input)
        )

    def start_analysis(self) -> None:
        if self.closing:
            return
        value = self.url_input.text()
        try:
            source = validate_youtube_url(value)
        except AnalysisError as error:
            self.cancel_analysis()
            self.status_label.setText(error.user_message)
            return
        if self.worker is not None and self.active_input == value and self.progress.isVisible():
            return
        self.request_id += 1
        self.active_input = value
        self.metadata = None
        self.preview.hide()
        self.thumbnail.load_url(None)
        self.progress.show()
        self.status_label.setText("Video analiz ediliyor…")
        self.analyze_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.pending = (self.request_id, source.normalized_url)
        if self.worker is not None:
            self.worker.cancel()
        else:
            self._start_pending()

    def _start_pending(self) -> None:
        if self.pending is None or self.closing:
            return
        request_id, url = self.pending
        self.pending = None
        self.worker = AnalysisWorker(request_id, url, self)
        self.worker.succeeded.connect(self._success)
        self.worker.failed.connect(self._error)
        self.worker.cancelled.connect(self._cancelled)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _success(self, request_id: int, metadata: VideoMetadata) -> None:
        if request_id != self.request_id or self.closing:
            return
        self.metadata = metadata
        self.title_label.setText(metadata.title)
        self.channel_label.setText(metadata.channel)
        self.duration_label.setText(metadata.readable_duration)
        self.source_label.setText(metadata.source_url)
        self.thumbnail.load_url(metadata.thumbnail_url)
        self.preview.show()
        self._settle("Analiz tamamlandı.")

    def _error(self, request_id: int, error: AnalysisError) -> None:
        if request_id == self.request_id and not self.closing:
            self._settle(error.user_message)

    def _cancelled(self, request_id: int) -> None:
        if request_id == self.request_id and not self.closing:
            self._settle("Analiz iptal edildi.")

    def _settle(self, message: str) -> None:
        self.progress.hide()
        self.cancel_button.setEnabled(False)
        self.analyze_button.setEnabled(not self.closing)
        self.status_label.setText(message)

    def _finished(self) -> None:
        self.worker.deleteLater()
        self.worker = None
        if self.pending is not None and not self.closing:
            self._start_pending()
        else:
            self.analyze_button.setEnabled(not self.closing)
            self.idle.emit()

    def cancel_analysis(self) -> None:
        self.request_id += 1
        self.pending = None
        self.metadata = None
        self.preview.hide()
        self.thumbnail.load_url(None)
        if self.worker is not None:
            self.worker.cancel()
        self._settle("Analiz iptal edildi.")

    def shutdown(self) -> bool:
        self.closing = True
        self.cancel_analysis()
        return self.worker is None or not self.worker.isRunning()
