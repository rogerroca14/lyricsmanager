"""Application configuration management."""

import json
import os
from pathlib import Path
from typing import Any


APP_NAME = "LyricsManager"
APP_VERSION = "1.0.0"

CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULTS: dict[str, Any] = {
    "lyrics_save_mode": "lrc",
    "lrc_same_folder": True,
    "lrc_output_folder": "",
    "prefer_plain_lyrics": True,            # prefer plain over synced LRC
    "artwork_save_cover_png": True,
    "artwork_embed_metadata": True,
    "artwork_overwrite": False,
    "artwork_resize_cover": False,   # downscale cover.png to artwork_cover_max_size
    "artwork_cover_max_size": 600,   # px — applied to longest side, never upscales
    "last_library_path": "",
    "window_geometry": None,
    "theme": "dark",
    "language": "es",                       # "es" | "en"
    "musicbrainz_useragent": f"{APP_NAME}/{APP_VERSION} (contact@example.com)",
    "lyrics_sources": ["lrclib", "netease"],
    "artwork_sources": ["coverart", "itunes"],
    "hires_sample_rate_threshold": 88200,
    "hires_bit_depth_threshold": 24,
    "audio_output_device": None,            # None = system default
}


class Config:
    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        with CONFIG_FILE.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self.save()


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
