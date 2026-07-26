# Lightroom Preview Recovery — Agent Handoff

## Mission

Finish and ship a standalone, Windows-friendly Lightroom Classic preview
recovery utility. It must not require Lightroom or Python on the destination
computer.

The application accepts:

- `Lightroom Catalog.lrcat`
- `Lightroom Catalog Previews.lrdata`
- A user-selected output parent

It reads the catalog and preview cache without modifying them, maps preview
records to original catalog filenames/folders where possible, extracts the
highest-resolution valid embedded JPEG, writes collision-safe outputs, supports
cancellation and resume, and produces HTML/CSV/text reports.

Recovered files are cached JPEG previews, not original RAW/JPEG/TIFF/PSD files.

## Non-negotiable source safety

The supplied backup is read-only:

```text
E:\WD_BACKUP\Lightroom\Lightroom Catalog.lrcat
E:\WD_BACKUP\Lightroom\Lightroom Catalog Previews.lrdata
```

Never create, modify, rename, move, delete, chmod, repair, or vacuum anything
under `E:\WD_BACKUP\Lightroom`.

Live tests may read these paths only. All smoke-test output belongs under:

```text
work\smoke-output
```

Before and after live-source work, compare the catalog, `previews.db`,
`root-pixels.db`, and the `.lrprev` metadata manifest. The existing live test
already implements this proof.

## Current repository state

- Branch: `codex/lightroom-preview-recovery`
- Git commits through Task 6 are recorded.
- Tasks 7–10 contain important uncommitted files. Do not discard or overwrite
  them.
- Run `git status --short` before editing.
- Preserve unrelated/user changes.
- Do not use `git reset --hard` or destructive checkout commands.

Canonical project documents:

```text
docs\superpowers\specs\2026-07-24-lightroom-preview-recovery-design.md
docs\superpowers\plans\2026-07-24-lightroom-preview-recovery.md
.superpowers\sdd\progress.md
.superpowers\sdd\task-*-report.md
```

## Completed and reviewed

The following areas were implemented with TDD and passed independent reviews:

1. Project types and foundation
2. Marker-aware embedded JPEG extraction
3. Read-only SQLite catalog/preview mapping
4. Windows-safe output planning and containment
5. Incremental HTML/CSV/text reports
6. Atomic resumable recovery coordinator
7. Preflight validation and source/output safety
8. The original PySide6 GUI behavior and thread lifecycle
9. Read-only compatibility with the supplied backup

Important verified live-source facts:

- 8,099 `Adobe_images`
- 8,098 `AgLibraryFile` records
- 8,099 `ImageCacheEntry` preview records
- All 8,099 preview image IDs map to catalog image IDs
- A real largest preview parsed at 2136×1424
- The exact 8,099-file metadata manifest and database size/mtime snapshots were
  unchanged after the live test

## Current state: tkinter migration and onedir packaging complete

The PySide6-to-tkinter migration and the onedir packaging rework (formerly
Task 10 and the "next actions" below) are finished and independently
reviewed:

- `main.py` launches `gui.MainWindow().mainloop()` directly — no PySide6
  anywhere in the codebase or in `pyproject.toml`'s dependencies.
- `packaging/LightroomPreviewRecovery.spec` builds a PyInstaller **onedir**
  package with `excludes=["PySide6", "shiboken6", "PyQt5", "PyQt6"]`.
- `scripts/build.ps1` is portable (`-Python` param → `LRPR_PYTHON` env var →
  project `.venv` → PATH `python`; no hardcoded external venv path).
- `scripts/verify-package.ps1` validates the onedir layout and the exact
  license inventory (Python, Tcl/Tk, OpenSSL, PyInstaller — LGPL notice
  removed as unused).
- A fresh onedir build was produced from a clean `build/`/`dist/`/`outputs/`,
  scanned for `*Qt*`/`*PySide*`/`*shiboken*` with zero matches, and passed
  `verify-package.ps1` (window shows, closes cleanly, no forbidden files).
