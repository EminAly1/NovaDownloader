"""Sanitized yt-dlp format data. Media URLs and authentication never cross the UI boundary."""

import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

MAX_BYTES = 2**63 - 1
FORMAT_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}\Z")
SPECIAL_SELECTOR = re.compile(r"(?:best|worst|b|w)(?:video|audio|v|a)?(?:\.[1-9]\d*)?\Z")
RESERVED_IDS = {
    "all",
    "mergeall",
    "best",
    "worst",
    "bestvideo",
    "bestaudio",
    "worstvideo",
    "worstaudio",
    "b",
    "w",
    "bv",
    "ba",
    "wv",
    "wa",
    "mp4",
    "webm",
    "mkv",
    "mp3",
    "m4a",
    "ogg",
    "flv",
    "3gp",
    "aac",
    "flac",
    "opus",
    "wav",
    "mov",
    "avi",
    "m4v",
    "mka",
    "ogv",
    "ts",
}


def positive_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def positive_int(value: Any, maximum: int = MAX_BYTES) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = Decimal(str(value))
        if number.is_finite() and 0 < number <= maximum and number == number.to_integral_value():
            return int(number)
    except (InvalidOperation, ValueError):
        pass
    return None


def _text(value: Any) -> str | None:
    return value.strip()[:200] if isinstance(value, str) and value.strip() else None


class StreamKind(StrEnum):
    MUXED = "muxed"
    VIDEO = "video"
    AUDIO = "audio"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MediaFormat:
    format_id: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    ext: str | None = None
    vcodec: str | None = None
    acodec: str | None = None
    tbr: float | None = None
    vbr: float | None = None
    abr: float | None = None
    filesize: int | None = None
    filesize_approx: int | None = None
    protocol: str | None = None
    language: str | None = None
    language_preference: float = 0
    format_note: str | None = None
    dynamic_range: str | None = None
    audio_channels: int | None = None
    asr: int | None = None

    @property
    def kind(self) -> StreamKind:
        video = self.vcodec is not None and self.vcodec != "none"
        audio = self.acodec is not None and self.acodec != "none"
        if video and audio:
            return StreamKind.MUXED
        if video and self.acodec == "none":
            return StreamKind.VIDEO
        if audio and self.vcodec == "none":
            return StreamKind.AUDIO
        return StreamKind.UNKNOWN

    @classmethod
    def from_info(cls, info: Any) -> "MediaFormat | None":
        if not isinstance(info, dict) or info.get("has_drm") not in (None, False):
            return None
        identifier = info.get("format_id")
        if not isinstance(identifier, str) or not FORMAT_ID.fullmatch(identifier):
            return None
        if identifier in RESERVED_IDS or SPECIAL_SELECTOR.fullmatch(identifier):
            return None
        values = {key: positive_number(info.get(key)) for key in ("fps", "tbr", "vbr", "abr")}
        values.update(
            {
                key: positive_int(info.get(key))
                for key in (
                    "width",
                    "height",
                    "filesize",
                    "filesize_approx",
                    "audio_channels",
                    "asr",
                )
            }
        )
        values.update(
            {
                key: _text(info.get(key))
                for key in (
                    "ext",
                    "vcodec",
                    "acodec",
                    "protocol",
                    "language",
                    "format_note",
                    "dynamic_range",
                )
            }
        )
        for key in ("ext", "vcodec", "acodec", "protocol"):
            if values[key]:
                values[key] = values[key].lower()
        try:
            preference = float(info.get("language_preference", 0))
            values["language_preference"] = preference if math.isfinite(preference) else 0
        except (TypeError, ValueError, OverflowError):
            values["language_preference"] = 0
        result = cls(format_id=identifier, **values)
        if (
            result.kind == StreamKind.UNKNOWN
            or result.ext in {"mhtml", "jpg", "png"}
            or result.vcodec == "images"
            or result.protocol == "mhtml"
        ):
            return None
        return result


def parse_formats(values: Any) -> tuple[MediaFormat, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    parsed: dict[str, MediaFormat] = {}
    conflicts: set[str] = set()
    for value in values:
        item = MediaFormat.from_info(value)
        if item is None:
            continue
        if item.format_id in parsed and parsed[item.format_id] != item:
            conflicts.add(item.format_id)
        else:
            parsed[item.format_id] = item
    # A format selector must identify one stream unambiguously.
    return tuple(item for key, item in sorted(parsed.items()) if key not in conflicts)
