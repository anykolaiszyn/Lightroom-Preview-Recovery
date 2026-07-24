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
