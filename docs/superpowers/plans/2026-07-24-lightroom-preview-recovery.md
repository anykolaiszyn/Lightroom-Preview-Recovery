# Lightroom Preview Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and package an unsigned portable Windows GUI that reads a Lightroom catalog and preview cache without modifying them, recovers each record's highest-resolution JPEG, reconstructs names and folders where possible, and writes auditable reports.

**Architecture:** A PySide6 GUI runs a recovery coordinator on a worker thread. Focused modules handle read-only SQLite access, `.lrprev` parsing, safe Windows output paths, atomic file writes, incremental reports, preflight validation, and resumable recovery. PyInstaller produces a single Windows executable that includes its Python runtime.

**Tech Stack:** Python 3.11, PySide6 6.8+, SQLite through Python's standard library, pytest 8.3+, pytest-qt 4.4+, and PyInstaller 6.11+.

## Global Constraints

- Run on 64-bit Windows 10 and Windows 11 without Lightroom or Python installed.
- Never write, rename, delete, repair, or upgrade the `.lrcat` or `.lrdata` sources.
- Open all supplied SQLite databases with `mode=ro` and `PRAGMA query_only=ON`.
- Recover cached JPEG previews only; do not claim to recover original RAW or full-resolution files.
- Choose the candidate with the largest pixel count; use byte size only as a tie-breaker.
- Never overwrite an existing output file.
- Preserve separate catalog records even when their JPEG hashes are identical.
- Keep `Mobile Downloads.lrdata`, EXIF writing, Lightroom develop-setting reconstruction, signing, and installation outside version-one scope.
- Package an unsigned portable `.exe` plus `README.html` and `LICENSES.txt`.
- Never commit copied catalog data, preview records, recovered photographs, or generated build artifacts.

---

## Planned File Structure

```text
pyproject.toml
.gitignore
src/lightroom_preview_recovery/
  __init__.py          package version
  models.py            immutable domain records and status enums
  sqlite_ro.py         read-only SQLite connection helper
  jpeg.py              embedded JPEG discovery, validation, dimensions
  catalog.py           Lightroom catalog image/file/folder mapping
  previews.py          previews.db reader and .lrprev path resolution
  paths.py             Windows-safe names, containment, collision planning
  reports.py           incremental CSV/log and finalized HTML report
  preflight.py         validation, counts, output and free-space checks
  recovery.py          resumable coordinator, atomic writes, cancellation
  worker.py            Qt worker signals around recovery.py
  gui.py               main window and GUI state transitions
  main.py              application entry point
tests/
  conftest.py
  fixture_builders.py
  test_jpeg.py
  test_catalog.py
  test_previews.py
  test_paths.py
  test_reports.py
  test_preflight.py
  test_recovery.py
  test_gui.py
  test_live_backup.py
packaging/
  LightroomPreviewRecovery.spec
  version_info.txt
scripts/
  build.ps1
  verify-package.ps1
assets/
  README.html
  LICENSES.txt
```

## Task 1: Project Foundation and Domain Types

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/lightroom_preview_recovery/__init__.py`
- Create: `src/lightroom_preview_recovery/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: Nothing.
- Produces: `CatalogImage`, `PreviewEntry`, `RecoveryResult`, `RecoverySummary`, `PreflightResult`, `RecoveryConfig`, and `RecoveryStatus`.

- [ ] **Step 1: Write the failing model test**

```python
# tests/test_models.py
from pathlib import Path

from lightroom_preview_recovery.models import (
    CatalogImage,
    RecoveryStatus,
)


def test_catalog_image_retains_virtual_copy_name() -> None:
    image = CatalogImage(
        image_id=42,
        base_name="IMG_0042",
        extension="CR2",
        original_filename="IMG_0042.CR2",
        root_name="Pictures",
        folder_path="2019/Trip",
        copy_name="Warm edit",
    )

    assert image.image_id == 42
    assert image.copy_name == "Warm edit"
    assert RecoveryStatus.RECOVERED.value == "recovered"
```

- [ ] **Step 2: Add project metadata and install the editable test environment**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "lightroom-preview-recovery"
version = "0.1.0"
description = "Recover the largest JPEG previews from a Lightroom Classic preview cache"
requires-python = ">=3.11,<3.13"
dependencies = ["PySide6>=6.8,<7"]

[project.optional-dependencies]
dev = [
  "pytest>=8.3,<9",
  "pytest-qt>=4.4,<5",
  "PyInstaller>=6.11,<7",
]

[project.gui-scripts]
lightroom-preview-recovery = "lightroom_preview_recovery.main:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: editable package and test dependencies install successfully.

- [ ] **Step 3: Run the test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`

Expected: FAIL because `lightroom_preview_recovery.models` does not exist.

- [ ] **Step 4: Implement the domain types**

```python
# src/lightroom_preview_recovery/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RecoveryStatus(str, Enum):
    RECOVERED = "recovered"
    UNMAPPED = "unmapped"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CatalogImage:
    image_id: int
    base_name: str | None
    extension: str | None
    original_filename: str | None
    root_name: str | None
    folder_path: str | None
    copy_name: str | None


@dataclass(frozen=True, slots=True)
class PreviewEntry:
    image_id: int
    uuid: str
    digest: str
    orientation: int | None
    record_path: Path

    @property
    def key(self) -> str:
        return f"{self.uuid.lower()}:{self.digest.lower()}"


