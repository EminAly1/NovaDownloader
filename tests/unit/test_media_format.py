from dataclasses import asdict

import pytest

from novadownloader.models.media_format import MAX_BYTES, MediaFormat, StreamKind, parse_formats

BASE = {"format_id": "137", "vcodec": "avc1.640028", "acodec": "none", "height": 1080}


def test_normalization_preserves_all_required_fields():
    raw = dict(
        BASE,
        width="1920",
        height="1080",
        fps="59.94",
        ext="MP4",
        tbr="1000.5",
        vbr=900,
        abr=None,
        filesize="9007199254740993",
        filesize_approx=9999,
        protocol="HTTPS",
    )
    item = MediaFormat.from_info(raw)
    assert item.format_id == "137" and item.kind == StreamKind.VIDEO
    assert item.width == 1920 and item.height == 1080 and item.fps == 59.94
    assert item.ext == "mp4" and item.tbr == 1000.5 and item.vbr == 900
    assert item.filesize == 9007199254740993 and item.filesize_approx == 9999
    assert item.protocol == "https" and item.abr is None


@pytest.mark.parametrize(
    "value", [None, False, -1, 0, "invalid", float("nan"), float("inf"), [], {}]
)
def test_invalid_optional_numbers_become_unknown(value):
    item = MediaFormat.from_info(dict(BASE, fps=value, width=value, tbr=value, filesize=value))
    assert item is not None
    assert item.fps is None and item.width is None and item.tbr is None and item.filesize is None


@pytest.mark.parametrize(
    "identifier", [None, 137, "", "best", "mp4", "137+140", "137/22", "x[y]", "a,b", " a", "a\n"]
)
def test_unsafe_or_ambiguous_selector_ids_are_rejected(identifier):
    assert MediaFormat.from_info(dict(BASE, format_id=identifier)) is None


def test_safe_composite_identifier_is_preserved():
    assert MediaFormat.from_info(dict(BASE, format_id="137-drc.1")).format_id == "137-drc.1"


@pytest.mark.parametrize("identifier", ["best.2", "bestaudio.3", "bv.4", "wvideo.2", "3gp"])
def test_selector_aliases_cannot_select_an_unrelated_stream(identifier):
    assert MediaFormat.from_info(dict(BASE, format_id=identifier)) is None


@pytest.mark.parametrize(
    "fields",
    [
        {"has_drm": True},
        {"vcodec": "none", "acodec": "none"},
        {"vcodec": None},
        {"acodec": None},
        {"ext": "mhtml"},
        {"vcodec": "images"},
        {"protocol": "mhtml"},
    ],
)
def test_drm_storyboards_and_ambiguous_streams_are_omitted(fields):
    assert MediaFormat.from_info(dict(BASE, **fields)) is None


@pytest.mark.parametrize("raw", [None, {}, "formats", [None, {}, "x"]])
def test_malformed_format_lists_are_safe(raw):
    assert parse_formats(raw) == ()


def test_duplicates_and_conflicting_ids():
    assert len(parse_formats([BASE, BASE])) == 1
    assert parse_formats([BASE, dict(BASE, height=720)]) == ()


def test_no_media_url_or_credentials_are_retained():
    item = MediaFormat.from_info(
        dict(BASE, url="https://secret", http_headers={"Authorization": "secret"})
    )
    assert "secret" not in str(asdict(item))
    assert MediaFormat.from_info(dict(BASE, filesize=MAX_BYTES + 1)).filesize is None
