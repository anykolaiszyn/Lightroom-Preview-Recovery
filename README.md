# Lightroom Preview Recovery

You found an old hard drive with a Lightroom backup. The RAW files are long gone. But Lightroom already rendered a JPEG of every photo and cached it — you just can't see it in the app anymore. This tool extracts those cached JPEGs and saves them as normal image files with your original folder structure and filenames intact.

If you have a **Lightroom Catalog Previews.lrdata** folder (and its matching **.lrcat** catalog file) sitting somewhere on a backup, that's all you need. This tool reads both, finds the best cached copy of each photo, and hands you back a folder of JPEGs. No Lightroom install required. No special knowledge. Just point it at the files, click go, and wait.

**Important:** these are preview images, not your original RAW/JPEG/TIFF/PSD files. Quality is whatever Lightroom happened to cache — usually good enough to recognize the photo and use in a pinch, not a substitute for the original.

Your catalog and preview cache are never modified. Everything is opened read-only; the tool only ever writes to a destination folder you choose.

## Download

Nothing to install. No Python to set up. Just download and run.

1. Go to the [**Releases**](../../releases/latest) page.
2. Download `Lightroom-Preview-Recovery-Windows.zip`.
3. Unzip it anywhere (Desktop, Documents, wherever).
4. Double-click `LightroomPreviewRecovery.exe` inside the unzipped folder.

Windows may show a blue "Windows protected your PC" SmartScreen warning because the app isn't code-signed. If you downloaded it from this page, click **More info → Run anyway**. (It's safe — the code is right here on GitHub.)

## How to use it

You need two things from your Lightroom backup — find them sitting next to each other on your backup drive:

- The catalog file — looks like `Lightroom Catalog.lrcat`
- The preview folder — `Lightroom Catalog Previews.lrdata` (a folder, not a file)

**Steps:**

1. Open the app.
2. **Catalog (.lrcat)** — browse to and select your `.lrcat` file.
3. **Preview cache (.lrdata)** — browse to the `Lightroom Catalog Previews.lrdata` folder.
4. **Destination folder** — pick a new, empty folder somewhere else entirely. Not inside the catalog or preview folder — just a clean place to dump the recovered photos.
5. Click **Start recovery**. The app will count the photos first and show you the number — if it matches roughly what you remember, you're in good shape.
6. Let it work. You can stop anytime by clicking **Cancel** or just closing the window — it'll finish saving whatever it's currently working on and stop cleanly. No orphaned or half-written files.

When it's done, click **Open output** to look at your recovered photos, or **Open report** to see a full summary of what got recovered, what was skipped, and what couldn't be read.

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

### Stopped midway? Just run it again

Run the app a second time with the same catalog, preview folder, and destination. Already-recovered photos get checked and left alone — only what's missing gets processed. Nothing gets overwritten or duplicated, so it's safe to re-run.

## Troubleshooting

- **"Cannot start" / a path error** — the destination folder can't be nested inside the catalog folder or the preview folder. Pick a completely separate location.
- **The photo count looks off** — shown as a warning, not an error. Usually just means a photo was added to or removed from the catalog after Lightroom last generated previews for it.
- **Not enough space** — the app checks free disk space upfront and tells you immediately if there isn't enough. You'll need roughly the total size of all the preview images to save.

## Support this project

If this got your photos back from a backup you'd nearly written off, and it saved you from starting from scratch — or just cost you nothing and actually worked — a quick coffee tip would mean a lot. The fact that you're reading this probably means it helped, and I built it specifically for situations like yours.

**[☕ Buy me a coffee](https://buymeacoffee.com/alexnyk)**

## For developers

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