@dataclass(frozen=True, slots=True)
class JpegCandidate:
    data: bytes
    width: int
    height: int

    @property
    def pixel_count(self) -> int:
        return self.width * self.height


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    image_id: int
    preview_uuid: str
    preview_digest: str
    original_filename: str | None
    original_folder: str | None
    recovered_path: Path | None
    width: int | None
    height: int | None
    byte_size: int | None
    sha256: str | None
    mapping_status: str
    status: RecoveryStatus
    message: str = ""


@dataclass(slots=True)
class RecoverySummary:
    examined: int = 0
    recovered: int = 0
    unmapped: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: bool = False
    results: list[RecoveryResult] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    catalog_path: Path
    previews_root: Path
    output_parent: Path

    @property
    def output_root(self) -> Path:
        return self.output_parent / "Recovered Lightroom Previews"


@dataclass(frozen=True, slots=True)
class PreflightResult:
    blocking_errors: tuple[str, ...]
    warnings: tuple[str, ...]
    catalog_count: int
    preview_count: int
    estimated_required_bytes: int

    @property
    def can_start(self) -> bool:
        return not self.blocking_errors
```

```python
# src/lightroom_preview_recovery/__init__.py
__version__ = "0.1.0"
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
build/
dist/
*.spec.bak
work/
*.lrcat
*.lrprev
*.lrdata/
Recovered Lightroom Previews/
```

- [ ] **Step 5: Run the model test**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`

Expected: 1 passed.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml .gitignore src/lightroom_preview_recovery tests/test_models.py
git commit -m "build: establish recovery project types"
```

## Task 2: Embedded JPEG Parser

**Files:**
- Create: `src/lightroom_preview_recovery/jpeg.py`
- Create: `tests/test_jpeg.py`

**Interfaces:**
- Consumes: `models.JpegCandidate`.
- Produces: `iter_jpeg_streams(data: bytes) -> Iterator[bytes]`, `jpeg_dimensions(data: bytes) -> tuple[int, int]`, and `select_largest_jpeg(data: bytes) -> JpegCandidate`.

- [ ] **Step 1: Write parser tests with deterministic synthetic JPEGs**

```python
# tests/test_jpeg.py
import pytest

from lightroom_preview_recovery.jpeg import (
    InvalidPreviewRecord,
    select_largest_jpeg,
)


def fake_jpeg(width: int, height: int, payload: bytes = b"x") -> bytes:
    sof = (
        b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    )
    return b"\xff\xd8" + sof + b"\xff\xda\x00\x08" + payload + b"\xff\xd9"


def test_selects_largest_dimensions_before_byte_length() -> None:
    noisy_small = fake_jpeg(320, 200, b"x" * 500)
    concise_large = fake_jpeg(1280, 853, b"y")

    result = select_largest_jpeg(b"header" + noisy_small + concise_large)

    assert (result.width, result.height) == (1280, 853)
    assert result.data == concise_large


def test_rejects_record_without_complete_jpeg() -> None:
    with pytest.raises(InvalidPreviewRecord, match="complete JPEG"):
        select_largest_jpeg(b"\xff\xd8\xff\xc0truncated")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_jpeg.py -v`

Expected: FAIL because `jpeg.py` does not exist.

- [ ] **Step 3: Implement stream discovery, SOF parsing, and ranking**

```python
# src/lightroom_preview_recovery/jpeg.py
from __future__ import annotations

from collections.abc import Iterator

from .models import JpegCandidate

JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"
SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


class InvalidPreviewRecord(ValueError):
    pass


