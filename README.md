**English** | [中文](README.zh-CN.md)

# NCM Converter

Convert NetEase Cloud Music `.ncm` files into audio that any player can open, while fully preserving title, artist, album and cover art. Cross-platform (macOS / Windows) with a clean graphical interface.

## Features

- **Lossless by design**: NCM is an encrypted wrapper around the original audio, not a codec. The app decrypts and writes the original stream untouched — FLAC stays FLAC, bit-for-bit identical, with no quality change.
- **Fast & smooth**: the decryption keystream is periodic (256 bytes), so it is precomputed once and applied with a vectorized numpy XOR that releases the GIL. A 24-bit/192 kHz track decrypts in ~0.25 s, and the interface stays responsive even when converting many large files at once.
- **Original format first**: FLAC → FLAC, MP3 → MP3 — no re-encoding.
- **MP3 / FLAC passthrough**: existing `.mp3` and `.flac` files are accepted and passed through unchanged (not re-encoded) — they can still be renamed, have lyrics added, and be copied by default (or moved when "delete source" is on).
- **Special formats handled safely**: spatial / Dolby audio is exported as-is (`.m4a`) and flagged, never force-converted into broken files.
- **Batch & queue management**: drag in files or folders (recursive scan), a numbered list, multi-threaded conversion with per-file progress and a live spinner; remove selected items (Delete / Backspace) or clear all.
- **Preview before converting**: title / artist / album / format / cover thumbnail shown up front.
- **Metadata & cover**: written back into FLAC / MP3; non-RGB covers are normalized to RGB so players display them.
- **Lyrics**: if a same-named `.lrc` sits next to the source, it can be added to the result — as an external sidecar `.lrc` (recommended, best player compatibility) or embedded inside the file. NetEase JSON lines are cleaned, timed lines kept.
- **Thoughtful options**: naming templates, preserve folder structure, conflict policy (overwrite / rename / skip), optional convert-to-WAV (auto-disabled when ffmpeg is missing), optional delete-source (also removes the matching `.lrc`), light / dark theme, retry failed, one-click open output folder — with a **?** help button next to each option.

## Screenshot

![NCM Converter](assets/screenshot.png)

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

PyInstaller cannot cross-compile, so a macOS `.app` must be built on macOS and a Windows `.exe` on Windows. To build automatically, push a `v*` tag (e.g. `v1.0.0`): GitHub Actions builds a macOS (Apple Silicon, arm64) package and a Windows package and attaches them to the release. You can also trigger the workflow manually from the Actions tab.

Intel Macs: the arm64 build runs only on Apple Silicon. GitHub's free Intel macOS runners are scarce and being retired, so CI does not produce an Intel (x86_64) build. If you need one, build it on an Intel Mac with `pyinstaller build.spec` (that build also runs on Apple Silicon via Rosetta).

## Metadata & cover art

Title, artist, album and cover are preserved where the output format allows:

- **FLAC / MP3**: title, artist, album and cover art are fully written back.
- **WAV**: the WAV format does not support embedded cover art or tags, so converting to WAV loses this information. If you need full metadata and cover, keep the original FLAC instead of converting to WAV.
- **m4a (spatial / immersive audio)**: exported as-is as a special format; tags and cover are not re-written.

## Spatial / immersive audio (Dolby)

NetEase "spatial audio / 沉浸声" (Dolby) downloads are delivered as `.m4a` (an object-based spatial stream). The converter exports them **as-is** and flags them as a special format. They **cannot be converted to FLAC**: FLAC is plain PCM and cannot carry object-based spatial audio, so any conversion would downmix to stereo and lose the immersive effect. Some players also cannot play these `.m4a` files. If you need FLAC output, adding spatial-audio tracks is not recommended.

## Notes

This tool is for converting music you have already downloaded / purchased yourself into a common format so you can play it in other players. For personal use only.

**This software must not be used for any commercial purpose.**
