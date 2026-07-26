"""Opt-in compatibility check for a supplied Lightroom backup.

This test never writes below either live source path.  It records metadata for
the catalog, SQLite cache databases, and every preview record before opening
them, then requires the identical snapshot after all read-only work is done.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from lightroom_preview_recovery.catalog import CatalogReader
from lightroom_preview_recovery.jpeg import select_largest_jpeg
from lightroom_preview_recovery.previews import PreviewIndex


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    catalog_size: int
    catalog_mtime_ns: int
    previews_db_size: int
    previews_db_mtime_ns: int
    root_pixels_db_size: int
    root_pixels_db_mtime_ns: int
    record_count: int
    record_total_bytes: int
    record_manifest_sha256: str
    first_record: str | None
    last_record: str | None


def _stat_pair(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _validate_live_paths(catalog_path: Path, previews_root: Path) -> None:
    """Reject invalid opt-in configuration before any metadata snapshot."""

    if not catalog_path.is_file():
        raise pytest.UsageError("live catalog must be an existing file")
    if not previews_root.is_dir():
        raise pytest.UsageError(
            "live preview cache must be an existing directory"
        )
    if not (previews_root / "previews.db").is_file():
        raise pytest.UsageError("live preview cache is missing previews.db")
    if not (previews_root / "root-pixels.db").is_file():
        raise pytest.UsageError("live preview cache is missing root-pixels.db")


def snapshot_sources(catalog_path: Path, previews_root: Path) -> SourceSnapshot:
    """Build an exact, compact metadata manifest without opening files to write."""

    digest = hashlib.sha256()
    record_count = 0
    record_total_bytes = 0
    first_record: str | None = None
    last_record: str | None = None

    for record_path in sorted(previews_root.rglob("*.lrprev")):
        relative = record_path.relative_to(previews_root).as_posix()
        stat = record_path.stat()
        encoded = f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8")
        digest.update(encoded)
        record_count += 1
        record_total_bytes += stat.st_size
        if first_record is None:
            first_record = relative
        last_record = relative

    catalog_size, catalog_mtime_ns = _stat_pair(catalog_path)
    previews_db_size, previews_db_mtime_ns = _stat_pair(previews_root / "previews.db")
    root_pixels_size, root_pixels_mtime_ns = _stat_pair(
        previews_root / "root-pixels.db"
    )
    return SourceSnapshot(
        catalog_size=catalog_size,
        catalog_mtime_ns=catalog_mtime_ns,
        previews_db_size=previews_db_size,
        previews_db_mtime_ns=previews_db_mtime_ns,
        root_pixels_db_size=root_pixels_size,
        root_pixels_db_mtime_ns=root_pixels_mtime_ns,
        record_count=record_count,
        record_total_bytes=record_total_bytes,
        record_manifest_sha256=digest.hexdigest(),
        first_record=first_record,
        last_record=last_record,
    )


@pytest.mark.parametrize(
    ("missing_item", "expected_message"),
    [
        ("catalog", "catalog must be an existing file"),
        ("previews_root", "preview cache must be an existing directory"),
        ("previews_db", "preview cache is missing previews.db"),
        ("root_pixels_db", "preview cache is missing root-pixels.db"),
    ],
)
def test_validate_live_paths_reports_concise_configuration_errors(
    tmp_path: Path,
    missing_item: str,
    expected_message: str,
) -> None:
    catalog_path = tmp_path / "Catalog.lrcat"
    previews_root = tmp_path / "Catalog Previews.lrdata"
    catalog_path.write_bytes(b"catalog")
    previews_root.mkdir()
    (previews_root / "previews.db").write_bytes(b"previews")
    (previews_root / "root-pixels.db").write_bytes(b"pixels")

    if missing_item == "catalog":
        catalog_path.unlink()
    elif missing_item == "previews_root":
        previews_root.rename(tmp_path / "moved-preview-cache")
    else:
        (previews_root / f"{missing_item.removesuffix('_db').replace('_', '-')}.db").unlink()

    with pytest.raises(pytest.UsageError, match=expected_message):
        _validate_live_paths(catalog_path, previews_root)


def test_live_backup_maps_and_extracts_without_writing(request) -> None:
    catalog_option = request.config.getoption("--live-catalog")
    previews_option = request.config.getoption("--live-previews")
    if not catalog_option or not previews_option:
        pytest.skip("live Lightroom paths were not supplied")

    catalog_path = Path(catalog_option)
    previews_root = Path(previews_option)
    _validate_live_paths(catalog_path, previews_root)
    before = snapshot_sources(catalog_path, previews_root)

    try:
        images = CatalogReader(catalog_path).load_images()
        entries = PreviewIndex(previews_root).load_entries()
        mapped_ids = {entry.image_id for entry in entries if entry.image_id in images}
        existing = next(entry for entry in entries if entry.record_path.is_file())
        with existing.record_path.open("rb") as record:
            candidate = select_largest_jpeg(record.read())

        # Adobe_images is the source of truth.  In this supplied catalog it has
        # one more row than AgLibraryFile, so do not use the latter as a count.
        assert len(images) == 8_099
        assert len(entries) == 8_099
        assert len(mapped_ids) == 8_099
        assert mapped_ids == set(images)
        assert candidate.width > 0
        assert candidate.height > 0
    finally:
        after = snapshot_sources(catalog_path, previews_root)
        assert after == before, (
            "live source metadata changed during a read-only compatibility test: "
            f"before={before!r}; after={after!r}"
        )
