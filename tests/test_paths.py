from pathlib import Path

import pytest

from lightroom_preview_recovery.models import CatalogImage, PreviewEntry
from lightroom_preview_recovery.paths import (
    collision_path,
    contained_path,
    constrain_destination,
    planned_relative_path,
    sanitize_component,
    windows_path_key,
)


def test_sanitizes_windows_reserved_and_invalid_names() -> None:
    assert sanitize_component("CON") == "_CON"
    assert sanitize_component("con. ") == "_con"
    assert sanitize_component("bad:name. ") == "bad_name"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("CON.txt", "_CON.txt"),
        ("LPT1.jpg", "_LPT1.jpg"),
        ("cOn.TxT", "_cOn.TxT"),
        ("COM¹.txt", "_COM¹.txt"),
        ("lPt³.JPG", "_lPt³.JPG"),
    ],
)
def test_sanitizes_windows_device_names_with_extensions(
    value: str, expected: str
) -> None:
    assert sanitize_component(value) == expected


def test_virtual_copy_is_named_before_jpg_suffix(tmp_path: Path) -> None:
    image = CatalogImage(
        7, "IMG_0007", "CR2", "IMG_0007.CR2",
        "Pictures", "2020/Trip", "Monochrome",
    )
    entry = PreviewEntry(7, "abcd", "deadbeef", 1, Path("record.lrprev"))

    relative = planned_relative_path(image, entry)

    assert relative == Path("Photos/Pictures/2020/Trip/IMG_0007 - Monochrome.jpg")
    assert contained_path(tmp_path, relative).is_relative_to(tmp_path.resolve())


def test_unmapped_preview_uses_stable_name() -> None:
    entry = PreviewEntry(7, "abcd", "deadbeef", 1, Path("record.lrprev"))
    assert planned_relative_path(None, entry) == Path("Unmapped/abcd-deadbeef.jpg")


def test_contained_path_rejects_relative_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        contained_path(tmp_path, Path("Photos/../..") / "outside.jpg")


def test_collision_path_never_reuses_occupied_filename(tmp_path: Path) -> None:
    path = tmp_path / "preview.jpg"
    occupied = {path, tmp_path / "preview (2).jpg"}

    assert collision_path(path, occupied.__contains__) == tmp_path / "preview (3).jpg"


def test_collision_path_uses_windows_case_insensitive_reservations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preview.jpg"
    occupied = {windows_path_key(tmp_path / "PREVIEW.JPG")}

    assert collision_path(path, lambda candidate: windows_path_key(candidate) in occupied) == (
        tmp_path / "preview (2).jpg"
    )


def test_collision_path_honors_custom_windows_unit_limit(tmp_path: Path) -> None:
    path = tmp_path / ("x" * 30 + ".jpg")
    max_chars = _windows_units(str(path))

    result = collision_path(path, lambda candidate: candidate == path, max_chars)

    assert _windows_units(str(result)) <= max_chars
    assert result.name.endswith(" (2).jpg")


def test_destination_collapses_middle_when_over_239_characters(tmp_path: Path) -> None:
    relative = Path("Photos/Root") / Path(*(["very-long-folder"] * 30)) / "x.jpg"

    result = constrain_destination(tmp_path, relative)

    assert _windows_units(str(result)) <= 239
    assert result.name == "x.jpg"
    assert any(part.startswith("_long_path_") for part in result.parts)


def test_destination_long_path_collapse_is_deterministic(tmp_path: Path) -> None:
    relative = Path("Photos/Root") / Path(*(["very-long-folder"] * 30)) / "x.jpg"

    assert constrain_destination(tmp_path, relative) == constrain_destination(tmp_path, relative)


def test_destination_limit_uses_windows_utf16_code_units(tmp_path: Path) -> None:
    relative = Path("Photos") / ("😀" * 10) / "x.jpg"
    code_point_limit = len(str(tmp_path.resolve() / relative)) + 5

    result = constrain_destination(tmp_path, relative, max_chars=code_point_limit)

    assert _windows_units(str(result)) <= code_point_limit
    assert any(part.startswith("_long_path_") for part in result.parts)


def test_collision_suffixing_preserves_windows_path_limit(tmp_path: Path) -> None:
    destination = constrain_destination(tmp_path, Path("a" * 500 + ".jpg"))

    result = collision_path(destination, lambda candidate: candidate == destination)

    assert _windows_units(str(destination)) == 239
    assert _windows_units(str(result)) <= 239
    assert result.name.endswith(" (2).jpg")


def _windows_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2
