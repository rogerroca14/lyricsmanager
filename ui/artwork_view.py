"""Artwork panel: view embedded art, search 5 options, save as PNG."""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFrame,
)

from core.metadata import TrackMetadata, get_embedded_artwork
from i18n import t


def _icon(name: str, color: str = "#888"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


class ArtworkView(QWidget):
    fetch_requested = pyqtSignal()
    save_requested = pyqtSignal(object)     # ArtworkResult

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meta: TrackMetadata | None = None
        self._result = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_fetch = QPushButton(t("art_search"))
        self._btn_fetch.setIcon(_icon("fa5s.search", "#e0e0e0"))
        self._btn_fetch.clicked.connect(self.fetch_requested.emit)

        self._btn_extract = QPushButton(t("art_extract_cover"))
        self._btn_extract.setIcon(_icon("fa5s.file-export", "#e0e0e0"))
        self._btn_extract.setToolTip(t("art_extract_cover"))
        self._btn_extract.setEnabled(False)
        self._btn_extract.clicked.connect(self._on_extract_embedded)

        self._btn_save = QPushButton(t("art_save"))
        self._btn_save.setIcon(_icon("fa5s.save", "#e0e0e0"))
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(self._btn_fetch)
        btn_row.addWidget(self._btn_extract)
        btn_row.addWidget(self._btn_save)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Two columns: current vs selected
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # Current artwork
        cur_group = QGroupBox(t("art_embedded"))
        cur_layout = QVBoxLayout(cur_group)
        cur_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_label = self._make_art_label(280)
        cur_layout.addWidget(self._current_label, 0, Qt.AlignmentFlag.AlignCenter)
        self._current_info = QLabel("")
        self._current_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_info.setStyleSheet("color:#555; font-size:11px;")
        cur_layout.addWidget(self._current_info)
        cols.addWidget(cur_group, 1)

        # Selected result
        res_group = QGroupBox(t("art_found"))
        res_layout = QVBoxLayout(res_group)
        res_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label = self._make_art_label(280)
        res_layout.addWidget(self._result_label, 0, Qt.AlignmentFlag.AlignCenter)
        self._result_info = QLabel("")
        self._result_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_info.setStyleSheet("color:#0078d4; font-size:11px;")
        res_layout.addWidget(self._result_info)
        cols.addWidget(res_group, 1)

        root.addLayout(cols, 1)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet("color:#555; font-size:11px;")
        root.addWidget(self._status)

    def _make_art_label(self, size: int) -> QLabel:
        lbl = QLabel(t("art_no_artwork"))
        lbl.setFixedSize(size, size)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "background:#242424; border:1px solid #383838; border-radius:4px; color:#555;"
        )
        return lbl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_track(self, meta: TrackMetadata) -> None:
        self._meta = meta
        self._result = None
        self._btn_save.setEnabled(False)
        self._status.setText("")

        embedded = get_embedded_artwork(meta.path)
        # Enable extract button only when there is real embedded art in the file
        self._btn_extract.setEnabled(bool(embedded))

        display_data = embedded
        if not display_data:
            cover_png = meta.path.parent / "cover.png"
            if cover_png.exists():
                display_data = cover_png.read_bytes()

        if display_data:
            self._set_pixmap(self._current_label, display_data)
            src_hint = "Embedded" if embedded else "cover.png"
            self._current_info.setText(src_hint)
        else:
            self._current_label.setPixmap(QPixmap())
            self._current_label.setText(t("art_no_artwork"))
            self._current_info.setText("")

        self._result_label.setPixmap(QPixmap())
        self._result_label.setText(t("art_no_artwork"))
        self._result_info.setText("")

    def set_artwork_result(self, result) -> None:
        """Called after user picks one option from the picker dialog."""
        self._result = result
        if result:
            self._set_pixmap(self._result_label, result.data)
            self._result_info.setText(
                f"{result.source.upper()} — {result.size_str} — PNG on save"
            )
            self._btn_save.setEnabled(True)
            self._status.setText(t("status_art_found").format(
                source=result.source, size=result.size_str
            ))
        else:
            self._result_label.setText(t("art_not_found"))
            self._result_info.setText("")
            self._status.setText(t("art_not_found"))

    def clear(self) -> None:
        self._meta = None
        self._result = None
        self._btn_save.setEnabled(False)
        self._btn_extract.setEnabled(False)
        for lbl in (self._current_label, self._result_label):
            lbl.setPixmap(QPixmap())
            lbl.setText(t("art_no_artwork"))
        self._current_info.setText("")
        self._result_info.setText("")
        self._status.setText("")

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_pixmap(self, label: QLabel, data: bytes) -> None:
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            pix = pix.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(pix)
            label.setText("")

    def _on_save(self) -> None:
        if not self._result:
            return
        from ui.artwork_save_dialog import ArtworkSaveDialog
        from core.artwork_manager import ArtworkResult
        import io

        dlg = ArtworkSaveDialog(self._result, self)
        if dlg.exec():
            dlg.save_config()
            # Build a new ArtworkResult whose data is the final image chosen by the user
            final_img = dlg.output_image()
            buf = io.BytesIO()
            final_img.save(buf, format="PNG", compress_level=0)
            final_result = ArtworkResult(
                data=buf.getvalue(),
                mime="image/png",
                source=self._result.source,
                width=final_img.width,
                height=final_img.height,
                label=self._result.label,
            )
            self.save_requested.emit(final_result)

    def _on_extract_embedded(self) -> None:
        if not self._meta:
            return
        from core.metadata import get_embedded_artwork
        from core.artwork_manager import ArtworkResult, _save_cover_png
        from ui.artwork_save_dialog import ArtworkSaveDialog
        import io

        data = get_embedded_artwork(self._meta.path)
        if not data:
            self._status.setText(t("art_no_embedded"))
            return

        # Build a temporary ArtworkResult so the dialog can preview it
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        tmp = ArtworkResult(
            data=data,
            mime="image/png" if img.format == "PNG" else "image/jpeg",
            source="embedded",
            width=img.width,
            height=img.height,
            label=self._meta.path.name,
        )

        dlg = ArtworkSaveDialog(tmp, self)
        if not dlg.exec():
            return

        dlg.save_config()
        final_img = dlg.output_image()
        buf = io.BytesIO()
        final_img.save(buf, format="PNG", compress_level=0)
        final = ArtworkResult(
            data=buf.getvalue(),
            mime="image/png",
            source="embedded",
            width=final_img.width,
            height=final_img.height,
        )
        ok, msg = _save_cover_png(self._meta.path.parent, final)
        self._status.setText(msg)
        if ok:
            self.load_track(self._meta)
