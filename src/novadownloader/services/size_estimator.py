"""Source transfer size and transformed output estimates are deliberately separate."""

from collections.abc import Iterable
from decimal import Decimal

from novadownloader.models.format_selection import SizeCertainty, SizeEstimate, SizeSource
from novadownloader.models.media_format import (
    MAX_BYTES,
    MediaFormat,
    StreamKind,
    positive_int,
    positive_number,
)


def estimate_from_bitrate(duration: float | None, bitrate: float | None) -> SizeEstimate:
    duration = positive_number(duration)
    bitrate = positive_number(bitrate)
    if duration is None or bitrate is None:
        return SizeEstimate()
    size = Decimal(str(duration)) * Decimal(str(bitrate)) * 1000 / 8
    if size < 1 or size > MAX_BYTES:
        return SizeEstimate()
    return SizeEstimate(int(size), SizeCertainty.ESTIMATED, SizeSource.BITRATE)


def estimate_stream(
    stream: MediaFormat, duration: float | None, *, is_live: bool = False
) -> SizeEstimate:
    if is_live:
        return SizeEstimate()
    if exact := positive_int(stream.filesize):
        return SizeEstimate(exact, SizeCertainty.EXACT, SizeSource.FILESIZE)
    if approximate := positive_int(stream.filesize_approx):
        return SizeEstimate(approximate, SizeCertainty.ESTIMATED, SizeSource.FILESIZE_APPROX)
    # tbr already includes all components of THIS stream; never add abr again.
    bitrate = positive_number(stream.tbr)
    if bitrate is None:
        if stream.kind == StreamKind.VIDEO:
            bitrate = positive_number(stream.vbr)
        elif stream.kind == StreamKind.AUDIO:
            bitrate = positive_number(stream.abr)
        elif (
            stream.kind == StreamKind.MUXED
            and positive_number(stream.vbr)
            and positive_number(stream.abr)
        ):
            bitrate = positive_number(stream.vbr) + positive_number(stream.abr)
    return estimate_from_bitrate(duration, bitrate)


def combine_sizes(sizes: Iterable[SizeEstimate]) -> SizeEstimate:
    sizes = tuple(sizes)
    if not sizes or any(item.bytes is None for item in sizes):
        return SizeEstimate()
    total = sum(item.bytes for item in sizes)
    if not 0 < total <= MAX_BYTES:
        return SizeEstimate()
    certainty = (
        SizeCertainty.EXACT
        if all(item.certainty == SizeCertainty.EXACT for item in sizes)
        else SizeCertainty.ESTIMATED
    )
    return SizeEstimate(total, certainty, SizeSource.SUM)
