import csv
import os
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


def test_report_writer_rejects_symlink_target_to_protected_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "catalog.lrcat"
    source.write_bytes(b"catalog")
    output = tmp_path / "output"
    output.mkdir()
    target = output / "recovery-report.csv"
    try:
        target.symlink_to(source)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    with pytest.raises(ValueError, match="link|reparse|protected"):
        ReportWriter(output, protected_sources=(source,))

    assert source.read_bytes() == b"catalog"


def test_report_writer_rejects_hardlink_same_file_as_protected_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "previews.db"
    source.write_bytes(b"database")
    output = tmp_path / "output"
    output.mkdir()
    target = output / "recovery-report.log"
    try:
        os.link(source, target)
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")

    with pytest.raises(ValueError, match="hard links|protected"):
        ReportWriter(output, protected_sources=(source,))

    assert source.read_bytes() == b"database"


def test_report_writer_rejects_non_regular_report_target(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "recovery-report.html").mkdir()

    with pytest.raises(ValueError, match="regular file"):
        ReportWriter(output)


@pytest.mark.parametrize(
    "bad_row",
    [
        ["8", "only-two-fields"],
        [
            "not-an-int", "bad-int", "digest", "", "", "", "", "", "",
            "", "unmapped", "failed", "bad integer",
        ],
        [
            "8", "bad-status", "digest", "", "", "", "", "", "", "",
            "unmapped", "not-a-status", "bad status",
        ],
    ],
    ids=["missing-fields", "invalid-integer", "invalid-status"],
)
def test_resume_index_skips_bad_rows_and_retains_valid_rows(
    tmp_path: Path,
    bad_row: list[str],
) -> None:
    writer = ReportWriter(tmp_path)
    valid = make_result(tmp_path, preview_uuid="valid", preview_digest="first")
    writer.append(valid)
    with writer.csv_path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(bad_row)
    later = make_result(
        tmp_path,
        preview_uuid="later",
        preview_digest="second",
        recovered_path=tmp_path / "Photos" / "later.jpg",
    )
    writer.append(later)
    warnings: list[str] = []

    index = load_resume_index(writer.csv_path, warnings.append)

    assert index == {"valid:first": valid, "later:second": later}
    assert len(warnings) == 1
    assert "resume row" in warnings[0].lower()


def test_resume_index_retains_rows_before_malformed_trailing_csv(
    tmp_path: Path,
) -> None:
    writer = ReportWriter(tmp_path)
    valid = make_result(tmp_path)
    writer.append(valid)
    with writer.csv_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write('"unterminated trailing field')
    warnings: list[str] = []

    index = load_resume_index(writer.csv_path, on_warning=warnings.append)

    assert index == {"abcd:deadbeef": valid}
    assert len(warnings) == 1
    assert "malformed" in warnings[0].lower()


def test_finalize_atomically_replaces_html_and_cleans_owned_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = ReportWriter(tmp_path)
    writer.html_path.write_text("old report", encoding="utf-8")
    original_replace = os.replace
    observed_temporary: Path | None = None

    def inspecting_replace(source: Path, destination: Path) -> None:
        nonlocal observed_temporary
        observed_temporary = Path(source)
        assert observed_temporary.parent == tmp_path.resolve()
        assert observed_temporary.exists()
        assert Path(destination) == writer.html_path
        original_replace(source, destination)

    monkeypatch.setattr("lightroom_preview_recovery.reports.os.replace", inspecting_replace)

    writer.finalize(RecoverySummary())

    assert observed_temporary is not None
    assert not observed_temporary.exists()
    assert writer.html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert not list(tmp_path.glob("*.partial"))
