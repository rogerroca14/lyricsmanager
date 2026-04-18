"""Metadata viewer panel — shows full audiophile-relevant info for a track."""

from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QFormLayout, QScrollArea, QFrame, QPushButton, QSizePolicy,
    QTextEdit,
)

from core.metadata import TrackMetadata, get_embedded_artwork
from i18n import t
from ui.theme import apply_badge, SURFACE, BORDER, TEXT_MUTED, BG


# ── helpers ──────────────────────────────────────────────────────────────

def _field(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    return lbl


def _value(text: str = "—") -> QLabel:
    lbl = QLabel(text or "—")
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lbl.setWordWrap(True)
    return lbl


def _qicon(name: str, color: str = "#888"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


# ── main widget ──────────────────────────────────────────────────────────

class MetadataView(QWidget):
    """Full metadata panel for a single audio file."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meta: TrackMetadata | None = None
        self._raw_visible = False
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        self._build_header()
        self._build_info_groups()
        self._build_raw_section()

        self._layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    def _build_header(self) -> None:
        """Artwork on the left, title/artist/album/badges stacked on the right."""
        row = QHBoxLayout()
        row.setSpacing(16)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Artwork thumbnail ──────────────────────────────────────────
        self._artwork_label = QLabel()
        self._artwork_label.setFixedSize(160, 160)
        self._artwork_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._artwork_label.setStyleSheet(
            f"background-color:{SURFACE}; border:1px solid {BORDER};"
            "border-radius:6px;"
        )
        self._artwork_label.setPixmap(
            _qicon("fa5s.compact-disc", "#383838").pixmap(48, 48)
        )
        row.addWidget(self._artwork_label, 0, Qt.AlignmentFlag.AlignTop)

        # ── Meta text column ───────────────────────────────────────────
        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        self._title_label = QLabel(t("meta_no_file"))
        self._title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title_label.setWordWrap(True)
        text_col.addWidget(self._title_label)

        self._artist_label = QLabel()
        self._artist_label.setWordWrap(True)
        self._artist_label.setStyleSheet("font-size:12px; color:#c0c0c0;")
        self._artist_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_col.addWidget(self._artist_label)

        self._album_label = QLabel()
        self._album_label.setWordWrap(True)
        self._album_label.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        self._album_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_col.addWidget(self._album_label)

        # Badge row: quality + LRC + ART
        badge_row = QHBoxLayout()
        badge_row.setSpacing(5)
        badge_row.setContentsMargins(0, 6, 0, 0)

        self._badge_quality = QLabel()
        self._badge_quality.setVisible(False)

        self._badge_lrc = QLabel("LRC")
        self._badge_lrc.setStyleSheet(
            "background:#0078d4; color:white; border-radius:3px;"
            "padding:1px 6px; font-size:11px; font-weight:bold;"
        )
        self._badge_lrc.setVisible(False)

        self._badge_artwork = QLabel("ART")
        self._badge_artwork.setStyleSheet(
            "background:#4caf50; color:white; border-radius:3px;"
            "padding:1px 6px; font-size:11px; font-weight:bold;"
        )
        self._badge_artwork.setVisible(False)

        badge_row.addWidget(self._badge_quality)
        badge_row.addWidget(self._badge_lrc)
        badge_row.addWidget(self._badge_artwork)
        badge_row.addStretch()
        text_col.addLayout(badge_row)

        text_col.addStretch()
        row.addLayout(text_col, 1)
        self._layout.addLayout(row)

    def _build_info_groups(self) -> None:
        """Two side-by-side groups: Track Info | Audio Specs."""
        groups_row = QHBoxLayout()
        groups_row.setSpacing(12)

        # ── Track info ─────────────────────────────────────────────────
        basic = QGroupBox(t("meta_track_info"))
        basic_form = QFormLayout(basic)
        basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        basic_form.setSpacing(5)
        basic_form.setContentsMargins(8, 14, 8, 8)

        self._f_artist      = _value()
        self._f_album       = _value()
        self._f_album_artist = _value()
        self._f_year        = _value()
        self._f_genre       = _value()
        self._f_track       = _value()
        self._f_disc        = _value()
        self._f_composer    = _value()
        self._f_duration    = _value()

        basic_form.addRow(_field(t("meta_artist")),       self._f_artist)
        basic_form.addRow(_field(t("meta_album")),        self._f_album)
        basic_form.addRow(_field(t("meta_album_artist")), self._f_album_artist)
        basic_form.addRow(_field(t("meta_year")),         self._f_year)
        basic_form.addRow(_field(t("meta_genre")),        self._f_genre)
        basic_form.addRow(_field(t("meta_track")),        self._f_track)
        basic_form.addRow(_field(t("meta_disc")),         self._f_disc)
        basic_form.addRow(_field(t("meta_composer")),     self._f_composer)
        basic_form.addRow(_field(t("meta_duration")),     self._f_duration)

        # ── Audio specs ────────────────────────────────────────────────
        tech = QGroupBox(t("meta_audio_spec"))
        tech_form = QFormLayout(tech)
        tech_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        tech_form.setSpacing(5)
        tech_form.setContentsMargins(8, 14, 8, 8)

        self._f_codec      = _value()
        self._f_samplerate = _value()
        self._f_bitdepth   = _value()
        self._f_channels   = _value()
        self._f_bitrate    = _value()
        self._f_filesize   = _value()
        self._f_filepath   = _value()
        self._f_filepath.setWordWrap(True)
        self._f_filepath.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:11px; font-family:'Consolas',monospace;"
        )

        tech_form.addRow(_field(t("meta_codec")),      self._f_codec)
        tech_form.addRow(_field(t("meta_samplerate")), self._f_samplerate)
        tech_form.addRow(_field(t("meta_bitdepth")),   self._f_bitdepth)
        tech_form.addRow(_field(t("meta_channels")),   self._f_channels)
        tech_form.addRow(_field(t("meta_bitrate")),    self._f_bitrate)
        tech_form.addRow(_field(t("meta_filesize")),   self._f_filesize)
        tech_form.addRow(_field(t("meta_path")),       self._f_filepath)

        groups_row.addWidget(basic, 1)
        groups_row.addWidget(tech, 1)
        self._layout.addLayout(groups_row)

    def _build_raw_section(self) -> None:
        """Collapsible raw-tags section with a toggle button."""
        # Toggle button (looks like a section header)
        self._raw_toggle = QPushButton()
        self._raw_toggle.setCheckable(True)
        self._raw_toggle.setChecked(False)
        self._raw_toggle.setFlat(True)
        self._raw_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._raw_toggle.setStyleSheet(
            f"QPushButton {{ text-align:left; color:{TEXT_MUTED}; font-size:11px;"
            f"  font-weight:bold; text-transform:uppercase; letter-spacing:0.5px;"
            f"  border:none; border-top:1px solid {BORDER}; padding:8px 2px;"
            f"  background:transparent; }}"
            f"QPushButton:hover {{ color:#c0c0c0; }}"
        )
        self._raw_toggle.toggled.connect(self._on_toggle_raw)
        self._layout.addWidget(self._raw_toggle)

        # The text area (hidden by default)
        self._raw_tags = QTextEdit()
        self._raw_tags.setReadOnly(True)
        self._raw_tags.setFont(QFont("Consolas", 10))
        self._raw_tags.setMaximumHeight(180)
        self._raw_tags.setVisible(False)
        self._layout.addWidget(self._raw_tags)

        self._refresh_raw_toggle_label()

    def _refresh_raw_toggle_label(self) -> None:
        arrow = "▼" if self._raw_toggle.isChecked() else "▶"
        self._raw_toggle.setText(f"  {arrow}  {t('meta_raw_tags')}")

    def _on_toggle_raw(self, checked: bool) -> None:
        self._raw_tags.setVisible(checked)
        self._refresh_raw_toggle_label()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, meta: TrackMetadata) -> None:
        self._meta = meta
        q = meta.quality

        # Header
        self._title_label.setText(meta.display_title)
        self._artist_label.setText(meta.artist or "")
        self._artist_label.setVisible(bool(meta.artist))

        album_parts = [p for p in [meta.album, meta.year] if p]
        self._album_label.setText("  ·  ".join(album_parts))
        self._album_label.setVisible(bool(album_parts))

        # Badges
        apply_badge(self._badge_quality, q.label)
        self._badge_quality.setVisible(True)
        self._badge_lrc.setVisible(meta.has_lyrics or self._lrc_file_exists(meta.path))
        self._badge_artwork.setVisible(meta.has_artwork)

        # Basic fields
        self._f_artist.setText(meta.artist or "—")
        self._f_album.setText(meta.album or "—")
        self._f_album_artist.setText(meta.album_artist or "—")
        self._f_year.setText(meta.year or "—")
        self._f_genre.setText(meta.genre or "—")
        self._f_track.setText(meta.track_number or "—")
        self._f_disc.setText(meta.disc_number or "—")
        self._f_composer.setText(meta.composer or "—")
        self._f_duration.setText(meta.duration_str)

        # Tech fields
        channels_map = {1: "Mono", 2: "Stereo", 4: "4-ch", 6: "5.1", 8: "7.1"}
        ch = channels_map.get(q.channels or 0, f"{q.channels}-ch" if q.channels else "—")
        self._f_codec.setText(q.codec or "—")
        self._f_samplerate.setText(q.sample_rate_khz)
        self._f_bitdepth.setText(q.bit_depth_str)
        self._f_channels.setText(ch)
        self._f_bitrate.setText(meta.bitrate_str)
        self._f_filesize.setText(meta.file_size_str)
        self._f_filepath.setText(str(meta.path))

        # Raw tags
        raw_lines = "\n".join(f"{k}: {v}" for k, v in sorted(meta.raw_tags.items()))
        self._raw_tags.setPlainText(raw_lines or "(no raw tags)")

        # Artwork
        self._load_artwork(meta)

    def _load_artwork(self, meta: TrackMetadata) -> None:
        data = get_embedded_artwork(meta.path)
        if not data:
            cover_png = meta.path.parent / "cover.png"
            if cover_png.exists():
                data = cover_png.read_bytes()

        if data:
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                pix = pix.scaled(
                    160, 160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._artwork_label.setPixmap(pix)
                return

        # Placeholder
        self._artwork_label.setPixmap(
            _qicon("fa5s.compact-disc", "#383838").pixmap(48, 48)
        )

    def clear(self) -> None:
        self._meta = None
        self._title_label.setText(t("meta_no_file"))
        self._artist_label.setText("")
        self._album_label.setText("")
        self._badge_quality.setVisible(False)
        self._badge_lrc.setVisible(False)
        self._badge_artwork.setVisible(False)
        for lbl in (self._f_artist, self._f_album, self._f_album_artist,
                    self._f_year, self._f_genre, self._f_track, self._f_disc,
                    self._f_composer, self._f_duration, self._f_codec,
                    self._f_samplerate, self._f_bitdepth, self._f_channels,
                    self._f_bitrate, self._f_filesize, self._f_filepath):
            lbl.setText("—")
        self._raw_tags.clear()
        self._artwork_label.setPixmap(
            _qicon("fa5s.compact-disc", "#383838").pixmap(48, 48)
        )

    @staticmethod
    def _lrc_file_exists(path: Path) -> bool:
        return (path.parent / (path.stem + ".lrc")).exists()
