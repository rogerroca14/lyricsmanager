"""Background worker threads for non-blocking API calls."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


class LyricsWorker(QThread):
    finished = pyqtSignal(object)   # LyricsResult | None
    error = pyqtSignal(str)

    def __init__(self, title: str, artist: str, album: str, duration: float | None) -> None:
        super().__init__()
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = duration

    def run(self) -> None:
        try:
            from core.lyrics_manager import fetch_lyrics
            result = fetch_lyrics(self.title, self.artist, self.album, self.duration)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(None)


class ArtworkStreamWorker(QThread):
    """Fetch artwork candidates one by one, emitting each as it arrives."""

    result_found = pyqtSignal(object)   # ArtworkResult
    search_done  = pyqtSignal(int)      # total found count
    error        = pyqtSignal(str)

    def __init__(self, album: str, artist: str) -> None:
        super().__init__()
        self.album = album
        self.artist = artist

    def run(self) -> None:
        from config import get_config
        from core.artwork_manager import _make_result, MAX_OPTIONS

        cfg = get_config()
        sources = cfg.get("artwork_sources") or ["coverart", "itunes"]
        found = 0

        for source in sources:
            if found >= MAX_OPTIONS:
                break
            try:
                if source == "coverart":
                    from services.musicbrainz import search_release
                    from services.coverart import download_cover
                    for release in search_release(self.album, self.artist, limit=MAX_OPTIONS):
                        if found >= MAX_OPTIONS:
                            break
                        data = download_cover(release.mbid)
                        if data:
                            r = _make_result(data, "coverart",
                                             f"{release.title} ({release.date})")
                            if r:
                                self.result_found.emit(r)
                                found += 1

                elif source == "itunes":
                    from services.itunes import search_artwork, download_artwork
                    for item in search_artwork(self.album, self.artist, limit=MAX_OPTIONS):
                        if found >= MAX_OPTIONS:
                            break
                        data = download_artwork(item.artwork_url)
                        if data:
                            r = _make_result(data, "itunes",
                                             f"{item.artist} — {item.album}")
                            if r:
                                self.result_found.emit(r)
                                found += 1
            except Exception as e:
                self.error.emit(str(e))

        self.search_done.emit(found)


class ScanWorker(QThread):
    progress = pyqtSignal(int, str)     # count, current path
    finished = pyqtSignal(list)         # list[Path]
    error = pyqtSignal(str)

    def __init__(self, root: Path, recursive: bool = True) -> None:
        super().__init__()
        self.root = root
        self.recursive = recursive

    def run(self) -> None:
        try:
            from core.music_scanner import scan_directory
            paths = list(scan_directory(
                self.root,
                recursive=self.recursive,
                progress_callback=lambda c, p: self.progress.emit(c, p),
            ))
            self.finished.emit(paths)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit([])


class MetadataWorker(QThread):
    progress = pyqtSignal(int, int)     # current, total
    finished = pyqtSignal(list)         # list[TrackMetadata]

    def __init__(self, paths: list[Path]) -> None:
        super().__init__()
        self.paths = paths

    def run(self) -> None:
        from core.metadata import read_metadata
        results = []
        for i, path in enumerate(self.paths, 1):
            try:
                results.append(read_metadata(path))
            except Exception:
                pass
            self.progress.emit(i, len(self.paths))
        self.finished.emit(results)


class BatchLyricsWorker(QThread):
    """Fetch and save lyrics for a list of tracks, emitting per-track status."""

    track_started = pyqtSignal(str)                 # path str — searching started
    track_done = pyqtSignal(str, str, bool)         # path str, source, is_synced
    track_failed = pyqtSignal(str)                  # path str — not found
    all_done = pyqtSignal(int, int)                 # found_count, total

    def __init__(self, paths: list[Path]) -> None:
        super().__init__()
        self.paths = paths

    def run(self) -> None:
        from core.metadata import read_metadata
        from core.lyrics_manager import fetch_lyrics, save_lyrics

        found = 0
        for path in self.paths:
            self.track_started.emit(str(path))
            try:
                meta = read_metadata(path)
                result = fetch_lyrics(meta.title, meta.artist, meta.album, meta.duration)
                if result and (result.has_synced or result.has_plain):
                    save_lyrics(path, result)
                    found += 1
                    self.track_done.emit(str(path), result.source, result.has_synced)
                else:
                    self.track_failed.emit(str(path))
            except Exception:
                self.track_failed.emit(str(path))

        self.all_done.emit(found, len(self.paths))
