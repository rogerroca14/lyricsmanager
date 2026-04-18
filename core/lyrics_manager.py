"""Orchestrate lyrics searching and saving across multiple services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import get_config
from utils.helpers import sanitize_filename
from core.metadata import embed_lyrics_in_metadata


@dataclass
class LyricsResult:
    synced: str | None      # LRC-formatted
    plain: str | None
    source: str
    title: str = ""
    artist: str = ""
    album: str = ""

    @property
    def has_synced(self) -> bool:
        return bool(self.synced and self.synced.strip())

    @property
    def has_plain(self) -> bool:
        return bool(self.plain and self.plain.strip())


def fetch_lyrics(
    title: str,
    artist: str,
    album: str = "",
    duration: float | None = None,
) -> LyricsResult | None:
    """Try each configured lyrics source in order and return the first hit."""
    cfg = get_config()
    sources = cfg.get("lyrics_sources") or ["lrclib", "netease"]

    for source in sources:
        result = _fetch_from_source(source, title, artist, album, duration)
        if result:
            return result
    return None


def _fetch_from_source(
    source: str,
    title: str,
    artist: str,
    album: str,
    duration: float | None,
) -> LyricsResult | None:
    try:
        if source == "lrclib":
            from services.lrclib import get_lyrics, search_by_fields
            r = get_lyrics(title, artist, album, duration)
            if r and (r.has_synced or r.has_plain):
                return LyricsResult(
                    synced=r.synced_lyrics,
                    plain=r.plain_lyrics,
                    source="lrclib",
                    title=r.title,
                    artist=r.artist,
                    album=r.album,
                )
            # Fall back to search
            results = search_by_fields(title=title, artist=artist, album=album)
            for candidate in results:
                if candidate.has_synced or candidate.has_plain:
                    return LyricsResult(
                        synced=candidate.synced_lyrics,
                        plain=candidate.plain_lyrics,
                        source="lrclib",
                        title=candidate.title,
                        artist=candidate.artist,
                        album=candidate.album,
                    )

        elif source == "netease":
            from services.netease import search_and_fetch
            r = search_and_fetch(title, artist, album)
            if r and (r.has_synced or r.has_plain):
                return LyricsResult(
                    synced=r.synced_lyrics,
                    plain=r.plain_lyrics,
                    source="netease",
                    title=r.title,
                    artist=r.artist,
                    album=r.album,
                )
    except Exception:
        pass
    return None


def save_lyrics(audio_path: Path | str, result: LyricsResult) -> tuple[bool, str]:
    """Save lyrics according to user config. Returns (success, message)."""
    audio_path = Path(audio_path)
    cfg = get_config()
    mode = cfg.get("lyrics_save_mode")   # "lrc" or "metadata"

    content = result.synced if result.has_synced else result.plain
    if not content:
        return False, "No lyrics content to save."

    if mode == "lrc":
        return _save_lrc_file(audio_path, content, result.has_synced)
    else:
        is_synced = result.has_synced
        ok = embed_lyrics_in_metadata(audio_path, content, is_synced)
        return ok, "Saved to metadata." if ok else "Failed to embed in metadata."


def _save_lrc_file(audio_path: Path, content: str, is_synced: bool) -> tuple[bool, str]:
    cfg = get_config()
    if cfg.get("lrc_same_folder"):
        out_dir = audio_path.parent
    else:
        custom = cfg.get("lrc_output_folder")
        out_dir = Path(custom) if custom else audio_path.parent

    out_dir.mkdir(parents=True, exist_ok=True)
    ext = ".lrc" if is_synced else ".txt"
    lrc_path = out_dir / (audio_path.stem + ext)

    try:
        lrc_path.write_text(content, encoding="utf-8")
        return True, f"Saved to {lrc_path.name}"
    except OSError as e:
        return False, str(e)


def lrc_exists(audio_path: Path | str) -> bool:
    audio_path = Path(audio_path)
    return (audio_path.parent / (audio_path.stem + ".lrc")).exists()


def read_lrc_file(audio_path: Path | str) -> str | None:
    audio_path = Path(audio_path)
    lrc_path = audio_path.parent / (audio_path.stem + ".lrc")
    if lrc_path.exists():
        return lrc_path.read_text(encoding="utf-8")
    return None
