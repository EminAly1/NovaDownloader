"""A selected intent for Phase 3. Creating it never starts a download."""

from dataclasses import dataclass

from novadownloader.models.format_selection import FormatSelection
from novadownloader.models.video_metadata import VideoMetadata


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    video_id: str
    source_url: str
    title: str
    selection: FormatSelection

    @classmethod
    def from_selection(cls, metadata: VideoMetadata, selection: FormatSelection):
        streams = [stream for stream in (selection.video, selection.audio) if stream is not None]
        if (
            not selection.available
            or not streams
            or any(stream not in metadata.formats for stream in streams)
        ):
            raise ValueError("Seçim bu videonun kullanılabilir formatlarıyla eşleşmiyor.")
        return cls(metadata.video_id, metadata.source_url, metadata.title, selection)