def iter_jpeg_streams(data: bytes) -> Iterator[bytes]:
    position = 0
    while True:
        start = data.find(JPEG_START, position)
        if start < 0:
            return
        end = data.find(JPEG_END, start + len(JPEG_START))
        if end < 0:
            return
        end += len(JPEG_END)
        yield data[start:end]
        position = end


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
        segment_length = int.from_bytes(data[position:position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            break
        if marker in SOF_MARKERS and segment_length >= 7:
            height = int.from_bytes(data[position + 3:position + 5], "big")
            width = int.from_bytes(data[position + 5:position + 7], "big")
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
```

- [ ] **Step 4: Run parser tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_jpeg.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/lightroom_preview_recovery/jpeg.py tests/test_jpeg.py
git commit -m "feat: extract largest embedded preview JPEG"
```

## Task 3: Read-Only Catalog and Preview Mapping

**Files:**
- Create: `src/lightroom_preview_recovery/sqlite_ro.py`
- Create: `src/lightroom_preview_recovery/catalog.py`
- Create: `src/lightroom_preview_recovery/previews.py`
- Create: `tests/fixture_builders.py`
- Create: `tests/test_catalog.py`
- Create: `tests/test_previews.py`

**Interfaces:**
- Consumes: `CatalogImage`, `PreviewEntry`.
- Produces: `connect_readonly(path: Path) -> ContextManager[sqlite3.Connection]`, `CatalogReader.load_images() -> dict[int, CatalogImage]`, and `PreviewIndex.load_entries() -> list[PreviewEntry]`.

- [ ] **Step 1: Write mapping and path-resolution tests**

```python
# tests/test_catalog.py
from lightroom_preview_recovery.catalog import CatalogReader
from tests.fixture_builders import build_catalog


def test_loads_file_folder_root_and_copy_name(tmp_path) -> None:
    catalog = build_catalog(tmp_path / "sample.lrcat")

    images = CatalogReader(catalog).load_images()

    assert images[7].base_name == "IMG_0007"
    assert images[7].extension == "CR2"
    assert images[7].root_name == "Pictures"
    assert images[7].folder_path == "2020/Trip"
    assert images[7].copy_name == "Monochrome"
```

```python
# tests/test_previews.py
from lightroom_preview_recovery.previews import PreviewIndex
from tests.fixture_builders import build_previews


def test_resolves_uuid_digest_record_path(tmp_path) -> None:
    root = build_previews(tmp_path / "Catalog Previews.lrdata")

    entries = PreviewIndex(root).load_entries()

    assert entries[0].image_id == 7
    assert entries[0].record_path.name == (
        "ABCD1234-0000-0000-0000-000000000000-deadbeef.lrprev"
    )
    assert entries[0].record_path.exists()
```

- [ ] **Step 2: Add synthetic SQLite fixture builders**

```python
# tests/fixture_builders.py
import sqlite3
from pathlib import Path


def build_catalog(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY, rootFile INTEGER, copyName TEXT
        );
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY, baseName TEXT, extension TEXT,
            originalFilename TEXT, folder INTEGER
        );
        CREATE TABLE AgLibraryFolder (
            id_local INTEGER PRIMARY KEY, pathFromRoot TEXT, rootFolder INTEGER
        );
        CREATE TABLE AgLibraryRootFolder (
            id_local INTEGER PRIMARY KEY, name TEXT
        );
        INSERT INTO AgLibraryRootFolder VALUES (1, 'Pictures');
        INSERT INTO AgLibraryFolder VALUES (2, '2020/Trip', 1);
        INSERT INTO AgLibraryFile VALUES
            (3, 'IMG_0007', 'CR2', 'IMG_0007.CR2', 2);
        INSERT INTO Adobe_images VALUES (7, 3, 'Monochrome');
    """)
    con.commit()
    con.close()
    return path


def build_previews(root: Path, record_data: bytes = b"record") -> Path:
    root.mkdir(parents=True)
    uuid = "ABCD1234-0000-0000-0000-000000000000"
    digest = "deadbeef"
    con = sqlite3.connect(root / "previews.db")
    con.execute(
        "CREATE TABLE ImageCacheEntry "
        "(imageId INTEGER, uuid TEXT, digest TEXT, orientation INTEGER)"
    )
    con.execute(
        "INSERT INTO ImageCacheEntry VALUES (?, ?, ?, ?)",
        (7, uuid, digest, 1),
    )
    con.commit()
    con.close()
    record_dir = root / "A" / "ABCD"
    record_dir.mkdir(parents=True)
    (record_dir / f"{uuid}-{digest}.lrprev").write_bytes(record_data)
    return root
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_catalog.py tests/test_previews.py -v`

Expected: FAIL because the reader modules do not exist.

- [ ] **Step 4: Implement query-only SQLite access and catalog joins**

```python
# src/lightroom_preview_recovery/sqlite_ro.py
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect_readonly(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
    finally:
        connection.close()
```

```python
# src/lightroom_preview_recovery/catalog.py
from pathlib import Path

from .models import CatalogImage
from .sqlite_ro import connect_readonly

CATALOG_QUERY = """
SELECT
    image.id_local,
    file.baseName,
    file.extension,
    file.originalFilename,
    root.name,
    folder.pathFromRoot,
    image.copyName
FROM Adobe_images AS image
LEFT JOIN AgLibraryFile AS file ON file.id_local = image.rootFile
LEFT JOIN AgLibraryFolder AS folder ON folder.id_local = file.folder
LEFT JOIN AgLibraryRootFolder AS root ON root.id_local = folder.rootFolder
ORDER BY image.id_local
"""


class CatalogReader:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_images(self) -> dict[int, CatalogImage]:
        with connect_readonly(self.path) as connection:
            rows = connection.execute(CATALOG_QUERY).fetchall()
        return {
            int(row[0]): CatalogImage(
                image_id=int(row[0]),
                base_name=row[1],
                extension=row[2],
                original_filename=row[3],
                root_name=row[4],
                folder_path=row[5],
                copy_name=row[6],
            )
            for row in rows
        }
```

- [ ] **Step 5: Implement preview index loading and path resolution**

```python
# src/lightroom_preview_recovery/previews.py
from pathlib import Path

from .models import PreviewEntry
from .sqlite_ro import connect_readonly


def preview_record_path(root: Path, uuid: str, digest: str) -> Path:
    canonical_uuid = uuid.upper()
    return (
        root
        / canonical_uuid[0]
        / canonical_uuid[:4]
        / f"{canonical_uuid}-{digest}.lrprev"
    )


class PreviewIndex:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load_entries(self) -> list[PreviewEntry]:
        with connect_readonly(self.root / "previews.db") as connection:
            rows = connection.execute(
                "SELECT imageId, uuid, digest, orientation "
                "FROM ImageCacheEntry ORDER BY imageId"
            ).fetchall()
        return [
            PreviewEntry(
                image_id=int(image_id),
                uuid=str(uuid),
                digest=str(digest),
                orientation=orientation,
                record_path=preview_record_path(self.root, str(uuid), str(digest)),
            )
            for image_id, uuid, digest, orientation in rows
        ]
```

- [ ] **Step 6: Run mapping tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_catalog.py tests/test_previews.py -v`

Expected: 2 passed.

- [ ] **Step 7: Commit**

```powershell
git add src/lightroom_preview_recovery/sqlite_ro.py src/lightroom_preview_recovery/catalog.py src/lightroom_preview_recovery/previews.py tests
git commit -m "feat: map catalog images to preview records"
```

## Task 4: Safe Windows Output Planning

**Files:**
- Create: `src/lightroom_preview_recovery/paths.py`
- Create: `tests/test_paths.py`

**Interfaces:**
- Consumes: `CatalogImage`, `PreviewEntry`.
- Produces: `sanitize_component(value: str) -> str`, `planned_relative_path(image, entry) -> Path`, `contained_path(root, relative) -> Path`, and `collision_path(path, occupied) -> Path`.

- [ ] **Step 1: Write path-safety tests**

```python
# tests/test_paths.py
from pathlib import Path

from lightroom_preview_recovery.models import CatalogImage, PreviewEntry
from lightroom_preview_recovery.paths import (
    contained_path,
    planned_relative_path,
    sanitize_component,
)


def test_sanitizes_windows_reserved_and_invalid_names() -> None:
    assert sanitize_component("CON") == "_CON"
    assert sanitize_component('bad:name. ') == "bad_name"


def test_virtual_copy_is_named_before_jpg_suffix(tmp_path) -> None:
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
    assert planned_relative_path(None, entry) == Path(
        "Unmapped/abcd-deadbeef.jpg"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_paths.py -v`

Expected: FAIL because `paths.py` does not exist.

- [ ] **Step 3: Implement sanitization, naming, and containment**

```python
# src/lightroom_preview_recovery/paths.py
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from .models import CatalogImage, PreviewEntry

INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_component(value: str, max_length: int = 100) -> str:
    cleaned = INVALID.sub("_", value).rstrip(" .") or "_"
    if cleaned.upper() in RESERVED:
        cleaned = "_" + cleaned
    if len(cleaned) > max_length:
        digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
        cleaned = f"{cleaned[:max_length - 9]}-{digest}"
    return cleaned


def _filename(image: CatalogImage) -> str:
    if image.base_name:
        stem = image.base_name
    elif image.original_filename:
        stem = Path(image.original_filename).stem
    else:
        stem = f"image-{image.image_id}"
    if image.copy_name:
        stem = f"{stem} - {image.copy_name}"
    return sanitize_component(stem) + ".jpg"


def planned_relative_path(
    image: CatalogImage | None,
    entry: PreviewEntry,
) -> Path:
    if image is None:
        name = sanitize_component(f"{entry.uuid}-{entry.digest}") + ".jpg"
        return Path("Unmapped") / name
    parts = ["Photos", sanitize_component(image.root_name or "Unknown Root")]
    for part in PurePosixPath((image.folder_path or "").replace("\\", "/")).parts:
        if part not in {"", ".", "..", "/"}:
            parts.append(sanitize_component(part))
    return Path(*parts) / _filename(image)


def contained_path(root: Path, relative: Path) -> Path:
    resolved_root = root.resolve()
    destination = (resolved_root / relative).resolve()
    if not destination.is_relative_to(resolved_root):
        raise ValueError("planned output escapes the selected output root")
    return destination


def collision_path(path: Path, occupied: Callable[[Path], bool]) -> Path:
    if not occupied(path):
        return path
    for number in range(2, 100_000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not occupied(candidate):
            return candidate
    raise OSError(f"too many filename collisions for {path.name}")


def constrain_destination(
    root: Path,
    relative: Path,
    max_chars: int = 239,
) -> Path:
    destination = contained_path(root, relative)
    if len(str(destination)) <= max_chars:
        return destination
    parts = relative.parts
    digest = hashlib.sha1(str(relative).encode("utf-8")).hexdigest()[:8]
    if len(parts) >= 4:
        relative = Path(parts[0], parts[1], f"_long_path_{digest}", parts[-1])
    else:
        relative = Path(f"_long_path_{digest}", parts[-1])
    destination = contained_path(root, relative)
    if len(str(destination)) <= max_chars:
        return destination
    overflow = len(str(destination)) - max_chars
    keep = max(12, len(destination.stem) - overflow - 9)
    shortened = f"{destination.stem[:keep]}-{digest}{destination.suffix}"
    destination = destination.with_name(shortened)
    if len(str(destination)) > max_chars:
        raise OSError("selected output path is too long for safe recovery")
    return destination
```

- [ ] **Step 4: Run path tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_paths.py -v`

Expected: 3 passed.

- [ ] **Step 5: Add a long-path regression test and collapsing rule**

```python
def test_destination_collapses_middle_when_over_239_characters(tmp_path) -> None:
    from lightroom_preview_recovery.paths import constrain_destination

    relative = Path("Photos/Root") / Path(*(["very-long-folder"] * 30)) / "x.jpg"
    result = constrain_destination(tmp_path, relative)

    assert len(str(result)) <= 239
    assert result.name == "x.jpg"
    assert any(part.startswith("_long_path_") for part in result.parts)
```

- [ ] **Step 6: Run path tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_paths.py -v`

Expected: 4 passed.

```powershell
git add src/lightroom_preview_recovery/paths.py tests/test_paths.py
git commit -m "feat: plan contained Windows-safe output paths"
```

## Task 5: Incremental Reports and Resume Index

**Files:**
- Create: `src/lightroom_preview_recovery/reports.py`
- Create: `tests/test_reports.py`

**Interfaces:**
- Consumes: `RecoveryResult`, `RecoverySummary`.
- Produces: `ReportWriter.append(result)`, `ReportWriter.log(message)`, `ReportWriter.finalize(summary)`, and `load_resume_index(csv_path) -> dict[str, RecoveryResult]`.

- [ ] **Step 1: Write report escaping and resume tests**

```python
# tests/test_reports.py
import csv

from lightroom_preview_recovery.models import RecoveryResult, RecoveryStatus, RecoverySummary
from lightroom_preview_recovery.reports import ReportWriter, load_resume_index


def test_report_escapes_html_and_round_trips_resume_key(tmp_path) -> None:
    result = RecoveryResult(
        image_id=7,
        preview_uuid="abcd",
        preview_digest="deadbeef",
        original_filename="<photo>.CR2",
        original_folder="Trip & Family",
        recovered_path=tmp_path / "Photos" / "photo.jpg",
        width=1280,
        height=853,
        byte_size=100,
        sha256="a" * 64,
        mapping_status="mapped",
        status=RecoveryStatus.RECOVERED,
        message="",
    )
    writer = ReportWriter(tmp_path)
    writer.append(result)
    writer.finalize(RecoverySummary(examined=1, recovered=1, results=[result]))

    html = (tmp_path / "recovery-report.html").read_text(encoding="utf-8")
    assert "&lt;photo&gt;.CR2" in html
    assert "Trip &amp; Family" in html
    assert load_resume_index(tmp_path / "recovery-report.csv")[
        "abcd:deadbeef"
    ].sha256 == "a" * 64
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_reports.py -v`

Expected: FAIL because `reports.py` does not exist.

- [ ] **Step 3: Implement append-only CSV/log output and HTML finalization**

Implement `ReportWriter` with:

```python
CSV_FIELDS = [
    "image_id", "preview_uuid", "preview_digest", "original_filename",
    "original_folder", "recovered_path", "width", "height", "byte_size",
    "sha256", "mapping_status", "status", "message",
]
```

Use `csv.DictWriter(..., lineterminator="\n")`, flush after every appended row,
and use `html.escape` for every table cell. `load_resume_index` must parse rows,
convert numeric fields back to integers or `None`, convert `status` through
`RecoveryStatus`, and retain the last row for each
`preview_uuid.lower():preview_digest.lower()` key.

The finalized HTML must contain:

```html
<h1>Lightroom Preview Recovery Report</h1>
<p>This report describes cached JPEG previews, not recovered originals.</p>
```

It must show all five counters and a row for every latest result. The text log
uses UTF-8 and ISO-8601 local timestamps.

- [ ] **Step 4: Run report tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_reports.py -v`

Expected: 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/lightroom_preview_recovery/reports.py tests/test_reports.py
git commit -m "feat: write auditable recovery reports"
```

## Task 6: Recovery Coordinator, Atomic Writes, and Cancellation

**Files:**
- Create: `src/lightroom_preview_recovery/recovery.py`
- Create: `tests/test_recovery.py`

**Interfaces:**
- Consumes: readers, preview parser, output planner, reports, and domain models.
- Produces: `RecoveryCoordinator.run(config, cancel_event, on_progress) -> RecoverySummary`.

- [ ] **Step 1: Write end-to-end synthetic recovery tests**

```python
# tests/test_recovery.py
from threading import Event

from lightroom_preview_recovery.models import RecoveryConfig, RecoveryStatus
from lightroom_preview_recovery.recovery import RecoveryCoordinator
from tests.fixture_builders import build_catalog, build_previews
from tests.test_jpeg import fake_jpeg


def test_recovers_largest_jpeg_with_catalog_path_and_report(tmp_path) -> None:
    catalog = build_catalog(tmp_path / "sample.lrcat")
    previews = build_previews(
        tmp_path / "Catalog Previews.lrdata",
        fake_jpeg(320, 200) + fake_jpeg(1280, 853),
    )
    config = RecoveryConfig(catalog, previews, tmp_path / "output")

    summary = RecoveryCoordinator().run(config, Event(), lambda *_: None)

    assert summary.recovered == 1
    result = summary.results[0]
    assert result.status is RecoveryStatus.RECOVERED
    assert (result.width, result.height) == (1280, 853)
    assert result.recovered_path.exists()
    assert result.recovered_path.name == "IMG_0007 - Monochrome.jpg"
    assert (config.output_root / "recovery-report.html").exists()


def test_cancellation_finalizes_partial_report(tmp_path) -> None:
    cancel = Event()
    cancel.set()
    catalog = build_catalog(tmp_path / "sample.lrcat")
    previews = build_previews(tmp_path / "Previews.lrdata", fake_jpeg(80, 54))
    config = RecoveryConfig(catalog, previews, tmp_path / "output")

    summary = RecoveryCoordinator().run(config, cancel, lambda *_: None)

    assert summary.cancelled is True
    assert (config.output_root / "recovery-report.html").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_recovery.py -v`

Expected: FAIL because `recovery.py` does not exist.

- [ ] **Step 3: Implement atomic JPEG writing**

Add these helpers in `recovery.py`:

```python
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_validated(destination: Path, candidate: JpegCandidate) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{uuid4().hex}.partial"
    )
    try:
        temporary.write_bytes(candidate.data)
        written = temporary.read_bytes()
        if jpeg_dimensions(written) != (candidate.width, candidate.height):
            raise OSError("written JPEG failed validation")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


class RecoveryCancelled(Exception):
    pass


def read_record(path: Path, cancel_event: threading.Event) -> bytes:
    chunks: list[bytes] = []
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            if cancel_event.is_set():
                raise RecoveryCancelled
            chunks.append(chunk)
    return b"".join(chunks)
```

- [ ] **Step 4: Implement one-record processing**

`RecoveryCoordinator._process_entry` must:

1. Return a failed `RecoveryResult` when the `.lrprev` is missing or unreadable.
2. Read and pass the record to `select_largest_jpeg`.
3. Plan mapped or unmapped output.
4. Check the resume row's path, size, and SHA-256 before returning `SKIPPED`.
5. Use `collision_path` without overwriting unrelated existing files.
6. Call `atomic_write_validated`.
7. Return `RECOVERED` for mapped files and `UNMAPPED` for unmapped files.

Use this signature:

```python
def _process_entry(
    self,
    entry: PreviewEntry,
    image: CatalogImage | None,
    output_root: Path,
    resume: RecoveryResult | None,
    cancel_event: threading.Event,
) -> RecoveryResult:
```

It must call `read_record(entry.record_path, cancel_event)` instead of
`Path.read_bytes()`. `RecoveryCancelled` propagates to the coordinator so the
loop can finalize a cancelled report without recording the current entry as a
failure.

- [ ] **Step 5: Implement the coordinator loop**

Use this public signature:

```python
ProgressCallback = Callable[[RecoverySummary, PreviewEntry], None]


class RecoveryCoordinator:
    def run(
        self,
        config: RecoveryConfig,
        cancel_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> RecoverySummary:
```

The method creates the output root, loads catalog images and preview entries,
loads the prior CSV resume index, opens `ReportWriter`, checks cancellation
before each record, appends and flushes each result, updates exactly one status
counter, calls `on_progress`, and always finalizes the HTML report in `finally`.
It must catch record-level `OSError`, `InvalidPreviewRecord`, and `ValueError`
inside the loop and convert them into `FAILED` results. It catches
`RecoveryCancelled` outside record-level error handling, sets
`summary.cancelled = True`, and proceeds directly to report finalization.

- [ ] **Step 6: Run recovery tests and the full unit suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_recovery.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: recovery tests pass; full suite passes.

- [ ] **Step 7: Commit**

```powershell
git add src/lightroom_preview_recovery/recovery.py tests/test_recovery.py
git commit -m "feat: add resumable atomic preview recovery"
```

## Task 7: Preflight Validation

**Files:**
- Create: `src/lightroom_preview_recovery/preflight.py`
- Create: `tests/test_preflight.py`

**Interfaces:**
- Consumes: `RecoveryConfig`, read-only SQLite helper.
- Produces: `run_preflight(config: RecoveryConfig) -> PreflightResult`.

- [ ] **Step 1: Write blocking and successful preflight tests**

```python
# tests/test_preflight.py
from lightroom_preview_recovery.models import RecoveryConfig
from lightroom_preview_recovery.preflight import run_preflight
from tests.fixture_builders import build_catalog, build_previews


def test_preflight_accepts_valid_sources(tmp_path) -> None:
    config = RecoveryConfig(
        build_catalog(tmp_path / "sample.lrcat"),
        build_previews(tmp_path / "Previews.lrdata"),
        tmp_path / "output",
    )
    result = run_preflight(config)
    assert result.can_start
    assert result.catalog_count == 1
    assert result.preview_count == 1


def test_preflight_rejects_output_inside_preview_source(tmp_path) -> None:
    previews = build_previews(tmp_path / "Previews.lrdata")
    config = RecoveryConfig(
        build_catalog(tmp_path / "sample.lrcat"),
        previews,
        previews / "bad-output",
    )
    result = run_preflight(config)
    assert not result.can_start
    assert any("inside" in error for error in result.blocking_errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -v`

Expected: FAIL because `preflight.py` does not exist.

- [ ] **Step 3: Implement exact validation checks**

`run_preflight` must:

- Require a `.lrcat` file.
- Require a preview root directory and `previews.db`.
- Verify required catalog tables:
  `Adobe_images`, `AgLibraryFile`, `AgLibraryFolder`, `AgLibraryRootFolder`.
- Verify preview table `ImageCacheEntry`.
- Run `PRAGMA quick_check` on both databases and require exactly `ok`.
- Count `Adobe_images` and `ImageCacheEntry`.
- Reject an output parent inside the catalog's parent backup directory or
  inside the preview root. Compare resolved paths with `Path.is_relative_to`.
- Create and remove one uniquely named zero-byte probe in the output parent.
- Sum `.lrprev` file sizes as a conservative required-space estimate.
- Compare the estimate to `shutil.disk_usage(output_parent).free`.
- Return low-space as a blocking error and a count mismatch as a warning.

All database inspection must use `connect_readonly`.

- [ ] **Step 4: Run preflight tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_preflight.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/lightroom_preview_recovery/preflight.py tests/test_preflight.py
git commit -m "feat: validate recovery inputs before writing"
```

## Task 8: Responsive PySide6 GUI

**Files:**
- Create: `src/lightroom_preview_recovery/worker.py`
- Create: `src/lightroom_preview_recovery/gui.py`
- Create: `src/lightroom_preview_recovery/main.py`
- Create: `tests/test_gui.py`

**Interfaces:**
- Consumes: `run_preflight`, `RecoveryCoordinator`, and domain models.
- Produces: `RecoveryWorker`, `MainWindow`, and `main()`.

- [ ] **Step 1: Write a GUI state test**

```python
# tests/test_gui.py
from lightroom_preview_recovery.gui import MainWindow


def test_start_disabled_until_all_paths_are_selected(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.start_button.isEnabled()

    window.catalog_edit.setText(r"C:\Backup\Catalog.lrcat")
    window.previews_edit.setText(r"C:\Backup\Catalog Previews.lrdata")
    window.output_edit.setText(r"D:\Recovered")

    assert window.start_button.isEnabled()
```

- [ ] **Step 2: Run the GUI test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`

Expected: FAIL because `gui.py` does not exist.

- [ ] **Step 3: Implement the Qt recovery worker**

```python
# src/lightroom_preview_recovery/worker.py
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from .models import RecoveryConfig, RecoverySummary
from .recovery import RecoveryCoordinator


class RecoveryWorker(QObject):
    progress = Signal(object, object)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, config: RecoveryConfig) -> None:
        super().__init__()
        self.config = config
        self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            summary = RecoveryCoordinator().run(
                self.config,
                self.cancel_event,
                lambda summary, entry: self.progress.emit(summary, entry),
            )
            self.completed.emit(summary)
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")
        finally:
            self.finished.emit()

    @Slot()
    def cancel(self) -> None:
        self.cancel_event.set()
```

- [ ] **Step 4: Implement the main window**

`MainWindow` must construct, without a `.ui` file:

- Three `QLineEdit` path fields and Browse buttons
- Preflight status label
- `QProgressBar`
- Labels for elapsed time and five counters
- Start and Cancel buttons
- A read-only activity text area
- Completion buttons to open output and report through
  `QDesktopServices.openUrl(QUrl.fromLocalFile(...))`

Connect every line edit's `textChanged` signal to:

```python
def _update_start_enabled(self) -> None:
    ready = all(
        field.text().strip()
        for field in (self.catalog_edit, self.previews_edit, self.output_edit)
    )
    self.start_button.setEnabled(ready and self._thread is None)
```

When Start is clicked, run preflight synchronously, display every blocking error
or warning, then move `RecoveryWorker` to a `QThread`. During recovery, disable
all selectors and Start, enable Cancel, set the progress maximum from
`preflight.preview_count`, and update counters from worker signals. On finish,
quit and delete the thread and worker, restore selector state, and label a
cancelled run explicitly. Start a `QElapsedTimer` with the worker and use a
one-second `QTimer` to render elapsed time as `HH:MM:SS`; stop the timer in every
completion and failure path.

- [ ] **Step 5: Add the application entry point**

```python
# src/lightroom_preview_recovery/main.py
import sys

from PySide6.QtWidgets import QApplication

from lightroom_preview_recovery.gui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Lightroom Preview Recovery")
    window = MainWindow()
    window.resize(820, 620)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run GUI and full tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/test_gui.py -v
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:\QT_QPA_PLATFORM
```

Expected: GUI test passes; full suite passes.

- [ ] **Step 7: Launch the development GUI manually**

Run: `.\.venv\Scripts\python.exe -m lightroom_preview_recovery.main`

Expected: the window opens, browse dialogs work, Start remains disabled until
three paths are supplied, and closing the idle window exits cleanly.

- [ ] **Step 8: Commit**

```powershell
git add src/lightroom_preview_recovery/worker.py src/lightroom_preview_recovery/gui.py src/lightroom_preview_recovery/main.py tests/test_gui.py
git commit -m "feat: add Windows recovery interface"
```

## Task 9: Live Backup Compatibility Test

**Files:**
- Create: `tests/test_live_backup.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: supplied backup paths through environment variables.
- Produces: opt-in read-only compatibility evidence without committing user data.

- [ ] **Step 1: Add opt-in command-line options**

```python
# tests/conftest.py
def pytest_addoption(parser) -> None:
    parser.addoption("--live-catalog", action="store", default=None)
    parser.addoption("--live-previews", action="store", default=None)
```

- [ ] **Step 2: Write the live read-only test**

```python
# tests/test_live_backup.py
from pathlib import Path

import pytest

from lightroom_preview_recovery.catalog import CatalogReader
from lightroom_preview_recovery.jpeg import select_largest_jpeg
from lightroom_preview_recovery.previews import PreviewIndex


def test_live_backup_maps_and_extracts_without_writing(request) -> None:
    catalog_path = request.config.getoption("--live-catalog")
    previews_root = request.config.getoption("--live-previews")
    if not catalog_path or not previews_root:
        pytest.skip("live Lightroom paths were not supplied")

    images = CatalogReader(Path(catalog_path)).load_images()
    entries = PreviewIndex(Path(previews_root)).load_entries()
    existing = next(entry for entry in entries if entry.record_path.exists())
    candidate = select_largest_jpeg(existing.record_path.read_bytes())

    assert len(images) == 8099
    assert len(entries) == 8099
    assert existing.image_id in images
    assert candidate.width > 0
    assert candidate.height > 0
```

- [ ] **Step 3: Run the live compatibility test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_live_backup.py -v `
  --live-catalog 'E:\WD_BACKUP\Lightroom\Lightroom Catalog.lrcat' `
  --live-previews 'E:\WD_BACKUP\Lightroom\Lightroom Catalog Previews.lrdata'
```

Expected: 1 passed, with 8,099 catalog images, 8,099 preview entries, and one
successfully parsed real preview. Confirm no files on `E:` have changed by
comparing catalog and database sizes and modification times to the recorded
values in the design.

- [ ] **Step 4: Run the entire suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: all synthetic tests pass and the live test skips when no paths are
provided.

- [ ] **Step 5: Commit**

```powershell
git add tests/conftest.py tests/test_live_backup.py
git commit -m "test: verify supplied Lightroom backup compatibility"
```

## Task 10: Package, Instructions, Licenses, and Final Verification

**Files:**
- Create: `assets/README.html`
- Create: `assets/LICENSES.txt`
- Create: `packaging/LightroomPreviewRecovery.spec`
- Create: `packaging/version_info.txt`
- Create: `scripts/build.ps1`
- Create: `scripts/verify-package.ps1`

**Interfaces:**
- Consumes: complete application package.
- Produces: `outputs/Lightroom-Preview-Recovery-Windows.zip`.

- [ ] **Step 1: Write user instructions**

`assets/README.html` must be a self-contained UTF-8 HTML document with:

- A visible warning that outputs are cached JPEG previews, not originals
- Three numbered input-selection steps
- The exact output tree
- Explanation of mapped, unmapped, skipped, and failed statuses
- Safe cancellation and rerun instructions
- SmartScreen instructions limited to reviewing the publisher warning and
  choosing to run only if the ZIP came directly from this build
- A reminder to preserve the original backup

Do not load fonts, scripts, images, stylesheets, or analytics from the network.

- [ ] **Step 2: Add license notices**

`assets/LICENSES.txt` must identify:

- This utility's project license
- Python Software Foundation license
- Qt for Python / PySide6 LGPLv3 notice and relinking rights
- PyInstaller GPLv2-with-bootloader-exception notice

Include links as plain text and include complete required redistributed license
texts or ship their upstream license files beside this notice. Verify the
installed package license metadata before finalizing the text.

- [ ] **Step 3: Create PyInstaller configuration**

```python
# packaging/LightroomPreviewRecovery.spec
from pathlib import Path

root = Path(SPECPATH).parent.parent

a = Analysis(
    [str(root / "src" / "lightroom_preview_recovery" / "main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LightroomPreviewRecovery",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    version=str(root / "packaging" / "version_info.txt"),
)
```

`version_info.txt` must set file and product version `0.1.0.0`, company name
`Local Recovery Utility`, product name `Lightroom Preview Recovery`, and file
description `Recovers cached JPEG previews from Lightroom Classic backups`.

- [ ] **Step 4: Create the deterministic build script**

```powershell
# scripts/build.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$dist = Join-Path $root 'dist'
$package = Join-Path $dist 'Lightroom Preview Recovery'
$output = Join-Path $root 'outputs\Lightroom-Preview-Recovery-Windows.zip'

& $python -m pytest -q
& $python -m PyInstaller --clean --noconfirm `
  (Join-Path $root 'packaging\LightroomPreviewRecovery.spec')

New-Item -ItemType Directory -Force -Path $package | Out-Null
Copy-Item (Join-Path $dist 'LightroomPreviewRecovery.exe') $package -Force
Copy-Item (Join-Path $root 'assets\README.html') $package -Force
Copy-Item (Join-Path $root 'assets\LICENSES.txt') $package -Force
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output }
Compress-Archive -LiteralPath $package -DestinationPath $output
Write-Host "Created $output"
```

- [ ] **Step 5: Add package verification**

`verify-package.ps1` must:

1. Expand the ZIP into `work/package-verification`.
2. Require exactly the executable, README, and license file.
3. Fail if any filename ends in `.lrcat`, `.lrprev`, `.lrdata`, `.jpg`, or
   contains `WD_BACKUP`.
4. Start the executable, wait for its main window, and stop it cleanly.
5. Exit nonzero if the process exits unexpectedly or no window appears within
   30 seconds.

Use `Start-Process -PassThru -WindowStyle Hidden` only for noninteractive
helpers; the GUI itself must be visible for this smoke test.

- [ ] **Step 6: Run complete verification**

Run:

```powershell
.\scripts\build.ps1
.\scripts\verify-package.ps1
```

Expected:

- Full tests pass.
- PyInstaller completes without missing-module warnings affecting startup.
- ZIP exists at `outputs/Lightroom-Preview-Recovery-Windows.zip`.
- The packaged GUI opens without an installed Python runtime dependency.
- The ZIP contains no source backup or recovered image data.

- [ ] **Step 7: Run a final real-source GUI smoke test**

Launch the packaged executable, select the supplied `.lrcat` and
`Previews.lrdata`, choose a new directory under `work/smoke-output`, and confirm
preflight reports 8,099 catalog images and 8,099 preview entries. Cancel before
starting a full recovery, or start and cancel after at most three records.
Verify the partial report opens and all writes are confined to
`work/smoke-output/Recovered Lightroom Previews`.

- [ ] **Step 8: Commit source and packaging files**

```powershell
git add assets packaging scripts
git commit -m "build: package portable Windows recovery utility"
```

- [ ] **Step 9: Record final verification evidence**

Run:

```powershell
git status --short
.\.venv\Scripts\python.exe -m pytest -q
Get-FileHash '.\outputs\Lightroom-Preview-Recovery-Windows.zip' -Algorithm SHA256
```

Expected: source worktree is clean except intentionally untracked output
artifacts, all tests pass, and a SHA-256 hash is printed for the deliverable.

## Completion Review

Before claiming completion:

- Compare every design acceptance criterion to a passing test or explicit smoke
  test result.
- Reconfirm the `.lrcat`, `previews.db`, and `root-pixels.db` size and
  modification time on `E:` did not change.
- Open the HTML report from the three-record smoke run and compare its counters
  to the files actually written.
- Inspect the ZIP file list and confirm it contains no personal source data.
- Report the executable and ZIP SHA-256 hashes to the user.
