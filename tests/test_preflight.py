from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

import lightroom_preview_recovery.preflight as preflight
from lightroom_preview_recovery.models import RecoveryConfig
from lightroom_preview_recovery.preflight import run_preflight
from tests.fixture_builders import build_catalog, build_previews


def _sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    backup = tmp_path / "backup"
    backup.mkdir()
    catalog = build_catalog(backup / "Lightroom Catalog.lrcat")
    previews = build_previews(
        backup / "Lightroom Catalog Previews.lrdata", b"preview-record"
    )
    (previews / "root-pixels.db").write_bytes(b"pixel-cache")
    return catalog, previews, tmp_path / "recovery-output"


def test_preflight_accepts_valid_sources_without_leaving_probe_artifacts(
    tmp_path: Path,
) -> None:
    catalog, previews, output = _sources(tmp_path)
    source_snapshots = {
        path: (path.stat().st_size, path.stat().st_mtime_ns, path.read_bytes())
        for path in (
            catalog,
            previews / "previews.db",
            previews / "root-pixels.db",
            next(previews.rglob("*.lrprev")),
        )
    }

    result = run_preflight(RecoveryConfig(catalog, previews, output))

    assert result.can_start
    assert result.catalog_count == 1
    assert result.preview_count == 1
    assert result.estimated_required_bytes == len(b"preview-record")
    assert result.warnings == ()
    assert not output.exists()
    for path, snapshot in source_snapshots.items():
        assert (path.stat().st_size, path.stat().st_mtime_ns, path.read_bytes()) == snapshot


def test_preflight_rejects_output_inside_preview_source(tmp_path: Path) -> None:
    catalog, previews, _ = _sources(tmp_path)
    result = run_preflight(
        RecoveryConfig(catalog, previews, previews / "bad-output")
    )

    assert not result.can_start
    assert any("preview" in error.lower() and "inside" in error.lower() for error in result.blocking_errors)


def test_preflight_rejects_output_inside_catalog_backup_directory(
    tmp_path: Path,
) -> None:
    catalog, previews, _ = _sources(tmp_path)
    result = run_preflight(
        RecoveryConfig(catalog, previews, catalog.parent / "bad-output")
    )

    assert not result.can_start
    assert any("catalog backup" in error.lower() for error in result.blocking_errors)


def test_preflight_reports_missing_required_catalog_table(tmp_path: Path) -> None:
    catalog, previews, output = _sources(tmp_path)
    with sqlite3.connect(catalog) as connection:
        connection.execute("DROP TABLE AgLibraryFolder")

    result = run_preflight(RecoveryConfig(catalog, previews, output))

    assert not result.can_start
    assert any("aglibraryfolder" in error.lower() for error in result.blocking_errors)


def test_preflight_reports_missing_preview_database_and_table(tmp_path: Path) -> None:
    catalog, previews, output = _sources(tmp_path)
    (previews / "previews.db").unlink()

    missing = run_preflight(RecoveryConfig(catalog, previews, output))

    assert not missing.can_start
    assert any("previews.db" in error.lower() for error in missing.blocking_errors)

    with sqlite3.connect(previews / "previews.db") as connection:
        connection.execute("CREATE TABLE not_the_preview_table (id INTEGER)")
    no_table = run_preflight(RecoveryConfig(catalog, previews, output))

    assert not no_table.can_start
    assert any("imagecacheentry" in error.lower() for error in no_table.blocking_errors)


def test_preflight_requires_clean_quick_check(tmp_path: Path) -> None:
    catalog, previews, output = _sources(tmp_path)
    catalog.write_bytes(b"not a sqlite database")

    result = run_preflight(RecoveryConfig(catalog, previews, output))

    assert not result.can_start
    assert any("quick_check" in error.lower() for error in result.blocking_errors)


def test_preflight_warns_when_catalog_and_preview_counts_differ(tmp_path: Path) -> None:
    catalog, previews, output = _sources(tmp_path)
    with sqlite3.connect(catalog) as connection:
        connection.execute("INSERT INTO Adobe_images VALUES (?, ?, ?)", (8, 3, None))

    result = run_preflight(RecoveryConfig(catalog, previews, output))

    assert result.can_start
    assert result.catalog_count == 2
    assert result.preview_count == 1
    assert any("count mismatch" in warning.lower() for warning in result.warnings)


def test_preflight_blocks_low_disk_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog, previews, output = _sources(tmp_path)
    usage_type = type(shutil.disk_usage(tmp_path))
    monkeypatch.setattr(
        preflight.shutil,
        "disk_usage",
        lambda _: usage_type(total=100, used=100, free=0),
    )

    result = run_preflight(RecoveryConfig(catalog, previews, output))

    assert not result.can_start
    assert any("free space" in error.lower() for error in result.blocking_errors)
    assert not output.exists()


def test_preflight_requires_lrcat_file_and_preview_root(tmp_path: Path) -> None:
    catalog, previews, output = _sources(tmp_path)
    wrong_catalog = catalog.with_suffix(".db")
    os.replace(catalog, wrong_catalog)

    result = run_preflight(RecoveryConfig(wrong_catalog, tmp_path / "missing", output))

    assert not result.can_start
    assert any(".lrcat" in error.lower() for error in result.blocking_errors)
    assert any("preview root" in error.lower() for error in result.blocking_errors)


def test_output_parent_creation_stops_at_an_unreachable_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(Path, "exists", lambda _: False)

    created = preflight._create_output_parent(tmp_path / "unreachable", errors)

    assert created is None
    assert any("root" in error.lower() for error in errors)


def test_preflight_rejects_output_parent_through_a_source_symlink(
    tmp_path: Path,
) -> None:
    catalog, previews, _ = _sources(tmp_path)
    link = tmp_path / "output-link"
    try:
        link.symlink_to(previews, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    result = run_preflight(RecoveryConfig(catalog, previews, link / "child"))

    assert not result.can_start
    assert not list(previews.rglob("*.probe"))


def test_preflight_rejects_output_parent_with_safe_target_symlink(
    tmp_path: Path,
) -> None:
    catalog, previews, _ = _sources(tmp_path)
    target = tmp_path / "safe-target"
    target.mkdir()
    link = tmp_path / "output-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    result = run_preflight(RecoveryConfig(catalog, previews, link / "child"))

    assert not result.can_start
    assert any("link" in error.lower() or "reparse" in error.lower() for error in result.blocking_errors)
    assert not list(target.rglob("*.probe"))


def test_preflight_revalidates_output_after_source_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog, previews, output = _sources(tmp_path)
    original = preflight._inspect_database
    replaced = False

    def replace_output_after_initial_validation(*args: object, **kwargs: object) -> int:
        nonlocal replaced
        if not replaced:
            output.symlink_to(previews, target_is_directory=True)
            replaced = True
        return original(*args, **kwargs)  # type: ignore[arg-type]

    try:
        monkeypatch.setattr(preflight, "_inspect_database", replace_output_after_initial_validation)
        result = run_preflight(RecoveryConfig(catalog, previews, output))
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    assert not result.can_start
    assert not list(previews.rglob("*.probe"))


def test_preflight_reports_symlink_resolution_loop_as_blocking_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog, previews, output = _sources(tmp_path)
    original_resolve = Path.resolve

    def loop_for_output(self: Path, *args: object, **kwargs: object) -> Path:
        if self == output:
            raise RuntimeError("symlink loop")
        return original_resolve(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", loop_for_output)

    result = run_preflight(RecoveryConfig(catalog, previews, output))

    assert not result.can_start
    assert any("resolve" in error.lower() for error in result.blocking_errors)
