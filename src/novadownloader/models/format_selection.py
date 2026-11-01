from dataclasses import dataclass
from enum import StrEnum

from novadownloader.models.media_format import MediaFormat, positive_int


class SizeCertainty(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class SizeSource(StrEnum):
    FILESIZE = "filesize"
    FILESIZE_APPROX = "filesize_approx"
    BITRATE = "bitrate"
    SUM = "sum"
    UNKNOWN = "unknown"


def format_bytes(value: int | None) -> str:
    """Decimal SI units: MB=1,000,000 bytes; GB=1,000,000,000 bytes."""
    value = positive_int(value)
    if value is None:
        return "Boyut bilinmiyor"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} GB"
    if value >= 1_000_000:
        mb = value / 1_000_000
        return f"{mb:.1f} MB" if mb < 100 else f"{mb:.0f} MB"
    if value >= 1000:
        return f"{value / 1000:.1f} KB"
    return f"{value} B"


@dataclass(frozen=True, slots=True)
class SizeEstimate:
    bytes: int | None = None
    certainty: SizeCertainty = SizeCertainty.UNKNOWN
    source: SizeSource = SizeSource.UNKNOWN

    @property
    def label(self) -> str:
        label = format_bytes(self.bytes)
        return f"Yaklaşık {label}" if self.certainty == SizeCertainty.ESTIMATED else label


class SelectionKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class FormatSelection:
    kind: SelectionKind
    display_name: str
    video: MediaFormat | None
    audio: MediaFormat | None
    output_ext: str | None
    download_size: SizeEstimate
    output_size: SizeEstimate
    requires_merge: bool = False
    requires_remux: bool = False
    requires_conversion: bool = False
    target_audio_bitrate: int | None = None
    available: bool = True
    unavailable_reason: str = ""
    recommended: bool = False
    notes: tuple[str, ...] = ()

    @property
    def format_ids(self) -> tuple[str, ...]:
        return tuple(stream.format_id for stream in (self.video, self.audio) if stream is not None)

    @property
    def format_expression(self) -> str | None:
        return "+".join(self.format_ids) if self.available else None

    @property
    def ffmpeg_required(self) -> bool:
        return self.requires_merge or self.requires_remux or self.requires_conversion

    @property
    def resolution(self) -> int | None:
        return self.video.height if self.video else None

    @property
    def fps(self) -> float | None:
        return self.video.fps if self.video else None

    @property
    def codec(self) -> str | None:
        return self.video.vcodec if self.video else self.audio.acodec if self.audio else None

    @property
    def required_audio_id(self) -> str | None:
        return self.audio.format_id if self.requires_merge and self.audio else None


@dataclass(frozen=True, slots=True)
class FormatCatalog:
    video_options: tuple[FormatSelection, ...] = ()
    audio_options: tuple[FormatSelection, ...] = ()
