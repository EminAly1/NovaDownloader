from threading import Event

from PySide6.QtCore import QThread, Signal

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.core.logging_config import log_failure
from novadownloader.services.video_analyzer import VideoAnalyzer


class AnalysisWorker(QThread):
    succeeded = Signal(int, object)
    failed = Signal(int, object)
    cancelled = Signal(int)

    def __init__(self, request_id: int, url: str, parent=None, analyzer=None):
        super().__init__(parent)
        self.request_id = request_id
        self.url = url
        self.analyzer = analyzer if analyzer is not None else VideoAnalyzer()
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            result = self.analyzer.analyze(self.url, self.cancel_event)
            if self.cancel_event.is_set():
                self.cancelled.emit(self.request_id)
            else:
                self.succeeded.emit(self.request_id, result)
        except AnalysisError as error:
            if error.code == AnalysisErrorCode.CANCELLED or self.cancel_event.is_set():
                self.cancelled.emit(self.request_id)
            else:
                self.failed.emit(self.request_id, error)
        except Exception as error:
            log_failure("Analysis worker", error)
            if self.cancel_event.is_set():
                self.cancelled.emit(self.request_id)
            else:
                self.failed.emit(self.request_id, AnalysisError(AnalysisErrorCode.EXTRACTOR))
