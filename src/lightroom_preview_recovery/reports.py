from __future__ import annotations

import csv
import html
import os
import stat
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from .models import RecoveryResult, RecoveryStatus, RecoverySummary


CSV_FIELDS = [
    "image_id",
    "preview_uuid",
    "preview_digest",
    "original_filename",
    "original_folder",
    "recovered_path",
    "width",
    "height",
    "byte_size",
    "sha256",
    "mapping_status",
    "status",
    "message",
]


class ReportWriter:
    """Write recovery progress in formats safe to inspect after interruption."""

    def __init__(
        self,
        output_root: Path,
        protected_sources: Iterable[Path] = (),
    ) -> None:
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._protected_sources = tuple(
            source.resolve() for source in protected_sources if source.exists()
        )
        self.csv_path = self.output_root / "recovery-report.csv"
        self.log_path = self.output_root / "recovery-report.log"
        self.html_path = self.output_root / "recovery-report.html"
        for target in (self.csv_path, self.log_path, self.html_path):
            self._validate_target(target)

    def append(self, result: RecoveryResult) -> None:
        """Append and flush one result so resume data survives an interruption."""
        with self._open_append(self.csv_path, newline="") as handle:
            write_header = os.fstat(handle.fileno()).st_size == 0
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
            if write_header:
                writer.writeheader()
            writer.writerow(self._row_for_result(result))
            handle.flush()

    def log(self, message: str) -> None:
        """Append one locally timestamped log line."""
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._open_append(self.log_path, newline="\n") as handle:
            handle.write(f"{timestamp} {message}\n")
            handle.flush()

    def finalize(self, summary: RecoverySummary) -> None:
        """Write the final, standalone HTML report from the latest results."""
        latest: dict[str, RecoveryResult] = {}
        for result in summary.results:
            latest[self._resume_key(result.preview_uuid, result.preview_digest)] = result

        counter_rows = (
            ("Examined", summary.examined),
            ("Recovered", summary.recovered),
            ("Unmapped", summary.unmapped),
            ("Skipped", summary.skipped),
            ("Failed", summary.failed),
        )
        counters = "\n".join(
            f"<li>{html.escape(label)}: {html.escape(str(value))}</li>"
            for label, value in counter_rows
        )
        header_cells = "".join(f"<th>{html.escape(name)}</th>" for name in CSV_FIELDS)
        result_rows = "\n".join(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(value))}</td>"
                for value in self._row_for_result(result).values()
            )
            + "</tr>"
            for result in latest.values()
        )
        document = f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><title>Lightroom Preview Recovery Report</title></head>
