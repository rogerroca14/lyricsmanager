"""Audio file metadata reading and writing via mutagen."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, USLT, TIT2, TPE1, TALB, TRCK, TDRC, TCON
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis

from config import get_config
from utils.helpers import format_duration, format_bitrate, format_file_size


@dataclass
class AudioQuality:
    sample_rate: int | None = None       # Hz
    bit_depth: int | None = None         # bits per sample
    channels: int | None = None
    bitrate: int | None = None           # bps
    codec: str = ""
    is_lossless: bool = False
    is_hires: bool = False
    is_mqa: bool = False
    is_dsd: bool = False

    @property
    def label(self) -> str:
        if self.is_dsd:
            return "DSD"
        if self.is_mqa:
            return "MQA"
        if self.is_hires:
            return "Hi-Res"
        if self.is_lossless:
            return "Lossless"
        return "Lossy"

    @property
    def sample_rate_khz(self) -> str:
        if self.sample_rate is None:
            return "—"
        return f"{self.sample_rate / 1000:.1f} kHz"

    @property
    def bit_depth_str(self) -> str:
        return f"{self.bit_depth}-bit" if self.bit_depth else "—"


@dataclass
class TrackMetadata:
    path: Path
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    track_number: str = ""
    disc_number: str = ""
    year: str = ""
    genre: str = ""
    comment: str = ""
    composer: str = ""
    duration: float | None = None
    file_size: int | None = None
    quality: AudioQuality = field(default_factory=AudioQuality)
    has_lyrics: bool = False
    has_artwork: bool = False
    raw_tags: dict[str, Any] = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        return self.title or self.path.stem

    @property
    def duration_str(self) -> str:
        return format_duration(self.duration)

    @property
    def bitrate_str(self) -> str:
        return format_bitrate(self.quality.bitrate)

    @property
    def file_size_str(self) -> str:
        return format_file_size(self.file_size)


def _detect_quality(audio: Any, ext: str) -> AudioQuality:
    q = AudioQuality()
    cfg = get_config()
    hires_sr = cfg.get("hires_sample_rate_threshold")
    hires_bd = cfg.get("hires_bit_depth_threshold")

    ext = ext.lower()

    if ext in (".dsf", ".dff"):
        q.codec = "DSD"
        q.is_lossless = True
        q.is_dsd = True
    elif ext == ".flac":
        q.codec = "FLAC"
        q.is_lossless = True
    elif ext in (".wav", ".aiff"):
        q.codec = ext.lstrip(".").upper()
        q.is_lossless = True
    elif ext in (".ape", ".wv"):
        q.codec = "APE" if ext == ".ape" else "WavPack"
        q.is_lossless = True
    elif ext == ".mp3":
        q.codec = "MP3"
    elif ext in (".aac", ".m4a"):
        q.codec = "AAC"
    elif ext in (".ogg", ".opus"):
        q.codec = ext.lstrip(".").upper()
    else:
        q.codec = ext.lstrip(".").upper()

    info = getattr(audio, "info", None)
    if info:
        q.sample_rate = getattr(info, "sample_rate", None)
        q.channels = getattr(info, "channels", None)
        q.bitrate = getattr(info, "bitrate", None)
        if q.bitrate:
            q.bitrate *= 1000   # mutagen returns kbps for most formats

        # FLAC exposes bits_per_sample directly
        q.bit_depth = getattr(info, "bits_per_sample", None)

    if not q.is_dsd and q.sample_rate and q.bit_depth:
        q.is_hires = (q.sample_rate >= hires_sr) or (q.bit_depth >= hires_bd)
    elif not q.is_dsd and q.sample_rate:
        q.is_hires = q.sample_rate >= hires_sr

    return q


def _first(tags: dict, *keys: str) -> str:
    for key in keys:
        val = tags.get(key)
        if val:
            if isinstance(val, list):
                return str(val[0])
            return str(val)
    return ""


def read_metadata(path: Path | str) -> TrackMetadata:
    path = Path(path)
    meta = TrackMetadata(path=path)
    meta.file_size = path.stat().st_size if path.exists() else None

    audio = MutagenFile(path, easy=False)
    if audio is None:
        return meta

    ext = path.suffix.lower()
    meta.quality = _detect_quality(audio, ext)
    meta.duration = getattr(audio.info, "length", None)

    if isinstance(audio, FLAC):
        _read_flac(audio, meta)
    elif isinstance(audio, MP4):
        _read_mp4(audio, meta)
    elif isinstance(audio, ID3) or hasattr(audio, "tags") and isinstance(getattr(audio, "tags", None), ID3):
        _read_id3(audio, meta)
    elif isinstance(audio, OggVorbis):
        _read_vorbis(audio, meta)
    else:
        # Generic easy-tag fallback
        try:
            easy = MutagenFile(path, easy=True)
            if easy and easy.tags:
                t = easy.tags
                meta.title = _first(t, "title")
                meta.artist = _first(t, "artist")
                meta.album = _first(t, "album")
                meta.year = _first(t, "date")
                meta.genre = _first(t, "genre")
                meta.track_number = _first(t, "tracknumber")
        except Exception:
            pass

    return meta


def _read_flac(audio: FLAC, meta: TrackMetadata) -> None:
    t = audio.tags or {}
    meta.title = _first(t, "title", "TITLE")
    meta.artist = _first(t, "artist", "ARTIST")
    meta.album = _first(t, "album", "ALBUM")
    meta.album_artist = _first(t, "albumartist", "ALBUMARTIST")
    meta.track_number = _first(t, "tracknumber", "TRACKNUMBER")
    meta.disc_number = _first(t, "discnumber", "DISCNUMBER")
    meta.year = _first(t, "date", "DATE", "year", "YEAR")
    meta.genre = _first(t, "genre", "GENRE")
    meta.comment = _first(t, "comment", "COMMENT", "description", "DESCRIPTION")
    meta.composer = _first(t, "composer", "COMPOSER")
    meta.has_lyrics = bool(_first(t, "lyrics", "LYRICS", "unsyncedlyrics", "UNSYNCEDLYRICS"))
    meta.has_artwork = bool(audio.pictures)
    meta.raw_tags = {k: v for k, v in t.items()}


def _read_id3(audio: Any, meta: TrackMetadata) -> None:
    tags = audio.tags
    if not tags:
        return
    meta.title = str(tags.get("TIT2", ""))
    meta.artist = str(tags.get("TPE1", ""))
    meta.album = str(tags.get("TALB", ""))
    meta.album_artist = str(tags.get("TPE2", ""))
    meta.track_number = str(tags.get("TRCK", ""))
    meta.disc_number = str(tags.get("TPOS", ""))
    meta.year = str(tags.get("TDRC", ""))
    meta.genre = str(tags.get("TCON", ""))
    meta.composer = str(tags.get("TCOM", ""))
    uslt = [v for k, v in tags.items() if k.startswith("USLT")]
    meta.has_lyrics = bool(uslt)
    meta.has_artwork = bool([v for k, v in tags.items() if k.startswith("APIC")])


def _read_mp4(audio: MP4, meta: TrackMetadata) -> None:
    t = audio.tags or {}
    meta.title = _first(t, "\xa9nam")
    meta.artist = _first(t, "\xa9ART")
    meta.album = _first(t, "\xa9alb")
    meta.album_artist = _first(t, "aART")
    meta.year = _first(t, "\xa9day")
    meta.genre = _first(t, "\xa9gen")
    meta.composer = _first(t, "\xa9wrt")
    trk = t.get("trkn")
    if trk and isinstance(trk, list):
        meta.track_number = str(trk[0][0]) if isinstance(trk[0], tuple) else str(trk[0])
    meta.has_artwork = bool(t.get("covr"))
    meta.has_lyrics = bool(_first(t, "\xa9lyr"))


def _read_vorbis(audio: OggVorbis, meta: TrackMetadata) -> None:
    t = audio.tags or {}
    meta.title = _first(t, "title", "TITLE")
    meta.artist = _first(t, "artist", "ARTIST")
    meta.album = _first(t, "album", "ALBUM")
    meta.album_artist = _first(t, "albumartist", "ALBUMARTIST")
    meta.track_number = _first(t, "tracknumber")
    meta.year = _first(t, "date")
    meta.genre = _first(t, "genre")
    meta.has_lyrics = bool(_first(t, "lyrics"))


def get_embedded_artwork(path: Path | str) -> bytes | None:
    """Return raw bytes of the first embedded artwork, or None."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        audio = MutagenFile(path, easy=False)
        if audio is None:
            return None
        if isinstance(audio, FLAC):
            if audio.pictures:
                return audio.pictures[0].data
        elif isinstance(audio, MP4):
            covers = (audio.tags or {}).get("covr", [])
            if covers:
                return bytes(covers[0])
        elif hasattr(audio, "tags"):
            tags = audio.tags
            if tags:
                for key in tags:
                    if key.startswith("APIC"):
                        return tags[key].data
    except Exception:
        pass
    return None


