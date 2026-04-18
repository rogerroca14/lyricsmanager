"""Cover Art Archive client (MusicBrainz-backed)."""

from __future__ import annotations

import requests

BASE_URL = "https://coverartarchive.org/release"
TIMEOUT = 10


def get_cover_url(mbid: str, size: str = "500") -> str | None:
    """Return URL of the front cover for a MusicBrainz release MBID."""
    try:
        resp = requests.get(f"{BASE_URL}/{mbid}", timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return None
        images = resp.json().get("images", [])
        for img in images:
            if img.get("front"):
                thumbs = img.get("thumbnails", {})
                return thumbs.get(size) or thumbs.get("large") or img.get("image")
        if images:
            return images[0].get("image")
    except Exception:
        pass
    return None


def download_cover(mbid: str, size: str = "500") -> bytes | None:
    """Download cover image bytes for a MusicBrainz release."""
    url = get_cover_url(mbid, size)
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None
