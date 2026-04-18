"""Lyrics panel: fetch, display, edit, and preview synchronized lyrics.

Includes real audio playback via ui.player (sounddevice + soundfile).
"""

from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSplitter, QSlider, QGroupBox, QFrame, QComboBox,
)

from config import get_config
from core.metadata import TrackMetadata
from i18n import t
from utils.helpers import parse_lrc, format_duration


def _icon(name: str, color: str = "#888") -> "QIcon":
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


class LyricsView(QWidget):
    fetch_requested = pyqtSignal()
    save_requested = pyqtSignal(object)     # LyricsResult

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meta: TrackMetadata | None = None
        self._lyrics_result = None
        self._synced_lines: list[tuple[float, str]] = []
        self._current_line = -1

        # Audio player (lazy import to avoid errors if sounddevice not installed)
        self._player = None
        self._init_player()

        self._build_ui()
        self._populate_devices()

    def _init_player(self) -> None:
        try:
            from ui.player import AudioPlayer
            self._player = AudioPlayer(self)
            self._player.position_changed.connect(self._on_position_changed)
            self._player.state_changed.connect(self._on_player_state)
            self._player.finished.connect(self._on_playback_finished)
            self._player.error.connect(self._on_player_error)
        except Exception:
            self._player = None

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Top bar
        top = QHBoxLayout()
        self._source_label = QLabel(t("lyr_no_lyrics"))
        self._source_label.setStyleSheet("color:#888; font-size:12px;")
        top.addWidget(self._source_label)
        top.addStretch()

        self._btn_fetch = QPushButton(t("lyr_fetch"))
        self._btn_fetch.setIcon(_icon("fa5s.search", "#e0e0e0"))
        self._btn_fetch.clicked.connect(self._on_fetch_clicked)
        self._btn_save = QPushButton(t("lyr_save"))
        self._btn_save.setIcon(_icon("fa5s.save", "#e0e0e0"))
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        top.addWidget(self._btn_fetch)
        top.addWidget(self._btn_save)
        root.addLayout(top)

        # Split: editor | sync preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left: editor ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 11))
        self._editor.setPlaceholderText("Lyrics will appear here…")
        self._editor.textChanged.connect(self._on_text_changed)
        left_layout.addWidget(self._editor)
        splitter.addWidget(left)

        # ---- Right: sync preview + player ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Sync display
        preview_label = QLabel(t("lyr_sync_preview"))
        preview_label.setStyleSheet("color:#555; font-size:11px; text-transform:uppercase; letter-spacing:1px;")
        right_layout.addWidget(preview_label)

        self._sync_display = QTextEdit()
        self._sync_display.setReadOnly(True)
        self._sync_display.setFont(QFont("Segoe UI", 13))
        self._sync_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self._sync_display, 1)

        # Device selector
        if self._player is not None:
            dev_row = QHBoxLayout()
            dev_icon = QLabel()
            dev_icon.setPixmap(_icon("fa5s.headphones", "#888").pixmap(14, 14))
            dev_lbl = QLabel(t("player_device"))
            dev_lbl.setStyleSheet("color:#888; font-size:11px;")
            self._combo_device = QComboBox()
            self._combo_device.setMinimumWidth(200)
            self._combo_device.currentIndexChanged.connect(self._on_device_changed)
            dev_row.addWidget(dev_icon)
            dev_row.addWidget(dev_lbl)
            dev_row.addWidget(self._combo_device, 1)
            right_layout.addLayout(dev_row)
        else:
            self._combo_device = None

        # Playback controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        self._btn_play = QPushButton()
        self._btn_play.setIcon(_icon("fa5s.play", "#e0e0e0"))
        self._btn_play.setFixedWidth(80)
        self._btn_play.clicked.connect(self._on_play_clicked)

        self._btn_stop = QPushButton()
        self._btn_stop.setIcon(_icon("fa5s.stop", "#e0e0e0"))
        self._btn_stop.setFixedWidth(50)
        self._btn_stop.clicked.connect(self._on_stop)

        if self._player is None:
            self._btn_play.setEnabled(False)
            self._btn_stop.setEnabled(False)
            self._btn_play.setToolTip("Install sounddevice + soundfile for playback")

        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_stop)
        ctrl.addStretch()
        right_layout.addLayout(ctrl)

        # Time slider
        slider_row = QHBoxLayout()
        self._time_label = QLabel("0:00")
        self._time_label.setStyleSheet("color:#888; font-size:11px; min-width:36px;")
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        self._slider_dragging = False
        self._duration_label = QLabel("0:00")
        self._duration_label.setStyleSheet("color:#888; font-size:11px; min-width:36px;")
        slider_row.addWidget(self._time_label)
        slider_row.addWidget(self._slider, 1)
        slider_row.addWidget(self._duration_label)
        right_layout.addLayout(slider_row)

        splitter.addWidget(right)
        splitter.setSizes([480, 380])
        root.addWidget(splitter, 1)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet("color:#555; font-size:11px;")
        root.addWidget(self._status)

    def _populate_devices(self) -> None:
        if self._combo_device is None:
            return
        try:
            from ui.player import list_output_devices, get_default_device_id
            devices = list_output_devices()
            default_id = get_default_device_id()
            self._combo_device.blockSignals(True)
            self._combo_device.clear()
            self._combo_device.addItem(t("player_no_device"), None)
            for dev in devices:
                self._combo_device.addItem(dev["display"], dev["id"])
                if dev["default"] or dev["id"] == default_id:
                    self._combo_device.setCurrentIndex(self._combo_device.count() - 1)
            self._combo_device.blockSignals(False)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_track(self, meta: TrackMetadata) -> None:
        self._meta = meta
        self._lyrics_result = None
        self._clear_sync()
        self._editor.clear()
        self._source_label.setText(t("lyr_no_lyrics"))
        self._btn_save.setEnabled(False)

        # Load existing .lrc sidecar
        from core.lyrics_manager import read_lrc_file
        lrc = read_lrc_file(meta.path)
        if lrc:
            self._set_lyrics_text(lrc, "local .lrc")
            return

        # Embedded lyrics
        full_tags = meta.raw_tags
        embedded = (
            full_tags.get("lyrics") or full_tags.get("LYRICS") or
            full_tags.get("unsyncedlyrics") or full_tags.get("UNSYNCEDLYRICS")
        )
        if embedded:
            text = embedded[0] if isinstance(embedded, list) else str(embedded)
            self._set_lyrics_text(text, "embedded metadata")
            return

        self._source_label.setText(t("lyr_no_lyrics") + " — " + t("lyr_fetch"))

        # Load audio for playback
        if self._player and meta.path.exists():
            self._player.load(meta.path)
            if meta.duration:
                self._slider.setMaximum(int(meta.duration * 10))
                self._duration_label.setText(format_duration(meta.duration))

    def set_lyrics_result(self, result) -> None:
        self._lyrics_result = result
        if result:
            cfg = get_config()
            prefer_plain = cfg.get("prefer_plain_lyrics")
            if prefer_plain and result.has_plain:
                content = result.plain
                src = f"{result.source} (plain)"
            elif result.has_synced:
                content = result.synced
                src = f"{result.source} (synced)"
            else:
                content = result.plain
                src = f"{result.source} (plain)"
            self._set_lyrics_text(content or "", src)
            self._btn_save.setEnabled(True)
        else:
            self._source_label.setText(t("lyr_not_found"))
            self._status.setText(t("lyr_no_results"))

    def clear(self) -> None:
        self._meta = None
        self._lyrics_result = None
        self._editor.clear()
        self._clear_sync()
        self._source_label.setText(t("lyr_no_lyrics"))
        self._btn_save.setEnabled(False)
        if self._player:
            self._player.stop()

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def on_fetch_done(self) -> None:
        self._btn_fetch.setEnabled(True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_lyrics_text(self, text: str, source: str) -> None:
        self._editor.blockSignals(True)
        self._editor.setPlainText(text)
        self._editor.blockSignals(False)
        self._source_label.setText(t("lyr_source").format(source=source))
        self._parse_sync(text)

        # (Re)load audio
        if self._player and self._meta and self._meta.path.exists():
            self._player.load(self._meta.path)
            if self._meta.duration:
                self._slider.setMaximum(int(self._meta.duration * 10))
                self._duration_label.setText(format_duration(self._meta.duration))

    def _parse_sync(self, text: str) -> None:
        self._synced_lines = parse_lrc(text)
        self._sync_display.clear()
        if self._synced_lines:
            self._sync_display.setPlainText("\n".join(line for _, line in self._synced_lines))
        else:
            self._sync_display.setPlainText(text)

    def _clear_sync(self) -> None:
        self._synced_lines = []
        self._current_line = -1
        self._sync_display.clear()
        self._slider.setValue(0)
        self._time_label.setText("0:00")
        self._duration_label.setText("0:00")

    # ------------------------------------------------------------------
    # Audio playback slots
    # ------------------------------------------------------------------

    def _on_play_clicked(self) -> None:
        if not self._player:
            return
        if self._player.is_playing:
            self._player.pause()
        else:
            if self._player.elapsed > 0:
                self._player.pause()    # resume
            else:
                self._player.play()

    def _on_stop(self) -> None:
        if self._player:
            self._player.stop()
        self._slider.setValue(0)
        self._time_label.setText("0:00")
        self._current_line = -1
        self._highlight_line(-1)

    def _on_position_changed(self, elapsed: float) -> None:
        if self._slider_dragging:
            return
        self._time_label.setText(format_duration(elapsed))
        if self._player and self._player.duration > 0:
            pos = int(elapsed / self._player.duration * self._slider.maximum())
            self._slider.blockSignals(True)
            self._slider.setValue(pos)
            self._slider.blockSignals(False)
        self._advance_lyrics(elapsed)

    def _on_player_state(self, state: str) -> None:
        if state == "playing":
            self._btn_play.setIcon(_icon("fa5s.pause", "#e0e0e0"))
        else:
            self._btn_play.setIcon(_icon("fa5s.play", "#e0e0e0"))

    def _on_playback_finished(self) -> None:
        self._slider.setValue(0)
        self._time_label.setText("0:00")
        self._current_line = -1
        self._highlight_line(-1)
        self._btn_play.setIcon(_icon("fa5s.play", "#e0e0e0"))

    def _on_player_error(self, msg: str) -> None:
        self._status.setText(f"Audio error: {msg}")

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        if self._player and self._player.duration > 0:
            seek_to = self._slider.value() / self._slider.maximum() * self._player.duration
            self._player.seek(seek_to)

    def _on_slider_moved(self, value: int) -> None:
        if self._player and self._player.duration > 0:
            elapsed = value / self._slider.maximum() * self._player.duration
            self._time_label.setText(format_duration(elapsed))

    def _on_device_changed(self, idx: int) -> None:
        if self._player and self._combo_device:
            device_id = self._combo_device.itemData(idx)
            self._player.set_device(device_id)

    # ------------------------------------------------------------------
    # Lyrics sync
    # ------------------------------------------------------------------

    def _advance_lyrics(self, elapsed: float) -> None:
        if not self._synced_lines:
            return
        line_idx = -1
        for i, (ts, _) in enumerate(self._synced_lines):
            if ts <= elapsed:
                line_idx = i
            else:
                break
        if line_idx != self._current_line:
            self._current_line = line_idx
            self._highlight_line(line_idx)

    def _highlight_line(self, idx: int) -> None:
        doc = self._sync_display.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        reset_fmt = QTextCharFormat()
        reset_fmt.setBackground(QColor("transparent"))
        reset_fmt.setForeground(QColor("#888"))
        reset_fmt.setFontPointSize(12)
        cursor.setCharFormat(reset_fmt)
        cursor.clearSelection()

        if idx < 0 or idx >= doc.blockCount():
            return

        block = doc.findBlockByNumber(idx)
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        hl_fmt = QTextCharFormat()
        hl_fmt.setBackground(QColor("#0078d4"))
        hl_fmt.setForeground(QColor("white"))
        hl_fmt.setFontPointSize(14)
        hl_fmt.setFontWeight(700)
        cursor.setCharFormat(hl_fmt)
        self._sync_display.setTextCursor(cursor)
        self._sync_display.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_fetch_clicked(self) -> None:
        if not self._meta:
            self._status.setText(t("lyr_select_track"))
            return
        self._btn_fetch.setEnabled(False)
        self._status.setText(t("lyr_searching"))
        self.fetch_requested.emit()

    def _on_save(self) -> None:
        if self._lyrics_result:
            self.save_requested.emit(self._lyrics_result)

    def _on_text_changed(self) -> None:
        self._parse_sync(self._editor.toPlainText())
