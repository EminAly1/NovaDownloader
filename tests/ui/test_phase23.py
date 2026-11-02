from dataclasses import replace
from threading import Event

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.models.format_selection import SelectionKind, SizeCertainty
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.video_analyzer import VideoAnalyzer
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.ui.analysis_panel import AnalysisPanel
from novadownloader.ui.main_window import MainWindow
from novadownloader.ui.theme import stylesheet
from novadownloader.workers import dependency_worker

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"
OTHER = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


@pytest.fixture(autouse=True)
def theme(qapp):
    previous = qapp.styleSheet()
    qapp.setStyle("Fusion")
    qapp.setStyleSheet(stylesheet())
    yield
    qapp.setStyleSheet(previous)


@pytest.fixture
def metadata(raw_formats):
    return VideoMetadata.from_info(
        {"title": "Gerçek model", "channel": "Kanal", "duration": 1000, "formats": raw_formats},
        validate_youtube_url(URL),
    )


@pytest.fixture
def panel(qtbot):
    widget = AnalysisPanel()
    widget.resize(960, 720)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.shutdown()
    qtbot.waitUntil(lambda: widget.worker is None, timeout=4000)


def analyze(qtbot, monkeypatch, panel, metadata):
    monkeypatch.setattr(VideoAnalyzer, "analyze", lambda *args: metadata)
    panel.url_input.setText(metadata.source_url)
    qtbot.keyClick(panel.url_input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: panel.worker is None)


def test_paste_clear_and_input_edit_invalidate_complete_selection(
    qtbot, monkeypatch, panel, metadata
):
    QApplication.clipboard().setText(URL)
    qtbot.mouseClick(panel.paste_button, Qt.MouseButton.LeftButton)
    assert panel.url_input.text() == URL
    analyze(qtbot, monkeypatch, panel, metadata)
    assert panel.selected_request is not None
    panel.url_input.setText(OTHER)
    assert panel.selected_request is None and panel.metadata is None
    assert not panel.preview.isVisible()
    assert not panel.quality_panel.isVisible()
    qtbot.mouseClick(panel.clear_button, Qt.MouseButton.LeftButton)
    assert panel.url_input.text() == ""
    assert panel.empty_state.isVisible()
    assert not panel.progress.isVisible()
    assert panel.url_card.property("state") == "empty"


def test_real_models_populate_sorted_options_and_recommendation(
    qtbot, monkeypatch, panel, metadata
):
    analyze(qtbot, monkeypatch, panel, metadata)
    quality = panel.quality_panel
    assert [card.choice.resolution for card in quality.cards] == [2160, 1080, 1080, 1080, 720]
    assert [card.choice.fps for card in quality.cards] == [60, 60, 30, 30, 30]
    assert quality.selected.recommended and quality.selected.resolution == 1080
    assert sum(card.isChecked() for card in quality.cards) == 1
    assert panel.title_label.text() == metadata.title
    assert panel.duration_label.text() == "16:40"
    assert panel.thumbnail.text() == "Önizleme yok"
    assert panel.thumbnail.width() * 9 == panel.thumbnail.height() * 16
    assert panel.selected_request.source_url == URL
    assert not panel.download_summary.download_button.isEnabled()
    assert "birleştirilecek" in panel.download_summary.processing_label.text()


def test_keyboard_selection_changes_summary_and_single_checked_card(
    qtbot, monkeypatch, panel, metadata
):
    analyze(qtbot, monkeypatch, panel, metadata)
    quality = panel.quality_panel
    quality.cards[1].setFocus()
    qtbot.keyClick(quality.cards[1], Qt.Key.Key_Down)
    assert quality.cards[2].isChecked()
    assert panel.selected_request.selection.format_expression == "137+140"
    qtbot.keyClick(quality.cards[2], Qt.Key.Key_End)
    assert quality.cards[-1].isChecked()
    assert "Ses dahil" in panel.download_summary.processing_label.text()
    qtbot.keyClick(quality.cards[-1], Qt.Key.Key_Home)
    assert quality.cards[0].isChecked()
    qtbot.keyClick(quality.cards[1], Qt.Key.Key_Space)
    assert quality.cards[1].isChecked()
    assert sum(card.isChecked() for card in quality.cards) == 1


