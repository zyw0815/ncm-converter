**English** | [中文](README.zh-CN.md)

# NCM Converter

Convert NetEase Cloud Music `.ncm` files into audio that any player can open, while fully preserving title, artist, album and cover art. Cross-platform (macOS / Windows) with a clean graphical interface.

## Features

- **Original format first**: if the NCM holds FLAC it outputs FLAC, if it holds MP3 it outputs MP3 — no re-encoding, no quality change.
- **Safe handling of special formats**: non-standard containers (e.g. spatial audio) are exported as-is in their real format and flagged in the UI, never force-converted or turned into broken files.
- **Batch conversion**: drag in files or folders (all `.ncm` are scanned recursively), processed in parallel.
- **Preview before converting**: the list shows the detected title / artist / album / format / cover up front.
- **Full metadata**: title, artist, album and cover written back into FLAC / MP3.
- **Thoughtful options**: custom naming templates, preserve source folder structure, output conflict policy (skip / overwrite / rename), optional convert-to-WAV, optional delete-source-after-success (with a first-time confirmation), light / dark theme, retry failed items, one-click open output folder.

## Requirements & Installation

Requires Python 3.9+.

```bash
pip install -r requirements.txt
```

Optional: install [ffmpeg](https://ffmpeg.org/) to enable the "convert to WAV" feature; everything else works without it.

## Run

```bash
python main.py
```

## Packaging

Build with PyInstaller using the bundled spec (run on macOS for a `.app`, on Windows for an `.exe`):

```bash
pip install -r requirements-dev.txt
pyinstaller build.spec
```

The output is placed in the `dist/` directory.

## Notes

This tool is for converting music you have already downloaded / purchased yourself into a common format so you can play it in other players. For personal use only.

**This software must not be used for any commercial purpose.**
