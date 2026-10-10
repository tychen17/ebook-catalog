# EbookCatalog

A small, read-only desktop tool to inventory ebooks on external drives. Point it at a folder, scan, and export a CSV catalog with book name, format, and location. Handles multi-level folders and books that are split into chapters (e.g. `1.txt`, `2.txt`, ... under a folder named after the book).

## Features

- **Read-only scanning** — only walks directories and reads file names; never opens, modifies, moves, or deletes any source file
- **Manual folder selection** — works on any drive or subfolder, any nesting depth
- **Optional drive label** — type your own name for the drive (e.g. "work disk"); it is written into every row so records stay identifiable across drives
- **Relative paths in output** — locations are relative to the scanned folder, no drive letters, so records survive drive-letter changes between computers
- **Editable format list** — default: txt, pdf, epub, mobi, azw3, azw, djvu, fb2, chm, doc, docx, rtf, html, htm, md, mht, cbz, cbr
- **Multi-chapter merging** — files that look like chapters (`1.txt`, `01-intro.txt`, `第一章.txt`, `卷一.txt`, ...) in the same folder are grouped into a single book entry; the files themselves are untouched
- **Non-ebook files listed separately** — optional; other formats (images, archives, ...) appear at the end with a "non-ebook" note
- **Cancel anytime** — scanning runs in a background thread
- **CSV export** — UTF-8 with BOM, opens cleanly in Excel

## Requirements

- Windows 10 / 11
- Python 3.10+ (standard library only, no third-party dependencies) — only needed when running from source
- Or just run the prebuilt `EbookCatalog.exe` (no Python required)

## Usage

### GUI

1. Launch `EbookCatalog.exe` (or `python ebook_catalog.py`).
2. Optional: type a drive name you want to use as a label, e.g. `work disk`.
3. Click **Browse...** and pick the folder to scan (drive root or any subfolder).
4. Adjust options if needed: ebook extensions, chapter-merge threshold, whether to list non-ebook files.
5. Click **Start Scan**, then **Export CSV** and choose where to save.

### Self-test

```
python ebook_catalog.py --selftest
```

Creates a temporary folder structure, runs the scan, and asserts the expected results.

## How multi-chapter merging works

Within the same folder and format, if the number of files reaches the threshold (default 3) and at least 60% of the file names match chapter patterns, the files are merged into one book entry:


Files that do not look like chapters (e.g. `notes1.txt`, `intro.txt`) are still listed individually.

## Output columns

`Drive name | Book name | Format | Location (relative path) | Note`

## Build the executable

```
pip install pyinstaller
pyinstaller --onefile --windowed --name EbookCatalog ebook_catalog.py
```

The executable is in `dist/`.

## Notes

- The exe is a PyInstaller one-file build; some antivirus tools may flag it on first run (false positive) — add an exception if so.
- This project has no runtime dependencies beyond the Python standard library.
