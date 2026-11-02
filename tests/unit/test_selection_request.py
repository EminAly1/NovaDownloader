import json
from dataclasses import asdict, replace

import pytest

from novadownloader.models.download_request import DownloadRequest
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.selection_service import selection_catalog
from novadownloader.services.youtube_url_validator import validate_youtube_url

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"


def metadata(formats):
    return VideoMetadata.from_info(
        {"formats": formats, "duration": 1000}, validate_youtube_url(URL)
    )


def test_selection_catalog_uses_existing_real_sources(raw_formats):
    model = metadata(raw_formats)
    catalog = selection_catalog(model)
    assert len(catalog.video_options) == 5
    assert len(catalog.audio_options) == 3
    mp3 = catalog.audio_options[-1]
    assert mp3.requires_conversion and mp3.target_audio_bitrate == 192
    assert mp3.audio == catalog.audio_options[0].audio
    assert mp3.audio.abr == 160
    assert mp3.output_size.bytes == 24_000_000
    assert mp3.download_size.bytes == 20_000_000


@pytest.mark.parametrize(
    "formats", [[], [{"format_id": "x", "vcodec": "none", "acodec": "unrecognized"}]]
)
def test_no_fabricated_mp3_without_supported_source(formats):
    assert not any(
        choice.requires_conversion for choice in selection_catalog(metadata(formats)).audio_options
    )


def test_request_serializes_exact_source_and_choice_without_starting_io(raw_formats):
    model = metadata(raw_formats)
    choice = selection_catalog(model).video_options[0]
    request = DownloadRequest.from_selection(model, choice)
    serialized = json.loads(json.dumps(asdict(request), allow_nan=False))
    assert serialized["source_url"] == URL
    assert serialized["video_id"] == model.video_id
    assert request.selection.format_expression == "313+251"
    assert serialized["selection"]["requires_merge"] is True


@pytest.mark.parametrize("reason", ["unavailable", "foreign", "empty"])
def test_invalid_request_is_rejected(raw_formats, reason):
    model = metadata(raw_formats)
    choice = selection_catalog(model).video_options[0]
    if reason == "unavailable":
        choice = replace(choice, available=False)
    elif reason == "foreign":
        choice = replace(choice, video=replace(choice.video, format_id="not-this-video"))
    else:
        choice = replace(choice, video=None, audio=None)
    with pytest.raises(ValueError):
        DownloadRequest.from_selection(model, choice)
