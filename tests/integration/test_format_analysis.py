import json
from threading import Event

from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services import video_analyzer
from novadownloader.services.format_selector import build_catalog
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.workers import analysis_process

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"


def test_extractor_child_json_parent_catalog_roundtrip(raw_formats, monkeypatch, capsys):
    import yt_dlp

    raw_formats[0]["url"] = "https://media.example/private-token"
    raw_formats[0]["http_headers"] = {"Authorization": "private-token"}

    class FakeYtdlp:
        def __init__(self, options):
            assert options["skip_download"] and options["noplaylist"]
            assert options["check_formats"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download):
            assert url == URL and download is False
            return {
                "id": "BaW_jenozKc",
                "title": "Başlık",
                "duration": 1000,
                "formats": raw_formats,
            }

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYtdlp)
    monkeypatch.setattr(analysis_process.sys, "argv", ["analysis", URL, "/tools/deno"])
    assert analysis_process.main() == 0
    wire = capsys.readouterr().out
    assert "private-token" not in wire and "http_headers" not in wire
    assert len(json.loads(wire)["metadata"]["formats"]) == len(raw_formats)
    monkeypatch.setattr(video_analyzer, "_run_process", lambda *args: wire)
    result = video_analyzer.VideoAnalyzer(lambda: "/tools/deno").analyze(URL, Event())
    assert result.title == "Başlık" and result.duration_seconds == 1000
    catalog = build_catalog(result.formats, result.duration_seconds)
    assert len(catalog.video_options) == 5 and len(catalog.audio_options) == 2
    assert catalog.video_options[0].format_expression == "313+251"
    assert catalog.video_options[1].download_size.bytes == 5_016_000_000


def test_empty_formats_preserve_metadata_success():
    model = VideoMetadata.from_info({"title": "Başlık", "formats": None}, validate_youtube_url(URL))
    assert model.title == "Başlık" and model.formats == ()
    assert build_catalog(model.formats, model.duration_seconds).video_options == ()


def test_qt_metadata_panel_retains_formats_without_new_quality_screen(
    qtbot, monkeypatch, raw_formats
):
    from novadownloader.ui.analysis_panel import AnalysisPanel

    model = VideoMetadata.from_info(
        {"title": "Kaynak", "duration": 1000, "formats": raw_formats}, validate_youtube_url(URL)
    )
    monkeypatch.setattr(video_analyzer.VideoAnalyzer, "analyze", lambda *args: model)
    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.url_input.setText(URL)
    panel.start_analysis()
    qtbot.waitUntil(lambda: panel.worker is None)
    assert panel.title_label.text() == "Kaynak"
    assert panel.metadata.formats == model.formats
    assert len(build_catalog(panel.metadata.formats, 1000).video_options) == 5
