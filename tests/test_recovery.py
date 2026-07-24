from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from threading import Event

import pytest

import lightroom_preview_recovery.recovery as recovery
from lightroom_preview_recovery.models import (
    JpegCandidate,
    RecoveryConfig,
    RecoveryStatus,
)
from lightroom_preview_recovery.paths import windows_path_key
from lightroom_preview_recovery.recovery import (
    RecoveryCancelled,
    RecoveryCoordinator,
    atomic_write_validated,
    read_record,
)
from tests.fixture_builders import build_catalog, build_previews
from tests.test_jpeg import fake_jpeg


def _add_catalog_image(catalog: Path, image_id: int, base_name: str) -> None:
    with sqlite3.connect(catalog) as connection:
        file_id = image_id + 100
        connection.execute(
            "INSERT INTO AgLibraryFile VALUES (?, ?, ?, ?, ?)",
            (file_id, base_name, "CR2", f"{base_name}.CR2", 2),
        )
        connection.execute(
            "INSERT INTO Adobe_images VALUES (?, ?, ?)",
            (image_id, file_id, None),
        )


def _set_catalog_base_name(catalog: Path, base_name: str) -> None:
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "UPDATE AgLibraryFile SET baseName = ?, originalFilename = ? "
            "WHERE id_local = 3",
            (base_name, f"{base_name}.CR2"),
        )
        connection.execute(
            "UPDATE Adobe_images SET copyName = NULL WHERE id_local = 7"
        )


def _add_preview(
    previews: Path,
    image_id: int,
    uuid: str,
    digest: str,
    record_data: bytes | None,
) -> Path:
    with sqlite3.connect(previews / "previews.db") as connection:
        connection.execute(
            "INSERT INTO ImageCacheEntry VALUES (?, ?, ?, ?)",
            (image_id, uuid, digest, 1),
        )
    record = previews / uuid[0].upper() / uuid[:4].upper() / (
        f"{uuid.upper()}-{digest}.lrprev"
    )
    if record_data is not None:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_bytes(record_data)
    return record


def _config(tmp_path: Path, record_data: bytes) -> RecoveryConfig:
    catalog = build_catalog(tmp_path / "sample.lrcat")
    previews = build_previews(tmp_path / "Catalog Previews.lrdata", record_data)
    return RecoveryConfig(catalog, previews, tmp_path / "output")


def test_recovers_largest_jpeg_with_catalog_path_and_report(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        fake_jpeg(320, 200) + fake_jpeg(1280, 853),
    )

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    assert summary.recovered == 1
    assert summary.examined == 1
    result = summary.results[0]
    assert result.status is RecoveryStatus.RECOVERED
    assert result.mapping_status == "mapped"
    assert (result.width, result.height) == (1280, 853)
    assert result.recovered_path is not None
    assert result.recovered_path.exists()
    assert result.recovered_path.name == "IMG_0007 - Monochrome.jpg"
    assert (config.output_root / "recovery-report.html").exists()


def test_cancellation_finalizes_partial_report(tmp_path: Path) -> None:
    cancel = Event()
    cancel.set()
    config = _config(tmp_path, fake_jpeg(80, 54))

    summary = RecoveryCoordinator().run(config, cancel, lambda *_: None)

    assert summary.cancelled is True
    assert summary.examined == 0
    assert (config.output_root / "recovery-report.html").exists()


def test_case_only_destinations_collide_within_one_run_without_deduplication(
    tmp_path: Path,
) -> None:
    jpeg = fake_jpeg(640, 480)
    config = _config(tmp_path, jpeg)
    _set_catalog_base_name(config.catalog_path, "CaseName")
    _add_catalog_image(config.catalog_path, 8, "casename")
    _add_preview(
        config.previews_root,
        8,
        "BCDE1234-0000-0000-0000-000000000000",
        "feedface",
        jpeg,
    )

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    assert summary.recovered == 2
    paths = [result.recovered_path for result in summary.results]
    assert all(path is not None and path.exists() for path in paths)
    assert len({windows_path_key(path) for path in paths if path is not None}) == 2
    assert {path.name.casefold() for path in paths if path is not None} == {
        "casename.jpg",
        "casename (2).jpg",
    }
    assert [path.read_bytes() for path in paths if path is not None] == [jpeg, jpeg]


def test_preexisting_destination_is_preserved_and_numbered(
    tmp_path: Path,
) -> None:
    jpeg = fake_jpeg(640, 480)
    config = _config(tmp_path, jpeg)
    destination = (
        config.output_root
        / "Photos"
        / "Pictures"
        / "2020"
        / "Trip"
        / "IMG_0007 - Monochrome.jpg"
    )
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"unrelated")

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    result = summary.results[0]
    assert destination.read_bytes() == b"unrelated"
    assert result.recovered_path == destination.with_name(
        "IMG_0007 - Monochrome (2).jpg"
    )
    assert result.recovered_path.read_bytes() == jpeg


