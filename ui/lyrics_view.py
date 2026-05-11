"""Lyrics panel — preview only.

Shows the track's lyrics (plain or karaoke-synced) with a playback
control bar. All editing/searching/syncing lives in `LyricsEditorDialog`,
opened via the single 'Edit / Search' button.
"""

from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSlider, QFrame, QStackedWidget,
)


class _ClickableDisplay(QTextEdit):
    """Read-only display that emits `clicked_empty` on click when the
    container marks it as empty (via `set_empty(True)`). Lets the empty
    state act as a giant button to open the editor."""

    clicked_empty = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_empty = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_empty(self, empty: bool) -> None:
        self._is_empty = empty
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if empty
            else Qt.CursorShape.IBeamCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._is_empty:
            self.clicked_empty.emit()
            return
        super().mousePressEvent(event)

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
    """Preview-only lyrics panel. Edits are delegated to the editor dialog."""

    save_requested = pyqtSignal(object)   # LyricsResult (built from editor result)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meta: TrackMetadata | None = None
        self._current_text: str = ""
        self._source: str = ""
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

        self._btn_edit = QPushButton(t("lyr_edit_button"))
        self._btn_edit.setIcon(_icon("fa5s.edit", "#e0e0e0"))
        self._btn_edit.setFixedHeight(28)
        self._btn_edit.setStyleSheet(
            "QPushButton { font-size:11px; padding:2px 12px; background:#0a3a66; color:#fff; }"
            "QPushButton:hover { background:#0d4a80; }"
            "QPushButton:disabled { background:#2a2a2a; color:#555; }"
        )
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._on_edit_clicked)
        top.addWidget(self._btn_edit)

        root.addLayout(top)

        # ── Stacked main area ──────────────────────────────────────────
        self._stack = QStackedWidget()

        # Page 0 — read-only source view (LRC or plain). Click-to-edit when empty.
        self._display = _ClickableDisplay()
        self._display.setReadOnly(True)
        self._display.setFont(QFont("Consolas", 11))
        self._display.setStyleSheet(
            "QTextEdit { background:#1a1a1a; border:1px solid #2a2a2a; padding:8px;"
            " color:#e0e0e0; }"
        )
        self._display.clicked_empty.connect(self._on_edit_clicked)
        self._stack.addWidget(self._display)

        # Page 1 — karaoke display
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
            self._btn_play.setToolTip("Install sounddevice + soundfile for playback")

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
        self._clear_sync()
        self._current_text = ""
        self._source = ""
        self._display.clear()
        self._source_label.setText(t("lyr_no_lyrics"))
        self._btn_edit.setEnabled(True)   # always enabled when a track is loaded

        from core.lyrics_manager import read_lrc_file
        lrc = read_lrc_file(meta.path)
        if lrc:
            self._show_text(lrc, "local .lrc")
        else:
            full_tags = meta.raw_tags
            embedded = (
                full_tags.get("lyrics") or full_tags.get("LYRICS") or
                full_tags.get("unsyncedlyrics") or full_tags.get("UNSYNCEDLYRICS")
            )
            if embedded:
                text = embedded[0] if isinstance(embedded, list) else str(embedded)
                self._show_text(text, "embedded metadata")
            else:
                self._render_empty_state()

        if self._player and meta.path.exists():
            self._player.load(meta.path)
            if meta.duration:
                self._slider.setMaximum(int(meta.duration * 10))
                self._duration_label.setText(format_duration(meta.duration))

    def set_lyrics_result(self, result) -> None:
        """Called when an external fetch (toolbar/menu) returns lyrics."""
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
            self._show_text(content or "", src)
        else:
            # No result: keep current preview if any, otherwise refresh empty
            # state so the call-to-action stays visible and reachable.
            if not self._current_text.strip() and self._meta is not None:
                self._render_empty_state()
            self._source_label.setText(t("lyr_not_found"))
            self._status.setText(t("lyr_no_results"))

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def on_fetch_done(self) -> None:
        # Kept for compatibility with main_window's external fetch flow.
        pass

    def clear(self) -> None:
        self._meta = None
        self._current_text = ""
        self._source = ""
        self._display.clear()
        self._display.set_empty(True)
        self._clear_sync()
        self._source_label.setText(t("lyr_no_lyrics"))
        self._btn_edit.setText(t("lyr_add_button"))
        self._btn_edit.setIcon(_icon("fa5s.plus", "#e0e0e0"))
        self._btn_edit.setEnabled(False)
        if self._player:
            self._player.stop()

    # ------------------------------------------------------------------
    # Toggle preview / karaoke
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

    def _show_text(self, text: str, source: str) -> None:
        self._current_text = text
        self._source = source
        self._display.set_empty(not bool(text.strip()))
        self._display.setPlainText(text)
        self._source_label.setText(t("lyr_source").format(source=source))
        self._parse_sync(text)
        if text.strip():
            self._btn_edit.setText(t("lyr_edit_button"))
            self._btn_edit.setIcon(_icon("fa5s.edit", "#e0e0e0"))
            self._btn_edit.setEnabled(self._meta is not None)
        else:
            self._render_empty_state()

    def _render_empty_state(self) -> None:
        """Show a prominent click-to-add prompt inside the display area."""
        self._current_text = ""
        self._source = ""
        html = (
            "<div style='text-align:center; color:#888; padding:48px 16px;'>"
            "<div style='font-size:32px; margin-bottom:14px;'>♪</div>"
            "<div style='font-size:13px; line-height:1.6; white-space:pre-line;'>"
            f"{t('lyr_empty_state')}"
            "</div></div>"
        )
        self._display.setHtml(html)
        self._display.set_empty(True)
        self._source_label.setText(t("lyr_no_lyrics"))
        self._btn_edit.setText(t("lyr_add_button"))
        self._btn_edit.setIcon(_icon("fa5s.plus", "#e0e0e0"))
        # Track exists if `_meta` is set — keep the action reachable.
        self._btn_edit.setEnabled(self._meta is not None)
        self._synced_lines = []
        self._sync_display.clear()

    def _parse_sync(self, text: str) -> None:
        self._synced_lines = parse_lrc(text)
        self._sync_display.clear()
        if self._synced_lines:
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
    # Karaoke advance + highlight
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

        if idx > 0:
            prev = doc.findBlockByNumber(idx - 1)
            c = QTextCursor(prev)
            c.select(QTextCursor.SelectionType.BlockUnderCursor)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#aaaaaa"))
            fmt.setFontPointSize(12)
            c.setCharFormat(fmt)

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
    # Editor popup
    # ------------------------------------------------------------------

    def _on_edit_clicked(self) -> None:
        if not self._meta:
            return
        # Stop the view's player and hand the same instance to the editor /
        # sync dialog so they share one audio stream — having two players
        # racing for the same device causes silent playback on Windows.
        if self._player:
            self._player.stop()
            self._slider.setValue(0)
            self._time_label.setText("0:00")

        cfg = get_config()
        device_id = cfg.get("audio_output_device")

        from ui.lyrics_editor_dialog import LyricsEditorDialog
        dlg = LyricsEditorDialog(
            audio_path=self._meta.path,
            initial_text=self._current_text,
            track_title=self._meta.title,
            track_artist=self._meta.artist,
            track_album=self._meta.album,
            duration=self._meta.duration,
            device_id=device_id,
            audio_player=self._player,
            parent=self.window(),
        )
        if not dlg.exec():
            return

        new_text = dlg.result_text
        if not new_text.strip():
            return
        self._show_text(new_text, "edited")

        from core.lyrics_manager import LyricsResult
        is_synced = bool(parse_lrc(new_text))
        result = LyricsResult(
            synced=new_text if is_synced else None,
            plain=None if is_synced else new_text,
            source="manual",
            title=self._meta.title,
            artist=self._meta.artist,
            album=self._meta.album,
        )
        self.save_requested.emit(result)
