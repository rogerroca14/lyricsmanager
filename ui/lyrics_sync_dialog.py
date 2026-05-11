"""Manual lyrics synchronization dialog.

Lets the user assign timestamps to plain-text lyrics by pressing Space
while playing the track. Returns LRC-formatted text on accept.

Timing:
- Stamps are recorded as `player.elapsed + offset_seconds`.
- `offset_seconds` compensates for audio buffer + human reaction latency.
- User can run a 4-tap audio calibration to learn the offset empirically.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import qtawesome as qta
import sounddevice as sd
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QColor, QBrush
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QSizePolicy,
)

from i18n import t
from utils.helpers import (
    parse_lrc_line, format_duration, seconds_to_lrc_timestamp,
)


def _icon(name: str, color: str = "#888"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


# ----------------------------------------------------------------------
# Audio-tap calibration sub-dialog
# ----------------------------------------------------------------------

class CalibrationDialog(QDialog):
    """Plays N evenly-spaced clicks; user taps Space on each.

    The mean of (tap_time - expected_click_time) is the latency offset
    needed to align future stamps. Negative offset means user should
    stamp *earlier* than they hear it (typical case: 200-400 ms).
    """

    N_CLICKS = 4
    CLICK_INTERVAL = 1.0          # seconds
    LEAD_IN = 1.0                 # silence before first click
    CLICK_DURATION = 0.04         # seconds
    SAMPLE_RATE = 44100

    def __init__(self, device_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("lyr_cal_title"))
        self.setModal(True)
        self.resize(420, 260)
        self._device = device_id
        self._taps: list[float] = []
        self._start_time: float | None = None
        self.offset_seconds: float | None = None    # filled on accept
        self._build_ui()
        self._register_shortcut()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel(t("lyr_cal_title"))
        title.setStyleSheet("font-size:14px; font-weight:600; color:#e0e0e0;")
        root.addWidget(title)

        explain = QLabel(t("lyr_cal_explain"))
        explain.setStyleSheet("color:#bbb; font-size:11px;")
        explain.setWordWrap(True)
        root.addWidget(explain)

        self._status_label = QLabel(t("lyr_cal_press_start"))
        self._status_label.setStyleSheet(
            "background:#1f1f1f; border:1px solid #333; border-radius:4px; "
            "padding:14px; color:#9aa; font-size:12px;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setMinimumHeight(70)
        root.addWidget(self._status_label, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._btn_start = QPushButton(t("lyr_cal_start"))
        self._btn_start.setIcon(_icon("fa5s.play", "#fff"))
        self._btn_start.setStyleSheet(
            "QPushButton { background:#0078d4; color:#fff; padding:6px 14px; }"
        )
        self._btn_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_start.clicked.connect(self._start)
        btn_row.addWidget(self._btn_start)
        btn_row.addStretch(1)

        self._btn_cancel = QPushButton(t("lyr_sync_cancel"))
        self._btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)
        root.addLayout(btn_row)

    def _register_shortcut(self) -> None:
        sc = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(self._tap)

    def _start(self) -> None:
        self._taps.clear()
        self._btn_start.setEnabled(False)
        self._status_label.setText(t("lyr_cal_listen"))
        # Build click track
        sr = self.SAMPLE_RATE
        total_samples = int(sr * (self.LEAD_IN + self.CLICK_INTERVAL * self.N_CLICKS))
        out = np.zeros(total_samples, dtype="float32")
        click_len = int(sr * self.CLICK_DURATION)
        tone = np.zeros(click_len, dtype="float32")
        ts = np.arange(click_len) / sr
        tone[:] = 0.6 * np.sin(2 * np.pi * 1500 * ts) * np.exp(-ts * 80)
        for i in range(self.N_CLICKS):
            start = int(sr * (self.LEAD_IN + i * self.CLICK_INTERVAL))
            out[start:start + click_len] += tone
        try:
            sd.play(out, sr, device=self._device, blocking=False)
        except Exception as e:
            self._status_label.setText(f"Audio error: {e}")
            self._btn_start.setEnabled(True)
            return
        self._start_time = time.perf_counter()

    def _tap(self) -> None:
        if self._start_time is None:
            return
        now = time.perf_counter() - self._start_time
        if len(self._taps) >= self.N_CLICKS:
            return
        self._taps.append(now)
        remaining = self.N_CLICKS - len(self._taps)
        if remaining > 0:
            self._status_label.setText(t("lyr_cal_more").format(n=remaining))
        else:
            self._compute_and_finish()

    def _compute_and_finish(self) -> None:
        expected = [self.LEAD_IN + i * self.CLICK_INTERVAL for i in range(self.N_CLICKS)]
        diffs = [t_tap - t_exp for t_tap, t_exp in zip(self._taps, expected)]
        if len(diffs) >= 3:
            mean = sum(diffs) / len(diffs)
            worst = max(diffs, key=lambda d: abs(d - mean))
            diffs.remove(worst)
        mean_delay = sum(diffs) / len(diffs)
        # `mean_delay` = how late the user tapped relative to the click.
        # Subtract from future stamps → offset is negative.
        self.offset_seconds = -mean_delay
        ms = int(round(self.offset_seconds * 1000))
        self._status_label.setText(t("lyr_cal_done").format(ms=ms))
        try:
            sd.stop()
        except Exception:
            pass
        QTimer.singleShot(900, self.accept)

    def reject(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass
        super().reject()

    def closeEvent(self, event) -> None:
        try:
            sd.stop()
        except Exception:
            pass
        super().closeEvent(event)


# ----------------------------------------------------------------------
# Main sync dialog
# ----------------------------------------------------------------------

class LyricsSyncDialog(QDialog):
    """Modal dialog. Returns final LRC text via `result_text` after accept()."""

    REWIND_SECONDS = 3.0
    DEFAULT_OFFSET_S = -0.25
    NUDGE_FINE = 0.05
    NUDGE_COARSE = 0.5

    def __init__(
        self,
        audio_path: Path,
        lyrics_text: str,
        track_title: str = "",
        track_artist: str = "",
        device_id: int | None = None,
        audio_player=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("lyr_sync_title"))
        self.setModal(True)
        self.resize(660, 680)

        self._audio_path = Path(audio_path)
        self._track_title = track_title
        self._track_artist = track_artist
        self._device_id = device_id
        self._shared_player = audio_player    # if provided, reuse instead of creating
        self._owns_player = audio_player is None

        # Strip any existing timestamps; preserve text + blank lines.
        self._lines: list[str] = []
        self._stamps: list[float | None] = []
        for raw in lyrics_text.splitlines():
            _, text = parse_lrc_line(raw)
            self._lines.append(text)
            self._stamps.append(None)

        self._current_idx = 0
        self._slider_dragging = False
        self._dirty = False
        self._offset_seconds = self.DEFAULT_OFFSET_S
        self._player = None

        self._build_ui()
        self._init_player()
        self._refresh_list()
        self._update_progress()
        self._update_offset_label()
        self._select_index(0)

    # ------------------------------------------------------------------
    # Player
    # ------------------------------------------------------------------

    def _init_player(self) -> None:
        if self._shared_player is not None:
            # Reuse the caller's player to avoid two OutputStreams competing
            # for the same audio device.
            self._player = self._shared_player
            try:
                self._player.stop()      # reset position
            except Exception:
                pass
            self._player.position_changed.connect(self._on_position_changed)
            self._player.state_changed.connect(self._on_player_state)
            self._player.finished.connect(self._on_finished)
            self._player.error.connect(self._on_error)
            if self._audio_path.exists() and self._player.duration <= 0:
                self._player.load(self._audio_path)
            if self._player.duration > 0:
                self._duration_label.setText(format_duration(self._player.duration))
            return

        try:
            from ui.player import AudioPlayer
            self._player = AudioPlayer(self)
            if self._device_id is not None:
                self._player.set_device(self._device_id)
            self._player.position_changed.connect(self._on_position_changed)
            self._player.state_changed.connect(self._on_player_state)
            self._player.finished.connect(self._on_finished)
            self._player.error.connect(self._on_error)
            if self._audio_path.exists():
                self._player.load(self._audio_path)
                if self._player.duration > 0:
                    self._duration_label.setText(format_duration(self._player.duration))
        except Exception:
            self._player = None
            self._btn_play.setEnabled(False)
            self._btn_stop.setEnabled(False)
            self._btn_rewind.setEnabled(False)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # Header
        title = QLabel(self._track_title or self._audio_path.stem)
        title.setStyleSheet("font-size:14px; font-weight:600; color:#e0e0e0;")
        root.addWidget(title)
        if self._track_artist:
            artist = QLabel(self._track_artist)
            artist.setStyleSheet("font-size:11px; color:#888;")
            root.addWidget(artist)
        subtitle = QLabel(t("lyr_sync_subtitle"))
        subtitle.setStyleSheet("font-size:11px; color:#aaa; padding-top:4px;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Hint
        hint = QLabel(t("lyr_sync_hint"))
        hint.setStyleSheet(
            "background:#1f1f1f; color:#9aa; font-size:10px; "
            "padding:6px 8px; border:1px solid #333; border-radius:4px;"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Calibration row
        cal_row = QHBoxLayout()
        cal_row.setSpacing(6)
        self._btn_calibrate = QPushButton(t("lyr_cal_button"))
        self._btn_calibrate.setIcon(_icon("fa5s.compass", "#e0e0e0"))
        self._btn_calibrate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_calibrate.setToolTip(t("lyr_cal_tooltip"))
        self._btn_calibrate.clicked.connect(self._calibrate)
        cal_row.addWidget(self._btn_calibrate)

        self._offset_label = QLabel("")
        self._offset_label.setStyleSheet("color:#bbb; font-size:11px;")
        cal_row.addWidget(self._offset_label)
        cal_row.addStretch(1)

        self._btn_offset_reset = QPushButton(t("lyr_cal_reset"))
        self._btn_offset_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_offset_reset.setFlat(True)
        self._btn_offset_reset.setStyleSheet("color:#888; font-size:10px;")
        self._btn_offset_reset.clicked.connect(self._reset_offset)
        cal_row.addWidget(self._btn_offset_reset)
        root.addLayout(cal_row)

        # Lyrics list
        self._list = QListWidget()
        self._list.setFont(QFont("Segoe UI", 12))
        self._list.setStyleSheet(
            "QListWidget { background:#181818; border:1px solid #2a2a2a; padding:4px; }"
            "QListWidget::item { padding:6px 8px; border-radius:3px; }"
            "QListWidget::item:selected { background:#0a3a66; color:#fff; }"
        )
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._list, 1)

        # Progress
        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(self._progress_label)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#333;")
        root.addWidget(sep)

        # Player controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        self._btn_play = QPushButton()
        self._btn_play.setIcon(_icon("fa5s.play", "#e0e0e0"))
        self._btn_play.setFixedSize(38, 30)
        self._btn_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_play.clicked.connect(self._toggle_play)

        self._btn_stop = QPushButton()
        self._btn_stop.setIcon(_icon("fa5s.stop", "#e0e0e0"))
        self._btn_stop.setFixedSize(30, 30)
        self._btn_stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_stop.clicked.connect(self._stop)

        self._btn_rewind = QPushButton()
        self._btn_rewind.setIcon(_icon("fa5s.undo", "#e0e0e0"))
        self._btn_rewind.setFixedSize(30, 30)
        self._btn_rewind.setToolTip("R")
        self._btn_rewind.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_rewind.clicked.connect(self._rewind)

        self._time_label = QLabel("0:00")
        self._time_label.setStyleSheet("color:#bbb; font-size:11px; min-width:36px;")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.sliderPressed.connect(lambda: setattr(self, "_slider_dragging", True))
        self._slider.sliderReleased.connect(self._on_slider_released)

        self._duration_label = QLabel("0:00")
        self._duration_label.setStyleSheet("color:#bbb; font-size:11px; min-width:36px;")

        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_stop)
        ctrl.addWidget(self._btn_rewind)
        ctrl.addWidget(self._time_label)
        ctrl.addWidget(self._slider, 1)
        ctrl.addWidget(self._duration_label)
        root.addLayout(ctrl)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._btn_reset = QPushButton(t("lyr_sync_reset_all"))
        self._btn_reset.setIcon(_icon("fa5s.eraser", "#e0e0e0"))
        self._btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_reset.clicked.connect(self._reset_all)
        btn_row.addWidget(self._btn_reset)
        btn_row.addStretch(1)

        self._btn_cancel = QPushButton(t("lyr_sync_cancel"))
        self._btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_cancel)

        self._btn_apply = QPushButton(t("lyr_sync_apply"))
        self._btn_apply.setIcon(_icon("fa5s.check", "#ffffff"))
        self._btn_apply.setStyleSheet(
            "QPushButton { background:#0078d4; color:#fff; padding:6px 14px; }"
            "QPushButton:hover { background:#1389e6; }"
        )
        self._btn_apply.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_apply.setDefault(False)
        self._btn_apply.setAutoDefault(False)
        self._btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(self._btn_apply)
        root.addLayout(btn_row)

        self._register_shortcuts()

    def _register_shortcuts(self) -> None:
        def add(seq, handler):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(handler)

        add(Qt.Key.Key_Space, self._stamp_and_advance)
        add("Shift+Space", self._restamp_current)
        add(Qt.Key.Key_Left, self._go_prev)
        add(Qt.Key.Key_Right, self._skip_forward)
        add(Qt.Key.Key_Up, self._go_prev)
        add(Qt.Key.Key_Down, self._skip_forward)
        add(Qt.Key.Key_Backspace, self._clear_current)
        add(Qt.Key.Key_R, self._rewind)
        add("Ctrl+Return", self._on_apply)
        add(Qt.Key.Key_BracketLeft,  lambda: self._nudge_current(-self.NUDGE_FINE))
        add(Qt.Key.Key_BracketRight, lambda: self._nudge_current(+self.NUDGE_FINE))
        add("Shift+[", lambda: self._nudge_current(-self.NUDGE_COARSE))
        add("Shift+]", lambda: self._nudge_current(+self.NUDGE_COARSE))

    # ------------------------------------------------------------------
    # List rendering
    # ------------------------------------------------------------------

    def _format_item(self, idx: int) -> tuple[str, QColor]:
        text = self._lines[idx]
        ts = self._stamps[idx]
        stamp = seconds_to_lrc_timestamp(ts) if ts is not None else "  [   —   ]  "
        display = "  " + text if text else "  " + t("lyr_sync_blank")
        label = f"{stamp}   {display}"
        if not text:
            color = QColor("#666")
        elif ts is None:
            color = QColor("#bbb")
        else:
            color = QColor("#e0e0e0")
        return label, color

    def _refresh_list(self) -> None:
        self._list.clear()
        for i in range(len(self._lines)):
            label, color = self._format_item(i)
            item = QListWidgetItem(label)
            item.setForeground(QBrush(color))
            self._list.addItem(item)

    def _update_item(self, idx: int) -> None:
        if idx < 0 or idx >= self._list.count():
            return
        label, color = self._format_item(idx)
        item = self._list.item(idx)
        item.setText(label)
        item.setForeground(QBrush(color))

    def _update_progress(self) -> None:
        total = sum(1 for ln in self._lines if ln.strip())
        done = sum(1 for i, ts in enumerate(self._stamps) if ts is not None and self._lines[i].strip())
        self._progress_label.setText(
            t("lyr_sync_progress").format(done=done, total=total)
        )

    def _update_offset_label(self) -> None:
        ms = int(round(self._offset_seconds * 1000))
        self._offset_label.setText(t("lyr_cal_current").format(ms=ms))

    def _select_index(self, idx: int) -> None:
        if not self._lines:
            return
        idx = max(0, min(idx, len(self._lines) - 1))
        self._current_idx = idx
        self._list.setCurrentRow(idx)
        self._list.scrollToItem(self._list.item(idx))

    # ------------------------------------------------------------------
    # Sync actions
    # ------------------------------------------------------------------

    def _current_time(self) -> float:
        if not self._player:
            return 0.0
        return max(0.0, self._player.elapsed + self._offset_seconds)

    def _stamp_and_advance(self) -> None:
        if not self._lines:
            return
        idx = self._current_idx
        self._stamps[idx] = self._current_time()
        self._dirty = True
        self._update_item(idx)
        self._update_progress()
        if idx + 1 < len(self._lines):
            self._select_index(idx + 1)

    def _restamp_current(self) -> None:
        if not self._lines:
            return
        self._stamps[self._current_idx] = self._current_time()
        self._dirty = True
        self._update_item(self._current_idx)
        self._update_progress()

    def _nudge_current(self, delta: float) -> None:
        idx = self._current_idx
        if self._stamps[idx] is None:
            return
        self._stamps[idx] = max(0.0, self._stamps[idx] + delta)
        self._dirty = True
        self._update_item(idx)

    def _go_prev(self) -> None:
        self._select_index(self._current_idx - 1)

    def _skip_forward(self) -> None:
        self._select_index(self._current_idx + 1)

    def _clear_current(self) -> None:
        if not self._lines:
            return
        if self._stamps[self._current_idx] is not None:
            self._stamps[self._current_idx] = None
            self._dirty = True
            self._update_item(self._current_idx)
            self._update_progress()

    def _reset_all(self) -> None:
        if not any(ts is not None for ts in self._stamps):
            return
        if QMessageBox.question(
            self, t("lyr_sync_reset_all"), t("lyr_sync_reset_all") + " ?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self._stamps = [None] * len(self._lines)
        self._dirty = True
        self._refresh_list()
        self._update_progress()
        self._select_index(0)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _calibrate(self) -> None:
        # Fully stop playback during calibration so the device is free for
        # sd.play() and clicks aren't masked by music.
        if self._player:
            self._player.stop()
            self._slider.setValue(0)
            self._time_label.setText("0:00")
        dlg = CalibrationDialog(device_id=self._device_id, parent=self)
        if dlg.exec() and dlg.offset_seconds is not None:
            # Clamp to a sane range
            self._offset_seconds = max(-1.0, min(0.5, dlg.offset_seconds))
            self._update_offset_label()

    def _reset_offset(self) -> None:
        self._offset_seconds = self.DEFAULT_OFFSET_S
        self._update_offset_label()

    # ------------------------------------------------------------------
    # Player controls
    # ------------------------------------------------------------------

    def _toggle_play(self) -> None:
        if not self._player:
            return
        if self._player.is_playing:
            self._player.pause()
        elif self._player.elapsed > 0:
            self._player.pause()
        else:
            self._player.play()

    def _stop(self) -> None:
        if self._player:
            self._player.stop()
        self._slider.setValue(0)
        self._time_label.setText("0:00")

    def _rewind(self) -> None:
        if not self._player:
            return
        target = max(0.0, self._player.elapsed - self.REWIND_SECONDS)
        self._player.seek(target)

    def _on_position_changed(self, elapsed: float) -> None:
        if self._slider_dragging:
            return
        self._time_label.setText(format_duration(elapsed))
        if self._player and self._player.duration > 0:
            pos = int(elapsed / self._player.duration * self._slider.maximum())
            self._slider.blockSignals(True)
            self._slider.setValue(pos)
            self._slider.blockSignals(False)

    def _on_player_state(self, state: str) -> None:
        self._btn_play.setIcon(
            _icon("fa5s.pause", "#e0e0e0") if state == "playing"
            else _icon("fa5s.play", "#e0e0e0")
        )
        if self._player and self._player.duration > 0:
            self._duration_label.setText(format_duration(self._player.duration))

    def _on_finished(self) -> None:
        self._slider.setValue(0)
        self._time_label.setText("0:00")
        self._btn_play.setIcon(_icon("fa5s.play", "#e0e0e0"))

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Audio", msg)

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        if self._player and self._player.duration > 0:
            seek_to = self._slider.value() / self._slider.maximum() * self._player.duration
            self._player.seek(seek_to)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        idx = self._list.row(item)
        if idx >= 0:
            self._current_idx = idx

    # ------------------------------------------------------------------
    # Accept / Cancel
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        unstamped = [
            i for i, ts in enumerate(self._stamps)
            if ts is None and self._lines[i].strip()
        ]
        if unstamped:
            r = QMessageBox.question(
                self, t("lyr_sync_title"),
                t("lyr_sync_unstamped_warning").format(n=len(unstamped)),
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self._stop_player()
        self.accept()

    def _on_cancel(self) -> None:
        if self._dirty:
            r = QMessageBox.question(
                self, t("lyr_sync_title"), t("lyr_sync_confirm_discard"),
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self._stop_player()
        self.reject()

    def reject(self) -> None:
        self._stop_player()
        super().reject()

    def closeEvent(self, event) -> None:
        if self._dirty:
            r = QMessageBox.question(
                self, t("lyr_sync_title"), t("lyr_sync_confirm_discard"),
            )
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._stop_player()
        super().closeEvent(event)

    def _stop_player(self) -> None:
        if not self._player:
            return
        try:
            self._player.stop()
        except Exception:
            pass
        if not self._owns_player:
            # Disconnect only our slots; leave the player alive for the caller.
            for sig, slot in (
                (self._player.position_changed, self._on_position_changed),
                (self._player.state_changed, self._on_player_state),
                (self._player.finished, self._on_finished),
                (self._player.error, self._on_error),
            ):
                try:
                    sig.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    @property
    def result_text(self) -> str:
        out = []
        for text, ts in zip(self._lines, self._stamps):
            if ts is not None:
                out.append(f"{seconds_to_lrc_timestamp(ts)}{text}")
            else:
                out.append(text)
        return "\n".join(out)
