"""Library panel with per-track lyrics status icons (qtawesome)."""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal, QSortFilterProxyModel, QTimer, QSize
from PyQt6.QtGui import QIcon, QStandardItem, QStandardItemModel, QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QLineEdit, QProgressBar, QMenu,
)

from i18n import t
from utils.helpers import AUDIO_EXTENSIONS

PATH_ROLE = Qt.ItemDataRole.UserRole + 1
STATUS_ROLE = Qt.ItemDataRole.UserRole + 2


class LyricsStatus(Enum):
    NONE = auto()
    LOADING = auto()
    FOUND_PLAIN = auto()
    FOUND_SYNCED = auto()
    NOT_FOUND = auto()


# Spinner animation frames (fa5s.circle-notch rotated via QTimer)
_SPINNER_FRAMES = ["fa5s.circle-notch"]

_STATUS_ICONS: dict[LyricsStatus, tuple[str, str]] = {
    LyricsStatus.NONE:         ("fa5s.music", "#555"),
    LyricsStatus.LOADING:      ("fa5s.circle-notch", "#e5a50a"),
    LyricsStatus.FOUND_PLAIN:  ("fa5s.check", "#4caf50"),
    LyricsStatus.FOUND_SYNCED: ("fa5s.sync-alt", "#4caf50"),
    LyricsStatus.NOT_FOUND:    ("fa5s.times", "#e05252"),
}

_QUALITY_ICONS: dict[str, tuple[str, str]] = {
    "DSD":      ("fa5s.compact-disc", "#c07000"),
    "Hi-Res":   ("fa5s.compact-disc", "#e5a50a"),
    "Lossless": ("fa5s.compact-disc", "#0078d4"),
    "Lossy":    ("fa5s.compact-disc", "#555555"),
    "MQA":      ("fa5s.compact-disc", "#8b5cf6"),
}


def _qta_icon(fa_name: str, color: str) -> QIcon:
    try:
        return qta.icon(fa_name, color=color)
    except Exception:
        return QIcon()


