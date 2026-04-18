"""LRCLIB API client — https://lrclib.net/api"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://lrclib.net/api"
TIMEOUT = 10


@dataclass
class LrcLibResult:
    id: int
    title: str
    artist: str
    album: str
    duration: float | None
    synced_lyrics: str | None       # LRC-formatted
    plain_lyrics: str | None
    source: str = "lrclib"

    @property
    def has_synced(self) -> bool:
        return bool(self.synced_lyrics and self.synced_lyrics.strip())

    @property
    def has_plain(self) -> bool:
        return bool(self.plain_lyrics and self.plain_lyrics.strip())


def _parse_result(data: dict[str, Any]) -> LrcLibResult:
    return LrcLibResult(
        id=data.get("id", 0),
        title=data.get("trackName", ""),
        artist=data.get("artistName", ""),
        album=data.get("albumName", ""),
        duration=data.get("duration"),
        synced_lyrics=data.get("syncedLyrics"),
        plain_lyrics=data.get("plainLyrics"),
    )


def get_lyrics(
    title: str,
    artist: str,
    album: str = "",
    duration: float | None = None,
) -> LrcLibResult | None:
    """Fetch lyrics using the LRCLIB /get endpoint (exact match preferred)."""
    params: dict[str, Any] = {
        "track_name": title,
        "artist_name": artist,
    }
    if album:
        params["album_name"] = album
    if duration is not None:
        params["duration"] = int(duration)

    try:
        resp = requests.get(f"{BASE_URL}/get", params=params, timeout=TIMEOUT)
        if resp.status_code == 200:
            return _parse_result(resp.json())
    except requests.RequestException:
        pass
    return None


def search_lyrics(query: str) -> list[LrcLibResult]:
    """Full-text search across LRCLIB."""
    try:
        resp = requests.get(f"{BASE_URL}/search", params={"q": query}, timeout=TIMEOUT)
        if resp.status_code == 200:
            return [_parse_result(item) for item in resp.json()]
    except requests.RequestException:
        pass
    return []


def search_by_fields(
    title: str = "",
    artist: str = "",
    album: str = "",
) -> list[LrcLibResult]:
    params: dict[str, str] = {}
    if title:
        params["track_name"] = title
    if artist:
        params["artist_name"] = artist
    if album:
        params["album_name"] = album
    try:
        resp = requests.get(f"{BASE_URL}/search", params=params, timeout=TIMEOUT)
        if resp.status_code == 200:
            return [_parse_result(item) for item in resp.json()]
    except requests.RequestException:
        pass
    return []
