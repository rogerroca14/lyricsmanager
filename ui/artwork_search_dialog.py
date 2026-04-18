"""Streaming artwork search dialog.

Opens immediately and populates cards one by one as each result arrives.
Provides separate "Save as cover.png" and "Embed in metadata" actions,
both going through ArtworkSaveDialog for size selection first.
"""

from __future__ import annotations

import io

import qtawesome as qta
from PIL import Image
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QSizePolicy,
)

from i18n import t


CARD_W = 150
CARD_H = 210
THUMB  = 130


def _icon(name: str, color: str = "#e0e0e0"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


class ArtworkSearchDialog(QDialog):
    """Streaming search dialog — cards appear as results are fetched."""

    cover_save_requested = pyqtSignal(object)   # ArtworkResult (chosen + sized)
    embed_requested      = pyqtSignal(object)   # ArtworkResult (chosen + sized)

    def __init__(self, album: str, artist: str, parent=None) -> None:
        super().__init__(parent)
        self._album  = album
        self._artist = artist
        self._results: list = []
        self._selected: int | None = None
        self._cards: list[_ArtCard] = []
        self._worker = None

        self.setWindowTitle(t("art_search_title").format(album=album or artist))
        self.setMinimumSize(680, 360)
        self.setModal(True)
        self._build_ui()
        self._start_search()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Status row
        status_row = QHBoxLayout()
        self._spinner_lbl = QLabel()
        self._spinner_lbl.setFixedSize(18, 18)
        try:
            spin_icon = qta.icon("fa5s.circle-notch", color="#0078d4",
                                 animation=qta.Spin(self._spinner_lbl))
            self._spinner_lbl.setPixmap(spin_icon.pixmap(18, 18))
        except Exception:
            pass
        self._status_lbl = QLabel(t("art_search_searching"))
        self._status_lbl.setStyleSheet("color:#888; font-size:12px;")
        status_row.addWidget(self._spinner_lbl)
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        root.addLayout(status_row)

        # Scrollable card row
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(CARD_H + 20)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cards_container = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(4, 4, 4, 4)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()    # pushes cards to the left
        scroll.setWidget(self._cards_container)
        root.addWidget(scroll, 1)

        # Selection hint
        self._hint_lbl = QLabel(t("art_search_select"))
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_lbl.setStyleSheet("color:#555; font-size:11px;")
        root.addWidget(self._hint_lbl)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_save = QPushButton(t("art_btn_save_cover"))
        self._btn_save.setIcon(_icon("fa5s.file-image"))
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save_cover)

        self._btn_embed = QPushButton(t("art_btn_embed"))
        self._btn_embed.setIcon(_icon("fa5s.database"))
        self._btn_embed.setEnabled(False)
        self._btn_embed.clicked.connect(self._on_embed)

        self._btn_cancel = QPushButton(t("menu_quit") if False else "Cancelar")
        self._btn_cancel.setIcon(_icon("fa5s.times", "#888"))
        self._btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_embed)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _start_search(self) -> None:
        from ui.workers import ArtworkStreamWorker
        self._worker = ArtworkStreamWorker(self._album, self._artist)
        self._worker.result_found.connect(self._on_result_found)
        self._worker.search_done.connect(self._on_search_done)
        self._worker.error.connect(lambda msg: self._status_lbl.setText(f"Error: {msg}"))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_result_found(self, result) -> None:
        idx = len(self._results)
        self._results.append(result)

        card = _ArtCard(idx, result, self._cards_container)
        card.selected.connect(self._on_card_selected)
        self._cards.append(card)

        # Insert before the trailing stretch
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _on_search_done(self, count: int) -> None:
        self._spinner_lbl.setPixmap(
            _icon("fa5s.check-circle", "#4caf50").pixmap(18, 18)
        )
        if count:
            self._status_lbl.setText(t("art_search_done").format(n=count))
        else:
            self._status_lbl.setText(t("art_search_none"))
            self._hint_lbl.setText(t("art_search_none"))

    # ------------------------------------------------------------------
    # Card selection
    # ------------------------------------------------------------------

    def _on_card_selected(self, idx: int) -> None:
        self._selected = idx
        for card in self._cards:
            card.set_active(card.index == idx)
        self._btn_save.setEnabled(True)
        self._btn_embed.setEnabled(True)
        self._hint_lbl.setText(
            self._results[idx].size_str + f"  ·  {self._results[idx].source}"
        )

    # ------------------------------------------------------------------
    # Actions — both go through ArtworkSaveDialog for size selection
    # ------------------------------------------------------------------

    def _selected_result(self):
        if self._selected is None:
            return None
        return self._results[self._selected]

    def _run_save_dialog(self, result) -> "ArtworkResult | None":
        from ui.artwork_save_dialog import ArtworkSaveDialog
        from core.artwork_manager import ArtworkResult

        dlg = ArtworkSaveDialog(result, self)
        if not dlg.exec():
            return None
        dlg.save_config()
        final_img = dlg.output_image()
        buf = io.BytesIO()
        final_img.save(buf, format="PNG", compress_level=0)
        return ArtworkResult(
            data=buf.getvalue(),
            mime="image/png",
            source=result.source,
            width=final_img.width,
            height=final_img.height,
            label=result.label,
        )

    def _on_save_cover(self) -> None:
        result = self._selected_result()
        if not result:
            return
        final = self._run_save_dialog(result)
        if final:
            self.cover_save_requested.emit(final)
            self.accept()

    def _on_embed(self) -> None:
        result = self._selected_result()
        if not result:
            return
        final = self._run_save_dialog(result)
        if final:
            self.embed_requested.emit(final)
            self.accept()

    # ------------------------------------------------------------------
    # Clean up worker if dialog is closed mid-search
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(500)
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────────
# Card widget
# ──────────────────────────────────────────────────────────────────────

class _ArtCard(QFrame):
    selected = pyqtSignal(int)

    def __init__(self, index: int, result, parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self._result = result
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_style(False)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Thumbnail
        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(THUMB, THUMB)
        thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_lbl.setStyleSheet("background:#1c1c1c; border-radius:4px;")
        try:
            raw = self._result.thumbnail_bytes(THUMB)
            pix = QPixmap()
            pix.loadFromData(raw)
            thumb_lbl.setPixmap(
                pix.scaled(THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        except Exception:
            thumb_lbl.setText("?")
        layout.addWidget(thumb_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Size
        size_lbl = QLabel(self._result.size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_lbl.setStyleSheet("font-weight:bold; font-size:11px;")
        layout.addWidget(size_lbl)

        # Source badge
        src_lbl = QLabel(self._result.source.upper())
        src_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        src_lbl.setStyleSheet(
            "background:#0078d4; color:white; border-radius:3px;"
            "padding:1px 6px; font-size:10px; font-weight:bold;"
        )
        layout.addWidget(src_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Label (album name etc.)
        if self._result.label:
            desc_lbl = QLabel(self._result.label[:28])
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color:#555; font-size:9px;")
            layout.addWidget(desc_lbl)

    def set_active(self, active: bool) -> None:
        self._set_style(active)

    def _set_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                "QFrame{background:#242424;border:2px solid #0078d4;border-radius:6px;}"
            )
        else:
            self.setStyleSheet(
                "QFrame{background:#242424;border:1px solid #383838;border-radius:6px;}"
                "QFrame:hover{border-color:#555;}"
            )

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.index)
        super().mousePressEvent(event)