@pytest.mark.skipif(os.name != "nt", reason="Windows rename semantics")
def test_destination_appearing_at_rename_is_preserved_and_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jpeg = fake_jpeg(640, 480)
    config = _config(tmp_path, jpeg)
    original_rename = recovery.os.rename
    raced_destination: Path | None = None
    calls = 0

    def racing_rename(source: Path, destination: Path) -> None:
        nonlocal calls, raced_destination
        calls += 1
        if calls == 1:
            raced_destination = Path(destination)
            raced_destination.write_bytes(b"racer")
            raise FileExistsError("destination appeared")
        original_rename(source, destination)

    monkeypatch.setattr(recovery.os, "rename", racing_rename)

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    assert raced_destination is not None
    assert raced_destination.read_bytes() == b"racer"
    assert summary.results[0].recovered_path == raced_destination.with_name(
        "IMG_0007 - Monochrome (2).jpg"
    )
    assert summary.results[0].recovered_path.read_bytes() == jpeg
    assert not list(config.output_root.rglob("*.partial"))


def test_resume_requires_matching_path_size_and_sha256(tmp_path: Path) -> None:
    jpeg = fake_jpeg(640, 480, b"payload")
    config = _config(tmp_path, jpeg)

    first = RecoveryCoordinator().run(config, Event(), lambda *_: None)
    recovered = first.results[0].recovered_path
    assert recovered is not None

    exact = RecoveryCoordinator().run(config, Event(), lambda *_: None)
    assert exact.skipped == 1
    assert exact.results[0].recovered_path == recovered

    recovered.write_bytes(b"z" * len(jpeg))
    hash_mismatch = RecoveryCoordinator().run(config, Event(), lambda *_: None)
    assert hash_mismatch.recovered == 1
    hash_recovery = hash_mismatch.results[0].recovered_path
    assert hash_recovery is not None
    assert hash_recovery != recovered

    hash_recovery.write_bytes(jpeg[:-1])
    size_mismatch = RecoveryCoordinator().run(config, Event(), lambda *_: None)
    assert size_mismatch.recovered == 1
    assert size_mismatch.results[0].recovered_path not in {recovered, hash_recovery}


def test_read_record_checks_cancellation_during_chunked_read(
    tmp_path: Path,
) -> None:
    record = tmp_path / "large.lrprev"
    record.write_bytes(b"x" * (1024 * 1024 + 1))
    cancel = Event()
    cancel.set()

    with pytest.raises(RecoveryCancelled):
        read_record(record, cancel)


def test_corrupt_and_missing_records_are_isolated_from_valid_records(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, fake_jpeg(640, 480))
    _add_preview(
        config.previews_root,
        8,
        "BCDE1234-0000-0000-0000-000000000000",
        "corrupt",
        b"not a jpeg",
    )
    _add_preview(
        config.previews_root,
        9,
        "CDEF1234-0000-0000-0000-000000000000",
        "missing",
        None,
    )

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    assert summary.examined == 3
    assert summary.recovered == 1
    assert summary.failed == 2
    assert [result.status for result in summary.results] == [
        RecoveryStatus.RECOVERED,
        RecoveryStatus.FAILED,
        RecoveryStatus.FAILED,
    ]
    assert (config.output_root / "recovery-report.html").exists()


def test_mapped_and_unmapped_entries_use_distinct_statuses(tmp_path: Path) -> None:
    jpeg = fake_jpeg(640, 480)
    config = _config(tmp_path, jpeg)
    _add_preview(
        config.previews_root,
        99,
        "BCDE1234-0000-0000-0000-000000000000",
        "unmapped",
        jpeg,
    )

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    assert summary.recovered == 1
    assert summary.unmapped == 1
    assert [(result.status, result.mapping_status) for result in summary.results] == [
        (RecoveryStatus.RECOVERED, "mapped"),
        (RecoveryStatus.UNMAPPED, "unmapped"),
    ]
    assert summary.results[1].recovered_path is not None
    assert summary.results[1].recovered_path.parent.name == "Unmapped"


def test_atomic_write_uses_exclusive_temporary_and_cleans_it_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "preview.jpg"
    partial = tmp_path / ".preview.jpg.fixed.partial"
    partial.write_bytes(b"owned by another writer")

    class FixedUuid:
        hex = "fixed"

    monkeypatch.setattr(recovery, "uuid4", lambda: FixedUuid())

    with pytest.raises(FileExistsError):
        atomic_write_validated(
            destination,
            JpegCandidate(fake_jpeg(80, 54), 80, 54),
        )

    assert partial.read_bytes() == b"owned by another writer"
    assert not destination.exists()


def test_progress_callback_failure_still_finalizes_report(tmp_path: Path) -> None:
    config = _config(tmp_path, fake_jpeg(80, 54))

    def fail_progress(*_: object) -> None:
        raise RuntimeError("callback failed")

    with pytest.raises(RuntimeError, match="callback failed"):
        RecoveryCoordinator().run(config, Event(), fail_progress)

    report = config.output_root / "recovery-report.html"
    assert report.exists()
    assert "Recovered: 1" in report.read_text(encoding="utf-8")


def test_recovered_hash_matches_written_bytes(tmp_path: Path) -> None:
    jpeg = fake_jpeg(80, 54)
    config = _config(tmp_path, jpeg)

    result = RecoveryCoordinator().run(config, Event(), lambda *_: None).results[0]

    assert result.byte_size == len(jpeg)
    assert result.sha256 == hashlib.sha256(jpeg).hexdigest()
