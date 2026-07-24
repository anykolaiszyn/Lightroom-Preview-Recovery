# Lightroom Preview Recovery Utility Design

## Purpose

Build a portable, Windows-friendly desktop utility that recovers the largest
available JPEG preview for each image in a Lightroom Classic catalog without
requiring Lightroom or Python to be installed.

The utility accepts:

- A Lightroom Classic catalog (`.lrcat`)
- Its corresponding `Previews.lrdata` directory
- A user-selected output parent directory

The utility reads the sources without modifying them, maps preview records to
catalog filenames and folders where possible, extracts the highest-resolution
valid JPEG, and produces a clear recovery report.

## Validated Source Characteristics

The design was validated read-only against the supplied backup:

- The catalog is a healthy SQLite database containing 8,099 `Adobe_images`
  records and 8,098 `AgLibraryFile` records.
- `Previews.lrdata/previews.db` is healthy and contains 8,099
  `ImageCacheEntry` records.
- All 8,099 preview `imageId` values join to `Adobe_images.id_local`.
- The first 250 preview database records tested resolved to their expected
  `.lrprev` files.
- Sample `.lrprev` records contain five or six complete JPEG streams at
  successively larger dimensions. Observed largest samples include 1280x853
  and 2136x1424.
- `root-pixels.db` is healthy and contains 8,099 records, but it is not needed
  when a usable `.lrprev` record exists.

The preview UUID does not equal `Adobe_images.id_global` in this catalog.
Mapping must therefore use `ImageCacheEntry.imageId` to
`Adobe_images.id_local`, not a UUID-to-global-ID assumption.

## Scope

### Included

- Portable unsigned Windows `.exe`
- Simple graphical interface
- Read-only catalog and preview-cache access
- Highest-resolution embedded JPEG selection
- Original filename and folder reconstruction where catalog data permits
- Safe handling of virtual copies and filename collisions
- Progress display and cancellation
- HTML, CSV, and text reports
- Automated unit and integration tests
- Packaging and simple run instructions

### Excluded from Version One

- Recovery of original RAW, JPEG, TIFF, PSD, or video files
- Reconstruction of editable Lightroom develop settings
- Scanning `Mobile Downloads.lrdata` for original assets
- Writing catalog metadata or EXIF into recovered JPEGs
- A signed installer or code-signing certificate
- Modification, repair, or upgrade of the Lightroom catalog

## User Experience

The main window contains:

1. A catalog selector for the `.lrcat` file
2. A preview-cache selector for `Previews.lrdata`
3. An output-parent-directory selector
4. A preflight summary
5. A Start Recovery button
6. A Cancel button active only during recovery
7. Progress, elapsed time, and live counters for:
   - Examined
   - Recovered
   - Unmapped
   - Skipped
   - Failed

The app never selects a location inside the source backup as the output
parent. The user must explicitly choose an output parent before starting. The
app then creates `Recovered Lightroom Previews` inside that parent.

At completion, the app displays the summary and provides buttons to open the
output folder or HTML report.

## Architecture

The project uses Python, PySide6, and PyInstaller. The packaged application does
not require Python to be installed on the destination computer.

### GUI Layer

The GUI collects paths, displays validation results and progress, starts the
recovery worker, requests cancellation, and presents the final summary. Recovery
work runs outside the GUI thread so the window remains responsive.

### Catalog Reader

The catalog reader opens the `.lrcat` database read-only and enables SQLite
query-only mode. It never issues schema or data mutations.

It builds each catalog mapping through:

```text
previews.db ImageCacheEntry.imageId
    -> Lightroom Catalog.lrcat Adobe_images.id_local
    -> Adobe_images.rootFile
    -> AgLibraryFile.id_local
    -> AgLibraryFile.folder
    -> AgLibraryFolder.id_local
    -> AgLibraryFolder.rootFolder
    -> AgLibraryRootFolder.id_local
```

The recovered filename uses `AgLibraryFile.baseName` plus `extension` when
available, then falls back to `originalFilename`, and finally to
`image-<catalog image ID>`. Its original extension is replaced with `.jpg`. A
virtual copy inserts the sanitized `Adobe_images.copyName` before `.jpg` when
present to distinguish it from its master.

The catalog reader returns structured records and does not construct output
paths or extract images.

### Preview Index

The preview index opens `Previews.lrdata/previews.db` read-only and reads
`ImageCacheEntry.imageId`, `uuid`, `digest`, and `orientation`.

It resolves primary preview records as:

```text
Previews.lrdata/
  <first UUID character>/
  <first four UUID characters>/
  <UUID>-<digest>.lrprev
```

Resolution is case-insensitive where Windows permits it. The index records a
missing-file warning rather than aborting the run.

### JPEG Extractor

The extractor scans a preview record for complete JPEG start and end markers.
For every candidate it:

- Validates JPEG framing
- Reads dimensions from a supported Start of Frame marker
- Rejects malformed or incomplete streams

It selects the candidate with the largest pixel count. Byte length breaks ties.
The selected JPEG is validated again after writing.

The extractor is independent of SQLite and output-path logic so it can be
tested using small synthetic fixtures.