def embed_lyrics_in_metadata(path: Path | str, lyrics: str, is_synced: bool = False) -> bool:
    """Embed lyrics text (plain or LRC) into the file's metadata."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".flac":
            audio = FLAC(path)
            key = "LYRICS" if not is_synced else "SYNCEDLYRICS"
            audio[key] = lyrics
            audio.save()
        elif ext == ".mp3":
            audio = ID3(path)
            audio.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
            audio.save()
        elif ext in (".m4a", ".aac"):
            audio = MP4(path)
            audio.tags["\xa9lyr"] = [lyrics]
            audio.save()
        else:
            return False
        return True
    except Exception:
        return False


def embed_artwork_in_metadata(path: Path | str, image_data: bytes, mime: str = "image/jpeg") -> bool:
    """Embed artwork bytes into the file's metadata."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".flac":
            audio = FLAC(path)
            pic = Picture()
            pic.type = 3  # Front cover
            pic.mime = mime
            pic.data = image_data
            audio.clear_pictures()
            audio.add_picture(pic)
            audio.save()
        elif ext == ".mp3":
            audio = ID3(path)
            audio["APIC"] = APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image_data)
            audio.save()
        elif ext in (".m4a", ".aac"):
            audio = MP4(path)
            fmt = MP4Cover.FORMAT_JPEG if "jpeg" in mime else MP4Cover.FORMAT_PNG
            audio.tags["covr"] = [MP4Cover(image_data, imageformat=fmt)]
            audio.save()
        else:
            return False
        return True
    except Exception:
        return False
