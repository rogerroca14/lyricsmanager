"""Scan directories for audio files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Generator

from utils.helpers import AUDIO_EXTENSIONS


def scan_directory(
    root: Path | str,
    recursive: bool = True,
    progress_callback: Callable[[int, str], None] | None = None,
) -> Generator[Path, None, None]:
    """Yield audio file paths found under root."""
    root = Path(root)
    count = 0
    if recursive:
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                fp = Path(dirpath) / fname
                if fp.suffix.lower() in AUDIO_EXTENSIONS:
                    count += 1
                    if progress_callback:
                        progress_callback(count, str(fp))
                    yield fp
    else:
        for item in root.iterdir():
            if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
                count += 1
                if progress_callback:
                    progress_callback(count, str(item))
                yield item


def group_by_album(paths: list[Path]) -> dict[tuple[str, str], list[Path]]:
    """Group file paths by (album_artist_or_artist, album) using only path heuristics.

    For accurate grouping, prefer using full TrackMetadata objects.
    """
    from core.metadata import read_metadata

    groups: dict[tuple[str, str], list[Path]] = {}
    for path in paths:
        try:
            meta = read_metadata(path)
            key = (meta.album_artist or meta.artist or "Unknown Artist", meta.album or "Unknown Album")
        except Exception:
            key = ("Unknown Artist", "Unknown Album")
        groups.setdefault(key, []).append(path)
    return groups
