"""Private child entry point. Stdout is a small JSON protocol, never yt-dlp logs."""

import json
import sys
from dataclasses import asdict

from novadownloader.core.exceptions import AnalysisError, classify_analysis_error
from novadownloader.core.logging_config import log_failure
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.youtube_url_validator import YouTubeURL, validate_youtube_url


class YtdlpLogger:
    def debug(self, message: str) -> None:
        pass  # yt-dlp debug can include full request details; do not collect it.

    def warning(self, message: str) -> None:
        log_failure("yt-dlp warning", message)

    def error(self, message: str) -> None:
        log_failure("yt-dlp error", message)


def extract_metadata(source: YouTubeURL, deno_path: str) -> VideoMetadata:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        from novadownloader.core.exceptions import AnalysisErrorCode

        raise AnalysisError(AnalysisErrorCode.DEPENDENCY) from None
    options = {
        "noplaylist": True,
        "skip_download": True,
        "simulate": True,
        "quiet": True,
        "no_warnings": False,
        "socket_timeout": 12,
        "retries": 1,
        "extractor_retries": 1,
        "js_runtimes": {"deno": {"path": deno_path}},
        "remote_components": [],
        "cachedir": False,
        "logger": YtdlpLogger(),
    }
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(source.normalized_url, download=False)
    if not isinstance(info, dict):
        from novadownloader.core.exceptions import AnalysisErrorCode

        raise AnalysisError(AnalysisErrorCode.EXTRACTOR)
    return VideoMetadata.from_info(info, source)


def main() -> int:
    try:
        source = validate_youtube_url(sys.argv[1])
        metadata = extract_metadata(source, sys.argv[2])
        # Wire keys intentionally match yt-dlp's small metadata subset.
        data = asdict(metadata)
        data.update(
            id=metadata.video_id,
            duration=metadata.duration_seconds,
            thumbnail=metadata.thumbnail_url,
        )
        result = {"metadata": data}
    except Exception as error:
        failure = classify_analysis_error(error)
        log_failure(f"Analysis {failure.code}", f"{type(error).__name__}: {error}")
        result = {"error": failure.code.value}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
