import json
from dataclasses import asdict, replace

import pytest

from novadownloader.models.format_selection import SizeCertainty
from novadownloader.models.media_format import MediaFormat, parse_formats
from novadownloader.services.format_selector import build_catalog, make_mp3_option


def video(identifier="137", **fields):
    return MediaFormat.from_info(
        dict(
            {
                "format_id": identifier,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "ext": "mp4",
                "height": 1080,
                "width": 1920,
                "fps": 30,
                "tbr": 1000,
                "protocol": "https",
            },
            **fields,
        )
    )


def audio(identifier="140", **fields):
    return MediaFormat.from_info(
        dict(
            {
                "format_id": identifier,
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "ext": "m4a",
                "abr": 128,
                "tbr": 128,
                "protocol": "https",
            },
            **fields,
        )
    )


def test_real_resolutions_fps_and_codec_variants_are_sorted(media_formats):
    catalog = build_catalog(media_formats, 1000)
    assert [item.resolution for item in catalog.video_options] == [2160, 1080, 1080, 1080, 720]
    assert catalog.video_options[1].fps == 60
    assert len({item.codec for item in catalog.video_options if item.resolution == 1080}) == 3
    assert catalog.video_options[0].display_name.startswith("4K UHD — 2160p — 60 FPS")
    assert "Yaklaşık" in catalog.video_options[0].display_name
    assert len(catalog.audio_options) == 2
    assert [item.video.format_id for item in catalog.video_options if item.recommended] == ["299"]
    assert sum(item.recommended for item in catalog.audio_options) == 1


@pytest.mark.parametrize(
    "vcodec,vext,acodec,aext,container",
    [
        ("avc1.640028", "mp4", "mp4a.40.2", "m4a", "mp4"),
        ("vp9", "webm", "opus", "webm", "webm"),
        ("avc1.640028", "mp4", "opus", "webm", "mkv"),
        ("vp9", "webm", "mp4a.40.2", "m4a", "mkv"),
        ("av01.0.08M.08", "mp4", "mp4a.40.2", "m4a", "mp4"),
        ("av01.0.08M.08", "webm", "opus", "webm", "webm"),
        ("hev1.1.6", "mp4", "mp4a.40.2", "m4a", "mp4"),
        ("vp8", "webm", "vorbis", "ogg", "webm"),
    ],
)
def test_container_compatibility_without_transcoding(vcodec, vext, acodec, aext, container):
    catalog = build_catalog((video(vcodec=vcodec, ext=vext), audio(acodec=acodec, ext=aext)), 100)
    option = catalog.video_options[0]
    assert option.output_ext == container and option.available
    assert option.requires_merge and option.ffmpeg_required and not option.requires_conversion
    assert option.format_expression == "137+140" and option.required_audio_id == "140"


def test_native_audio_container_preferred_over_incompatible_higher_bitrate():
    catalog = build_catalog(
        (video(), audio(), audio("251", acodec="opus", ext="webm", abr=200)), 100
    )
    assert catalog.video_options[0].required_audio_id == "140"


def test_default_language_preference_survives_pairing():
    preferred = audio("251", acodec="opus", ext="webm", language="tr", language_preference=10)
    option = build_catalog((video(), audio(), preferred), 100).video_options[0]
    assert option.audio.language == "tr" and option.output_ext == "mkv"


def test_muxed_stream_is_direct_and_retains_own_size():
    option = build_catalog(
        (video("22", acodec="aac", filesize=400000000), audio()), 100
    ).video_options[0]
    assert option.format_expression == "22" and option.audio is None
    assert not option.ffmpeg_required and not option.requires_merge
    assert option.output_size == option.download_size
    assert option.output_size.certainty == SizeCertainty.EXACT


@pytest.mark.parametrize("streams", [(video(),), (video(), audio(acodec="unrecognized"))])
def test_no_compatible_audio_never_silently_recommends_silent_video(streams):
    option = build_catalog(streams, 100).video_options[0]
    assert not option.available and not option.recommended
    assert option.format_expression is None and option.unavailable_reason
    assert option.video.format_id == "137"


def test_empty_or_audio_only_catalog_never_fabricates_qualities():
    assert build_catalog((), None).video_options == ()
    assert build_catalog((audio(),), 100).video_options == ()
    assert len(build_catalog((audio(),), 100).audio_options) == 1


def test_unusual_resolution_and_missing_fps_are_preserved():
    option = build_catalog((video(height=864, fps=None), audio()), 100).video_options[0]
    assert "864p" in option.display_name and "FPS bilinmiyor" in option.display_name
    assert option.recommended


