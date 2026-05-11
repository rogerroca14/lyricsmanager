"""Lyrics editor / search popup.

Single entry point for everything write-related on a track's lyrics:
- Paste / type plain text
- Fetch from online sources
- Open the manual sync dialog
- Return the final text on Apply (caller persists)
"""

from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QMessageBox, QSizePolicy,
)

from i18n import t
from utils.helpers import parse_lrc


def _icon(name: str, color: str = "#888"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


class LyricsEditorDialog(QDialog):
    """Modal popup. After accept() the final text is available via `result_text`."""

    def __init__(
        self,
        audio_path: Path,
        initial_text: str,
        track_title: str = "",
        track_artist: str = "",
        track_album: str = "",
        duration: float | None = None,
        device_id: int | None = None,
        audio_player=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("lyr_editor_title"))
        self.setModal(True)
        self.resize(640, 620)

        self._audio_path = Path(audio_path)
        self._title = track_title
        self._artist = track_artist
        self._album = track_album
        self._duration = duration
        self._device_id = device_id
        self._audio_player = audio_player
        self._original_text = initial_text
        self._dirty = False
        self._fetch_worker = None

        self._build_ui()
        self._editor.setPlainText(initial_text)
        self._editor.textChanged.connect(self._on_text_changed)
        self._update_buttons()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # Header
        title = QLabel(self._title or self._audio_path.stem)
        title.setStyleSheet("font-size:14px; font-weight:600; color:#e0e0e0;")
        root.addWidget(title)
        meta_parts = [p for p in (self._artist, self._album) if p]
        if meta_parts:
            sub = QLabel(" — ".join(meta_parts))
            sub.setStyleSheet("font-size:11px; color:#888;")
            root.addWidget(sub)

        subtitle = QLabel(t("lyr_editor_subtitle"))
        subtitle.setStyleSheet("font-size:11px; color:#aaa; padding-top:4px;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Action row: fetch + sync
        actions = QHBoxLayout()
        actions.setSpacing(6)

        self._btn_fetch = QPushButton(t("lyr_editor_fetch"))
        self._btn_fetch.setIcon(_icon("fa5s.search", "#e0e0e0"))
        self._btn_fetch.setToolTip(t("lyr_editor_fetch_tip"))
        self._btn_fetch.clicked.connect(self._on_fetch)
        actions.addWidget(self._btn_fetch)

        self._btn_sync = QPushButton(t("lyr_sync_manual"))
        self._btn_sync.setIcon(_icon("fa5s.stopwatch", "#e0e0e0"))
        self._btn_sync.setToolTip(t("lyr_sync_subtitle"))
        self._btn_sync.clicked.connect(self._on_sync)
        actions.addWidget(self._btn_sync)

        self._btn_clear = QPushButton(t("lyr_editor_clear"))
        self._btn_clear.setIcon(_icon("fa5s.trash-alt", "#e0e0e0"))
        self._btn_clear.clicked.connect(self._on_clear)
        actions.addWidget(self._btn_clear)

        actions.addStretch(1)

        self._kind_label = QLabel("")
        self._kind_label.setStyleSheet("color:#888; font-size:11px;")
        actions.addWidget(self._kind_label)
        root.addLayout(actions)

        # Editor
        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 11))
        self._editor.setPlaceholderText(t("lyr_editor_placeholder"))
        self._editor.setStyleSheet(
            "QTextEdit { background:#181818; border:1px solid #2a2a2a; padding:8px; }"
        )
        self._editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._editor, 1)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(self._status)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#333;")
        root.addWidget(sep)

        # Bottom row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch(1)

        self._btn_cancel = QPushButton(t("lyr_sync_cancel"))
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_cancel)

        self._btn_apply = QPushButton(t("lyr_editor_apply"))
        self._btn_apply.setIcon(_icon("fa5s.check", "#ffffff"))
        self._btn_apply.setStyleSheet(
            "QPushButton { background:#0078d4; color:#fff; padding:6px 14px; }"
            "QPushButton:hover { background:#1389e6; }"
        )
        self._btn_apply.setDefault(True)
        self._btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_apply)
        root.addLayout(btn_row)

        # Shortcuts
        sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc.activated.connect(self.accept)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _current_text(self) -> str:
        return self._editor.toPlainText()

    def _is_synced(self) -> bool:
        return bool(parse_lrc(self._current_text()))

    def _update_buttons(self) -> None:
        text = self._current_text().strip()
        has_content = bool(text)
        self._btn_sync.setEnabled(has_content and self._audio_path.exists())
        self._btn_clear.setEnabled(has_content)
        if not has_content:
            self._kind_label.setText("")
        elif self._is_synced():
            self._kind_label.setText(t("lyr_editor_kind_synced"))
        else:
            self._kind_label.setText(t("lyr_editor_kind_plain"))

    def _on_text_changed(self) -> None:
        self._dirty = self._current_text() != self._original_text
        self._update_buttons()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_fetch(self) -> None:
        from ui.workers import LyricsWorker
        self._btn_fetch.setEnabled(False)
        self._status.setText(t("lyr_searching"))
        worker = LyricsWorker(self._title, self._artist, self._album, self._duration)
        worker.finished.connect(self._on_fetch_done)
        worker.finished.connect(worker.deleteLater)
        self._fetch_worker = worker
        worker.start()

    def _on_fetch_done(self, result) -> None:
        self._btn_fetch.setEnabled(True)
        if not result:
            self._status.setText(t("lyr_no_results"))
            return
        # Confirm overwrite if editor has unsaved content
        if self._current_text().strip() and self._dirty:
            r = QMessageBox.question(
                self, t("lyr_editor_title"),
                t("lyr_editor_overwrite_confirm").format(source=result.source),
            )
            if r != QMessageBox.StandardButton.Yes:
                self._status.setText("")
                return
        content = result.synced if result.has_synced else result.plain
        if content:
            self._editor.setPlainText(content)
            self._status.setText(t("status_lyrics_found").format(source=result.source))

    def _on_sync(self) -> None:
        text = self._current_text().strip()
        if not text:
            self._status.setText(t("lyr_sync_no_lines"))
            return
        from ui.lyrics_sync_dialog import LyricsSyncDialog
        dlg = LyricsSyncDialog(
            audio_path=self._audio_path,
            lyrics_text=self._current_text(),
            track_title=self._title,
            track_artist=self._artist,
            device_id=self._device_id,
            audio_player=self._audio_player,
            parent=self,
        )
        if dlg.exec():
            self._editor.setPlainText(dlg.result_text)
            self._status.setText(t("lyr_editor_synced_ok"))

    def _on_clear(self) -> None:
        if not self._current_text().strip():
            return
        r = QMessageBox.question(
            self, t("lyr_editor_title"), t("lyr_editor_clear_confirm"),
        )
        if r == QMessageBox.StandardButton.Yes:
            self._editor.clear()

    # ------------------------------------------------------------------
    # Accept / Cancel
    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        if self._dirty:
            r = QMessageBox.question(
                self, t("lyr_editor_title"), t("lyr_editor_discard_confirm"),
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.reject()

    def closeEvent(self, event) -> None:
        if self._dirty:
            r = QMessageBox.question(
                self, t("lyr_editor_title"), t("lyr_editor_discard_confirm"),
            )
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    @property
    def result_text(self) -> str:
        return self._editor.toPlainText()

    @property
    def is_synced(self) -> bool:
        return self._is_synced()

    @property
    def has_changes(self) -> bool:
        return self._dirty