### Output Manager

The selected output parent receives:

```text
Recovered Lightroom Previews/
  Photos/
    <sanitized catalog root>/
      <reconstructed folder path>/
        <original filename>.jpg
  Unmapped/
  recovery-report.html
  recovery-report.csv
  recovery-log.txt
```

Catalog root labels and path components are sanitized for Windows. Invalid
characters, reserved device names, trailing spaces, and trailing periods are
replaced safely. Each catalog root is represented by its sanitized
`AgLibraryRootFolder.name`, followed by `AgLibraryFolder.pathFromRoot`.
Absolute catalog paths cannot escape `Recovered Lightroom Previews`.

All recovered images use a `.jpg` extension because they are cached JPEG
previews, regardless of the original file type.

Files are first written under a temporary name in the destination directory,
validated, and then renamed into place. Existing files are never overwritten.
Virtual-copy names and numeric suffixes resolve collisions deterministically.

A valid preview that cannot be mapped to a catalog record is saved in
`Unmapped` using a stable UUID-and-digest filename.

Separate catalog records are retained even when their rendered JPEG bytes are
identical. The report may flag identical SHA-256 hashes but does not silently
deduplicate them.

### Report Generator

The application creates:

- `recovery-report.html`: readable summary, counts, warnings, and result table
- `recovery-report.csv`: one machine-readable row per preview record
- `recovery-log.txt`: chronological diagnostic messages

Each result record includes:

- Catalog image ID
- Preview UUID and digest
- Original catalog filename and folder, when available
- Recovered path
- JPEG width, height, and byte size
- Mapping status
- Extraction status
- SHA-256 digest
- Warning or error message

The report does not embed image data or expose files outside the selected
output tree.

## Recovery Flow

1. Validate that the catalog is a readable SQLite database.
2. Validate `Previews.lrdata`, `previews.db`, and expected tables.
3. Confirm the output parent is writable and outside both sources.
4. Run SQLite quick checks and count catalog and preview records.
5. Estimate required free space from `.lrprev` sizes and warn if space is
   insufficient or uncertain.
6. Build catalog mappings and the preview index.
7. Process records one at a time while reporting progress.
8. Check for cancellation between records and during large file reads.
9. Extract, validate, and safely finalize each recovered JPEG.
10. Write reports incrementally so a partial run remains auditable.
11. Finalize reports and display the completion or cancellation summary.

## Error Handling and Resume Behavior

- A database validation failure blocks recovery and explains the failing check.
- A missing `.lrprev`, corrupt JPEG, invalid path, or write failure affects only
  that record and is logged.
- Unexpected worker errors produce a final report with the completed results
  retained.
- Cancellation stops after the current safe file operation and finalizes a
  partial report.
- On rerun, an existing recovered file is skipped only when its stored size and
  SHA-256 digest match the expected completed result. Otherwise a collision-safe
  filename is created.
- No operation deletes, renames, or writes into the `.lrcat` or `.lrdata`
  sources.

## Testing Strategy

### Unit Tests

- JPEG stream discovery and dimension parsing
- Largest-preview selection by pixel count and byte-size tie-break
- Truncated and malformed JPEG rejection
- Lightroom database row mapping
- Filename selection and virtual-copy naming
- Windows path sanitization and output containment
- Collision handling
- Cancellation behavior
- Report generation and escaping

### Integration Tests

- Synthetic SQLite catalog and `previews.db` fixtures
- Synthetic `.lrprev` records containing multiple JPEG sizes
- A small read-only sample copied from the supplied backup
- Mapped, unmapped, missing, and corrupt preview cases
- Partial run followed by safe rerun

### Package Verification

- Build the PyInstaller executable in a clean output directory
- Launch the `.exe` without relying on an installed Python runtime
- Run a sample recovery through the GUI
- Confirm all outputs open and reports agree with recovered-file counts
- Scan the package contents for accidental inclusion of source backup data

The full 8,099-record recovery is performed by the user after selecting an
output directory; package verification does not write a full recovery set.

## Packaging

The user-facing deliverable is a ZIP containing:

```text
Lightroom Preview Recovery/
  LightroomPreviewRecovery.exe
  README.html
  LICENSES.txt
```

`README.html` explains:

- The tool recovers previews, not original files
- How to select the catalog, cache, and output directory
- Expected Windows SmartScreen behavior for an unsigned executable
- Output structure and report meanings
- How to resume a cancelled or interrupted recovery
- How to preserve the original backup untouched

## Acceptance Criteria

- Runs on 64-bit Windows 10 and Windows 11 without Lightroom or Python
  installed.
- Opens the supplied catalog and preview databases without modifying them.
- Maps all 8,099 supplied primary preview records to catalog image IDs.
- Extracts the highest-resolution valid JPEG from each usable `.lrprev`.
- Reconstructs filenames and folder paths wherever the catalog relationship is
  complete.
- Never overwrites an existing output file.
- Continues after individual corrupt or missing records.
- Produces internally consistent HTML, CSV, and text reports.
- Cancels safely and can resume without losing completed work.
- Ships as a simple portable ZIP with an unsigned `.exe` and instructions.
