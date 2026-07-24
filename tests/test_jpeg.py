import pytest

from lightroom_preview_recovery.jpeg import (
    InvalidPreviewRecord,
    iter_jpeg_streams,
    jpeg_dimensions,
    select_largest_jpeg,
)


def fake_jpeg(width: int, height: int, payload: bytes = b"x") -> bytes:
    sof = (
        b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    )
    sos = b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
    return b"\xff\xd8" + sof + sos + payload + b"\xff\xd9"


def test_yields_complete_embedded_jpeg_streams() -> None:
    first = fake_jpeg(320, 200)
    second = fake_jpeg(1280, 853)

    assert list(iter_jpeg_streams(b"header" + first + b"gap" + second)) == [
        first,
        second,
    ]


def test_reads_dimensions_from_a_sof_marker() -> None:
    assert jpeg_dimensions(fake_jpeg(1280, 853)) == (1280, 853)


def test_ignores_eoi_bytes_inside_metadata_segment() -> None:
    jpeg = (
        b"\xff\xd8"
        + b"\xff\xe1\x00\x06ab\xff\xd9"
        + fake_jpeg(1280, 853)[2:]
    )

    assert list(iter_jpeg_streams(b"header" + jpeg)) == [jpeg]


def test_selects_largest_dimensions_before_byte_length() -> None:
    noisy_small = fake_jpeg(320, 200, b"x" * 500)
    concise_large = fake_jpeg(1280, 853, b"y")

    result = select_largest_jpeg(b"header" + noisy_small + concise_large)

    assert (result.width, result.height) == (1280, 853)
    assert result.data == concise_large


def test_breaks_equal_pixel_count_ties_by_byte_length() -> None:
    concise = fake_jpeg(640, 480, b"x")
    detailed = fake_jpeg(640, 480, b"y" * 500)

    result = select_largest_jpeg(concise + detailed)

    assert result.data == detailed


def test_rejects_record_without_complete_jpeg() -> None:
    with pytest.raises(InvalidPreviewRecord, match="complete JPEG"):
        select_largest_jpeg(b"\xff\xd8\xff\xc0truncated")
