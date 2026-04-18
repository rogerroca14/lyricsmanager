"""Dialog to preview artwork at a chosen output size before saving."""

from __future__ import annotations

import io

from PIL import Image
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox, QCheckBox, QDialogButtonBox, QFrame,
)
import qtawesome as qta

from config import get_config
from i18n import t


def _icon(name: str, color: str = "#888"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


class ArtworkSaveDialog(QDialog):
    """Preview + size selector shown before saving a cover.png."""

    PREVIEW_SIZE = 400      # max display size of the preview widget

    def __init__(self, result, parent=None) -> None:
        super().__init__(parent)
        self._result = result
        self._original_img: Image.Image = Image.open(io.BytesIO(result.data))
        self._cfg = get_config()

        # Debounce timer so preview only redraws after user stops dragging
        self._debounce = QTimer(self)
        self._debounce.setSingleStep = lambda _: None   # unused
        self._debounce.setInterval(120)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._refresh_preview)

        self.setWindowTitle(t("art_save_dlg_title"))
        self.setModal(True)
        self.setMinimumWidth(520)
        self._build_ui()
        self._init_values()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)

        # ── Preview ──
        preview_frame = QFrame()
        preview_frame.setStyleSheet(
            "background:#242424; border:1px solid #383838; border-radius:6px;"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background:transparent; border:none;")
        preview_layout.addWidget(self._preview_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Original size info
        ow, oh = self._original_img.size
        orig_lbl = QLabel(t("art_save_original").format(w=ow, h=oh))
        orig_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_lbl.setStyleSheet("color:#555; font-size:11px;")
        preview_layout.addWidget(orig_lbl)

        root.addWidget(preview_frame)

        # ── Resize controls ──
        ctrl_frame = QFrame()
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setSpacing(8)

        # Checkbox
        self._chk_resize = QCheckBox(t("art_save_resize"))
        self._chk_resize.setFont(QFont("Segoe UI", 12))
        self._chk_resize.stateChanged.connect(self._on_resize_toggled)
        ctrl_layout.addWidget(self._chk_resize)

        # Slider + spinbox row
        size_row = QHBoxLayout()
        size_row.setSpacing(10)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(100)
        self._slider.setMaximum(max(4000, max(self._original_img.size)))
        self._slider.setTickInterval(100)
        self._slider.valueChanged.connect(self._on_size_changed)

        self._spin = QSpinBox()
        self._spin.setRange(100, max(4000, max(self._original_img.size)))
        self._spin.setSuffix(" px")
        self._spin.setFixedWidth(90)
        self._spin.valueChanged.connect(self._on_spin_changed)

        size_row.addWidget(self._slider, 1)
        size_row.addWidget(self._spin)
        ctrl_layout.addLayout(size_row)

        # Target size info
        self._target_lbl = QLabel()
        self._target_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._target_lbl.setStyleSheet("color:#0078d4; font-size:12px; font-weight:bold;")
        ctrl_layout.addWidget(self._target_lbl)

        root.addWidget(ctrl_frame)

        # ── Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setIcon(_icon("fa5s.save", "#e0e0e0"))
        save_btn.setProperty("primary", True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _init_values(self) -> None:
        resize_on = self._cfg.get("artwork_resize_cover")
        saved_size = self._cfg.get("artwork_cover_max_size") or 600
        ow, oh = self._original_img.size

        self._chk_resize.setChecked(resize_on)

        # Default slider to saved setting, or original size if no resize
        initial = saved_size if resize_on else max(ow, oh)
        self._slider.setValue(initial)
        self._spin.setValue(initial)

        self._on_resize_toggled()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_resize_toggled(self) -> None:
        enabled = self._chk_resize.isChecked()
        self._slider.setEnabled(enabled)
        self._spin.setEnabled(enabled)
        self._debounce.start()

    def _on_size_changed(self, value: int) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)
        self._debounce.start()

    def _on_spin_changed(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self._debounce.start()

    def _refresh_preview(self) -> None:
        img = self._original_img.copy()
        ow, oh = img.size

        if self._chk_resize.isChecked():
            max_px = self._spin.value()
            if ow > max_px or oh > max_px:
                img.thumbnail((max_px, max_px), Image.LANCZOS)
            tw, th = img.size
            self._target_lbl.setText(
                t("art_save_target").format(w=tw, h=th)
            )
        else:
            self._target_lbl.setText(
                t("art_save_target").format(w=ow, h=oh)
            )

        # Display preview — scale to fit the preview widget
        disp = img.copy()
        disp.thumbnail((self.PREVIEW_SIZE, self.PREVIEW_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        disp.save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())
        self._preview_label.setPixmap(pix)

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def output_image(self) -> Image.Image:
        """Return the final PIL Image at the user-chosen size."""
        img = self._original_img.copy()
        if self._chk_resize.isChecked():
            max_px = self._spin.value()
            ow, oh = img.size
            if ow > max_px or oh > max_px:
                img.thumbnail((max_px, max_px), Image.LANCZOS)
        return img

    def save_config(self) -> None:
        """Persist the chosen settings so they become the new defaults."""
        self._cfg.set("artwork_resize_cover", self._chk_resize.isChecked())
        if self._chk_resize.isChecked():
            self._cfg.set("artwork_cover_max_size", self._spin.value())
