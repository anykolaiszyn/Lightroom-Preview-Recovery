from pathlib import Path

import pytest

from lightroom_preview_recovery.models import CatalogImage, PreviewEntry
from lightroom_preview_recovery.paths import (
    collision_path,
    contained_path,
    constrain_destination,
    planned_relative_path,
    sanitize_component,
)


def test_sanitizes_windows_reserved_and_invalid_names() -> None:
    assert sanitize_component("CON") == "_CON"
    assert sanitize_component("con. ") == "_con"
    assert sanitize_component("bad:name. ") == "bad_name"


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


def test_destination_collapses_middle_when_over_239_characters(tmp_path: Path) -> None:
    relative = Path("Photos/Root") / Path(*(["very-long-folder"] * 30)) / "x.jpg"

    result = constrain_destination(tmp_path, relative)

    assert len(str(result)) <= 239
    assert result.name == "x.jpg"
    assert any(part.startswith("_long_path_") for part in result.parts)


def test_destination_long_path_collapse_is_deterministic(tmp_path: Path) -> None:
    relative = Path("Photos/Root") / Path(*(["very-long-folder"] * 30)) / "x.jpg"

    assert constrain_destination(tmp_path, relative) == constrain_destination(tmp_path, relative)
