import importlib.metadata
import json
from threading import Event

import pytest

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services import video_analyzer as service
from novadownloader.services.youtube_url_validator import validate_youtube_url
from novadownloader.workers import analysis_process
from novadownloader.workers.analysis_process import extract_metadata

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"


def test_yt_dlp_is_called_without_downloading(monkeypatch):
    import yt_dlp

    class FakeYtdlp:
        def __init__(self, options):
            assert options["noplaylist"] and options["skip_download"]
            assert options["js_runtimes"] == {"deno": {"path": "/tools/deno"}}
            assert options["remote_components"] == []
            assert options["socket_timeout"] == 12
            assert options["extractor_retries"] == 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, *, download):
            assert url == URL and download is False
            return {"id": "BaW_jenozKc", "title": "Gerçek API yolu", "duration": 42}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYtdlp)
    result = extract_metadata(validate_youtube_url(URL), "/tools/deno")
    assert result.title == "Gerçek API yolu"
    assert result.duration_seconds == 42


def test_service_protocol_success(monkeypatch):
    def run(command, cancel, timeout):
        assert command[-2] == URL
        assert timeout == service.ANALYSIS_TIMEOUT
        return json.dumps({"metadata": {"id": "BaW_jenozKc", "title": "Başlık"}})

    monkeypatch.setattr(service, "_run_process", run)
    metadata = service.VideoAnalyzer(lambda: "/tools/deno").analyze(URL, Event())
    assert metadata.title == "Başlık"


@pytest.mark.parametrize(
    "response,expected",
    [
        ('{"error":"private"}', "private"),
        ('{"error":"network"}', "network"),
        ('{"error":"unknown"}', "extractor"),
        ("broken JSON", "extractor"),
        ('{"metadata":null}', "extractor"),
        ('{"metadata":{"id":[]}}', "extractor"),
    ],
)
def test_service_protocol_errors_are_friendly(monkeypatch, response, expected):
    monkeypatch.setattr(service, "_run_process", lambda *a: response)
    with pytest.raises(AnalysisError) as exc:
        service.VideoAnalyzer(lambda: "/tools/deno").analyze(URL, Event())
    assert exc.value.code.value == expected


def test_pre_cancelled_request_does_not_check_dependencies_or_start_process():
    cancel = Event()
    cancel.set()
    with pytest.raises(AnalysisError) as exc:
        service.VideoAnalyzer(lambda: pytest.fail("should not check")).analyze(URL, cancel)
    assert exc.value.code == AnalysisErrorCode.CANCELLED


def test_missing_python_dependency(monkeypatch):
    def missing(_):
        raise importlib.metadata.PackageNotFoundError()

    monkeypatch.setattr(service.importlib.metadata, "version", missing)
    with pytest.raises(AnalysisError) as exc:
        service.ensure_analysis_dependencies()
    assert exc.value.code == AnalysisErrorCode.DEPENDENCY


def test_missing_deno(monkeypatch):
    monkeypatch.setattr(service, "find_deno", lambda: None)
    with pytest.raises(AnalysisError) as exc:
        service.ensure_analysis_dependencies()
    assert exc.value.code == AnalysisErrorCode.DEPENDENCY


def test_unsupported_deno(monkeypatch):
    from novadownloader.core.dependencies import DependencyCheck, DependencyState

    monkeypatch.setattr(service, "find_deno", lambda: "/tools/deno")
    monkeypatch.setattr(
        service,
        "_command_check",
        lambda *a: DependencyCheck("Deno", DependencyState.UNSUPPORTED, "2.2.0", "Old version"),
    )
    with pytest.raises(AnalysisError) as exc:
        service.ensure_analysis_dependencies()
    assert exc.value.code == AnalysisErrorCode.DEPENDENCY


def test_child_serializes_only_metadata(monkeypatch, capsys):
    source = validate_youtube_url(URL)
    metadata = VideoMetadata.from_info({"title": "Başlık", "duration": 65}, source)
    monkeypatch.setattr(analysis_process.sys, "argv", ["analysis_process", URL, "/tools/deno"])
    monkeypatch.setattr(analysis_process, "extract_metadata", lambda *a: metadata)
    assert analysis_process.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["metadata"]["id"] == source.video_id
    assert result["metadata"]["duration"] == 65
    assert "formats" not in result["metadata"]


@pytest.mark.parametrize(
    "message,code",
    [
        ("Private video", "private"),
        ("Connection refused", "network"),
        ("Request timed out", "timeout"),
    ],
)
def test_child_failure_is_structured_and_logged(monkeypatch, capsys, message, code):
    from yt_dlp.utils import DownloadError

    logged = []

    def fail(*args):
        raise DownloadError(message)

    monkeypatch.setattr(analysis_process.sys, "argv", ["analysis_process", URL, "/tools/deno"])
    monkeypatch.setattr(analysis_process, "extract_metadata", fail)
    monkeypatch.setattr(analysis_process, "log_failure", lambda *args: logged.append(args))
    assert analysis_process.main() == 0
    assert json.loads(capsys.readouterr().out) == {"error": code}
    assert message in logged[-1][1]
