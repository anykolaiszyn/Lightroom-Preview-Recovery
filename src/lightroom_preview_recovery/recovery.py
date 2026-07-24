from __future__ import annotations

import hashlib
import os
import stat
import threading
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from .catalog import CatalogReader
from .jpeg import InvalidPreviewRecord, jpeg_dimensions, select_largest_jpeg
from .models import (
    CatalogImage,
    JpegCandidate,
    PreviewEntry,
    RecoveryConfig,
    RecoveryResult,
    RecoveryStatus,
    RecoverySummary,
)
from .paths import (
    collision_path,
    constrain_destination,
    planned_relative_path,
    windows_path_key,
)
from .previews import PreviewIndex
from .reports import ReportWriter, load_resume_index


_READ_CHUNK_SIZE = 1024 * 1024
_DESTINATION_RETRIES = 100


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _DestinationAppeared(FileExistsError):
    pass


def atomic_write_validated(destination: Path, candidate: JpegCandidate) -> None:
    """Write a validated JPEG atomically without replacing another file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.partial")
    created = False
    try:
        with temporary.open("xb") as handle:
            created = True
            handle.write(candidate.data)
            handle.flush()
            os.fsync(handle.fileno())

        written = temporary.read_bytes()
        try:
            dimensions = jpeg_dimensions(written)
        except InvalidPreviewRecord as error:
            raise OSError("written JPEG failed validation") from error
        if dimensions != (candidate.width, candidate.height):
            raise OSError("written JPEG failed validation")

        if destination.exists():
            raise _DestinationAppeared(str(destination))
        try:
            if os.name == "nt":
                os.rename(temporary, destination)
            else:
                os.link(temporary, destination)
                temporary.unlink()
        except FileExistsError as error:
            raise _DestinationAppeared(str(destination)) from error
    finally:
        if created:
            temporary.unlink(missing_ok=True)


class RecoveryCancelled(Exception):
    pass


def read_record(path: Path, cancel_event: threading.Event) -> bytes:
    chunks: list[bytes] = []
    with path.open("rb") as source:
        while True:
            if cancel_event.is_set():
                raise RecoveryCancelled
            chunk = source.read(_READ_CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


ProgressCallback = Callable[[RecoverySummary, PreviewEntry], None]


class RecoveryCoordinator:
    def __init__(self) -> None:
        self._reserved_destinations: set[str] = set()

    def run(
        self,
        config: RecoveryConfig,
        cancel_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> RecoverySummary:
        summary = RecoverySummary()
        output_root, catalog_path, previews_root = self._validated_paths(config)
        writer = ReportWriter(
            output_root,
            protected_sources=(
                catalog_path,
                previews_root / "previews.db",
                previews_root / "root-pixels.db",
            ),
        )
        self._reserved_destinations = set()

        try:
            images = CatalogReader(catalog_path).load_images()
            entries = PreviewIndex(previews_root).load_entries()
            resume_index = load_resume_index(writer.csv_path, writer.log)

            try:
                for entry in entries:
                    if cancel_event.is_set():
                        raise RecoveryCancelled
                    image = images.get(entry.image_id)
                    try:
                        result = self._process_entry(
                            entry,
                            image,
                            output_root,
                            resume_index.get(entry.key),
                            cancel_event,
                        )
                    except RecoveryCancelled:
                        raise
                    except (OSError, InvalidPreviewRecord, ValueError) as error:
                        result = self._failed_result(entry, image, error)

                    self._record_result(summary, result)
                    writer.append(result)
                    on_progress(summary, entry)
            except RecoveryCancelled:
                summary.cancelled = True
        finally:
            writer.finalize(summary)

        return summary

    @staticmethod
    def _validated_paths(config: RecoveryConfig) -> tuple[Path, Path, Path]:
        catalog_path = config.catalog_path.resolve(strict=True)
        previews_root = config.previews_root.resolve(strict=True)
        output_root = config.output_root.resolve()
        for source, label in (
            (catalog_path, "catalog"),
            (previews_root, "previews"),
        ):
            if (
                output_root == source
                or output_root.is_relative_to(source)
                or source.is_relative_to(output_root)
            ):
                raise ValueError(
                    f"recovery output must not overlap the {label} source"
                )
        return output_root, catalog_path, previews_root

    def _process_entry(
        self,
        entry: PreviewEntry,
        image: CatalogImage | None,
        output_root: Path,
        resume: RecoveryResult | None,
        cancel_event: threading.Event,
    ) -> RecoveryResult:
        mapping_status = "mapped" if image is not None else "unmapped"
        try:
            record = read_record(entry.record_path, cancel_event)
        except OSError as error:
            return self._failed_result(entry, image, error)

        candidate = select_largest_jpeg(record)
        if resume is not None and self._resume_is_valid(
            resume, output_root, cancel_event
        ):
            assert resume.recovered_path is not None
            self._reserved_destinations.add(
                windows_path_key(resume.recovered_path)
            )
            return RecoveryResult(
                image_id=entry.image_id,
                preview_uuid=entry.uuid,
                preview_digest=entry.digest,
                original_filename=self._original_filename(image),
                original_folder=self._original_folder(image),
                recovered_path=resume.recovered_path,
                width=resume.width,
                height=resume.height,
                byte_size=resume.byte_size,
                sha256=resume.sha256,
                mapping_status=mapping_status,
                status=RecoveryStatus.SKIPPED,
                message="verified existing recovery",
            )

        planned = planned_relative_path(image, entry)
        preferred = constrain_destination(output_root, planned)
        destination: Path | None = None
        for _ in range(_DESTINATION_RETRIES):
            destination = collision_path(preferred, self._is_occupied)
            self._reserved_destinations.add(windows_path_key(destination))
            try:
                atomic_write_validated(destination, candidate)
            except _DestinationAppeared:
                continue
            break
        else:
            raise OSError(f"destination kept changing for {preferred.name}")

        status = (
            RecoveryStatus.RECOVERED
            if image is not None
            else RecoveryStatus.UNMAPPED
        )
        return RecoveryResult(
            image_id=entry.image_id,
            preview_uuid=entry.uuid,
            preview_digest=entry.digest,
            original_filename=self._original_filename(image),
            original_folder=self._original_folder(image),
            recovered_path=destination,
            width=candidate.width,
            height=candidate.height,
            byte_size=len(candidate.data),
            sha256=sha256_bytes(candidate.data),
            mapping_status=mapping_status,
            status=status,
        )

    def _resume_is_valid(
        self,
        resume: RecoveryResult,
        output_root: Path,
        cancel_event: threading.Event,
    ) -> bool:
        if (
            resume.recovered_path is None
            or resume.byte_size is None
            or resume.sha256 is None
        ):
            return False

        try:
            metadata = resume.recovered_path.lstat()
        except OSError:
            return False
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or attributes & reparse_flag
            or not stat.S_ISREG(metadata.st_mode)
        ):
            return False

        recovered_path = resume.recovered_path.resolve()
        if not recovered_path.is_relative_to(output_root.resolve()):
            return False
        try:
            if recovered_path.stat().st_size != resume.byte_size:
                return False
            digest = self._sha256_file(recovered_path, cancel_event)
        except OSError:
            return False
        return digest == resume.sha256

    @staticmethod
    def _sha256_file(path: Path, cancel_event: threading.Event) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while True:
                if cancel_event.is_set():
                    raise RecoveryCancelled
                chunk = source.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _is_occupied(self, path: Path) -> bool:
        return path.exists() or windows_path_key(path) in self._reserved_destinations

    @staticmethod
    def _record_result(
        summary: RecoverySummary,
        result: RecoveryResult,
    ) -> None:
        summary.results.append(result)
        summary.examined += 1
        if result.status is RecoveryStatus.RECOVERED:
            summary.recovered += 1
        elif result.status is RecoveryStatus.UNMAPPED:
            summary.unmapped += 1
        elif result.status is RecoveryStatus.SKIPPED:
            summary.skipped += 1
        elif result.status is RecoveryStatus.FAILED:
            summary.failed += 1
        else:
            raise ValueError(f"unsupported result status: {result.status.value}")

    @classmethod
    def _failed_result(
        cls,
        entry: PreviewEntry,
        image: CatalogImage | None,
        error: Exception,
    ) -> RecoveryResult:
        return RecoveryResult(
            image_id=entry.image_id,
            preview_uuid=entry.uuid,
            preview_digest=entry.digest,
            original_filename=cls._original_filename(image),
            original_folder=cls._original_folder(image),
            recovered_path=None,
            width=None,
            height=None,
            byte_size=None,
            sha256=None,
            mapping_status="mapped" if image is not None else "unmapped",
            status=RecoveryStatus.FAILED,
            message=str(error) or error.__class__.__name__,
        )

    @staticmethod
    def _original_filename(image: CatalogImage | None) -> str | None:
        if image is None:
            return None
        return image.original_filename or (
            f"{image.base_name}.{image.extension}"
            if image.base_name and image.extension
            else image.base_name
        )

    @staticmethod
    def _original_folder(image: CatalogImage | None) -> str | None:
        if image is None:
            return None
        return image.folder_path
