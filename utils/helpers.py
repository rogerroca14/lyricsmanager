"""Miscellaneous utility functions."""

import re
from pathlib import Path


AUDIO_EXTENSIONS = {".flac", ".mp3", ".aac", ".m4a", ".ogg", ".opus", ".wav", ".aiff", ".dsf", ".dff", ".wv", ".ape"}


def is_audio_file(path: Path | str) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def format_file_size(bytes_: int | None) -> str:
    if bytes_ is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def format_bitrate(bps: int | None) -> str:
    if bps is None:
        return "—"
    return f"{bps // 1000} kbps"


def sanitize_filename(name: str) -> str:
    """Strip characters illegal on Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def parse_lrc_line(line: str) -> tuple[float | None, str]:
    """Parse a single LRC line into (timestamp_seconds, text).

    Returns (None, line) for non-timed lines.
    """
    match = re.match(r"^\[(\d{1,3}):(\d{2})\.(\d{1,3})\](.*)", line)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        centis = int(match.group(3).ljust(2, "0")[:2])
        text = match.group(4)
        total = minutes * 60 + seconds + centis / 100
        return total, text
    return None, line


def parse_lrc(content: str) -> list[tuple[float, str]]:
    """Parse full LRC content into sorted [(timestamp, text)] list."""
    lines = []
    for raw in content.splitlines():
        ts, text = parse_lrc_line(raw)
        if ts is not None:
            lines.append((ts, text))
    lines.sort(key=lambda x: x[0])
    return lines


def seconds_to_lrc_timestamp(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"[{m:02d}:{s:05.2f}]"
