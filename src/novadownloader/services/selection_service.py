"""Compose existing format services for the selection screen, without network work."""

from dataclasses import replace

from novadownloader.models.format_selection import FormatCatalog
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.format_selector import build_catalog, make_mp3_option


def selection_catalog(metadata: VideoMetadata) -> FormatCatalog:
    catalog = build_catalog(metadata.formats, metadata.duration_seconds, is_live=metadata.is_live)
    # One clearly labelled conversion from the first supported original source.
    # Original choices remain intact; 192 kbps is the target, never a source-quality claim.
    for option in catalog.audio_options:
        try:
            mp3 = make_mp3_option(
                option.audio, metadata.duration_seconds, 192, is_live=metadata.is_live
            )
        except ValueError:
            continue
        return replace(catalog, audio_options=(*catalog.audio_options, mp3))
    return catalog
