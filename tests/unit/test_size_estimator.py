from dataclasses import replace

import pytest

from novadownloader.models.format_selection import (
    SizeCertainty,
    SizeEstimate,
    SizeSource,
    format_bytes,
)
from novadownloader.models.media_format import MAX_BYTES, MediaFormat
from novadownloader.services.size_estimator import (
    combine_sizes,
    estimate_from_bitrate,
    estimate_stream,
)

MUXED = MediaFormat("22", vcodec="avc1", acodec="mp4a", tbr=1128, vbr=1000, abr=128)


def test_exact_size_has_priority_over_approximation_and_bitrate():
    size = estimate_stream(replace(MUXED, filesize=42_000_000, filesize_approx=50_000_000), 100)
    assert size == SizeEstimate(42_000_000, SizeCertainty.EXACT, SizeSource.FILESIZE)
    assert size.label == "42.0 MB"


def test_approximation_has_priority_over_bitrate():
    size = estimate_stream(replace(MUXED, filesize_approx=50_000_000), 100)
    assert size.bytes == 50_000_000 and size.certainty == SizeCertainty.ESTIMATED
    assert size.source == SizeSource.FILESIZE_APPROX
    assert size.label.startswith("Yaklaşık")


def test_muxed_total_bitrate_does_not_count_audio_twice():
    assert estimate_stream(MUXED, 100).bytes == 14_100_000
    assert estimate_stream(replace(MUXED, tbr=None), 100).bytes == 14_100_000


@pytest.mark.parametrize("fields", [{"tbr": None, "abr": None}, {"tbr": None, "vbr": None}])
def test_partial_muxed_bitrate_is_unknown(fields):
    assert estimate_stream(replace(MUXED, **fields), 100).bytes is None


def test_separate_streams_use_their_own_bitrate():
    video = MediaFormat("137", vcodec="avc1", acodec="none", vbr=1000)
    audio = MediaFormat("140", vcodec="none", acodec="aac", abr=128)
    assert estimate_stream(video, 100).bytes == 12_500_000
    assert estimate_stream(audio, 100).bytes == 1_600_000
    assert (
        combine_sizes([estimate_stream(video, 100), estimate_stream(audio, 100)]).bytes
        == 14_100_000
    )


@pytest.mark.parametrize("value", [None, 0, -1, False, "bad", float("nan"), float("inf"), {}, []])
def test_invalid_duration_and_bitrate_do_not_fabricate_sizes(value):
    assert estimate_from_bitrate(value, 128).bytes is None
    assert estimate_from_bitrate(100, value).bytes is None


@pytest.mark.parametrize("value", [0, -1, False, "bad", float("inf"), 1.5, {}, MAX_BYTES + 1])
def test_invalid_exact_size_falls_back_to_valid_approximation(value):
    result = estimate_stream(replace(MUXED, filesize=value, filesize_approx=1000), None)
    assert result.bytes == 1000 and result.certainty == SizeCertainty.ESTIMATED


def test_unknown_duration_does_not_destroy_reported_filesize():
    assert estimate_stream(replace(MUXED, filesize=1000), None).bytes == 1000
    assert estimate_stream(MUXED, None).label == "Boyut bilinmiyor"


def test_combining_exact_and_estimated_and_unknown():
    exact = SizeEstimate(100, SizeCertainty.EXACT, SizeSource.FILESIZE)
    approx = SizeEstimate(200, SizeCertainty.ESTIMATED, SizeSource.FILESIZE_APPROX)
    assert combine_sizes([exact, exact]).certainty == SizeCertainty.EXACT
    assert combine_sizes([exact, approx]).bytes == 300
    assert combine_sizes([exact, approx]).certainty == SizeCertainty.ESTIMATED
    assert combine_sizes([exact, SizeEstimate()]).bytes is None
    assert combine_sizes([]).bytes is None


def test_large_files_and_numerical_overflow():
    assert estimate_from_bitrate(7200, 80_000).bytes == 72_000_000_000
    assert estimate_stream(replace(MUXED, filesize=2**53 + 1), None).bytes == 2**53 + 1
    assert estimate_from_bitrate(1e308, 1e308).bytes is None
    assert combine_sizes([SizeEstimate(MAX_BYTES, SizeCertainty.EXACT)] * 2).bytes is None


def test_live_totals_are_unknown_even_if_extractor_reports_snapshot_size():
    assert estimate_stream(replace(MUXED, filesize=100), 100, is_live=True).bytes is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (14_500_000, "14.5 MB"),
        (327_000_000, "327 MB"),
        (1_250_000_000, "1.25 GB"),
        (4_800_000_000, "4.80 GB"),
        (1000, "1.0 KB"),
        (999, "999 B"),
        (None, "Boyut bilinmiyor"),
        (0, "Boyut bilinmiyor"),
        (-10, "Boyut bilinmiyor"),
        (float("nan"), "Boyut bilinmiyor"),
        ("bad", "Boyut bilinmiyor"),
    ],
)
def test_decimal_si_formatting(value, expected):
    assert format_bytes(value) == expected
