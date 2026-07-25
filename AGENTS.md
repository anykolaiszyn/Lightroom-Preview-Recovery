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

## Current unfinished state

The first PySide6 one-file build passed 102 tests but must not ship. Release
review found that it bundled unused Qt PDF/Virtual Keyboard components and did
not provide a satisfactory LGPL relinking/source mechanism. It also exposed a
PyInstaller one-file process-tree verification problem.

The current `outputs\Lightroom-Preview-Recovery-Windows.zip` is that rejected
build. Do not deliver or rely on it.

To remove the Qt redistribution burden, the GUI is being migrated from PySide6
to standard-library `tkinter`/`ttk`:

```text
src\lightroom_preview_recovery\gui.py
src\lightroom_preview_recovery\worker.py
src\lightroom_preview_recovery\main.py
tests\test_gui.py
```

The migration agent was interrupted by an account usage limit after writing the
new implementation and tests.

Current fresh verification:

```text
85 passed
1 optional live-source test skipped
13 GUI setup errors
```

The GUI errors occur before test logic because the installed Tcl scripts and
loaded Tcl runtime do not match:

```text
_tkinter.TclError: Can't find a usable init.tcl
```

Known local paths:

```text
Python:
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe

Base Python:
C:\Users\alexn\AppData\Local\Programs\Python\Python312\python.exe

Tcl scripts:
C:\Users\alexn\AppData\Local\Programs\Python\Python312\tcl\tcl8.6

Tk scripts:
C:\Users\alexn\AppData\Local\Programs\Python\Python312\tcl\tk8.6
```

`init.tcl` requires Tcl 8.6.15, but even base Python fails to initialize Tk
with those scripts. Treat this as a local Tcl/Tk installation mismatch, not an
application-test failure.

## Next actions, in order

1. Inspect the uncommitted Tk GUI, worker, entry point, and GUI tests.
2. Resolve the local Tcl/Tk mismatch using a matching runtime or a repaired
   Python Tcl/Tk installation. Do not copy random Tcl files from the internet.
3. Run:

   ```powershell
   C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m pytest tests\test_gui.py -v
   C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m pytest -q
   ```

4. Have a fresh reviewer inspect the Tk migration, especially:
   - no UI access from the worker thread
   - queue polling and scalar progress snapshots
   - cancellation and close-during-run behavior
   - no non-daemon worker left behind
   - startup/preflight exception cleanup
   - exact zero-preview progress behavior
   - output/report buttons gated by path existence
5. Rework packaging as PyInstaller **onedir**, not onefile.
6. Exclude PySide6, Shiboken6, Qt, and other unused frameworks completely.
7. Make `scripts\build.ps1` portable:
   - accept a `-Python` parameter
   - support an environment override
   - fall back to a project `.venv`
   - delete/recreate only the exact build/staging directories
8. Inventory every redistributed native library. Include exact project,
   Python, Tcl/Tk, PyInstaller, and any actually bundled third-party notices.
   Remove all obsolete Qt notices.
9. Make `scripts\verify-package.ps1` fail closed on unexpected package files,
   source-backup names/data, failed startup, or unclean shutdown.
10. Build a new ZIP and run the packaged GUI smoke test:
    - select the supplied catalog and preview cache
    - confirm preflight reports 8,099 / 8,099
    - write only under `work\smoke-output`
    - stop after at most three records
    - compare report counters with recovered files
11. Re-run the live-source immutability proof.
12. Obtain a fresh final code/package review before claiming completion.

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

