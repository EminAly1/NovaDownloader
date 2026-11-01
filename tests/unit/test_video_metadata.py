import pytest

from novadownloader.core.exceptions import AnalysisError
from novadownloader.models.video_metadata import VideoMetadata, safe_thumbnail_url
from novadownloader.services.youtube_url_validator import validate_youtube_url

SOURCE = validate_youtube_url("youtu.be/BaW_jenozKc")


def test_metadata_preserves_real_values_and_normalized_source():
    model = VideoMetadata.from_info(
        {
            "id": SOURCE.video_id,
            "title": "Türkçe <b>başlık</b>",
            "channel": "Kanal",
            "thumbnail": "https://i.ytimg.com/vi/BaW_jenozKc/hqdefault.jpg",
            "duration": 3661.9,
            "view_count": 123,
            "upload_date": "20260101",
            "description": "Metin",
        },
        SOURCE,
    )
    assert model.title == "Türkçe <b>başlık</b>"
    assert model.channel == "Kanal"
    assert model.readable_duration == "1:01:01"
    assert model.source_url == SOURCE.normalized_url
    assert model.view_count == 123
    assert model.description == "Metin"


@pytest.mark.parametrize(
    "duration,expected",
    [
        (None, "Süre bilinmiyor"),
        ("bad", "Süre bilinmiyor"),
        (-1, "Süre bilinmiyor"),
        (float("nan"), "Süre bilinmiyor"),
        (float("inf"), "Süre bilinmiyor"),
        (False, "Süre bilinmiyor"),
        (0, "0:00"),
        (65, "1:05"),
        ("125", "2:05"),
    ],
)
def test_missing_or_malformed_metadata_is_safe(duration, expected):
    model = VideoMetadata.from_info(
        {"duration": duration, "channel": {}, "view_count": "no"}, SOURCE
    )
    assert model.title == "Başlık bilinmiyor"
    assert model.channel == "Kanal bilinmiyor"
    assert model.video_id == SOURCE.video_id
    assert model.readable_duration == expected
    assert model.view_count is None
    assert model.thumbnail_url is None


def test_live_and_uploader_fallback_and_thumbnail_fallback():
    model = VideoMetadata.from_info(
        {
            "is_live": True,
            "uploader": "Yükleyen",
            "thumbnail": "file:///private/image",
            "thumbnails": [
                None,
                {"url": "https://i.ytimg.com/image.jpg"},
                {"url": "http://unsafe"},
            ],
        },
        SOURCE,
    )
    assert model.readable_duration == "Canlı yayın"
    assert model.channel == "Yükleyen"
    assert model.thumbnail_url == "https://i.ytimg.com/image.jpg"


@pytest.mark.parametrize(
    "info",
    [
        {"_type": "playlist"},
        {"id": "wrong_id123"},
        {"id": []},
        {"_type": {}},
    ],
)
def test_non_video_or_wrong_identity_is_rejected(info):
    with pytest.raises(AnalysisError):
        VideoMetadata.from_info(info, SOURCE)


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/a.png",
        "http://i.ytimg.com/image.jpg",
        "https://i.ytimg.com.evil.test/image",
        "https://user:password@i.ytimg.com/a",
        "https://127.0.0.1/image",
        "https://i.ytimg.com:443/a",
        None,
        [],
        "https://i.ytimg.com/ab\nc",
    ],
)
def test_untrusted_thumbnail_urls_are_not_loaded(url):
    assert safe_thumbnail_url(url) is None
