"""Lyrics panel: fetch, display, preview and edit synchronized lyrics."""

from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSlider, QFrame, QStackedWidget, QSizePolicy,
)

from config import get_config
from core.metadata import TrackMetadata
from i18n import t
from utils.helpers import parse_lrc, format_duration


def _icon(name: str, color: str = "#888"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


class LyricsView(QWidget):
    fetch_requested = pyqtSignal()
    save_requested  = pyqtSignal(object)   # LyricsResult

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meta: TrackMetadata | None = None
        self._lyrics_result = None
        self._synced_lines: list[tuple[float, str]] = []
        self._current_line = -1
        self._slider_dragging = False

        self._player = None
        self._init_player()
        self._build_ui()

    # ------------------------------------------------------------------
    # Player init
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── Top bar ────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(6)

        self._source_label = QLabel(t("lyr_no_lyrics"))
        self._source_label.setStyleSheet("color:#888; font-size:12px;")
        top.addWidget(self._source_label, 1)

        # Toggle: Letras ↔ Karaoke
        self._btn_toggle = QPushButton(t("lyr_sync_preview"))
        self._btn_toggle.setIcon(_icon("fa5s.eye", "#888"))
        self._btn_toggle.setCheckable(True)
        self._btn_toggle.setChecked(False)
        self._btn_toggle.setFixedHeight(28)
        self._btn_toggle.setStyleSheet(
            "QPushButton { font-size:11px; padding:2px 10px; }"
            "QPushButton:checked { background:#0078d4; color:white; border-color:#0078d4; }"
        )
        self._btn_toggle.toggled.connect(self._on_toggle_view)
        top.addWidget(self._btn_toggle)

        self._btn_fetch = QPushButton(t("lyr_fetch"))
        self._btn_fetch.setIcon(_icon("fa5s.search", "#e0e0e0"))
        self._btn_fetch.setFixedHeight(28)
        self._btn_fetch.clicked.connect(self._on_fetch_clicked)
        top.addWidget(self._btn_fetch)

        self._btn_save = QPushButton(t("lyr_save"))
        self._btn_save.setIcon(_icon("fa5s.save", "#e0e0e0"))
        self._btn_save.setFixedHeight(28)
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        top.addWidget(self._btn_save)

        root.addLayout(top)

        # ── Stacked main area ──────────────────────────────────────────
        self._stack = QStackedWidget()

        # Page 0 — editable source (.lrc / plain)
        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 11))
        self._editor.setPlaceholderText("Lyrics will appear here…")
        self._editor.textChanged.connect(self._on_text_changed)
        self._stack.addWidget(self._editor)

        # Page 1 — karaoke / sync display
        self._sync_display = QTextEdit()
        self._sync_display.setReadOnly(True)
        self._sync_display.setFont(QFont("Segoe UI", 14))
        self._sync_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sync_display.setStyleSheet(
            "QTextEdit { background:#1c1c1c; border:none; padding:16px; }"
        )
        self._stack.addWidget(self._sync_display)

        root.addWidget(self._stack, 1)

        # ── Divider ────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#383838;")
        root.addWidget(line)

        # ── Player controls ────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        self._btn_play = QPushButton()
        self._btn_play.setIcon(_icon("fa5s.play", "#e0e0e0"))
        self._btn_play.setFixedSize(36, 28)
        self._btn_play.clicked.connect(self._on_play_clicked)
        if self._player is None:
            self._btn_play.setEnabled(False)
            self._btn_play.setToolTip("Instala sounddevice + soundfile para reproducción")

        self._btn_stop = QPushButton()
        self._btn_stop.setIcon(_icon("fa5s.stop", "#e0e0e0"))
        self._btn_stop.setFixedSize(28, 28)
        self._btn_stop.clicked.connect(self._on_stop)
        if self._player is None:
            self._btn_stop.setEnabled(False)

        self._time_label = QLabel("0:00")
        self._time_label.setStyleSheet("color:#888; font-size:11px; min-width:34px;")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.sliderMoved.connect(self._on_slider_moved)

        self._duration_label = QLabel("0:00")
        self._duration_label.setStyleSheet("color:#888; font-size:11px; min-width:34px;")

        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_stop)
        ctrl.addWidget(self._time_label)
        ctrl.addWidget(self._slider, 1)
        ctrl.addWidget(self._duration_label)
        root.addLayout(ctrl)

        # ── Status ─────────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet("color:#555; font-size:11px;")
        root.addWidget(self._status)

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

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def on_fetch_done(self) -> None:
        self._btn_fetch.setEnabled(True)

    def clear(self) -> None:
        self._meta = None
        self._lyrics_result = None
        self._editor.clear()
        self._clear_sync()
        self._source_label.setText(t("lyr_no_lyrics"))
        self._btn_save.setEnabled(False)
        if self._player:
            self._player.stop()

    # ------------------------------------------------------------------
    # Toggle view
    # ------------------------------------------------------------------

    def _on_toggle_view(self, checked: bool) -> None:
        self._stack.setCurrentIndex(1 if checked else 0)
        self._btn_toggle.setIcon(
            _icon("fa5s.eye-slash", "#e0e0e0") if checked
            else _icon("fa5s.eye", "#888")
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_lyrics_text(self, text: str, source: str) -> None:
        self._editor.blockSignals(True)
        self._editor.setPlainText(text)
        self._editor.blockSignals(False)
        self._source_label.setText(t("lyr_source").format(source=source))
        self._parse_sync(text)

        if self._player and self._meta and self._meta.path.exists():
            self._player.load(self._meta.path)
            if self._meta.duration:
                self._slider.setMaximum(int(self._meta.duration * 10))
                self._duration_label.setText(format_duration(self._meta.duration))

    def _parse_sync(self, text: str) -> None:
        self._synced_lines = parse_lrc(text)
        self._sync_display.clear()
        if self._synced_lines:
            # Clean text without timestamps for karaoke view
            self._sync_display.setPlainText(
                "\n".join(line for _, line in self._synced_lines)
            )
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
    # Playback slots
    # ------------------------------------------------------------------

    def _on_play_clicked(self) -> None:
        if not self._player:
            return
        if self._player.is_playing:
            self._player.pause()
        else:
            if self._player.elapsed > 0:
                self._player.pause()   # resume
            else:
                self._player.play()
            # Auto-switch to karaoke view if there are synced lines
            if self._synced_lines and not self._btn_toggle.isChecked():
                self._btn_toggle.setChecked(True)

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
        self._btn_play.setIcon(
            _icon("fa5s.pause", "#e0e0e0") if state == "playing"
            else _icon("fa5s.play", "#e0e0e0")
        )

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
        reset_fmt.setForeground(QColor("#666"))
        reset_fmt.setFontPointSize(13)
        reset_fmt.setFontWeight(400)
        cursor.setCharFormat(reset_fmt)
        cursor.clearSelection()

        if idx < 0 or idx >= doc.blockCount():
            return

        # Highlight line above (preview)
        if idx > 0:
            prev = doc.findBlockByNumber(idx - 1)
            c = QTextCursor(prev)
            c.select(QTextCursor.SelectionType.BlockUnderCursor)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#aaaaaa"))
            fmt.setFontPointSize(12)
            c.setCharFormat(fmt)

        # Highlight current line (active)
        block = doc.findBlockByNumber(idx)
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        hl_fmt = QTextCharFormat()
        hl_fmt.setBackground(QColor("transparent"))
        hl_fmt.setForeground(QColor("#ffffff"))
        hl_fmt.setFontPointSize(16)
        hl_fmt.setFontWeight(700)
        cursor.setCharFormat(hl_fmt)
        self._sync_display.setTextCursor(cursor)
        self._sync_display.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Buttons
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
