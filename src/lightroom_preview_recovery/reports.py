from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path

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

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_root / "recovery-report.csv"
        self.log_path = self.output_root / "recovery-report.log"
        self.html_path = self.output_root / "recovery-report.html"

    def append(self, result: RecoveryResult) -> None:
        """Append and flush one result so resume data survives an interruption."""
        write_header = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
        with self.csv_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
            if write_header:
                writer.writeheader()
            writer.writerow(self._row_for_result(result))
            handle.flush()

    def log(self, message: str) -> None:
        """Append one locally timestamped log line."""
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
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
        self.html_path.write_text(document, encoding="utf-8")

    def _row_for_result(self, result: RecoveryResult) -> dict[str, object]:
        recovered_path = self._reported_path(result.recovered_path)
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


def load_resume_index(csv_path: Path) -> dict[str, RecoveryResult]:
    """Load append-only report rows, retaining the most recent result per preview."""
    if not csv_path.exists():
        return {}

    index: dict[str, RecoveryResult] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            result = RecoveryResult(
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
            index[ReportWriter._resume_key(result.preview_uuid, result.preview_digest)] = result
    return index


def _optional_int(value: str) -> int | None:
    return int(value) if value else None


def _optional_text(value: str) -> str | None:
    return value or None


def _optional_path(value: str) -> Path | None:
    return Path(value) if value else None
