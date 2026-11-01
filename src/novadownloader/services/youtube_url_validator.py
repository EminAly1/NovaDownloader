import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode

VIDEO_ID = re.compile(r"[a-zA-Z0-9_-]{11}\Z")
LONG_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


@dataclass(frozen=True, slots=True)
class YouTubeURL:
    video_id: str
    normalized_url: str


def validate_youtube_url(value: str) -> YouTubeURL:
    def invalid() -> AnalysisError:
        return AnalysisError(AnalysisErrorCode.INVALID_URL)

    if not isinstance(value, str) or len(value) > 4096:
        raise invalid()
    value = value.strip()
    if (
        not value
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
        or "\\" in value
    ):
        raise invalid()
    if "://" not in value:
        value = "https://" + value
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
            or parts.hostname not in LONG_HOSTS | SHORT_HOSTS
        ):
            raise invalid()
        query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=50)
    except (ValueError, UnicodeError):
        raise invalid() from None
    video_id = ""
    if parts.hostname in SHORT_HOSTS:
        video_id = parts.path.removeprefix("/").removesuffix("/")
    elif parts.path == "/watch":
        candidates = query.get("v", [])
        if len(candidates) == 1:
            video_id = candidates[0]
    elif parts.path.startswith("/shorts/"):
        video_id = parts.path.removeprefix("/shorts/").removesuffix("/")
    if not VIDEO_ID.fullmatch(video_id):
        raise invalid()
    return YouTubeURL(video_id, f"https://www.youtube.com/watch?v={video_id}")
