"""NetEase Cloud Music API client (public, no auth required).

Uses the public NeteaseCloudMusicApi endpoints for lyrics lookup as a
secondary source when LRCLIB returns no results.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import requests

BASE_SEARCH = "https://music.163.com/api/search/get"
BASE_LYRIC = "https://music.163.com/api/song/lyric"
TIMEOUT = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://music.163.com/",
}


@dataclass
class NeteaseResult:
    song_id: int
    title: str
    artist: str
    album: str
    synced_lyrics: str | None
    plain_lyrics: str | None
    source: str = "netease"

    @property
    def has_synced(self) -> bool:
        return bool(self.synced_lyrics and self.synced_lyrics.strip())

    @property
    def has_plain(self) -> bool:
        return bool(self.plain_lyrics and self.plain_lyrics.strip())


def _lrc_to_plain(lrc: str) -> str:
    """Strip LRC timestamps, returning plain text."""
    lines = []
    for line in lrc.splitlines():
        clean = re.sub(r"\[\d+:\d+\.\d+\]", "", line).strip()
        if clean:
            lines.append(clean)
    return "\n".join(lines)


def search(title: str, artist: str = "", album: str = "") -> list[NeteaseResult]:
    query = f"{artist} {title}".strip() if artist else title
    try:
        resp = requests.post(
            BASE_SEARCH,
            data={"s": query, "type": 1, "limit": 5, "offset": 0},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        songs = data.get("result", {}).get("songs", [])
    except Exception:
        return []

    results = []
    for song in songs:
        song_id = song.get("id")
        if not song_id:
            continue
        t = song.get("name", "")
        artists = "/".join(a.get("name", "") for a in song.get("artists", []))
        alb = song.get("album", {}).get("name", "")
        results.append(NeteaseResult(
            song_id=song_id,
            title=t,
            artist=artists,
            album=alb,
            synced_lyrics=None,
            plain_lyrics=None,
        ))
    return results


def get_lyrics(song_id: int) -> NeteaseResult | None:
    """Fetch lyrics for a specific Netease song ID."""
    try:
        resp = requests.get(
            BASE_LYRIC,
            params={"id": song_id, "lv": 1, "kv": 1, "tv": -1},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        synced = data.get("lrc", {}).get("lyric")
        plain = _lrc_to_plain(synced) if synced else None
        return NeteaseResult(
            song_id=song_id,
            title="",
            artist="",
            album="",
            synced_lyrics=synced,
            plain_lyrics=plain,
        )
    except Exception:
        return None


def search_and_fetch(title: str, artist: str = "", album: str = "") -> NeteaseResult | None:
    candidates = search(title, artist, album)
    if not candidates:
        return None
    best = candidates[0]
    lyrics = get_lyrics(best.song_id)
    if lyrics:
        lyrics.title = best.title
        lyrics.artist = best.artist
        lyrics.album = best.album
    return lyrics