def test_duplicate_transport_formats_collapsed_but_variants_kept():
    direct = video("137", filesize=1000)
    duplicate = replace(direct, format_id="hls137", protocol="m3u8_native", filesize=None)
    fps = replace(direct, format_id="299", fps=60)
    codec = replace(direct, format_id="399", vcodec="av01.0.08M.08")
    options = build_catalog((direct, duplicate, fps, codec, audio()), 100).video_options
    assert {item.video.format_id for item in options} == {"137", "299", "399"}


def test_hdr_and_audio_language_variants_are_not_lost():
    hdr = video("337", dynamic_range="HLG")
    tr = audio("140-tr", language="tr")
    en = audio("140-en", language="en")
    result = build_catalog((video(), hdr, tr, en), 100)
    assert len(result.video_options) == 2 and len(result.audio_options) == 2


def test_source_and_merged_output_sizes_are_distinct():
    option = build_catalog(
        (video(filesize=5_000_000_000), audio(filesize=16_000_000)), None
    ).video_options[0]
    assert option.download_size.bytes == 5_016_000_000
    assert option.download_size.certainty == SizeCertainty.EXACT
    assert option.output_size.bytes is None
    assert any("nihai" in note for note in option.notes)


def test_missing_audio_size_makes_combined_size_unknown():
    option = build_catalog((video(filesize=1000), audio(abr=None, tbr=None)), None).video_options[0]
    assert option.download_size.label == "Boyut bilinmiyor"


def test_audio_opus_remux_and_mp3_conversion_are_only_recipes():
    source = audio("251", acodec="opus", ext="webm", abr=128, filesize=1_000_000)
    opus = build_catalog((source,), 1000).audio_options[0]
    assert opus.output_ext == "opus" and opus.requires_remux and not opus.requires_conversion
    assert opus.output_size.bytes is None
    mp3 = make_mp3_option(source, 1000, 320)
    assert mp3.audio.acodec == "opus" and mp3.audio.abr == 128
    assert mp3.output_ext == "mp3" and mp3.requires_conversion and mp3.ffmpeg_required
    assert mp3.download_size.bytes == 1_000_000 and mp3.output_size.bytes == 40_000_000
    assert mp3.output_size.certainty == SizeCertainty.ESTIMATED
    assert mp3.format_expression == "251" and any("artırmaz" in note for note in mp3.notes)


@pytest.mark.parametrize("bitrate", [0, 64, 321, True, "192"])
def test_invalid_mp3_targets_rejected(bitrate):
    with pytest.raises(ValueError):
        make_mp3_option(audio(), 100, bitrate)


def test_mp3_requires_audio_only_and_live_size_is_unknown():
    with pytest.raises(ValueError):
        make_mp3_option(video(), 100, 192)
    assert make_mp3_option(audio(), 100, 192, is_live=True).output_size.bytes is None


def test_catalog_serialization_contains_recipe_and_source_details(media_formats):
    original = build_catalog(media_formats, 1000)
    payload = json.loads(json.dumps(asdict(original), allow_nan=False))
    for option, wire in zip(original.video_options, payload["video_options"], strict=True):
        assert wire["video"]["format_id"] == option.video.format_id
        assert wire["requires_merge"] == option.requires_merge
        assert wire["download_size"]["certainty"] == option.download_size.certainty


def test_selector_is_deterministic_under_input_permutation(media_formats):
    assert build_catalog(media_formats, 1000) == build_catalog(tuple(reversed(media_formats)), 1000)


def test_actual_ytdlp_selector_resolves_exact_ids(raw_formats):
    from yt_dlp import YoutubeDL

    option = next(
        item
        for item in build_catalog(parse_formats(raw_formats), 100).video_options
        if item.video.format_id == "137"
    )
    with YoutubeDL({"quiet": True, "cachedir": False}) as ydl:
        selector = ydl.build_format_selector(option.format_expression)
        chosen = list(
            selector(
                {"formats": raw_formats, "has_merged_format": True, "incomplete_formats": False}
            )
        )
    assert [stream["format_id"] for stream in chosen[0]["requested_formats"]] == ["137", "140"]


def test_hls_muxed_and_audio_sources_do_not_claim_exact_output_size():
    muxed = video("22", acodec="aac", filesize=1000, protocol="m3u8_native")
    hls_audio = audio(protocol="m3u8", filesize=100)
    result = build_catalog((muxed, hls_audio), 100)
    for option in (result.video_options[0], result.audio_options[0]):
        assert option.requires_remux and option.ffmpeg_required
        assert option.download_size.certainty == SizeCertainty.EXACT
        assert option.output_size.certainty == SizeCertainty.UNKNOWN


def test_recommendation_uses_smallest_available_resolution_above_1080():
    result = build_catalog((video("313", height=2160), video("271", height=1440), audio()), 100)
    assert [option.resolution for option in result.video_options if option.recommended] == [1440]


def test_unknown_codec_cannot_be_promised_as_mp3_conversion():
    with pytest.raises(ValueError):
        make_mp3_option(audio(acodec="unknown"), 100)
