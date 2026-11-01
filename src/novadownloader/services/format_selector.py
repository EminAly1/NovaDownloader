"""Deterministic stream pairing and UI-ready selection data; no downloader or Qt dependency."""

from dataclasses import replace

from novadownloader.models.format_selection import (
    FormatCatalog,
    FormatSelection,
    SelectionKind,
    SizeEstimate,
)
from novadownloader.models.media_format import MediaFormat, StreamKind
from novadownloader.services.size_estimator import (
    combine_sizes,
    estimate_from_bitrate,
    estimate_stream,
)

MP4_VIDEO = {"h264", "hevc", "av1"}
WEBM_VIDEO = {"vp8", "vp9", "av1"}
MKV_AUDIO = {"aac", "opus", "vorbis", "mp3", "flac", "alac", "pcm"}
QUALITY_NAMES = {2160: "4K UHD", 1440: "2K QHD", 1080: "Full HD", 720: "HD", 480: "SD"}


def codec_family(codec: str | None) -> str:
    value = (codec or "").lower()
    for prefixes, family in (
        (("avc1", "avc3", "h264"), "h264"),
        (("hev1", "hvc1", "hevc", "h265"), "hevc"),
        (("av01", "av1"), "av1"),
        (("vp09", "vp9"), "vp9"),
        (("vp08", "vp8"), "vp8"),
        (("mp4a", "aac"), "aac"),
        (("opus",), "opus"),
        (("vorbis",), "vorbis"),
        (("mp3",), "mp3"),
        (("flac",), "flac"),
        (("alac",), "alac"),
        (("pcm",), "pcm"),
    ):
        if value.startswith(prefixes):
            return family
    return value or "unknown"


def _container(video: MediaFormat, audio: MediaFormat) -> str | None:
    vc, ac = codec_family(video.vcodec), codec_family(audio.acodec)
    if video.ext == "mp4" and vc in MP4_VIDEO and ac == "aac":
        return "mp4"
    if video.ext == "webm" and vc in WEBM_VIDEO and ac in {"opus", "vorbis"}:
        return "webm"
    if vc in MP4_VIDEO | WEBM_VIDEO and ac in MKV_AUDIO:
        return "mkv"
    return None


def _source_priority(stream: MediaFormat) -> tuple:
    # Equivalent HTTP/HLS representations: prefer direct transport and known byte size.
    return (
        stream.protocol not in {"https", "http"},
        stream.filesize is None,
        stream.filesize_approx is None,
        stream.format_id,
    )


def _deduplicate(formats: tuple[MediaFormat, ...]) -> tuple[MediaFormat, ...]:
    grouped: dict[tuple, MediaFormat] = {}
    for stream in formats:
        key = tuple(
            getattr(stream, name)
            for name in (
                "kind",
                "width",
                "height",
                "fps",
                "ext",
                "vcodec",
                "acodec",
                "tbr",
                "vbr",
                "abr",
                "language",
                "language_preference",
                "format_note",
                "dynamic_range",
                "audio_channels",
                "asr",
            )
        )
        # Missing quality evidence is not sufficient to call two distinct IDs duplicates.
        if (stream.kind != StreamKind.AUDIO and stream.height is None) or not any(
            rate is not None for rate in (stream.tbr, stream.vbr, stream.abr)
        ):
            key += (stream.format_id,)
        current = grouped.get(key)
        if current is None or _source_priority(stream) < _source_priority(current):
            grouped[key] = stream
    return tuple(sorted(grouped.values(), key=lambda item: item.format_id))


def _audio_priority(stream: MediaFormat) -> tuple:
    return (-stream.language_preference, -(stream.abr or stream.tbr or 0), stream.format_id)


def _pair_audio(video: MediaFormat, audio: tuple[MediaFormat, ...]) -> MediaFormat | None:
    compatible = [item for item in audio if _container(video, item) is not None]
    return min(
        compatible,
        key=lambda item: (
            -item.language_preference,
            _container(video, item) != video.ext,
            -(item.abr or item.tbr or 0),
            item.format_id,
        ),
        default=None,
    )


