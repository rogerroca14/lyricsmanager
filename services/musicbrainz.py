"""MusicBrainz API client for release lookups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from config import get_config

BASE_URL = "https://musicbrainz.org/ws/2"
TIMEOUT = 10


@dataclass
class MBRelease:
    mbid: str
    title: str
    artist: str
    date: str
    country: str
    label: str
    barcode: str
    format: str     # "CD", "Vinyl", etc.
    track_count: int


def _headers() -> dict[str, str]:
    ua = get_config().get("musicbrainz_useragent")
    return {"User-Agent": ua, "Accept": "application/json"}


def search_release(album: str, artist: str = "", limit: int = 5) -> list[MBRelease]:
    query_parts = [f'release:"{album}"']
    if artist:
        query_parts.append(f'artist:"{artist}"')
    query = " AND ".join(query_parts)
    try:
        resp = requests.get(
            f"{BASE_URL}/release",
            params={"query": query, "limit": limit, "fmt": "json"},
            headers=_headers(),
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        releases = resp.json().get("releases", [])
        return [_parse_release(r) for r in releases]
    except Exception:
        return []


def _parse_release(data: dict[str, Any]) -> MBRelease:
    artist = ""
    credits = data.get("artist-credit", [])
    if credits:
        artist = credits[0].get("artist", {}).get("name", "")

    label = ""
    label_info = data.get("label-info", [])
    if label_info:
        label = label_info[0].get("label", {}).get("name", "")

    media = data.get("media", [])
    track_count = sum(m.get("track-count", 0) for m in media)
    fmt = media[0].get("format", "") if media else ""

    return MBRelease(
        mbid=data.get("id", ""),
        title=data.get("title", ""),
        artist=artist,
        date=data.get("date", ""),
        country=data.get("country", ""),
        label=label,
        barcode=data.get("barcode", ""),
        format=fmt,
        track_count=track_count,
    )


def get_release(mbid: str) -> MBRelease | None:
    try:
        resp = requests.get(
            f"{BASE_URL}/release/{mbid}",
            params={"inc": "artist-credits+labels+media", "fmt": "json"},
            headers=_headers(),
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return _parse_release(resp.json())
    except Exception:
        pass
    return None
