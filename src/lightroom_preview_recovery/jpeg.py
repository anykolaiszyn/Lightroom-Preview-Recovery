from __future__ import annotations

from collections.abc import Iterator

from .models import JpegCandidate

JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"
SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}


class InvalidPreviewRecord(ValueError):
    pass


def iter_jpeg_streams(data: bytes) -> Iterator[bytes]:
    position = 0
    while True:
        start = data.find(JPEG_START, position)
        if start < 0:
            return
        end = _jpeg_end(data, start)
        if end < 0:
            position = start + len(JPEG_START)
            continue
        yield data[start:end]
        position = end


def _jpeg_end(data: bytes, start: int) -> int:
    position = start + len(JPEG_START)
    while position < len(data):
        if data[position] != 0xFF:
            return -1
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            return -1
        marker = data[position]
        position += 1
        if marker == 0xD9:
            return position
        if marker in {0x01, 0xD8} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            return -1
        segment_length = int.from_bytes(data[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            return -1
        position += segment_length
        if marker != 0xDA:
            continue
        position = _scan_entropy_data(data, position)
        if position < 0:
            return -1
        if data[position - 2 : position] == JPEG_END:
            return position
    return -1


def _scan_entropy_data(data: bytes, position: int) -> int:
    while position < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        if position + 1 >= len(data):
            return -1
        marker = data[position + 1]
        if marker == 0x00 or 0xD0 <= marker <= 0xD7:
            position += 2
            continue
        if marker == 0xFF:
            position += 1
            continue
        if marker == 0xD9:
            return position + 2
        return position
    return -1


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(JPEG_START) or not data.endswith(JPEG_END):
        raise InvalidPreviewRecord("JPEG framing is incomplete")
    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0x01, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        segment_length = int.from_bytes(data[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            break
        if marker in SOF_MARKERS and segment_length >= 7:
            height = int.from_bytes(data[position + 3 : position + 5], "big")
            width = int.from_bytes(data[position + 5 : position + 7], "big")
            if width > 0 and height > 0:
                return width, height
            break
        position += segment_length
    raise InvalidPreviewRecord("JPEG has no valid dimension marker")


def select_largest_jpeg(data: bytes) -> JpegCandidate:
    candidates: list[JpegCandidate] = []
    for stream in iter_jpeg_streams(data):
        try:
            width, height = jpeg_dimensions(stream)
        except InvalidPreviewRecord:
            continue
        candidates.append(JpegCandidate(stream, width, height))
    if not candidates:
        raise InvalidPreviewRecord("preview record has no complete JPEG")
    return max(candidates, key=lambda item: (item.pixel_count, len(item.data)))
