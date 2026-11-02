"""Capture real Qt widgets using labelled deterministic fixtures, never live YouTube data.

Run from a development checkout with QT_QPA_PLATFORM=offscreen. This script is
not part of the production entry point; VideoAnalyzer is mocked only here.
"""

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from novadownloader.models.format_selection import SelectionKind
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.video_analyzer import VideoAnalyzer
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.ui.main_window import MainWindow
from novadownloader.ui.theme import stylesheet


def wait_until(predicate):
    deadline = time.monotonic() + 15
    while not predicate():
        if time.monotonic() > deadline:
            raise RuntimeError("Qt capture timed out")
        QTest.qWait(10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/novadownloader-ui"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()
    panel = window.analysis_panel
    source = validate_youtube_url("https://www.youtube.com/watch?v=BaW_jenozKc")
    formats = json.loads(
        (Path(__file__).resolve().parents[1] / "tests/fixtures/formats.json").read_text()
    )
    metadata = VideoMetadata.from_info(
        {
            "title": "Tasarımın ritmi: fikirden ilk prototipe",
            "channel": "Nova Studio · Test verisi",
            "duration": 1000,
            "formats": formats,
        },
        source,
    )

    def grab(name):
        QTest.qWait(100)  # Settle layouts and pending paints, never a fabricated loading delay.
        if not window.grab().save(str(args.output / name)):
            raise RuntimeError(f"Could not save {name}")
        print(name, window.size().toTuple(), "DPR", window.devicePixelRatioF())

    def analyze(model):
        with patch.object(VideoAnalyzer, "analyze", return_value=model):
            panel.url_input.setText(source.normalized_url)
            panel.start_analysis()
            wait_until(lambda: panel.worker is None)
        QTest.qWait(50)

    try:
        wait_until(lambda: window._worker is not None and not window._worker.isRunning())
        grab("01-empty.png")
        entered, release = Event(), Event()

        def slow(self, url, cancel):
            entered.set()
            release.wait(3)
            return metadata

        with patch.object(VideoAnalyzer, "analyze", slow):
            panel.url_input.setText(source.normalized_url)
            panel.start_analysis()
            try:
                wait_until(entered.is_set)
                grab("02-loading.png")
            finally:
                release.set()
            wait_until(lambda: panel.worker is None)
        grab("03-video.png")
        page = window.pages.widget(0)
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        grab("04-video-summary.png")
        panel.quality_panel.set_mode(SelectionKind.AUDIO)
        panel.quality_panel.cards[-1].click()
        QTest.qWait(50)
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        grab("05-audio-mp3.png")
        window.resize(1024, 700)
        page.verticalScrollBar().setValue(0)
        grab("06-1024.png")
        analyze(replace(metadata, title="Uzun başlık ve Türkçe karakterler — " * 40))
        window.resize(640, 520)
        page.verticalScrollBar().setValue(0)
        grab("07-640-long-title.png")
        window.resize(1280, 800)
        panel.url_input.setText("https://youtube.com.evil.test/watch?v=BaW_jenozKc")
        QTest.keyClick(panel.url_input, Qt.Key.Key_Return)
        page.verticalScrollBar().setValue(0)
        grab("08-error.png")
        window.nav_buttons[1].click()
        grab("09-downloads-placeholder.png")
        window.nav_buttons[3].click()
        grab("10-settings.png")
        window.nav_buttons[0].click()
        analyze(replace(metadata, formats=()))
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        grab("11-no-formats.png")
    finally:
        window.close()
        wait_until(lambda: not window.isVisible())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
