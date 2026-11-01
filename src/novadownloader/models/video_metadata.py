import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.models.media_format import MediaFormat, parse_formats
from novadownloader.services.youtube_url_validator import YouTubeURL


def _text(value: Any, fallback: str = "") -> str:
    return value.strip()[:2000] if isinstance(value, str) and value.strip() else fallback


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def safe_thumbnail_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 4096 or any(c.isspace() for c in value):
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (
            parts.scheme == "https"
            and parts.username is None
            and parts.password is None
            and parts.port is None
            and (host.endswith(".ytimg.com") or host in {"ytimg.com", "img.youtube.com"})
        ):
            return value
    except ValueError:
        pass
    return None


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    video_id: str
    title: str
    channel: str
    thumbnail_url: str | None
    duration_seconds: float | None
    source_url: str
    upload_date: str = ""
    view_count: int | None = None
    is_live: bool = False
    description: str = ""
    formats: tuple[MediaFormat, ...] = ()

    @property
    def readable_duration(self) -> str:
        if self.is_live:
            return "Canlı yayın"
        if self.duration_seconds is None:
            return "Süre bilinmiyor"
        seconds = int(self.duration_seconds)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"

    @classmethod
    def from_info(cls, info: dict[str, Any], source: YouTubeURL) -> "VideoMetadata":
        if info.get("_type", "video") not in ("video", None):
            raise AnalysisError(AnalysisErrorCode.EXTRACTOR)
        if info.get("id") not in (None, source.video_id):
            raise AnalysisError(AnalysisErrorCode.EXTRACTOR)
        thumbnail = safe_thumbnail_url(info.get("thumbnail"))
        if thumbnail is None and isinstance(info.get("thumbnails"), list):
            thumbnail = next(
                (
                    url
                    for item in reversed(info["thumbnails"])
                    if isinstance(item, dict) and (url := safe_thumbnail_url(item.get("url")))
                ),
                None,
            )
        views = _number(info.get("view_count"))
        return cls(
            video_id=source.video_id,
            title=_text(info.get("title"), "Başlık bilinmiyor"),
            channel=_text(info.get("channel")) or _text(info.get("uploader"), "Kanal bilinmiyor"),
            thumbnail_url=thumbnail,
            duration_seconds=_number(info.get("duration")),
            source_url=source.normalized_url,
            upload_date=_text(info.get("upload_date")),
            view_count=int(views) if views is not None else None,
            is_live=info.get("is_live") is True,
            description=_text(info.get("description")),
            formats=parse_formats(info.get("formats")),
        )