- The packaged-workflow smoke test ran against the real backup at
  `E:\WD_BACKUP\Lightroom\`: preflight reported exactly 8,099/8,099, a
  bounded 3-record recovery ran and cancelled cleanly, report counters
  matched files written, all confined to `work\smoke-output`.
- `tests/test_live_backup.py` was re-run immediately afterward and fully
  passed, proving the smoke test left the real backup unchanged.
- A fresh independent reviewer inspected the full diff and found no
  Critical/Important issues (a couple of low-severity hardening notes were
  applied: `build.ps1` now passes explicit `--distpath`/`--workpath` to
  PyInstaller, and `verify-package.ps1`'s `Compare-Object` checks are now
  case-sensitive).

**Known environment flakiness, not a code defect:** on this development
machine, `tests/test_gui.py` intermittently (roughly 1-in-5 runs) shows a
single `_tkinter.TclError` from creating many `tk.Tk()` instances in rapid
succession under pytest — root-caused to Windows Defender real-time
protection interfering with Tcl file reads under rapid file-handle churn.
It does not reproduce in a raw create/destroy loop outside pytest, and the
97 non-GUI tests are never affected. A real, separate bug in the `window`
test fixture's teardown (which could leave a Tk interpreter only
half-destroyed across tests) was found and fixed with a regression test;
that fix is unrelated to this residual environment flakiness.

The former one-file PySide6 build in `outputs\Lightroom-Preview-Recovery-Windows.zip`
has been replaced by the fresh onedir build described above.

## Test environment

Use:

```text
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe
```

This environment already contains pytest, PyInstaller, Pillow, and the earlier
GUI dependencies. Do not download or install packages unless genuinely needed
and explicitly authorized.

## Development method used on this project

This project followed a reusable gated, subagent-driven workflow:

1. **Discovery**
   - Inspect the real inputs read-only.
   - Establish counts, schema relationships, sample formats, and constraints.
2. **Design**
   - Write a durable design spec with scope, architecture, safety boundaries,
     UX, testing, packaging, and acceptance criteria.
3. **Implementation plan**
   - Split work into small tasks with owned files, interfaces, tests, commands,
     and explicit commits/checkpoints.
4. **TDD implementation**
   - Give each bounded task to a fresh implementer.
   - Require a failing test first, then the smallest robust implementation.
5. **Independent review gate**
   - Give the completed task to a different reviewer.
   - Fix every Critical or Important finding with regression tests.
   - Re-review until approved.
6. **Parallelism with discipline**
   - Run agents concurrently only when their files and dependencies are
     independent.
   - State file ownership and warn every agent not to revert others.
7. **Real-data validation**
   - Use opt-in, read-only integration tests.
   - Snapshot sources before/after.
8. **Release engineering**
   - Package only after core and GUI reviews pass.
   - Inventory licenses and package contents.
   - Launch the packaged artifact, exercise a bounded real workflow, and
     compare reports to outputs.
9. **Final review**
   - Review the entire accumulated implementation, not just the last patch.
   - Claim completion only from fresh test, package, and smoke evidence.

Recommended agent roles:

- Explorer: narrow codebase or format questions
- Worker/implementer: one bounded task with explicit file ownership
- Code reviewer: independent post-task review
- Security/performance specialist: only for high-risk areas
- Strong final reviewer: release-wide integration and packaging check

Do not spend a strong/expensive model on routine file edits. Reserve it for
architecture, unsafe I/O, concurrency, release integration, and final review.

## Reusable kickoff prompt

For a future idea-to-app project, start Codex in the target folder and use:

```text
Turn this idea into a finished, packaged application.

First inspect the available inputs read-only and write a design spec with
scope, architecture, UX, safety boundaries, tests, packaging, and acceptance
criteria. Then write a task-by-task implementation plan.

Execute the plan with bounded subagents. Give every implementation task clear
file ownership and require TDD. Use a different subagent to review each task.
Fix Critical and Important findings with regression tests and re-review before
continuing. Parallelize only independent tasks.

Finish with real-input validation, source immutability checks, package-content
and license review, a packaged-app smoke test, and a final independent review.
Do not declare completion until fresh verification passes.
```

