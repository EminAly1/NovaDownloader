from threading import Event

import pytest
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.video_analyzer import VideoAnalyzer
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.ui.analysis_panel import AnalysisPanel
from novadownloader.ui.main_window import MainWindow
from novadownloader.workers import dependency_worker

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"
OTHER = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


def model(url=URL, title="Video başlığı", thumbnail=None):
    return VideoMetadata.from_info(
        {
            "title": title,
            "channel": "Kanal",
            "duration": 65,
            "thumbnail": thumbnail,
        },
        validate_youtube_url(url),
    )


@pytest.fixture
def panel(qtbot):
    widget = AnalysisPanel()
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.shutdown()
    qtbot.waitUntil(lambda: widget.worker is None, timeout=4000)


def test_enter_displays_metadata_including_thumbnail_request(qtbot, monkeypatch, panel):
    thumbnail = "https://i.ytimg.com/vi/BaW_jenozKc/hqdefault.jpg"
    loaded, threads = [], []

    def analyze(self, url, cancel):
        threads.append(QThread.currentThread())
        return model(thumbnail=thumbnail, title="<b>Türkçe başlık</b>")

    monkeypatch.setattr(VideoAnalyzer, "analyze", analyze)
    monkeypatch.setattr(panel.thumbnail, "load_url", loaded.append)
    QApplication.clipboard().setText(URL)
    panel.url_input.setFocus()
    qtbot.keyClick(panel.url_input, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert panel.url_input.text() == URL
    qtbot.keyClick(panel.url_input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: panel.worker is None)
    assert threads[0] != QApplication.instance().thread()
    assert panel.preview.isVisible()
    assert panel.title_label.text() == "<b>Türkçe başlık</b>"
    assert panel.title_label.textFormat() == Qt.TextFormat.PlainText
    assert panel.channel_label.text() == "Kanal"
    assert panel.duration_label.text() == "1:05"
    assert loaded[-1] == thumbnail
    assert "tamamlandı" in panel.status_label.text()


def test_invalid_url_never_starts_worker(monkeypatch, panel):
    monkeypatch.setattr(
        VideoAnalyzer, "analyze", lambda *a: pytest.fail("invalid URL started network")
    )
    panel.url_input.setText("https://youtube.com.evil.test/watch?v=BaW_jenozKc")
    panel.start_analysis()
    assert panel.worker is None
    assert "Geçersiz bağlantı" in panel.status_label.text()
    assert not panel.preview.isVisible()


def test_error_then_retry(qtbot, monkeypatch, panel):
    def fail(*args):
        raise AnalysisError(AnalysisErrorCode.PRIVATE)

    monkeypatch.setattr(VideoAnalyzer, "analyze", fail)
    panel.url_input.setText(URL)
    panel.start_analysis()
    qtbot.waitUntil(lambda: panel.worker is None)
    assert "Video özel" in panel.status_label.text()
    assert not panel.preview.isVisible()
    monkeypatch.setattr(VideoAnalyzer, "analyze", lambda *a: model())
    qtbot.mouseClick(panel.analyze_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: panel.worker is None)
    assert panel.metadata.title == "Video başlığı"


def test_cancel_is_real_and_clears_result(qtbot, monkeypatch, panel):
    entered = Event()

    def analyze(self, url, cancel):
        entered.set()
        cancel.wait(3)
        raise AnalysisError(AnalysisErrorCode.CANCELLED)

    monkeypatch.setattr(VideoAnalyzer, "analyze", analyze)
    panel.url_input.setText(URL)
    panel.start_analysis()
    qtbot.waitUntil(entered.is_set)
    assert panel.progress.isVisible()
    assert not panel.analyze_button.isEnabled()
    qtbot.mouseClick(panel.cancel_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: panel.worker is None)
    assert "iptal edildi" in panel.status_label.text()
    assert panel.metadata is None and not panel.progress.isVisible()


def test_late_result_cannot_replace_new_request(qtbot, monkeypatch, panel):
    entered, release = Event(), Event()
    calls = []

    def analyze(self, url, cancel):
        calls.append(url)
        if url == URL:
            entered.set()
            release.wait(3)
        return model(url, "Eski" if url == URL else "Yeni")

    monkeypatch.setattr(VideoAnalyzer, "analyze", analyze)
    panel.url_input.setText(URL)
    panel.start_analysis()
    try:
        qtbot.waitUntil(entered.is_set)
        old_id, old_worker = panel.request_id, panel.worker
        panel.start_analysis()
        assert panel.worker is old_worker and len(calls) == 1
        panel.url_input.setText(OTHER)
        assert panel.analyze_button.isEnabled()
        panel.start_analysis()
        panel._success(old_id, model(title="Gecikmiş"))
        assert panel.metadata is None
    finally:
        release.set()
    qtbot.waitUntil(lambda: panel.worker is None)
    assert panel.metadata.title == "Yeni"
    panel._success(old_id, model(title="Eski sonuç"))
    panel._error(old_id, AnalysisError(AnalysisErrorCode.NETWORK))
    assert panel.metadata.title == "Yeni"
    assert "tamamlandı" in panel.status_label.text()


def test_main_window_waits_for_analysis_shutdown(qtbot, monkeypatch):
    entered = Event()

    def analyze(self, url, cancel):
        entered.set()
        cancel.wait(3)
        raise AnalysisError(AnalysisErrorCode.CANCELLED)

    monkeypatch.setattr(VideoAnalyzer, "analyze", analyze)
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda *a: [])
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.analysis_panel.url_input.setText(URL)
    window.analysis_panel.start_analysis()
    qtbot.waitUntil(entered.is_set)
    worker = window.analysis_panel.worker
    with qtbot.waitSignal(worker.finished, timeout=4000):
        window.close()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert window.analysis_panel.worker is None


def test_small_main_window_with_long_metadata(qtbot, monkeypatch):
    monkeypatch.setattr(VideoAnalyzer, "analyze", lambda *a: model(title="uzunbaşlık" * 100))
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda *a: [])
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(640, 520)
    window.show()
    window.analysis_panel.url_input.setText(URL)
    window.analysis_panel.start_analysis()
    qtbot.waitUntil(lambda: window.analysis_panel.worker is None)
    assert window.centralWidget().horizontalScrollBar().maximum() == 0
