"""Orchestrate artwork searching, downloading, and saving.

Always saves as PNG (converts from JPEG if needed).
Returns up to MAX_OPTIONS results for the user to choose from.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from config import get_config
from core.metadata import embed_artwork_in_metadata

MAX_OPTIONS = 5


@dataclass
class ArtworkResult:
    data: bytes           # raw image bytes (original format)
    mime: str             # original mime
    source: str           # "coverart" | "itunes"
    width: int = 0
    height: int = 0
    label: str = ""       # human label shown in picker

    @property
    def size_str(self) -> str:
        return f"{self.width}×{self.height}" if self.width else "Unknown"

    def as_png_bytes(self) -> bytes:
        """Return PNG-encoded bytes regardless of original format."""
        img = Image.open(io.BytesIO(self.data)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def thumbnail_bytes(self, size: int = 300) -> bytes:
        """Return a small PNG thumbnail for display."""
        img = Image.open(io.BytesIO(self.data)).convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def fetch_artwork_options(album: str, artist: str = "") -> list[ArtworkResult]:
    """Fetch up to MAX_OPTIONS artwork candidates from all configured sources."""
    cfg = get_config()
    sources = cfg.get("artwork_sources") or ["coverart", "itunes"]
    results: list[ArtworkResult] = []

    for source in sources:
        if len(results) >= MAX_OPTIONS:
            break
        try:
            new = _fetch_all_from_source(source, album, artist)
            results.extend(new[: MAX_OPTIONS - len(results)])
        except Exception:
            pass

    return results[:MAX_OPTIONS]


def _fetch_all_from_source(source: str, album: str, artist: str) -> list[ArtworkResult]:
    results = []
    if source == "coverart":
        from services.musicbrainz import search_release
        from services.coverart import download_cover
        releases = search_release(album, artist, limit=MAX_OPTIONS)
        for release in releases:
            data = download_cover(release.mbid)
            if data:
                r = _make_result(data, "coverart", f"{release.title} ({release.date})")
                if r:
                    results.append(r)
            if len(results) >= MAX_OPTIONS:
                break

    elif source == "itunes":
        from services.itunes import search_artwork, download_artwork
        items = search_artwork(album, artist, limit=MAX_OPTIONS)
        for item in items:
            data = download_artwork(item.artwork_url)
            if data:
                r = _make_result(data, "itunes", f"{item.artist} — {item.album}")
                if r:
                    results.append(r)
            if len(results) >= MAX_OPTIONS:
                break

    return results


def _make_result(data: bytes, source: str, label: str = "") -> ArtworkResult | None:
    try:
        img = Image.open(io.BytesIO(data))
        mime = "image/jpeg" if img.format in ("JPEG", "JPG") else "image/png"
        return ArtworkResult(
            data=data, mime=mime, source=source,
            width=img.width, height=img.height, label=label,
        )
    except Exception:
        return None


def save_artwork(audio_path: Path | str, result: ArtworkResult) -> tuple[bool, str]:
    """Save artwork as PNG and/or embed in metadata per config."""
    audio_path = Path(audio_path)
    cfg = get_config()
    messages = []
    success = False

    if cfg.get("artwork_save_cover_png"):
        ok, msg = _save_cover_png(audio_path.parent, result)
        messages.append(msg)
        success = success or ok

    if cfg.get("artwork_embed_metadata"):
        # Always embed as PNG
        png_bytes = result.as_png_bytes()
        ok = embed_artwork_in_metadata(audio_path, png_bytes, "image/png")
        if ok:
            messages.append("Incrustado en metadatos.")
        success = success or ok

    return success, " | ".join(messages)



def _resize_if_needed(img: Image.Image) -> Image.Image:
    """Downscale img to fit within the configured max size. Never upscales."""
    cfg = get_config()
    if not cfg.get("artwork_resize_cover"):
        return img
    max_px = int(cfg.get("artwork_cover_max_size") or 600)
    if img.width <= max_px and img.height <= max_px:
        return img
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    return img


def _save_cover_png(folder: Path, result: ArtworkResult) -> tuple[bool, str]:
    cfg = get_config()
    cover_path = folder / "cover.png"

    if cover_path.exists() and not cfg.get("artwork_overwrite"):
        from i18n import t
        return False, t("art_exists")

    try:
        img = _resize_if_needed(Image.open(io.BytesIO(result.data)))
        buf = io.BytesIO()
        img.save(buf, format="PNG", compress_level=0)
        cover_path.write_bytes(buf.getvalue())
        size_str = f"{img.width}×{img.height}"
        from i18n import t
        return True, t("art_saved_png").format(size=size_str)
    except Exception as e:
        from i18n import t
        return False, t("art_fail_png").format(err=e)