def test_mode_roundtrip_preserves_valid_selection_without_network(
    qtbot, monkeypatch, panel, metadata
):
    calls = []
    monkeypatch.setattr(VideoAnalyzer, "analyze", lambda *args: calls.append(args) or metadata)
    panel.url_input.setText(URL)
    panel.start_analysis()
    qtbot.waitUntil(lambda: panel.worker is None)
    quality = panel.quality_panel
    qtbot.mouseClick(quality.cards[-1], Qt.MouseButton.LeftButton)
    chosen_video = quality.selected
    qtbot.mouseClick(quality.media_type.buttons[SelectionKind.AUDIO], Qt.MouseButton.LeftButton)
    assert len(quality.cards) == 3
    qtbot.mouseClick(quality.cards[-1], Qt.MouseButton.LeftButton)
    mp3 = quality.selected
    assert mp3.requires_conversion
    assert "FFmpeg" in panel.download_summary.processing_label.text()
    assert "24.0 MB" in panel.download_summary.processing_label.text()
    assert "20.0 MB" in panel.download_summary.size_label.text()
    assert not panel.download_summary.download_button.isEnabled()
    quality.set_mode(SelectionKind.VIDEO)
    assert quality.selected == chosen_video
    quality.set_mode(SelectionKind.AUDIO)
    assert quality.selected == mp3
    assert len(calls) == 1


@pytest.mark.parametrize(
    "certainty,index,text",
    [
        (SizeCertainty.ESTIMATED, 0, "Yaklaşık 2.02 GB"),
        (SizeCertainty.EXACT, 1, "Boyut: 5.02 GB"),
    ],
)
def test_size_labels_use_service_results(
    qtbot, monkeypatch, panel, metadata, certainty, index, text
):
    analyze(qtbot, monkeypatch, panel, metadata)
    card = panel.quality_panel.cards[index]
    assert card.choice.download_size.certainty == certainty
    assert card.size_label.text() == text
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    assert text in panel.download_summary.size_label.text()
    panel.download_summary.details_button.click()
    assert panel.download_summary.technical.isVisible()
    assert card.choice.format_expression in panel.download_summary.technical.text()
    assert "Çıktı boyutu: Boyut bilinmiyor" in panel.download_summary.technical.text()


def test_unknown_size_and_metadata_fields_are_honest(qtbot, monkeypatch, panel):
    metadata = VideoMetadata.from_info(
        {
            "formats": [
                {"format_id": "18", "vcodec": "avc1", "acodec": "mp4a.40.2"},
            ]
        },
        validate_youtube_url(URL),
    )
    analyze(qtbot, monkeypatch, panel, metadata)
    card = panel.quality_panel.cards[0]
    assert card.title.text() == "Çözünürlük bilinmiyor"
    assert card.size_label.text() == "Boyut bilinmiyor"
    assert "FPS bilinmiyor" in card.detail.text()
    assert panel.title_label.text() == "Başlık bilinmiyor"
    assert panel.duration_label.text() == "Süre bilinmiyor"
    assert "Boyut bilinmiyor" in panel.download_summary.size_label.text()


@pytest.mark.parametrize(
    "formats", [[], [{"format_id": "137", "vcodec": "avc1", "acodec": "none", "height": 1080}]]
)
def test_empty_or_unpaired_formats_cannot_create_request(qtbot, monkeypatch, panel, formats):
    metadata = VideoMetadata.from_info({"formats": formats}, validate_youtube_url(URL))
    analyze(qtbot, monkeypatch, panel, metadata)
    quality = panel.quality_panel
    assert quality.selected is None
    assert panel.selected_request is None
    assert not panel.download_summary.download_button.isEnabled()
    if formats:
        assert not quality.cards[0].isEnabled()
        assert quality.cards[0].choice.unavailable_reason in quality.cards[0].accessibleName()
    else:
        assert quality.empty.isVisible()
    quality.set_mode(SelectionKind.AUDIO)
    assert quality.empty.isVisible()
    assert panel.selected_request is None


def test_audio_only_video_mode_empty_and_no_invented_video(qtbot, monkeypatch, panel, metadata):
    metadata = replace(
        metadata, formats=tuple(stream for stream in metadata.formats if stream.height is None)
    )
    analyze(qtbot, monkeypatch, panel, metadata)
    assert not panel.quality_panel.cards
    panel.quality_panel.set_mode(SelectionKind.AUDIO)
    assert panel.selected_request.selection.kind == SelectionKind.AUDIO
    panel.quality_panel.set_mode(SelectionKind.VIDEO)
    assert panel.selected_request is None


