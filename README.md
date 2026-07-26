# Lightroom Preview Recovery

A small Windows tool that pulls the preview images back out of a Lightroom
Classic backup — even if you no longer have the original photos, or Lightroom
itself.

If you have an old **Lightroom Catalog Previews.lrdata** folder (and the
matching **.lrcat** catalog file) sitting on a backup drive, Lightroom already
rendered a JPEG version of every photo in there — it just doesn't let you get
it back out easily. This tool finds the biggest, best copy of each one and
saves it as a normal `.jpg` file, with your original filenames and folders
restored where possible.

**Important:** these are preview images, not your original RAW/JPEG/TIFF/PSD
files. Quality is whatever Lightroom happened to cache — usually good enough
to recognize the photo and use in a pinch, not a substitute for the original.

Your catalog and preview cache are never modified. Everything is opened
read-only; the tool only ever writes to a destination folder you choose.

## Download

No install, no Python, nothing else to set up.

1. Go to the [**Releases**](../../releases/latest) page.
2. Download `Lightroom-Preview-Recovery-Windows.zip`.
3. Unzip it anywhere (Desktop, Documents, wherever).
4. Double-click `LightroomPreviewRecovery.exe` inside the unzipped folder.

Windows may show a blue "Windows protected your PC" SmartScreen warning
because the app isn't code-signed. If you downloaded it from this page,
click **More info → Run anyway**.

## How to use it

You need two things from your Lightroom backup, sitting next to each other:

- The catalog file — something like `Lightroom Catalog.lrcat`
- The matching preview folder — `Lightroom Catalog Previews.lrdata`

**Steps:**

1. Open the app.
2. **Catalog (.lrcat)** — browse to your `.lrcat` file.
3. **Preview cache (.lrdata)** — browse to the `Lightroom Catalog
   Previews.lrdata` folder next to it.
4. **Destination folder** — pick somewhere *else entirely* to save the
   recovered photos. Not inside the catalog or the preview folder.
5. Click **Start recovery**. It'll first tell you how many photos it found —
   that number should roughly match what you remember having.
6. Watch it work. You can click **Cancel**, or just close the window, at any
   time — it finishes whatever it's currently saving and stops cleanly. No
   half-written files.

When it's done, click **Open output** to see your recovered photos, or
**Open report** for a summary page of everything it did.

### Where your photos end up

```text
Recovered Lightroom Previews/
  Photos/
    <your Lightroom folder structure>/
      <original filename>.jpg
  Unmapped/                  ← recovered, but no original filename was found
  recovery-report.html       ← open this in a browser for a full summary
  recovery-report.csv
  recovery-report.log
```

### What the statuses mean

| Status | What it means |
|---|---|
| **Recovered** | Matched to your original filename and folder |
| **Unmapped** | A real photo was recovered, but no catalog match was found — saved in `Unmapped/` |
| **Skipped** | Already recovered in an earlier run; verified and left alone |
| **Failed** | That one file was unreadable or corrupted — everything else keeps going |

### Stopped partway through? Just run it again

Point the app at the same catalog, preview folder, and destination a second
time. Anything already recovered is verified and skipped — only what's
missing gets processed. Nothing gets overwritten or duplicated.

## Troubleshooting

- **"Cannot start" / a path error** — the destination folder can't be inside
  the catalog folder or the `.lrdata` preview folder. Pick a separate location.
- **The photo count looks off** — that's shown as a warning, not an error. It
  usually just means a photo was added or removed from the catalog after the
  last time Lightroom generated previews for it.
- **Not enough space** — the app checks free space before writing anything
  and will tell you up front if there isn't enough.

## Support this project

If this saved photos you thought were gone, and you'd like to say thanks:

**[☕ Buy me a coffee](https://buymeacoffee.com/alexnyk)**

## For developers

Building from source, running tests, and the internal architecture are
documented in [`AGENTS.md`](AGENTS.md) and [`CLAUDE.md`](CLAUDE.md). Short
version:

```powershell
git clone https://github.com/anykolaiszyn/Lightroom-Preview-Recovery.git
cd Lightroom-Preview-Recovery
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\scripts\build.ps1
```

This runs the test suite, builds a self-contained PyInstaller package (no
Qt, no external dependencies — just Python's built-in `tkinter`), and zips it
up under `outputs\`.

## License

MIT — see [`assets/LICENSE`](assets/LICENSE). Third-party notices for the
bundled Python/Tcl-Tk/OpenSSL/PyInstaller runtime are in
[`assets/LICENSES.txt`](assets/LICENSES.txt).
