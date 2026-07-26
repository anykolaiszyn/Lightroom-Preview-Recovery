from __future__ import annotations

import os
import shutil
import sqlite3
import stat
from pathlib import Path
from uuid import uuid4

from .models import PreflightResult, RecoveryConfig
from .sqlite_ro import connect_readonly


CATALOG_TABLES = frozenset(
    {
        "Adobe_images",
        "AgLibraryFile",
        "AgLibraryFolder",
        "AgLibraryRootFolder",
    }
)
PREVIEW_TABLES = frozenset({"ImageCacheEntry"})


def run_preflight(config: RecoveryConfig) -> PreflightResult:
    """Validate sources and output readiness without modifying either source."""
    errors: list[str] = []
    warnings: list[str] = []
    catalog_count = 0
    preview_count = 0
    estimated_required_bytes = 0

    catalog_ok = _validate_catalog_path(config.catalog_path, errors)
    previews_ok = _validate_previews_path(config.previews_root, errors)
    output_parent = _validate_output_location(config, errors)

    if catalog_ok:
        catalog_count = _inspect_database(
            config.catalog_path,
            CATALOG_TABLES,
            "Adobe_images",
            "catalog",
            errors,
        )
    if previews_ok:
        preview_count = _inspect_database(
            config.previews_root / "previews.db",
            PREVIEW_TABLES,
            "ImageCacheEntry",
            "preview cache",
            errors,
        )
        estimated_required_bytes = _estimate_preview_bytes(
            config.previews_root,
            errors,
        )

    if catalog_ok and previews_ok and catalog_count != preview_count:
        warnings.append(
            "Catalog/preview count mismatch: "
            f"{catalog_count:,} catalog images and {preview_count:,} preview entries."
        )

    if output_parent is not None and not errors:
        _validate_output_writable_and_space(
            config,
            estimated_required_bytes,
            errors,
        )

    return PreflightResult(
        blocking_errors=tuple(errors),
        warnings=tuple(warnings),
        catalog_count=catalog_count,
        preview_count=preview_count,
        estimated_required_bytes=estimated_required_bytes,
    )


def _validate_catalog_path(path: Path, errors: list[str]) -> bool:
    if path.suffix.casefold() != ".lrcat":
        errors.append("Catalog must be a .lrcat file.")
        return False
    if not path.is_file():
        errors.append(f"Catalog file was not found: {path}")
        return False
    return True


def _validate_previews_path(path: Path, errors: list[str]) -> bool:
    if not path.is_dir():
        errors.append(f"Preview root directory was not found: {path}")
        return False
    database = path / "previews.db"
    if not database.is_file():
        errors.append(f"Preview root is missing previews.db: {database}")
        return False
    return True


def _validate_output_location(
    config: RecoveryConfig, errors: list[str]
) -> Path | None:
    try:
        output_lexical = config.output_parent.absolute()
        output_parent = config.output_parent.resolve(strict=False)
        catalog_parent = config.catalog_path.resolve(strict=True).parent
        previews_root = config.previews_root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        errors.append(f"Could not resolve output and source paths: {error}")
        return None

    if output_parent == previews_root or output_parent.is_relative_to(previews_root):
        errors.append(
            "Output parent is inside the preview source; choose a separate location."
        )
        return None
    if output_parent == catalog_parent or output_parent.is_relative_to(catalog_parent):
        errors.append(
            "Output parent is inside the catalog backup directory; choose a separate location."
        )
        return None
    if _has_reparse_component(output_lexical, errors):
        return None
    if _has_reparse_component(output_parent, errors):
        return None
    return output_parent


def _has_reparse_component(path: Path, errors: list[str]) -> bool:
    """Reject a lexical output route containing a link or Windows reparse point."""
    components: list[Path] = []
    current = path
    while True:
        components.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for component in reversed(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            errors.append(f"Could not inspect output path component {component}: {error}")
            return True
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_flag:
            errors.append(
                "Output parent must not use a link or reparse point: "
                f"{component}"
            )
            return True
    return False


def _inspect_database(
    path: Path,
    required_tables: frozenset[str],
    count_table: str,
    label: str,
    errors: list[str],
) -> int:
    try:
        with connect_readonly(path) as connection:
            quick_check = [row[0] for row in connection.execute("PRAGMA quick_check")]
            if quick_check != ["ok"]:
                errors.append(
                    f"{label.capitalize()} quick_check did not return exactly ok."
                )
                return 0
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing = sorted(required_tables - tables)
            if missing:
                errors.append(
                    f"{label.capitalize()} is missing required table(s): "
                    + ", ".join(missing)
                )
                return 0
            return int(
                connection.execute(f"SELECT COUNT(*) FROM {count_table}").fetchone()[0]
            )
    except (OSError, sqlite3.DatabaseError) as error:
        errors.append(f"{label.capitalize()} quick_check failed: {error}")
        return 0


def _estimate_preview_bytes(root: Path, errors: list[str]) -> int:
    total = 0
    try:
        for path in root.rglob("*.lrprev"):
            if path.is_file():
                total += path.stat().st_size
    except OSError as error:
        errors.append(f"Could not estimate preview-cache size: {error}")
    return total


def _validate_output_writable_and_space(
    config: RecoveryConfig,
    required_bytes: int,
    errors: list[str],
) -> None:
    # Re-resolve immediately before creation.  Use this canonical path rather
    # than the user-supplied lexical route so a replaced link cannot redirect
    # the write probe into a source directory.
    output_parent = _validate_output_location(config, errors)
    if output_parent is None:
        return
    created_directories = _create_output_parent(output_parent, errors)
    if created_directories is None:
        return

    try:
        # A concurrent replacement between mkdir and probe must be checked
        # again.  The resulting canonical route is the only route used below.
        output_parent = _validate_output_location(config, errors)
        if output_parent is None:
            return
        probe = output_parent / f".lightroom-preview-recovery-{uuid4().hex}.probe"
        with probe.open("xb"):
            pass
        free_bytes = shutil.disk_usage(output_parent).free
        if free_bytes < required_bytes:
            errors.append(
                "Insufficient free space for recovery: "
                f"need at least {required_bytes:,} bytes, have {free_bytes:,} bytes."
            )
    except OSError as error:
        errors.append(f"Output parent is not writable: {output_parent} ({error})")
    finally:
        try:
            if "probe" in locals():
                probe.unlink(missing_ok=True)
        except OSError as error:
            errors.append(f"Could not remove output write probe: {error}")
        _remove_created_directories(created_directories)


def _create_output_parent(path: Path, errors: list[str]) -> list[Path] | None:
    if path.exists():
        if not path.is_dir():
            errors.append(f"Output parent is not a directory: {path}")
            return None
        return []

    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            errors.append(
                "Could not create output parent because no existing output root was found: "
                f"{current}"
            )
            return None
        current = parent
    if not current.is_dir():
        errors.append(f"Output parent ancestor is not a directory: {current}")
        return None

    created: list[Path] = []
    try:
        for directory in reversed(missing):
            try:
                directory.mkdir()
                created.append(directory)
            except FileExistsError:
                if not directory.is_dir():
                    raise
    except OSError as error:
        _remove_created_directories(created)
        errors.append(f"Could not create output parent for write check: {error}")
        return None
    return created


def _remove_created_directories(created_directories: list[Path]) -> None:
    for directory in reversed(created_directories):
        try:
            directory.rmdir()
        except OSError:
            break