def test_reanalysis_clears_previous_mode_and_quality(qtbot, monkeypatch, panel, metadata):
    analyze(qtbot, monkeypatch, panel, metadata)
    panel.quality_panel.set_mode(SelectionKind.AUDIO)
    panel.quality_panel.cards[-1].click()
    newer = replace(
        metadata,
        video_id="aqz-KE-bpKQ",
        source_url=OTHER,
        formats=tuple(stream for stream in metadata.formats if stream.vcodec == "none"),
    )
    analyze(qtbot, monkeypatch, panel, newer)
    assert panel.quality_panel.mode == SelectionKind.VIDEO
    assert panel.selected_request is None
    assert not panel.quality_panel.cards
    assert panel.quality_panel.remembered == {SelectionKind.VIDEO: None}


def test_loading_clear_and_late_result_never_restore_old_request(
    qtbot, monkeypatch, panel, metadata
):
    entered, release = Event(), Event()

    def slow(*args):
        entered.set()
        release.wait(3)
        return metadata

    monkeypatch.setattr(VideoAnalyzer, "analyze", slow)
    panel.url_input.setText(URL)
    panel.start_analysis()
    try:
        qtbot.waitUntil(entered.is_set)
        old_id = panel.request_id
        worker = panel.worker
        assert panel.url_card.property("state") == "loading"
        assert panel.progress.minimum() == panel.progress.maximum() == 0
        for _ in range(5):
            panel.start_analysis()
        assert panel.worker is worker
        panel.clear_button.click()
        assert worker.cancel_event.is_set()
        panel._success(old_id, metadata)
        assert panel.selected_request is None and panel.metadata is None
    finally:
        release.set()
    qtbot.waitUntil(lambda: panel.worker is None)
    assert panel.url_card.property("state") == "empty"
    assert not panel.quality_panel.isVisible()


@pytest.mark.parametrize(
    "code", [AnalysisErrorCode.NETWORK, AnalysisErrorCode.TIMEOUT, AnalysisErrorCode.PRIVATE]
)
def test_service_error_removes_results_and_exposes_retry(qtbot, monkeypatch, panel, metadata, code):
    analyze(qtbot, monkeypatch, panel, metadata)

    def fail(*args):
        raise AnalysisError(code)

    monkeypatch.setattr(VideoAnalyzer, "analyze", fail)
    panel.start_analysis()
    qtbot.waitUntil(lambda: panel.worker is None)
    assert panel.url_card.property("state") == "error"
    assert panel.status_label.text() == AnalysisError(code).user_message
    assert panel.selected_request is None
    assert not panel.preview.isVisible()
    assert panel.analyze_button.isEnabled()


def test_invalid_url_after_success_clears_all_selection(qtbot, monkeypatch, panel, metadata):
    analyze(qtbot, monkeypatch, panel, metadata)
    panel.url_input.setText("https://youtube.com.evil.test/watch?v=BaW_jenozKc")
    panel.start_analysis()
    assert "Geçersiz bağlantı" in panel.status_label.text()
    assert panel.url_card.property("state") == "error"
    assert panel.selected_request is None
    assert not panel.download_summary.isVisible()


@pytest.mark.parametrize("size", [(1280, 800), (1024, 700), (640, 520)])
def test_styled_window_resizes_with_long_titles_without_horizontal_overflow(
    qtbot, monkeypatch, metadata, size
):
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda *args: [])
    monkeypatch.setattr(
        VideoAnalyzer,
        "analyze",
        lambda *args: replace(metadata, title="çokuzunbaşlık" * 150, channel="Kanal" * 100),
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    panel = window.analysis_panel
    panel.url_input.setText(URL + "&extra=" + "x" * 1000)
    panel.start_analysis()
    qtbot.waitUntil(lambda: panel.worker is None)
    qtbot.waitUntil(lambda: window._worker is not None and not window._worker.isRunning())
    assert window.size().toTuple() == size
    assert window.centralWidget().horizontalScrollBar().maximum() == 0
    page = window.pages.widget(0)
    assert page.horizontalScrollBar().maximum() == 0
    assert panel.title_label.height() <= panel.title_label.fontMetrics().lineSpacing() * 3
    assert panel.title_label.toolTip() == "çokuzunbaşlık" * 150
    assert panel.thumbnail.width() * 9 == panel.thumbnail.height() * 16
    qtbot.waitUntil(lambda: page.verticalScrollBar().maximum() > 0)
    page.ensureWidgetVisible(panel.download_summary)
    qtbot.waitUntil(lambda: page.verticalScrollBar().value() > 0)
    assert not panel.download_summary.download_button.isEnabled()
    for card in panel.quality_panel.cards:
        assert card.width() <= page.viewport().width()
    window.close()


def test_navigation_placeholder_and_diagnostics_remain_functional(qtbot, monkeypatch):
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda *args: [])
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.copy_button.isEnabled)
    for index in (1, 2, 3, 0):
        window.nav_buttons[index].click()
        assert window.pages.currentIndex() == index
        assert sum(button.isChecked() for button in window.nav_buttons) == 1
        if index in (1, 2):
            back = next(
                b
                for b in window.pages.currentWidget().findChildren(QPushButton)
                if b.text() == "Ana sayfaya dön"
            )
            back.click()
            assert window.pages.currentIndex() == 0
    window.nav_buttons[3].click()
    assert window.copy_button.isVisible()
    window.copy_button.click()
    assert "NovaDownloader" in QApplication.clipboard().text()
    window.close()


