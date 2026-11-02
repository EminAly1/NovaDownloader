from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from novadownloader import __version__
from novadownloader.core.dependencies import DependencyCheck
from novadownloader.ui.analysis_panel import AnalysisPanel
from novadownloader.ui.components import EmptyStateWidget
from novadownloader.ui.icons import icon
from novadownloader.ui.theme import COLORS
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
        self.resize(1280, 800)
        self._worker: DependencyWorker | None = None
        self._closing = False
        self.checks: list[DependencyCheck] = []
        self._build_ui()
        QTimer.singleShot(0, self.start_checks)

    def _build_ui(self) -> None:
        # Keep the outer scroll surface for small displays; each page owns vertical scrolling.
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        self.setCentralWidget(outer)
        shell = QWidget()
        shell.setObjectName("canvas")
        outer.setWidget(shell)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(208)
        nav_layout = QVBoxLayout(self.sidebar)
        nav_layout.setContentsMargins(16, 24, 16, 16)
        nav_layout.setSpacing(8)
        branding = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icon("logo", COLORS["hover"], 32).pixmap(QSize(32, 32)))
        branding.addWidget(logo)
        self.brand_label = _label("NovaDownloader", "cardTitle")
        branding.addWidget(self.brand_label, 1)
        nav_layout.addLayout(branding)
        nav_layout.addSpacing(32)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []
        for index, (name, symbol) in enumerate(
            (
                ("Ana Sayfa", "home"),
                ("İndirilenler", "download"),
                ("Geçmiş", "history"),
                ("Ayarlar", "settings"),
            )
        ):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setIcon(icon(symbol))
            button.setIconSize(QSize(20, 20))
            button.setCheckable(True)
            button.setToolTip(name)
            button.setAccessibleName(name)
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            nav_layout.addWidget(button)
        self.nav_buttons[0].setChecked(True)
        nav_layout.addStretch()
        self.system_label = _label("Ortam kontrol ediliyor…", "footer")
        nav_layout.addWidget(self.system_label)
        self.busy_bar = QProgressBar()
        self.busy_bar.setAccessibleName("Bağımlılık kontrolü sürüyor")
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        nav_layout.addWidget(self.busy_bar)
        self.version_label = _label(f"v{__version__}  ·  Linux", "footer")
        nav_layout.addWidget(self.version_label)
        shell_layout.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        self.pages.setMinimumWidth(0)
        shell_layout.addWidget(self.pages, 1)
        self.nav_group.idClicked.connect(self.pages.setCurrentIndex)
        self.page_layouts = []
        for _ in range(4):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content.setObjectName("canvas")
            content.setMinimumWidth(0)
            layout = QVBoxLayout(content)
            layout.setContentsMargins(32, 24, 32, 24)
            layout.setSpacing(16)
            scroll.setWidget(content)
            self.pages.addWidget(scroll)
            self.page_layouts.append(layout)
        home = self.page_layouts[0]
        heading = QHBoxLayout()
        heading.addWidget(_label("NovaDownloader", "heading"), 1)
        heading.addWidget(_label("VİDEO & SES", "eyebrow"))
        home.addLayout(heading)
        home.addWidget(
            _label("Videolarını ve ses dosyalarını istediğin kalitede kaydet.", "subtitle")
        )
        self.analysis_panel = AnalysisPanel(self)
        self.analysis_panel.idle.connect(self._analysis_idle)
        home.addWidget(self.analysis_panel)
        home.addStretch()
        for index, title, symbol, description in (
            (1, "İndirilenler", "download", "İndirmeleriniz tamamlandığında burada görünecek."),
            (2, "Geçmiş", "history", "Geçmiş kayıtları sonraki fazlarda burada yer alacak."),
            (3, "Ayarlar", "settings", "Uygulama tercihleri sonraki fazlarda hazırlanacak."),
        ):
            layout = self.page_layouts[index]
            layout.addWidget(_label(title, "heading"))
            layout.addWidget(
                EmptyStateWidget("Bu özellik sonraki fazlarda hazırlanacak", description, symbol)
            )
            if index != 3:
                back = QPushButton("Ana sayfaya dön")
                back.clicked.connect(self._go_home)
                layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignHCenter)
                layout.addStretch()
        self._build_diagnostics(self.page_layouts[3])
        self.page_layouts[3].addStretch()
        self.statusBar().showMessage("Hazırlanıyor")

    def _go_home(self):
        self.pages.setCurrentIndex(0)
        self.nav_buttons[0].setChecked(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 900
        self.sidebar.setFixedWidth(72 if compact else 208)
        self.brand_label.setVisible(not compact)
        self.version_label.setVisible(not compact)
        self.system_label.setVisible(not compact)
        for button in self.nav_buttons:
            button.setText("" if compact else button.accessibleName())
        for layout in self.page_layouts:
            margin = 16 if compact else 32
            layout.setContentsMargins(margin, 24, margin, 24)

    def _build_diagnostics(self, layout):
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
        self.results_widget = QWidget()
        self.results_layout = QGridLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setHorizontalSpacing(16)
        self.results_layout.setVerticalSpacing(12)
        self.results_layout.setColumnStretch(2, 1)
        card_layout.addWidget(self.results_widget)
        actions = QHBoxLayout()
        self.recheck_button = QPushButton("Tekrar kontrol et")
        self.recheck_button.setAccessibleName("Çalışma ortamını tekrar kontrol et")
        self.recheck_button.clicked.connect(self.start_checks)
        self.copy_button = QPushButton("Tanılamayı kopyala")
        self.copy_button.setAccessibleName("Bağımlılık tanılamasını panoya kopyala")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_diagnostics)
        actions.addWidget(self.recheck_button)
        actions.addWidget(self.copy_button)
        card_layout.addLayout(actions)
        layout.addWidget(card)
        # Initialize hidden settings geometry before its first activation.
        card.ensurePolished()
        card_layout.activate()

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
        self.system_label.setText("Ortamı kontrol edin" if missing else "●  Sistem hazır")
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
        self.system_label.setText("Ortam kontrol edilemedi")
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