class LibraryView(QWidget):
    track_selected = pyqtSignal(object)             # Path
    batch_lyrics_requested = pyqtSignal(list)       # list[Path]
    batch_artwork_requested = pyqtSignal(list)      # list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracks: list[Path] = []
        self._path_to_item: dict[str, QStandardItem] = {}
        self._spinner_angle = 0
        self._loading_paths: set[str] = set()

        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._animate_spinners)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Search bar
        search_bar = QWidget()
        search_bar.setStyleSheet("background:#242424; border-bottom:1px solid #383838;")
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_icon = QLabel()
        search_icon.setPixmap(_qta_icon("fa5s.search", "#888").pixmap(14, 14))
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("lib_filter"))
        self._search.setStyleSheet("border:none; background:transparent; color:#e0e0e0;")
        self._search.textChanged.connect(self._on_search)
        search_layout.addWidget(search_icon)
        search_layout.addWidget(self._search, 1)
        root.addWidget(search_bar)

        # Tree
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels([t("tab_metadata")])

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setRecursiveFilteringEnabled(True)

        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(False)
        self._tree.setIconSize(QSize(16, 16))
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._tree.setIndentation(14)
        root.addWidget(self._tree, 1)

        # Progress bar (thin, at bottom)
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(3)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Footer
        self._count_label = QLabel(t("lib_no_library"))
        self._count_label.setStyleSheet(
            "color:#555; font-size:11px; padding:4px 8px; background:#1c1c1c;"
        )
        root.addWidget(self._count_label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(self, metadata_list: list) -> None:
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["Library"])
        self._tracks = [m.path for m in metadata_list]
        self._path_to_item.clear()

        groups: dict[str, dict[str, list]] = {}
        for meta in metadata_list:
            artist = meta.album_artist or meta.artist or "Unknown Artist"
            album = meta.album or "Unknown Album"
            groups.setdefault(artist, {}).setdefault(album, []).append(meta)

        root = self._model.invisibleRootItem()
        for artist_name in sorted(groups):
            artist_item = QStandardItem(f" {artist_name}")
            artist_item.setEditable(False)
            artist_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            artist_item.setData(None, PATH_ROLE)
            artist_item.setIcon(_qta_icon("fa5s.user", "#555"))

            for album_name in sorted(groups[artist_name]):
                album_item = QStandardItem(f" {album_name}")
                album_item.setEditable(False)
                album_item.setData(None, PATH_ROLE)
                album_item.setIcon(_qta_icon("fa5s.compact-disc", "#0078d4"))

                tracks = sorted(
                    groups[artist_name][album_name],
                    key=lambda m: self._track_sort_key(m),
                )
                for meta in tracks:
                    q_icon_name, q_color = _QUALITY_ICONS.get(
                        meta.quality.label, ("fa5s.music", "#555")
                    )
                    track_num = f"{meta.track_number.zfill(2)}. " if meta.track_number else ""
                    label = f" {track_num}{meta.display_title}"
                    track_item = QStandardItem(label)
                    track_item.setEditable(False)
                    track_item.setData(meta.path, PATH_ROLE)
                    track_item.setData(LyricsStatus.NONE, STATUS_ROLE)
                    track_item.setIcon(_qta_icon(q_icon_name, q_color))
                    track_item.setToolTip(
                        f"{meta.quality.label} | {meta.quality.sample_rate_khz} "
                        f"| {meta.quality.bit_depth_str} | {meta.duration_str}"
                    )
                    self._path_to_item[str(meta.path)] = track_item
                    album_item.appendRow(track_item)

                artist_item.appendRow(album_item)
            root.appendRow(artist_item)

        self._tree.expandToDepth(1)
        self._count_label.setText(t("lib_tracks").format(n=len(metadata_list)))

    def set_track_status(self, path: Path | str, status: LyricsStatus) -> None:
        key = str(path)
        item = self._path_to_item.get(key)
        if not item:
            return
        item.setData(status, STATUS_ROLE)

        if status == LyricsStatus.LOADING:
            self._loading_paths.add(key)
            if not self._spinner_timer.isActive():
                self._spinner_timer.start()
            item.setIcon(_qta_icon("fa5s.circle-notch", "#e5a50a"))
        else:
            self._loading_paths.discard(key)
            if not self._loading_paths:
                self._spinner_timer.stop()

            icon_name, color = {
                LyricsStatus.FOUND_PLAIN:  ("fa5s.check-circle", "#4caf50"),
                LyricsStatus.FOUND_SYNCED: ("fa5s.sync-alt", "#4caf50"),
                LyricsStatus.NOT_FOUND:    ("fa5s.times-circle", "#e05252"),
                LyricsStatus.NONE:         ("fa5s.compact-disc", "#555555"),
            }.get(status, ("fa5s.compact-disc", "#555555"))
            item.setIcon(_qta_icon(icon_name, color))

    def show_progress(self, current: int, total: int, msg: str = "") -> None:
        self._progress.setVisible(True)
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(current)

    def hide_progress(self) -> None:
        self._progress.setVisible(False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _animate_spinners(self) -> None:
        """Rotate spinner icons for loading items."""
        self._spinner_angle = (self._spinner_angle + 45) % 360
        angle = self._spinner_angle
        for key in list(self._loading_paths):
            item = self._path_to_item.get(key)
            if item:
                try:
                    icon = qta.icon("fa5s.circle-notch", color="#e5a50a",
                                    rotated=angle)
                    item.setIcon(icon)
                except Exception:
                    pass

    @staticmethod
    def _track_sort_key(meta) -> tuple:
        try:
            disc = int(meta.disc_number.split("/")[0]) if meta.disc_number else 0
            track = int(meta.track_number.split("/")[0]) if meta.track_number else 0
        except (ValueError, AttributeError):
            disc, track = 0, 0
        return (disc, track, meta.display_title)

    def _on_selection_changed(self, current, previous) -> None:
        source_idx = self._proxy.mapToSource(current)
        item = self._model.itemFromIndex(source_idx)
        if item:
            path = item.data(PATH_ROLE)
            if path:
                self.track_selected.emit(path)

    def _on_search(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        if text:
            self._tree.expandAll()
        else:
            self._tree.expandToDepth(1)

    def _on_context_menu(self, pos) -> None:
        idx = self._tree.indexAt(pos)
        if not idx.isValid():
            return
        source_idx = self._proxy.mapToSource(idx)
        item = self._model.itemFromIndex(source_idx)
        if not item:
            return

        menu = QMenu(self)
        path = item.data(PATH_ROLE)
        if path:
            act = menu.addAction(_qta_icon("fa5s.music", "#e0e0e0"), t("lib_ctx_fetch_lyrics"))
            act.triggered.connect(lambda: self.batch_lyrics_requested.emit([path]))
            act2 = menu.addAction(_qta_icon("fa5s.image", "#e0e0e0"), t("lib_ctx_fetch_artwork"))
            act2.triggered.connect(lambda: self.batch_artwork_requested.emit([path]))
        else:
            paths = self._collect_paths(item)
            if paths:
                act = menu.addAction(
                    _qta_icon("fa5s.music", "#e0e0e0"),
                    t("lib_ctx_fetch_lyrics_n").format(n=len(paths))
                )
                act.triggered.connect(lambda: self.batch_lyrics_requested.emit(paths))
                act2 = menu.addAction(
                    _qta_icon("fa5s.image", "#e0e0e0"),
                    t("lib_ctx_fetch_artwork_n").format(n=len(paths))
                )
                act2.triggered.connect(lambda: self.batch_artwork_requested.emit(paths))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _collect_paths(self, item: QStandardItem) -> list[Path]:
        paths = []
        path = item.data(PATH_ROLE)
        if path:
            paths.append(path)
        for row in range(item.rowCount()):
            paths.extend(self._collect_paths(item.child(row)))
        return paths