def test_navigation_during_analysis_then_close_is_safe(qtbot, monkeypatch, metadata):
    entered = Event()

    def slow(self, url, cancel):
        entered.set()
        cancel.wait(3)
        raise AnalysisError(AnalysisErrorCode.CANCELLED)

    monkeypatch.setattr(VideoAnalyzer, "analyze", slow)
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda *args: [])
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    panel = window.analysis_panel
    panel.url_input.setText(URL)
    panel.start_analysis()
    qtbot.waitUntil(entered.is_set)
    window.nav_buttons[2].click()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=4000)
    assert panel.worker is None
    assert panel.selected_request is None


def test_segmented_control_arrow_keys_switch_mode(qtbot, monkeypatch, panel, metadata):
    analyze(qtbot, monkeypatch, panel, metadata)
    selector = panel.quality_panel.media_type
    selector.buttons[SelectionKind.VIDEO].setFocus()
    qtbot.keyClick(selector.buttons[SelectionKind.VIDEO], Qt.Key.Key_Right)
    assert panel.quality_panel.mode == SelectionKind.AUDIO
    qtbot.keyClick(selector.buttons[SelectionKind.AUDIO], Qt.Key.Key_Left)
    assert panel.quality_panel.mode == SelectionKind.VIDEO
    assert sum(button.isChecked() for button in selector.buttons.values()) == 1


def test_many_formats_keyboard_scroll_and_focus_are_reachable(qtbot, monkeypatch, metadata):
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda *args: [])
    video = next(stream for stream in metadata.formats if stream.height == 720)
    formats = tuple(replace(video, format_id=str(1000 + i), height=144 + i * 72) for i in range(30))
    monkeypatch.setattr(VideoAnalyzer, "analyze", lambda *args: replace(metadata, formats=formats))
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1024, 700)
    window.show()
    panel = window.analysis_panel
    panel.url_input.setText(URL)
    panel.start_analysis()
    qtbot.waitUntil(lambda: panel.worker is None)
    quality = panel.quality_panel
    assert len(quality.cards) == 30
    quality.cards[0].setFocus()
    qtbot.keyClick(quality.cards[0], Qt.Key.Key_End)
    assert quality.cards[-1].isChecked()
    assert quality.cards[-1].hasFocus()
    page = window.pages.widget(0)
    qtbot.waitUntil(lambda: page.verticalScrollBar().value() > 0)
    position = quality.cards[-1].mapTo(page.viewport(), quality.cards[-1].rect().center())
    assert page.viewport().rect().contains(position)
    assert page.horizontalScrollBar().maximum() == 0
    window.close()


def test_thumbnail_resizing_keeps_aspect_and_device_pixel_ratio(qtbot):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QColor, QImage

    from novadownloader.ui.thumbnail import ThumbnailLabel

    thumbnail = ThumbnailLabel()
    qtbot.addWidget(thumbnail)
    thumbnail.show()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image = QImage(640, 360, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    image.save(buffer, "PNG")
    assert thumbnail._show_image(bytes(data))
    for width, height in ((160, 90), (224, 126)):
        thumbnail.setFixedSize(width, height)
        qtbot.waitUntil(
            lambda width=width: thumbnail.pixmap().deviceIndependentSize().width() == width
        )
        pixmap = thumbnail.pixmap()
        assert pixmap.devicePixelRatio() == thumbnail.devicePixelRatioF()
        assert pixmap.deviceIndependentSize().height() == height
    thumbnail.load_url(None)
    thumbnail.resize(160, 90)
    assert thumbnail.text() == "Önizleme yok"
    assert thumbnail.pixmap().isNull()
