"""iTunes Search API client for album artwork (no auth required)."""

from __future__ import annotations

from dataclasses import dataclass

import requests

BASE_URL = "https://itunes.apple.com/search"
TIMEOUT = 10


@dataclass
class ItunesArtwork:
    album: str
    artist: str
    artwork_url: str    # 100x100 by default; we'll upscale


def search_artwork(album: str, artist: str = "", limit: int = 5) -> list[ItunesArtwork]:
    query = f"{artist} {album}".strip() if artist else album
    try:
        resp = requests.get(
            BASE_URL,
            params={"term": query, "media": "music", "entity": "album", "limit": limit},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", [])
        artworks = []
        for r in results:
            url = r.get("artworkUrl100", "")
            if url:
                # Replace 100x100 thumbnail with highest-res version
                url = url.replace("100x100bb", "3000x3000bb")
                artworks.append(ItunesArtwork(
                    album=r.get("collectionName", ""),
                    artist=r.get("artistName", ""),
                    artwork_url=url,
                ))
        return artworks
    except Exception:
        return []


def download_artwork(url: str) -> bytes | None:
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None
