# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A standalone Windows utility that recovers the largest embedded JPEG preview for
each image from a Lightroom Classic preview cache (`Lightroom Catalog
Previews.lrdata`), mapped back to original filenames/folders via the paired
`.lrcat` catalog. It must not require Lightroom or Python on the destination
machine. Recovered files are cached JPEG previews, not original RAW/JPEG/TIFF/
PSD files — this distinction is surfaced in the UI and reports.

Read `AGENTS.md` before doing non-trivial work here — it is the live handoff
document tracking exactly what's done, what's broken, and the next ordered
steps. Update it as state changes; don't treat it as static background reading.

## Non-negotiable source safety

The project was built and tested against a real, irreplaceable backup:

```text
E:\WD_BACKUP\Lightroom\Lightroom Catalog.lrcat
E:\WD_BACKUP\Lightroom\Lightroom Catalog Previews.lrdata
```

Never create, modify, rename, move, delete, chmod, repair, or vacuum anything
under `E:\WD_BACKUP\Lightroom`. All catalog/preview reads throughout the
codebase go through `sqlite_ro.connect_readonly` (opens with `mode=ro` +
`PRAGMA query_only=ON`). Any new code path touching the catalog or preview
cache must use this helper, never a writable connection. Live/opt-in tests may
only read these paths, and all smoke-test output must go under
`work\smoke-output`.

## Commands