def _video_option(
    video: MediaFormat,
    audio: tuple[MediaFormat, ...],
    duration: float | None,
    is_live: bool,
) -> FormatSelection:
    paired = _pair_audio(video, audio) if video.kind == StreamKind.VIDEO else None
    missing_audio = video.kind == StreamKind.VIDEO and paired is None
    merging = paired is not None
    remux = video.kind == StreamKind.MUXED and (video.protocol or "").startswith("m3u8")
    size = estimate_stream(video, duration, is_live=is_live)
    output_ext = video.ext
    if paired:
        output_ext = _container(video, paired)
        size = combine_sizes((size, estimate_stream(paired, duration, is_live=is_live)))
    resolution = f"{video.height}p" if video.height else "Çözünürlük bilinmiyor"
    quality = QUALITY_NAMES.get(video.height)
    fps = f"{video.fps:g} FPS" if video.fps is not None else "FPS bilinmiyor"
    parts = [part for part in (quality, resolution, fps, size.label) if part]
    parts.append(f"{codec_family(video.vcodec).upper()} / {(output_ext or 'bilinmiyor').upper()}")
    notes = ["Boyut, indirilecek kaynak akışlarını ifade eder."]
    if merging:
        notes.append("FFmpeg ile birleştirme gerekir; nihai dosya boyutu değişebilir.")
    if remux:
        notes.append(
            "HLS kaynağı için FFmpeg kapsayıcı işlemi gerekebilir; nihai boyut bilinmiyor."
        )
    if missing_audio:
        notes.append("Uyumlu bir ses akışı bulunamadı; bu seçenek kullanılamıyor.")
    return FormatSelection(
        SelectionKind.VIDEO,
        " — ".join(parts),
        video,
        paired,
        output_ext,
        size,
        SizeEstimate() if merging or remux or missing_audio else size,
        requires_merge=merging,
        requires_remux=remux,
        available=not missing_audio,
        unavailable_reason="Uyumlu ses akışı bulunamadı." if missing_audio else "",
        notes=tuple(notes),
    )


def _audio_option(audio: MediaFormat, duration: float | None, is_live: bool) -> FormatSelection:
    codec = codec_family(audio.acodec)
    ext = (
        "opus" if codec == "opus" else "m4a" if codec == "aac" and audio.ext == "mp4" else audio.ext
    )
    remux = ext != audio.ext or (audio.protocol or "").startswith("m3u8")
    size = estimate_stream(audio, duration, is_live=is_live)
    bitrate = audio.abr or audio.tbr
    rate = f"{bitrate:g} kbps" if bitrate else "Bit hızı bilinmiyor"
    return FormatSelection(
        SelectionKind.AUDIO,
        f"{(ext or 'bilinmiyor').upper()} · {codec.upper()} · {rate} · {size.label}",
        None,
        audio,
        ext,
        size,
        SizeEstimate() if remux else size,
        requires_remux=remux,
        notes=("Kaynak ses kalitesi korunur.",)
        + (("FFmpeg ile kapsayıcı değişir; nihai boyut değişebilir.",) if remux else ()),
    )


def build_catalog(
    formats: tuple[MediaFormat, ...],
    duration: float | None,
    *,
    is_live: bool = False,
) -> FormatCatalog:
    streams = _deduplicate(formats)
    audio = tuple(item for item in streams if item.kind == StreamKind.AUDIO)
    videos = [
        _video_option(item, audio, duration, is_live)
        for item in streams
        if item.kind in {StreamKind.VIDEO, StreamKind.MUXED}
    ]
    videos.sort(
        key=lambda item: (
            -(item.resolution or 0),
            -(item.fps or 0),
            item.codec or "",
            item.format_ids,
        )
    )
    usable = [item for item in videos if item.available and item.resolution is not None]
    if usable:
        everyday = [item for item in usable if item.resolution <= 1080]
        target = (
            max(item.resolution for item in everyday)
            if everyday
            else min(item.resolution for item in usable)
        )
        recommendation = min(
            (item for item in usable if item.resolution == target),
            key=lambda item: (
                not (item.output_ext == "mp4" and codec_family(item.codec) == "h264"),
                -(item.fps or 0),
                item.ffmpeg_required,
                item.format_ids,
            ),
        )
        videos = [replace(item, recommended=item == recommendation) for item in videos]
    audio_options = [
        _audio_option(item, duration, is_live) for item in sorted(audio, key=_audio_priority)
    ]
    if audio_options:
        audio_options[0] = replace(audio_options[0], recommended=True)
    return FormatCatalog(tuple(videos), tuple(audio_options))


def make_mp3_option(
    audio: MediaFormat,
    duration: float | None,
    bitrate: int = 192,
    *,
    is_live: bool = False,
) -> FormatSelection:
    if (
        audio.kind != StreamKind.AUDIO
        or codec_family(audio.acodec) not in MKV_AUDIO
        or type(bitrate) is not int
        or bitrate not in {128, 192, 256, 320}
    ):
        raise ValueError(
            "MP3 seçimi bir audio-only kaynak ve desteklenen hedef bit hızı gerektirir."
        )
    return FormatSelection(
        SelectionKind.AUDIO,
        f"MP3 · {bitrate} kbps (dönüştürme)",
        None,
        audio,
        "mp3",
        estimate_stream(audio, duration, is_live=is_live),
        SizeEstimate() if is_live else estimate_from_bitrate(duration, bitrate),
        requires_conversion=True,
        target_audio_bitrate=bitrate,
        notes=(
            "FFmpeg ile MP3 dönüşümü gerekir; dosya boyutu tahminidir.",
            "Hedef bit hızını artırmak kaynak sesin gerçek kalitesini artırmaz.",
        ),
    )
