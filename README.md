# LyricsManager — Audiophile Edition

A polished desktop application for managing lyrics and artwork in a high-resolution music library. Built with PyQt6 for Windows, designed around the needs of audiophiles who care about metadata quality.

---

## Features

### Library Management
- **Recursive folder scan** — indexes any directory containing FLAC, ALAC, WAV, AIFF, MP3, AAC, OGG, WMA, DSD (DSF/DFF)
- **Artist → Album → Track** tree with instant filter / search
- **Quality-tier icons** per track using colour-coded disc badges:
  - 🟡 **DSD** (dark gold) — native DSD files
  - 🟡 **Hi-Res** (gold) — PCM ≥ 88.2 kHz or ≥ 24-bit
  - 🔵 **Lossless** (blue) — 44.1/48 kHz 16-bit lossless
  - 🟣 **MQA** — MQA-encoded files
  - ⚫ **Lossy** — MP3, AAC, OGG, etc.
- **Per-track lyrics-status icons** updated in real time during batch operations (searching, found synced/plain, not found)

### Lyrics
- **Multi-source search**: [LRCLIB](https://lrclib.net) · [NetEase Cloud Music](https://music.163.com) (with duration matching)
- **Configurable source priority** in Settings
- **Synchronized (.lrc) preview** — lyrics scroll and highlight in sync with playback; lines highlighted in accent blue
- **Save as .lrc file** (same folder or custom folder) or **embed in metadata**
- **Prefer plain lyrics** option to skip timestamps when available
- **Batch fetch** for entire albums or folders from the context menu, with live per-track status feedback

### Artwork
- **Streaming search dialog** — opens immediately and populates artwork cards one by one as results arrive
- **Multi-source search**: [Cover Art Archive](https://coverartarchive.org) / MusicBrainz · iTunes
- **ArtworkSaveDialog** — preview at full resolution with a live-updating resize slider (100 px → original size) before saving
- **Save as `cover.png`** alongside the audio files
- **Embed in metadata** (FLAC PICTURE block, ID3 APIC, M4A covr)
- **Extract embedded → `cover.png`** with the same resize/preview flow
- **Zero re-encoding for PNG source** — raw bytes are written directly; only JPEG→PNG conversion when needed

### Audio Playback
- **In-app synchronized preview** — plays the actual audio file while the lyrics panel scrolls in sync
- **Device selection** — lists all WASAPI, DirectSound, MME and WDM-KS output devices; persists across sessions
- Play / Pause / Stop controls with Font Awesome icons

### Metadata Viewer
- **Rich header card**: album art thumbnail · track title · artist · album · year · quality badge · LRC / ART presence badges
- **Track Info** and **Audio Specifications** displayed side-by-side in clean form layouts
- **Collapsible Raw Tags** section (toggle ▶ / ▼) showing all metadata fields in monospace
- Artwork sourced from embedded data or `cover.png` in the same folder

### Settings
- Lyrics save mode (`.lrc` file / embedded metadata)
- `.lrc` output folder (same as audio / custom)
- Prefer plain lyrics
- Lyrics source priority (drag-reorder list)
- Artwork save options (save PNG / embed / overwrite / max resize size)
- Artwork source priority
- Hi-Res detection thresholds (sample rate + bit depth)
- MusicBrainz User-Agent
- Audio output device
- Interface language (English / Spanish)

---

## Screenshots

> _Add screenshots here once the app is running on your system._

---

## Requirements

| Dependency | Minimum version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| PyQt6 | 6.4 | GUI framework |
| qtawesome | 1.3 | Font Awesome icons |
| mutagen | 1.46 | Audio metadata read/write |
| Pillow | 10.0 | Image processing / PNG conversion |
| requests | 2.28 | HTTP calls to lyrics & artwork APIs |
| sounddevice | 0.4.6 | Audio output streaming |
| soundfile | 0.12.1 | FLAC / WAV / AIFF decoding |

---

## Installation

```bash
# 1. Clone
git clone https://github.com/rogerroca/lyricsmanager.git
cd lyricsmanager

# 2. Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate      # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

> **Windows note:** `sounddevice` requires the Microsoft Visual C++ Redistributable. Download it from [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe) if playback fails on first run.

---

## Project Structure

```
app_lyrics/
├── main.py                   # Entry point — QApplication, theme, language
├── config.py                 # JSON settings persistence (%APPDATA%\LyricsManager)
├── requirements.txt
├── assets/
│   └── check.svg             # White checkmark for checkbox indicator
├── core/
│   ├── metadata.py           # read_metadata(), embed_artwork/lyrics, AudioQuality
│   ├── music_scanner.py      # Recursive directory scan for audio files
│   ├── lyrics_manager.py     # fetch_lyrics() — multi-source orchestration
│   └── artwork_manager.py    # ArtworkResult, fetch/save/embed artwork
├── services/
│   ├── lrclib.py             # LRCLIB REST API
│   ├── netease.py            # NetEase Cloud Music API
│   ├── musicbrainz.py        # MusicBrainz release search
│   ├── coverart.py           # Cover Art Archive download
│   └── itunes.py             # iTunes Search API
├── ui/
│   ├── theme.py              # Dark stylesheet + badge helpers, build_stylesheet()
│   ├── main_window.py        # QMainWindow — toolbar, menu, layout, worker wiring
│   ├── library_view.py       # QTreeView panel with quality icons + status icons
│   ├── metadata_view.py      # Track info panel with artwork, badges, collapsible tags
│   ├── lyrics_view.py        # Lyrics panel — sync preview + player controls
│   ├── artwork_view.py       # Artwork panel — embedded + search buttons
│   ├── artwork_search_dialog.py  # Streaming search dialog with card grid
│   ├── artwork_save_dialog.py    # Resize/preview dialog before saving artwork
│   ├── settings_dialog.py    # Tabbed settings dialog
│   ├── workers.py            # QThread workers: Scan, Metadata, Lyrics, Artwork, Batch
│   └── player.py             # AudioPlayer — sounddevice streaming, device management
├── i18n/
│   ├── __init__.py           # t(key) lookup + set_language()
│   └── strings.py            # Full EN + ES translation dictionaries
└── utils/
    └── helpers.py            # AUDIO_EXTENSIONS, format_duration, etc.
```

---

## Supported Formats

| Format | Read | Write lyrics | Write artwork |
|--------|------|-------------|---------------|
| FLAC | ✅ | ✅ | ✅ |
| ALAC (M4A) | ✅ | ✅ | ✅ |
| MP3 | ✅ | ✅ (ID3) | ✅ (ID3 APIC) |
| AAC (M4A) | ✅ | ✅ | ✅ |
| OGG Vorbis | ✅ | ✅ | ✅ |
| WAV | ✅ | — | — |
| AIFF | ✅ | — | — |
| DSD (DSF/DFF) | ✅ | — | — |
| WMA | ✅ | — | — |

---

## Configuration

Settings are stored at `%APPDATA%\LyricsManager\settings.json`. Defaults:

```json
{
  "lyrics_save_mode": "lrc",
  "lrc_output_mode": "same_folder",
  "prefer_plain_lyrics": false,
  "lyrics_sources": ["lrclib", "netease"],
  "artwork_save_cover_png": true,
  "artwork_embed_metadata": false,
  "artwork_overwrite": false,
  "artwork_resize_cover": false,
  "artwork_cover_max_size": 600,
  "artwork_sources": ["coverart", "itunes"],
  "hires_sample_rate_threshold": 88200,
  "hires_bit_depth_threshold": 24,
  "audio_output_device": null,
  "language": "es"
}
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Open library folder |
| `Ctrl+L` | Fetch lyrics for current track |
| `Ctrl+I` | Fetch artwork for current track |
| `Ctrl+,` | Open Settings |
| `Ctrl+Q` | Quit |

---

## Architecture Notes

- All network calls run in **QThread workers** — the UI never blocks.
- `BatchLyricsWorker` emits `track_started / track_done / track_failed` per track, so the library tree updates in real time.
- `ArtworkStreamWorker` emits `result_found(ArtworkResult)` as each source returns; the search dialog inserts cards immediately as they arrive.
- `ArtworkSaveDialog` applies a 120 ms debounce before re-rendering the resize preview to keep the UI responsive.
- The stylesheet is built at startup via `build_stylesheet(base_dir)` which resolves the `assets/check.svg` path, giving checkboxes a proper white checkmark on the blue indicator.

---

## Contributing

Pull requests are welcome. For major changes please open an issue first to discuss what you'd like to change.

---

## License

MIT — see `LICENSE` for details.