Tests (uses the project's own venv or the pinned dev environment):

```powershell
python -m pytest -q                       # full suite
python -m pytest tests/test_recovery.py -v -k some_test   # single test
python -m pytest --live-catalog <path> --live-previews <path>   # opt-in real-data test (test_live_backup.py)
```

The live-backup test is skipped unless `--live-catalog`/`--live-previews` (or
`LRPR_LIVE_CATALOG`/`LRPR_LIVE_PREVIEWS` env vars) are supplied. It snapshots
the catalog, `previews.db`, `root-pixels.db`, and the `.lrprev` metadata
manifest before and after, and fails if the source changed in any way.

Run the app directly:

```powershell
python -m lightroom_preview_recovery.main
```

Packaging (PyInstaller, driven by `scripts/build.ps1` and
`packaging/LightroomPreviewRecovery.spec`) is mid-migration — see "Known
inconsistent state" below before touching it.

## Architecture

Pure-Python core with no GUI dependency, plus a thin GUI shell:

- `models.py` — all shared dataclasses/enums (`CatalogImage`, `PreviewEntry`,
  `JpegCandidate`, `RecoveryResult`, `RecoverySummary`, `RecoveryConfig`,
  `PreflightResult`). Everything else imports from here; there is no other
  shared-state module.
- `sqlite_ro.py` — the only sanctioned way to open the catalog or
  `previews.db`. Enforces read-only mode at the connection level.
- `catalog.py` — one JOIN query mapping `Adobe_images` → `AgLibraryFile` →
  `AgLibraryFolder` → `AgLibraryRootFolder`, producing `image_id ->
  CatalogImage`.
- `previews.py` — reads `ImageCacheEntry` from `previews.db` and derives each
  preview's on-disk `.lrprev` path from its UUID (`root/U/UUID4/UUID-DIGEST.lrprev`
  sharding, per Lightroom's cache layout).
- `jpeg.py` — marker-aware embedded JPEG extraction. `.lrprev` files can
  contain multiple concatenated JPEG streams (progressively larger preview
  tiers); this scans JPEG markers (not just byte search) to find complete
  streams and their SOF dimensions, then `select_largest_jpeg` picks the one
  with the most pixels. This is the format-parsing core — treat marker-parsing
  changes here as high-risk and test-critical.
- `paths.py` — plans Windows-safe, deterministic output paths from a
  `CatalogImage` (mirrors the original folder structure under
  `Recovered Lightroom Previews/Photos/<root>/<folders>/`, or `Unmapped/` when
  there's no catalog match). Handles Windows reserved names, invalid
  characters, UTF-16 path-length limits (`MAX_PATH`-safe truncation with hash
  suffixes), and collision numbering. `windows_path_key` gives a
  case-insensitive dedup key for in-flight destination reservations.
- `recovery.py` — `RecoveryCoordinator.run(...)` is the orchestrator: loads the
  catalog and preview index, iterates entries, extracts+writes each preview
  atomically (`atomic_write_validated` writes to a temp file, re-reads and
  re-validates JPEG dimensions, then does a rename/link that fails closed if
  the destination appeared concurrently), and streams results through
  `ReportWriter`. Supports mid-run cancellation via a `threading.Event` and
  crash-safe resume: on restart it reads the existing CSV report
  (`load_resume_index`) and, for each previously-recorded destination, re-hashes
  the file on disk and only trusts the resume entry if size+sha256 still
  match — including a symlink/reparse-point/path-escape guard
  (`_safe_resume_path`) before ever touching a "resume" path.
- `reports.py` — `ReportWriter` appends CSV/log rows incrementally (so a crash
  mid-run leaves a usable partial report) and atomically rewrites a
  self-contained HTML summary after each run. All report targets are
  validated against being symlinks/reparse points/hardlinks/the protected
  source files before every write.
- `preflight.py` — `run_preflight` validates both sources and the output
  location *before* any recovery work starts: catalog/preview schema and
  `PRAGMA quick_check`, catalog/preview count parity (warning, not blocking),
  output-not-inside-source checks, reparse-point rejection on every path
  component, and a real write-probe + free-space check. Returns a
  `PreflightResult` the GUI must always check via `can_start` before
  proceeding.
- `worker.py` — `RecoveryWorker` runs `RecoveryCoordinator` on a background
  non-daemon `Thread` and communicates back only via a `Queue` of
  `WorkerMessage`s (`progress`/`completed`/`failed`/`finished`) drained by
  polling — no GUI object is ever touched from the worker thread.
- `gui.py` — `tkinter`/`ttk` UI (`MainWindow`). Polls `worker.drain_messages()`
  on a `self.after(...)` timer; never blocks on the worker. Tracks its own
  lifecycle state carefully (`_worker_finished_seen`, `_close_requested`,
  `_destroyed`) to support cancel-then-close and close-during-run without
  leaving a dangling non-daemon thread or double-destroying the Tk root.

Data flow for one recovery run: `preflight.run_preflight` (validate) →
`RecoveryWorker.start` → `RecoveryCoordinator.run` → for each `PreviewEntry`:
read raw `.lrprev` bytes → `jpeg.select_largest_jpeg` → look up mapped
`CatalogImage` → `paths.planned_relative_path` + collision resolution →
`atomic_write_validated` → `ReportWriter.append` → progress message back to GUI.

## GUI/packaging migration status (completed)

The GUI migration from PySide6/Qt to stdlib `tkinter`/`ttk` is finished:

- `gui.py` is the tkinter/ttk `MainWindow` implementation.
- `main.py` launches it directly via `MainWindow().mainloop()` — no Qt
  anywhere in the launch path.
- `pyproject.toml` has `dependencies = []` (tkinter is stdlib); `pytest-qt`
  was dropped from the `dev` extra.
- `packaging/LightroomPreviewRecovery.spec` builds a PyInstaller **onedir**
  package (`EXE(exclude_binaries=True)` + `COLLECT(...)`), with
  `excludes=["PySide6", "shiboken6", "PyQt5", "PyQt6"]` as defense-in-depth
  against a dirty environment re-bundling Qt.
- `scripts/build.ps1` resolves its Python interpreter via `-Python` param →
  `$env:LRPR_PYTHON` → project `.venv` → PATH `python`, with no hardcoded
  external path; it copies the full onedir output tree, not a single `.exe`.
- `scripts/verify-package.ps1` validates the onedir shape (`.exe` +
  `_internal/` + top-level file set) and the exact license inventory
  (Python, Tcl/Tk, OpenSSL, PyInstaller — no LGPL) rather than an exact
  onefile file list.
- `assets/licenses/LGPL-3.0.txt` was deleted as an orphaned leftover; every
  remaining file in `assets/licenses/` is referenced in `assets/LICENSES.txt`.

**Known environment flakiness in `tests/test_gui.py`, not a code defect:**
on this development machine, roughly 1-in-5 pytest runs of `test_gui.py`
shows exactly one intermittent `_tkinter.TclError` (varying test, varying
message) when creating many `tk.Tk()` instances in rapid succession under
pytest. Root-caused to Windows Defender real-time protection intermittently
interfering with Tcl script file reads under rapid file-handle churn — it
does **not** reproduce in a raw create/destroy loop of `tk.Tk()` or
`gui.MainWindow()` outside pytest (20/20 clean in both cases). If you hit a
single, non-reproducible GUI test error, re-run before assuming a
regression; the 97 non-GUI tests never show this behavior.

## Development method used on this project

Work here follows a gated, subagent-driven TDD workflow (discovery → design
spec → task-by-task implementation plan → bounded implementer per task →
independent reviewer per task, fixing all Critical/Important findings before
re-review → real-data validation with source snapshots → release engineering
→ final whole-project review). See `AGENTS.md` for the full write-up and the
reusable kickoff prompt. Task briefs/reports/review diffs for completed work
live under `.superpowers/sdd/`; design and plan documents live under
`docs/superpowers/specs/` and `docs/superpowers/plans/`.