<body>
<h1>Lightroom Preview Recovery Report</h1>
<p>This report describes cached JPEG previews, not recovered originals.</p>
<h2>Summary</h2>
<ul>
{counters}
</ul>
<h2>Latest results</h2>
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>
{result_rows}
</tbody>
</table>
</body>
</html>
"""
        self._atomic_write_html(document)

    def _atomic_write_html(self, document: str) -> None:
        self._validate_target(self.html_path)
        temporary = self.html_path.with_name(
            f".{self.html_path.name}.{uuid4().hex}.partial"
        )
        created = False
        try:
            with temporary.open("xb") as handle:
                created = True
                handle.write(document.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            self._validate_target(self.html_path)
            os.replace(temporary, self.html_path)
        finally:
            if created:
                temporary.unlink(missing_ok=True)

    def _open_append(
        self, path: Path, newline: str
    ) -> AbstractContextManager[TextIO]:
        return _AppendTarget(self, path, newline)

    def _validate_target(self, path: Path) -> None:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return

        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_flag:
            raise ValueError(f"report target must not be a link or reparse point: {path}")
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"report target must be a regular file: {path}")
        for source in self._protected_sources:
            try:
                if os.path.samefile(path, source):
                    raise ValueError(
                        f"report target must not be the same file as a protected source: {path}"
                    )
            except FileNotFoundError:
                continue
        if metadata.st_nlink != 1:
            raise ValueError(f"report target must not have multiple hard links: {path}")

    def _validate_open_file(self, path: Path, descriptor: int) -> None:
        self._validate_target(path)
        path_metadata = path.lstat()
        open_metadata = os.fstat(descriptor)
        if not os.path.samestat(path_metadata, open_metadata):
            raise ValueError(f"report target changed while it was being opened: {path}")

    def _row_for_result(self, result: RecoveryResult) -> dict[str, object]:
        recovered_path = self._reported_path(result.recovered_path)
        return _row_values(result, recovered_path)

    def _reported_path(self, recovered_path: Path | None) -> Path | None:
        if recovered_path is None:
            return None
        resolved_path = recovered_path.resolve()
        try:
            resolved_path.relative_to(self.output_root)
        except ValueError as error:
            raise ValueError("recovered paths must be inside the selected output tree") from error
        return recovered_path

    @staticmethod
    def _resume_key(preview_uuid: str, preview_digest: str) -> str:
        return f"{preview_uuid.lower()}:{preview_digest.lower()}"


WarningCallback = Callable[[str], None]


def load_resume_index(
    csv_path: Path,
    on_warning: WarningCallback | None = None,
) -> dict[str, RecoveryResult]:
    """Load append-only report rows, retaining the most recent result per preview."""
    if not csv_path.exists():
        return {}

    index: dict[str, RecoveryResult] = {}
    valid_results: list[RecoveryResult] = []
    syntax_error: str | None = None
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, strict=True)
        while True:
            try:
                row = next(reader)
            except StopIteration:
                break
            except (csv.Error, UnicodeError) as error:
                syntax_error = (
                    f"malformed trailing resume CSV near line "
                    f"{reader.line_num}: {error}"
                )
                break
            try:
                result = _result_from_row(row)
            except (KeyError, TypeError, ValueError) as error:
                _warn(
                    on_warning,
                    f"Ignoring malformed resume row at line "
                    f"{reader.line_num}: {error}",
                )
                continue
            valid_results.append(result)
            index[ReportWriter._resume_key(result.preview_uuid, result.preview_digest)] = result
    if syntax_error is not None:
        quarantine_path = _repair_resume_csv(csv_path, valid_results)
        _warn(
            on_warning,
            f"Repaired {syntax_error}; corrupt original quarantined at "
            f"{quarantine_path}",
        )
    return index


def _result_from_row(row: dict[str, str | None]) -> RecoveryResult:
    missing = [field for field in CSV_FIELDS if field not in row or row[field] is None]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")
    if not row["preview_uuid"] or not row["preview_digest"]:
        raise ValueError("preview UUID and digest are required")
    if not row["mapping_status"] or not row["status"]:
        raise ValueError("mapping status and recovery status are required")
    return RecoveryResult(
        image_id=int(row["image_id"]),
        preview_uuid=row["preview_uuid"],
        preview_digest=row["preview_digest"],
        original_filename=_optional_text(row["original_filename"]),
        original_folder=_optional_text(row["original_folder"]),
        recovered_path=_optional_path(row["recovered_path"]),
        width=_optional_int(row["width"]),
        height=_optional_int(row["height"]),
        byte_size=_optional_int(row["byte_size"]),
        sha256=_optional_text(row["sha256"]),
        mapping_status=row["mapping_status"],
        status=RecoveryStatus(row["status"]),
        message=row["message"],
    )


def _warn(callback: WarningCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def _repair_resume_csv(
    csv_path: Path,
    valid_results: list[RecoveryResult],
) -> Path:
    quarantine_path = csv_path.with_name(
        f"{csv_path.name}.{uuid4().hex}.corrupt"
    )
    with csv_path.open("rb") as source:
        with quarantine_path.open("xb") as quarantine:
            while chunk := source.read(1024 * 1024):
                quarantine.write(chunk)
            quarantine.flush()
            os.fsync(quarantine.fileno())

    temporary = csv_path.with_name(f".{csv_path.name}.{uuid4().hex}.partial")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="") as handle:
            created = True
            writer = csv.DictWriter(
                handle,
                fieldnames=CSV_FIELDS,
                lineterminator="\n",
            )
            writer.writeheader()
            for result in valid_results:
                writer.writerow(_row_values(result, result.recovered_path))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, csv_path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)
    return quarantine_path


def _row_values(
    result: RecoveryResult,
    recovered_path: Path | None,
) -> dict[str, object]:
    return {
        "image_id": result.image_id,
        "preview_uuid": result.preview_uuid,
        "preview_digest": result.preview_digest,
        "original_filename": result.original_filename,
        "original_folder": result.original_folder,
        "recovered_path": recovered_path,
        "width": result.width,
        "height": result.height,
        "byte_size": result.byte_size,
        "sha256": result.sha256,
        "mapping_status": result.mapping_status,
        "status": result.status.value,
        "message": result.message,
    }


def _optional_int(value: str | None) -> int | None:
    return int(value) if value else None


def _optional_text(value: str | None) -> str | None:
    return value or None


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


class _AppendTarget:
    def __init__(self, writer: ReportWriter, path: Path, newline: str) -> None:
        self._writer = writer
        self._path = path
        self._newline = newline
        self._handle: TextIO | None = None

    def __enter__(self) -> TextIO:
        flags = os.O_WRONLY | os.O_APPEND
        try:
            descriptor = os.open(
                self._path,
                flags | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            self._writer._validate_target(self._path)
            descriptor = os.open(self._path, flags)
            try:
                self._writer._validate_open_file(self._path, descriptor)
            except BaseException:
                os.close(descriptor)
                raise
        try:
            self._handle = os.fdopen(
                descriptor,
                "a",
                encoding="utf-8",
                newline=self._newline,
            )
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        return self._handle

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        assert self._handle is not None
        self._handle.close()
