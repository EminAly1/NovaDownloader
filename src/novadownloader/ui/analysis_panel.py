from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout

from novadownloader.core.exceptions import AnalysisError
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.ui.components import EmptyStateWidget, UrlInputWidget, VideoPreviewCard
from novadownloader.ui.quality_panel import DownloadSummaryCard, QualitySelectionPanel
from novadownloader.workers.analysis_worker import AnalysisWorker


class AnalysisPanel(QFrame):
    idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.request_id = 0
        self.worker = None
        self.pending = None
        self.closing = False
        self.active_input = ""
        self.metadata: VideoMetadata | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.url_card = UrlInputWidget()
        # Stable references retained for the existing controller and tests.
        for name in (
            "url_input",
            "analyze_button",
            "paste_button",
            "clear_button",
            "cancel_button",
            "progress",
            "status_label",
        ):
            setattr(self, name, getattr(self.url_card, name))
        self.url_input.returnPressed.connect(self.start_analysis)
        self.url_input.textChanged.connect(self._input_changed)
        self.analyze_button.clicked.connect(self.start_analysis)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.paste_button.clicked.connect(
            lambda: self.url_input.setText(QApplication.clipboard().text())
        )
        self.clear_button.clicked.connect(self.clear_input)
        layout.addWidget(self.url_card)
        self.empty_state = EmptyStateWidget()
        layout.addWidget(self.empty_state)
        self.preview = VideoPreviewCard()
        for name in ("thumbnail", "title_label", "channel_label", "duration_label", "source_label"):
            setattr(self, name, getattr(self.preview, name))
        layout.addWidget(self.preview)
        self.preview.hide()
        self.quality_panel = QualitySelectionPanel()
        self.download_summary = DownloadSummaryCard()
        self.quality_panel.selection_changed.connect(self.download_summary.set_request)
        layout.addWidget(self.quality_panel)
        layout.addWidget(self.download_summary)
        self.quality_panel.hide()
        self.download_summary.hide()

    @property
    def selected_request(self):
        return self.download_summary.request

    def _reset_result(self):
        self.metadata = None
        self.preview.hide()
        self.thumbnail.load_url(None)
        self.quality_panel.clear()
        self.download_summary.set_request(None)
        self.download_summary.hide()
        self.empty_state.show()

    def clear_input(self):
        self.cancel_analysis()
        self.url_input.clear()
        self._settle("Bir YouTube bağlantısı yapıştırarak başlayın.", "empty")
        self.url_input.setFocus()

    def _input_changed(self) -> None:
        if self.url_input.text() != self.active_input and (
            self.metadata is not None or self.worker is not None
        ):
            self.cancel_analysis()
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
            self._settle(error.user_message, "error")
            return
        if self.worker is not None and self.active_input == value and self.progress.isVisible():
            return
        self.request_id += 1
        self.active_input = value
        self._reset_result()
        self.url_card.set_state("loading", "Video analiz ediliyor…")
        self.empty_state.title.setText("Video bilgileri hazırlanıyor")
        self.empty_state.description.setText(
            "Başlık, süre ve mevcut formatlar alınıyor. İşlemi iptal edebilirsiniz."
        )
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
        self.preview.show_metadata(metadata)
        self.preview.show()
        self.quality_panel.set_metadata(metadata)
        self.download_summary.show()
        self.empty_state.hide()
        self._settle("Analiz tamamlandı. Kalite ve format seçebilirsiniz.", "success")

    def _error(self, request_id: int, error: AnalysisError) -> None:
        if request_id == self.request_id and not self.closing:
            self._settle(error.user_message, "error")

    def _cancelled(self, request_id: int) -> None:
        if request_id == self.request_id and not self.closing:
            self._settle("Analiz iptal edildi.")

    def _settle(self, message: str, state: str = "empty") -> None:
        self.url_card.set_state(state, message)
        if self.metadata is None:
            self.empty_state.title.setText(
                "Analiz tamamlanamadı" if state == "error" else "Bir sonraki videonuz burada."
            )
            self.empty_state.description.setText(
                "Bağlantıyı kontrol edip yeniden deneyin."
                if state == "error"
                else "Bağlantıyı yapıştırın; video bilgileri ve mevcut kaliteler burada görünsün."
            )
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
        self._reset_result()
        if self.worker is not None:
            self.worker.cancel()
        self._settle("Analiz iptal edildi.")

    def shutdown(self) -> bool:
        self.closing = True
        self.cancel_analysis()
        return self.worker is None or not self.worker.isRunning()
