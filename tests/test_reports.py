import csv
from datetime import datetime
from pathlib import Path

import pytest

from lightroom_preview_recovery.models import (
    RecoveryResult,
    RecoveryStatus,
    RecoverySummary,
)
from lightroom_preview_recovery.reports import ReportWriter, load_resume_index


def make_result(tmp_path: Path, **changes: object) -> RecoveryResult:
    fields: dict[str, object] = {
        "image_id": 7,
        "preview_uuid": "abcd",
        "preview_digest": "deadbeef",
        "original_filename": "photo.CR2",
        "original_folder": "Trip",
        "recovered_path": tmp_path / "Photos" / "photo.jpg",
        "width": 1280,
        "height": 853,
        "byte_size": 100,
        "sha256": "a" * 64,
        "mapping_status": "mapped",
        "status": RecoveryStatus.RECOVERED,
        "message": "",
    }
    fields.update(changes)
    return RecoveryResult(**fields)  # type: ignore[arg-type]


def test_report_escapes_html_and_round_trips_resume_key(tmp_path: Path) -> None:
    result = make_result(
        tmp_path,
        original_filename="<photo>.CR2",
        original_folder="Trip & Family",
    )
    writer = ReportWriter(tmp_path)
    writer.append(result)
    writer.finalize(RecoverySummary(examined=1, recovered=1, results=[result]))

    html = (tmp_path / "recovery-report.html").read_text(encoding="utf-8")
    assert "&lt;photo&gt;.CR2" in html
    assert "Trip &amp; Family" in html
    assert "<h1>Lightroom Preview Recovery Report</h1>" in html
    assert "This report describes cached JPEG previews, not recovered originals." in html
    assert load_resume_index(tmp_path / "recovery-report.csv")["abcd:deadbeef"].sha256 == "a" * 64


def test_append_flushes_csv_and_log_immediately(tmp_path: Path) -> None:
    result = make_result(tmp_path)
    writer = ReportWriter(tmp_path)
    writer.append(result)
    writer.log("Started <scan>")

    with (tmp_path / "recovery-report.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "image_id": "7",
            "preview_uuid": "abcd",
            "preview_digest": "deadbeef",
            "original_filename": "photo.CR2",
            "original_folder": "Trip",
            "recovered_path": str(tmp_path / "Photos" / "photo.jpg"),
            "width": "1280",
            "height": "853",
            "byte_size": "100",
            "sha256": "a" * 64,
            "mapping_status": "mapped",
            "status": "recovered",
            "message": "",
        }
    ]
    log_line = (tmp_path / "recovery-report.log").read_text(encoding="utf-8").strip()
    timestamp, message = log_line.split(" ", 1)
    assert datetime.fromisoformat(timestamp).tzinfo is not None
    assert message == "Started <scan>"


def test_resume_index_uses_last_row_and_restores_none_numeric_fields(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    writer.append(make_result(tmp_path, preview_uuid="ABCD", preview_digest="DEADBEEF"))
    latest = make_result(
        tmp_path,
        preview_uuid="abcd",
        preview_digest="deadbeef",
        recovered_path=None,
        width=None,
        height=None,
        byte_size=None,
        sha256=None,
        status=RecoveryStatus.SKIPPED,
        message="already processed",
    )
    writer.append(latest)

    index = load_resume_index(tmp_path / "recovery-report.csv")

    assert set(index) == {"abcd:deadbeef"}
    assert index["abcd:deadbeef"] == latest


def test_finalize_shows_all_five_counters_and_latest_rows(tmp_path: Path) -> None:
    first = make_result(tmp_path, message="first")
    latest = make_result(tmp_path, status=RecoveryStatus.FAILED, message="second")
    writer = ReportWriter(tmp_path)
    writer.finalize(
        RecoverySummary(
            examined=6,
            recovered=1,
            unmapped=2,
            skipped=3,
            failed=4,
            results=[first, latest],
        )
    )

    html = (tmp_path / "recovery-report.html").read_text(encoding="utf-8")
    for counter in ("Examined: 6", "Recovered: 1", "Unmapped: 2", "Skipped: 3", "Failed: 4"):
        assert counter in html
    assert html.count("second") == 1
    assert "first" not in html


def test_append_rejects_recovered_paths_outside_selected_output_tree(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path / "selected-output")

    with pytest.raises(ValueError, match="inside the selected output tree"):
        writer.append(make_result(tmp_path, recovered_path=tmp_path / "outside.jpg"))
