"""Main application window."""

from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QAction, QKeySequence, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTabWidget, QLabel, QFileDialog, QProgressBar, QStatusBar, QToolBar,
    QComboBox,
)

from config import get_config
from core.metadata import read_metadata, TrackMetadata
from i18n import t
from ui.library_view import LibraryView, LyricsStatus
from ui.metadata_view import MetadataView
from ui.lyrics_view import LyricsView
from ui.artwork_view import ArtworkView
from ui.settings_dialog import SettingsDialog
from ui.workers import LyricsWorker, ScanWorker, MetadataWorker, BatchLyricsWorker


def _icon(name: str, color: str = "#e0e0e0") -> QIcon:
    try:
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._cfg = get_config()
        self._current_meta: TrackMetadata | None = None
        self._active_workers: list[QThread] = []
        self._batch_lyrics_worker: BatchLyricsWorker | None = None

        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1100, 700)
        self._restore_geometry()
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu(t("menu_file"))
        open_act = QAction(_icon("fa5s.folder-open"), t("menu_open_folder"), self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self.open_folder)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction(t("menu_quit"), self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        tools_menu = mb.addMenu(t("menu_tools"))
        fetch_lyrics_act = QAction(_icon("fa5s.music"), t("menu_fetch_lyrics"), self)
        fetch_lyrics_act.setShortcut("Ctrl+L")
        fetch_lyrics_act.triggered.connect(self._fetch_lyrics_current)
        tools_menu.addAction(fetch_lyrics_act)

        fetch_art_act = QAction(_icon("fa5s.image"), t("menu_fetch_artwork"), self)
        fetch_art_act.setShortcut("Ctrl+I")
        fetch_art_act.triggered.connect(self._fetch_artwork_current)
        tools_menu.addAction(fetch_art_act)

        tools_menu.addSeparator()
        settings_act = QAction(_icon("fa5s.cog"), t("menu_settings"), self)
        settings_act.setShortcut("Ctrl+,")
        settings_act.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_act)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(__import__("PyQt6.QtCore", fromlist=["QSize"]).QSize(18, 18))
        self.addToolBar(tb)

        def _act(icon_name: str, label: str, slot, shortcut: str = "") -> QAction:
            act = QAction(_icon(icon_name), label, self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(shortcut)
            tb.addAction(act)
            return act

        _act("fa5s.folder-open",  t("tb_open"),          self.open_folder,           "Ctrl+O")
        tb.addSeparator()
        _act("fa5s.music",        t("tb_fetch_lyrics"),   self._fetch_lyrics_current, "Ctrl+L")
        _act("fa5s.image",        t("tb_fetch_artwork"),  self._fetch_artwork_current,"Ctrl+I")
        tb.addSeparator()
        _act("fa5s.cog",          t("tb_settings"),       self._open_settings,        "Ctrl+,")

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Library panel
        self._library = LibraryView()
        self._library.setMinimumWidth(220)
        self._library.setMaximumWidth(380)
        self._library.track_selected.connect(self._on_track_selected)
        self._library.batch_lyrics_requested.connect(self._batch_fetch_lyrics)
        self._library.batch_artwork_requested.connect(self._batch_fetch_artwork)
        splitter.addWidget(self._library)

        # Right tabs
        self._tabs = QTabWidget()
        self._metadata_view = MetadataView()
        self._lyrics_view = LyricsView()
        self._artwork_view = ArtworkView()

        self._tabs.addTab(self._metadata_view, _icon("fa5s.info-circle"), t("tab_metadata"))
        self._tabs.addTab(self._lyrics_view, _icon("fa5s.align-left"), t("tab_lyrics"))
        self._tabs.addTab(self._artwork_view, _icon("fa5s.image"), t("tab_artwork"))

        self._lyrics_view.fetch_requested.connect(self._fetch_lyrics_current)
        self._lyrics_view.save_requested.connect(self._save_lyrics)
        self._artwork_view.fetch_requested.connect(self._fetch_artwork_current)
        self._artwork_view.save_requested.connect(self._save_artwork)

        splitter.addWidget(self._tabs)
        splitter.setSizes([260, 840])
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel(t("status_ready"))
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(180)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        sb.addWidget(self._status_label, 1)
        sb.addPermanentWidget(self._progress)

        # ── Device selector (right side) ──────────────────────────────
        dev_lbl = QLabel()
        dev_lbl.setPixmap(_icon("fa5s.headphones", "#555").pixmap(13, 13))
        dev_lbl.setStyleSheet("margin-right:2px;")

        self._combo_device = QComboBox()
        self._combo_device.setMaximumWidth(230)
        self._combo_device.setFixedHeight(18)
        self._combo_device.setStyleSheet(
            "QComboBox { font-size:11px; padding:0 4px; border-radius:3px; }"
        )
        self._combo_device.currentIndexChanged.connect(self._on_device_changed)

        sb.addPermanentWidget(dev_lbl)
        sb.addPermanentWidget(self._combo_device)
        self._populate_device_combo()

    # ------------------------------------------------------------------
    # Folder / library
    # ------------------------------------------------------------------

    def open_folder(self) -> None:
        last = self._cfg.get("last_library_path") or ""
        folder = QFileDialog.getExistingDirectory(self, t("menu_open_folder"), last)
        if not folder:
            return
        self._cfg.set("last_library_path", folder)
        self._scan_folder(Path(folder))

    def _scan_folder(self, folder: Path) -> None:
        self._set_status(t("lib_scanning").format(folder=folder.name))
        self._library.show_progress(0, 1)

        worker = ScanWorker(folder)
        worker.finished.connect(self._on_scan_finished)
        worker.finished.connect(worker.deleteLater)
        self._active_workers.append(worker)
        worker.start()

    def _on_scan_finished(self, paths: list[Path]) -> None:
        if not paths:
            self._library.hide_progress()
            self._set_status(t("status_no_audio"))
            return
        self._set_status(t("lib_reading_meta").format(n=len(paths)))
        self._progress.setVisible(True)
        self._progress.setMaximum(len(paths))

        worker = MetadataWorker(paths)
        worker.progress.connect(lambda c, total: (
            self._progress.setValue(c),
            self._library.show_progress(c, total),
        ))
        worker.finished.connect(self._on_metadata_loaded)
        worker.finished.connect(worker.deleteLater)
        self._active_workers.append(worker)
        worker.start()

    def _on_metadata_loaded(self, metadata_list: list) -> None:
        self._library.hide_progress()
        self._progress.setVisible(False)
        self._library.populate(metadata_list)
        self._set_status(t("lib_loaded").format(n=len(metadata_list)))

    # ------------------------------------------------------------------
    # Track selection
    # ------------------------------------------------------------------

    def _on_track_selected(self, path: Path) -> None:
        try:
            meta = read_metadata(path)
        except Exception as e:
            self._set_status(f"Error: {e}")
            return
        self._current_meta = meta
        self._metadata_view.load(meta)
        self._lyrics_view.load_track(meta)
        self._artwork_view.load_track(meta)
        self._set_status(f"{meta.display_title}  ·  {meta.quality.label}  ·  "
                         f"{meta.quality.sample_rate_khz}  ·  {meta.quality.bit_depth_str}")

    # ------------------------------------------------------------------
    # Lyrics – single track
    # ------------------------------------------------------------------

    def _fetch_lyrics_current(self) -> None:
        if not self._current_meta:
            self._set_status(t("status_no_track"))
            return
        meta = self._current_meta
        self._set_status(t("status_fetching_lyrics").format(title=meta.display_title))
        self._lyrics_view.set_status(t("lyr_searching"))

        worker = LyricsWorker(meta.title, meta.artist, meta.album, meta.duration)
        worker.finished.connect(self._on_lyrics_fetched)
        worker.finished.connect(worker.deleteLater)
        self._active_workers.append(worker)
        worker.start()

    def _on_lyrics_fetched(self, result) -> None:
        self._lyrics_view.on_fetch_done()
        self._lyrics_view.set_lyrics_result(result)
        if result:
            self._set_status(t("status_lyrics_found").format(source=result.source))
        else:
            self._set_status(t("status_lyrics_none"))
        self._tabs.setCurrentWidget(self._lyrics_view)

    def _save_lyrics(self, result) -> None:
        if not self._current_meta or result is None:
            return
        from core.lyrics_manager import save_lyrics
        ok, msg = save_lyrics(self._current_meta.path, result)
        self._set_status(msg)
        self._lyrics_view.set_status(msg)

    # ------------------------------------------------------------------
    # Lyrics – batch (uses BatchLyricsWorker with per-track status icons)
    # ------------------------------------------------------------------

    def _batch_fetch_lyrics(self, paths: list[Path]) -> None:
        if not paths:
            return
        if self._batch_lyrics_worker and self._batch_lyrics_worker.isRunning():
            return  # already running

        for p in paths:
            self._library.set_track_status(p, LyricsStatus.LOADING)

        self._set_status(t("lib_reading_meta").format(n=len(paths)) + " (batch lyrics)")
        self._progress.setVisible(True)
        self._progress.setMaximum(len(paths))
        self._progress.setValue(0)
        self._batch_count = 0

        worker = BatchLyricsWorker(paths)
        worker.track_started.connect(self._on_batch_track_started)
        worker.track_done.connect(self._on_batch_track_done)
        worker.track_failed.connect(self._on_batch_track_failed)
        worker.all_done.connect(self._on_batch_all_done)
        worker.finished.connect(worker.deleteLater)
        self._batch_lyrics_worker = worker
        worker.start()

    def _on_batch_track_started(self, path_str: str) -> None:
        self._library.set_track_status(Path(path_str), LyricsStatus.LOADING)

    def _on_batch_track_done(self, path_str: str, source: str, is_synced: bool) -> None:
        status = LyricsStatus.FOUND_SYNCED if is_synced else LyricsStatus.FOUND_PLAIN
        self._library.set_track_status(Path(path_str), status)
        self._batch_count = getattr(self, "_batch_count", 0) + 1
        self._progress.setValue(self._batch_count)

    def _on_batch_track_failed(self, path_str: str) -> None:
        self._library.set_track_status(Path(path_str), LyricsStatus.NOT_FOUND)
        self._batch_count = getattr(self, "_batch_count", 0) + 1
        self._progress.setValue(self._batch_count)

    def _on_batch_all_done(self, found: int, total: int) -> None:
        self._progress.setVisible(False)
        self._set_status(f"{t('status_batch_done')} {found}/{total} tracks")
        self._batch_lyrics_worker = None

    # ------------------------------------------------------------------
    # Artwork – single track (streaming search dialog)
    # ------------------------------------------------------------------

    def _fetch_artwork_current(self) -> None:
        if not self._current_meta:
            self._set_status(t("status_no_track"))
            return
        meta = self._current_meta
        self._tabs.setCurrentWidget(self._artwork_view)

        from ui.artwork_search_dialog import ArtworkSearchDialog
        dlg = ArtworkSearchDialog(
            meta.album, meta.album_artist or meta.artist, self
        )
        dlg.cover_save_requested.connect(self._save_artwork_as_cover)
        dlg.embed_requested.connect(self._embed_artwork)
        dlg.exec()

    def _save_artwork_as_cover(self, result) -> None:
        if not self._current_meta or result is None:
            return
        from core.artwork_manager import _save_cover_png
        ok, msg = _save_cover_png(self._current_meta.path.parent, result)
        self._set_status(msg)
        self._artwork_view.set_status(msg)
        if ok:
            self._artwork_view.load_track(self._current_meta)
            self._metadata_view.load(self._current_meta)

    def _embed_artwork(self, result) -> None:
        if not self._current_meta or result is None:
            return
        from core.metadata import embed_artwork_in_metadata
        ok = embed_artwork_in_metadata(
            self._current_meta.path, result.data, result.mime
        )
        msg = "Incrustado en metadatos." if ok else "No se pudo incrustar."
        self._set_status(msg)
        self._artwork_view.set_status(msg)
        if ok:
            self._artwork_view.load_track(self._current_meta)
            self._metadata_view.load(self._current_meta)

    def _save_artwork(self, result) -> None:
        """Legacy handler for the artwork_view 'Save Selected' button."""
        if not self._current_meta or result is None:
            return
        from core.artwork_manager import _save_cover_png
        ok, msg = _save_cover_png(self._current_meta.path.parent, result)
        self._set_status(msg)
        self._artwork_view.set_status(msg)
        if ok:
            self._artwork_view.load_track(self._current_meta)
            self._metadata_view.load(self._current_meta)

    # ------------------------------------------------------------------
    # Artwork – batch (simple: save first result, no picker)
    # ------------------------------------------------------------------

    def _batch_fetch_artwork(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_status(t("status_fetching_art").format(album=f"{len(paths)} tracks"))
        self._batch_artwork_queue = list(paths)
        self._process_next_batch_artwork()

    def _process_next_batch_artwork(self) -> None:
        if not self._batch_artwork_queue:
            self._set_status(t("status_batch_done"))
            return
        path = self._batch_artwork_queue.pop(0)
        try:
            meta = read_metadata(path)
        except Exception:
            self._process_next_batch_artwork()
            return

        worker = ArtworkOptionsWorker(meta.album, meta.album_artist or meta.artist)
        worker.finished.connect(lambda results: self._on_batch_artwork_one(path, results))
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._process_next_batch_artwork)
        worker.start()

    def _on_batch_artwork_one(self, path: Path, results: list) -> None:
        if results:
            from core.artwork_manager import save_artwork
            ok, msg = save_artwork(path, results[0])
            self._set_status(f"{path.name}: {msg}")

    # ------------------------------------------------------------------
    # Device selector (status bar)
    # ------------------------------------------------------------------

    def _populate_device_combo(self) -> None:
        try:
            from ui.player import list_output_devices
        except Exception:
            self._combo_device.setVisible(False)
            return
        try:
            devices = list_output_devices()
        except Exception:
            self._combo_device.setVisible(False)
            return

        cfg_device = self._cfg.get("audio_output_device")
        self._combo_device.blockSignals(True)
        self._combo_device.clear()
        self._combo_device.addItem(t("player_no_device"), None)
        for dev in devices:
            self._combo_device.addItem(dev["display"], dev["id"])
            if dev["id"] == cfg_device or (cfg_device is None and dev.get("default")):
                self._combo_device.setCurrentIndex(self._combo_device.count() - 1)
        self._combo_device.blockSignals(False)

    def _on_device_changed(self, idx: int) -> None:
        device_id = self._combo_device.itemData(idx)
        self._cfg.set("audio_output_device", device_id)
        if self._lyrics_view._player:
            self._lyrics_view._player.set_device(device_id)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()
        # Re-sync device combo after settings may have changed
        self._populate_device_combo()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _restore_geometry(self) -> None:
        geo = self._cfg.get("window_geometry")
        if geo:
            try:
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromHex(bytes(geo, "ascii")))
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        self._cfg.set("window_geometry", self.saveGeometry().toHex().data().decode())
        if self._lyrics_view._player:
            self._lyrics_view._player.stop()
        super().closeEvent(event)
