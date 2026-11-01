from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from novadownloader import __version__
from novadownloader.core.dependencies import DependencyCheck
from novadownloader.ui.analysis_panel import AnalysisPanel
from novadownloader.workers.dependency_worker import DependencyWorker

STATE_LABELS = {
    "available": "Hazır",
    "missing": "Eksik",
    "unsupported": "Uyumsuz",
    "error": "Hata",
}


def _label(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    # Tool output must never be interpreted as rich text.
    from PySide6.QtCore import Qt

    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class MainWindow(QMainWindow):
    checks_completed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NovaDownloader")
        self.setMinimumSize(640, 520)
        self.resize(1000, 760)
        self._worker: DependencyWorker | None = None
        self._closing = False
        self.checks: list[DependencyCheck] = []
        self._build_ui()
        QTimer.singleShot(0, self.start_checks)

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(16)

        layout.addWidget(_label("NOVA  /  MASAÜSTÜ", "eyebrow"))
        layout.addWidget(_label("NovaDownloader", "heading"))
        layout.addWidget(
            _label("Videolarını ve ses dosyalarını istediğin kalitede kaydet.", "subtitle")
        )
        layout.addWidget(
            _label(
                "Faz 2.1 · Video analizi\n"
                "Video bilgilerini analiz edin. Kalite seçimi ve indirme "
                "sonraki aşamalarda eklenecek.",
                "phaseNote",
            )
        )

        self.analysis_panel = AnalysisPanel(self)
        self.analysis_panel.idle.connect(self._analysis_idle)
        layout.addWidget(self.analysis_panel)

        card = QFrame()
        card.setObjectName("statusCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        card_layout.addWidget(_label("Çalışma ortamı", "sectionHeading"))
        card_layout.addWidget(
            _label("Araçlar yalnızca kontrol edilir; otomatik kurulum yapılmaz.", "subtitle")
        )
        self.summary_label = _label("Ortam kontrolü başlatılıyor…", "summary")
        card_layout.addWidget(self.summary_label)
        self.busy_bar = QProgressBar()
        self.busy_bar.setAccessibleName("Bağımlılık kontrolü sürüyor")
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        card_layout.addWidget(self.busy_bar)
        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("background: transparent;")
        self.results_layout = QGridLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setHorizontalSpacing(16)
        self.results_layout.setVerticalSpacing(12)
        self.results_layout.setColumnStretch(2, 1)
        card_layout.addWidget(self.results_widget)

        actions = QHBoxLayout()
        self.recheck_button = QPushButton("Tekrar kontrol et")
        self.recheck_button.setObjectName("primaryButton")
        self.recheck_button.setAccessibleName("Çalışma ortamını tekrar kontrol et")
        self.recheck_button.clicked.connect(self.start_checks)
        self.copy_button = QPushButton("Tanılamayı kopyala")
        self.copy_button.setAccessibleName("Bağımlılık tanılamasını panoya kopyala")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_diagnostics)
        actions.addWidget(self.recheck_button)
        actions.addWidget(self.copy_button)
        actions.addStretch()
        card_layout.addLayout(actions)
        layout.addWidget(card)
        layout.addStretch()
        layout.addWidget(_label(f"Sürüm {__version__}  ·  Linux için geliştiriliyor", "footer"))
        self.statusBar().showMessage("Hazırlanıyor")

    def start_checks(self) -> None:
        if self._closing or (self._worker is not None and self._worker.isRunning()):
            return
        if self._worker is not None:
            self._worker.deleteLater()
        self.recheck_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.busy_bar.show()
        self.summary_label.setText("Bağımlılıklar kontrol ediliyor…")
        self.statusBar().showMessage(
            "Ortam kontrol ediliyor; pencereyi kullanmaya devam edebilirsiniz."
        )
        self._worker = DependencyWorker(self)
        self._worker.checks_ready.connect(self._show_checks)
        self._worker.check_failed.connect(self._show_failure)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _clear_results(self) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

    def _show_checks(self, checks: list[DependencyCheck]) -> None:
        if self._closing:
            return
        self.checks = checks
        self._clear_results()
        for row, check in enumerate(checks):
            name = _label(check.name)
            status = _label(STATE_LABELS[check.state])
            status.setProperty("state", check.state.value)
            detail = check.version if check.available else check.message
            description = _label(detail)
            description.setToolTip(check.message)
            self.results_layout.addWidget(name, row * 2, 0)
            self.results_layout.addWidget(status, row * 2, 1)
            self.results_layout.addWidget(description, row * 2, 2)
            if check.remedy:
                remedy = _label(check.remedy, "subtitle")
                self.results_layout.addWidget(remedy, row * 2 + 1, 0, 1, 3)
        missing = sum(not check.available for check in checks)
        self.summary_label.setText(
            f"{missing} bileşen için işlem gerekiyor." if missing else "Tüm bileşenler hazır."
        )
        self.copy_button.setEnabled(True)
        self.busy_bar.hide()
        self.statusBar().showMessage("Ortam kontrolü tamamlandı.")
        self.checks_completed.emit()

    def _show_failure(self, message: str) -> None:
        if self._closing:
            return
        self.checks = []
        self._clear_results()
        self.busy_bar.hide()
        self.summary_label.setText(message)
        self.statusBar().showMessage("Kontrol başarısız. Tekrar deneyebilirsiniz.")

    def _worker_finished(self) -> None:
        if self._closing:
            self.close()
        else:
            self.recheck_button.setEnabled(True)

    def copy_diagnostics(self) -> None:
        lines = [f"NovaDownloader {__version__}"]
        for check in self.checks:
            lines.append(
                f"{check.name}: {STATE_LABELS[check.state]} {check.version} — {check.message}"
            )
            if check.remedy:
                lines.append(check.remedy)
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage("Tanılama panoya kopyalandı.", 5000)

    def _analysis_idle(self) -> None:
        if self._closing:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        analysis_stopped = self.analysis_panel.shutdown()
        dependencies_running = self._worker is not None and self._worker.isRunning()
        if dependencies_running or not analysis_stopped:
            self._closing = True
            self.setEnabled(False)
            self.statusBar().showMessage("Kontrol durduruluyor; güvenle kapatılıyor…")
            if dependencies_running:
                self._worker.requestInterruption()
            event.ignore()
            return
        event.accept()
