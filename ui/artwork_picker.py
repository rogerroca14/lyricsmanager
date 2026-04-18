"""Dialog to pick one of multiple artwork candidates."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QDialogButtonBox,
)

from i18n import t


class ArtworkPickerDialog(QDialog):
    """Show up to 5 artwork options in a grid; user picks one."""

    def __init__(self, results: list, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("art_pick_title"))
        self.setMinimumWidth(700)
        self.setModal(True)
        self._results = results
        self._selected: int | None = None
        self._cards: list[_ArtCard] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        subtitle = QLabel(t("art_pick_subtitle"))
        subtitle.setStyleSheet("color: #888; font-size: 12px;")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        grid = QHBoxLayout(container)
        grid.setSpacing(12)
        grid.setContentsMargins(4, 4, 4, 4)

        for i, result in enumerate(self._results):
            card = _ArtCard(i, result, self)
            card.selected.connect(self._on_card_selected)
            self._cards.append(card)
            grid.addWidget(card)

        grid.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        root.addWidget(buttons)

    def _on_card_selected(self, idx: int) -> None:
        self._selected = idx
        for card in self._cards:
            card.set_active(card.index == idx)
        self._ok_btn.setEnabled(True)

    def selected_result(self):
        if self._selected is not None:
            return self._results[self._selected]
        return None


class _ArtCard(QFrame):
    """Clickable artwork thumbnail card."""

    from PyQt6.QtCore import pyqtSignal
    selected = pyqtSignal(int)

    def __init__(self, index: int, result, parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self._result = result
        self.setFixedWidth(130)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Artwork thumbnail
        art_lbl = QLabel()
        art_lbl.setFixedSize(116, 116)
        art_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art_lbl.setStyleSheet("background:#242424; border-radius:4px;")
        try:
            thumb = self._result.thumbnail_bytes(116)
            pix = QPixmap()
            pix.loadFromData(thumb)
            art_lbl.setPixmap(pix.scaled(116, 116, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        except Exception:
            art_lbl.setText("?")
        layout.addWidget(art_lbl)

        # Label
        num = QLabel(t("art_option").format(n=self.index + 1))
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet("font-weight:bold; font-size:11px;")
        layout.addWidget(num)

        # Size
        size_lbl = QLabel(self._result.size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_lbl.setStyleSheet("color:#888; font-size:10px;")
        layout.addWidget(size_lbl)

        # Source
        src_lbl = QLabel(self._result.source)
        src_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        src_lbl.setStyleSheet("color:#0078d4; font-size:10px;")
        layout.addWidget(src_lbl)

        # Truncated label
        if self._result.label:
            desc = QLabel(self._result.label[:40])
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setWordWrap(True)
            desc.setStyleSheet("color:#666; font-size:9px;")
            layout.addWidget(desc)

    def set_active(self, active: bool) -> None:
        self._apply_style(active)

    def _apply_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                "QFrame { background:#242424; border:2px solid #0078d4; border-radius:6px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame { background:#242424; border:1px solid #383838; border-radius:6px; }"
                "QFrame:hover { border-color:#555; }"
            )

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.index)
        super().mousePressEvent(event)
