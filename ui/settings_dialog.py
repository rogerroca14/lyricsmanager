"""Settings dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QFileDialog, QSpinBox, QDialogButtonBox, QTabWidget, QWidget,
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(540)
        self._cfg = get_config()
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        tabs = QTabWidget()

        # ── Lyrics ──
        lyrics_tab = QWidget()
        lyt = QVBoxLayout(lyrics_tab)
        lyt.setSpacing(10)

        save_group = QGroupBox(t("settings_save_mode"))
        sf = QFormLayout(save_group)
        self._combo_save_mode = QComboBox()
        self._combo_save_mode.addItems([t("settings_lrc_file"), t("settings_embedded")])
        sf.addRow(t("settings_save_as"), self._combo_save_mode)
        lyt.addWidget(save_group)

        lrc_group = QGroupBox(t("settings_lrc_output"))
        lf = QFormLayout(lrc_group)
        self._chk_same_folder = QCheckBox(t("settings_same_folder"))
        self._chk_same_folder.stateChanged.connect(self._on_same_folder_toggled)
        self._lrc_folder_row = QHBoxLayout()
        self._lrc_folder_edit = QLineEdit()
        lrc_folder_btn = QPushButton(t("settings_browse"))
        lrc_folder_btn.clicked.connect(self._browse_lrc_folder)
        self._lrc_folder_row.addWidget(self._lrc_folder_edit)
        self._lrc_folder_row.addWidget(lrc_folder_btn)
        lf.addRow(self._chk_same_folder)
        lf.addRow(t("settings_custom_folder"), self._lrc_folder_row)

        self._chk_prefer_plain = QCheckBox(t("settings_prefer_plain"))
        lf.addRow(self._chk_prefer_plain)
        lyt.addWidget(lrc_group)

        src_group = QGroupBox(t("settings_sources_order"))
        sl = QVBoxLayout(src_group)
        self._chk_lrclib = QCheckBox("LRCLIB (lrclib.net)")
        self._chk_netease = QCheckBox("NetEase Cloud Music")
        sl.addWidget(self._chk_lrclib)
        sl.addWidget(self._chk_netease)
        lyt.addWidget(src_group)
        lyt.addStretch()

        tabs.addTab(lyrics_tab, _icon("fa5s.music", "#888"), t("settings_lyrics_tab"))

        # ── Artwork ──
        art_tab = QWidget()
        al = QVBoxLayout(art_tab)
        al.setSpacing(10)

        art_save = QGroupBox(t("settings_art_save"))
        asf = QFormLayout(art_save)
        self._chk_save_png = QCheckBox(t("settings_save_png"))
        self._chk_embed_art = QCheckBox(t("settings_embed_art"))
        self._chk_overwrite = QCheckBox(t("settings_overwrite"))
        self._chk_resize = QCheckBox(t("settings_resize_cover"))
        self._spin_cover_size = QSpinBox()
        self._spin_cover_size.setRange(100, 4000)
        self._spin_cover_size.setSingleStep(100)
        self._spin_cover_size.setSuffix(" px")
        self._chk_resize.stateChanged.connect(
            lambda: self._spin_cover_size.setEnabled(self._chk_resize.isChecked())
        )
        asf.addRow(self._chk_save_png)
        asf.addRow(self._chk_embed_art)
        asf.addRow(self._chk_overwrite)
        asf.addRow(self._chk_resize)
        asf.addRow(t("settings_cover_max_size"), self._spin_cover_size)
        al.addWidget(art_save)

        art_src = QGroupBox(t("settings_art_sources"))
        asl = QVBoxLayout(art_src)
        self._chk_coverart = QCheckBox("Cover Art Archive (MusicBrainz)")
        self._chk_itunes = QCheckBox("iTunes Search API")
        asl.addWidget(self._chk_coverart)
        asl.addWidget(self._chk_itunes)
        al.addWidget(art_src)
        al.addStretch()

        tabs.addTab(art_tab, _icon("fa5s.image", "#888"), t("settings_artwork_tab"))

        # ── Audio / APIs ──
        audio_tab = QWidget()
        aud_l = QVBoxLayout(audio_tab)
        aud_l.setSpacing(10)

        hires_group = QGroupBox(t("settings_hires"))
        hf = QFormLayout(hires_group)
        self._spin_samplerate = QSpinBox()
        self._spin_samplerate.setRange(44100, 384000)
        self._spin_samplerate.setSingleStep(44100)
        self._spin_samplerate.setSuffix(" Hz")
        self._spin_bitdepth = QSpinBox()
        self._spin_bitdepth.setRange(16, 32)
        hf.addRow(t("settings_min_sr"), self._spin_samplerate)
        hf.addRow(t("settings_min_bd"), self._spin_bitdepth)
        aud_l.addWidget(hires_group)

        # Audio output device
        dev_group = QGroupBox(t("player_device"))
        dev_f = QFormLayout(dev_group)
        self._combo_audio_device = QComboBox()
        self._combo_audio_device.setMinimumWidth(280)
        try:
            from ui.player import list_output_devices
            devices = list_output_devices()
            self._combo_audio_device.addItem(t("player_no_device"), None)
            saved_device = self._cfg.get("audio_output_device")
            for dev in devices:
                self._combo_audio_device.addItem(dev["display"], dev["id"])
                if dev["id"] == saved_device:
                    self._combo_audio_device.setCurrentIndex(
                        self._combo_audio_device.count() - 1
                    )
        except Exception:
            self._combo_audio_device.addItem("sounddevice not available", None)
        dev_f.addRow(t("player_device"), self._combo_audio_device)
        aud_l.addWidget(dev_group)

        mb_group = QGroupBox(t("settings_mb"))
        mbf = QFormLayout(mb_group)
        self._mb_useragent = QLineEdit()
        mbf.addRow(t("settings_useragent"), self._mb_useragent)
        aud_l.addWidget(mb_group)
        aud_l.addStretch()

        tabs.addTab(audio_tab, _icon("fa5s.headphones", "#888"), t("settings_audio_tab"))

        # ── Language ──
        lang_tab = QWidget()
        ll = QVBoxLayout(lang_tab)
        lang_group = QGroupBox(t("settings_language"))
        lg = QFormLayout(lang_group)
        self._combo_lang = QComboBox()
        self._combo_lang.addItem("Español", "es")
        self._combo_lang.addItem("English", "en")
        lg.addRow(t("settings_language"), self._combo_lang)
        note = QLabel("Language change takes effect on next launch.")
        note.setStyleSheet("color:#555; font-size:11px;")
        lg.addRow(note)
        lang_group.setLayout(lg)
        ll.addWidget(lang_group)
        ll.addStretch()

        tabs.addTab(lang_tab, _icon("fa5s.globe", "#888"), t("settings_language_tab"))

        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _load_values(self) -> None:
        cfg = self._cfg
        self._combo_save_mode.setCurrentIndex(0 if cfg.get("lyrics_save_mode") == "lrc" else 1)
        self._chk_same_folder.setChecked(cfg.get("lrc_same_folder"))
        self._lrc_folder_edit.setText(cfg.get("lrc_output_folder") or "")
        self._chk_prefer_plain.setChecked(cfg.get("prefer_plain_lyrics"))

        sources = cfg.get("lyrics_sources") or []
        self._chk_lrclib.setChecked("lrclib" in sources)
        self._chk_netease.setChecked("netease" in sources)

        self._chk_save_png.setChecked(cfg.get("artwork_save_cover_png"))
        self._chk_embed_art.setChecked(cfg.get("artwork_embed_metadata"))
        self._chk_overwrite.setChecked(cfg.get("artwork_overwrite"))
        resize = cfg.get("artwork_resize_cover")
        self._chk_resize.setChecked(resize)
        self._spin_cover_size.setValue(cfg.get("artwork_cover_max_size") or 600)
        self._spin_cover_size.setEnabled(resize)

        art_sources = cfg.get("artwork_sources") or []
        self._chk_coverart.setChecked("coverart" in art_sources)
        self._chk_itunes.setChecked("itunes" in art_sources)

        self._spin_samplerate.setValue(cfg.get("hires_sample_rate_threshold"))
        self._spin_bitdepth.setValue(cfg.get("hires_bit_depth_threshold"))
        self._mb_useragent.setText(cfg.get("musicbrainz_useragent") or "")

        lang = cfg.get("language") or "es"
        idx = self._combo_lang.findData(lang)
        if idx >= 0:
            self._combo_lang.setCurrentIndex(idx)

        self._on_same_folder_toggled(self._chk_same_folder.checkState())

    def _on_same_folder_toggled(self, state) -> None:
        self._lrc_folder_edit.setEnabled(not self._chk_same_folder.isChecked())

    def _browse_lrc_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("settings_custom_folder"))
        if folder:
            self._lrc_folder_edit.setText(folder)

    def _save_and_accept(self) -> None:
        cfg = self._cfg
        cfg.set("lyrics_save_mode", "lrc" if self._combo_save_mode.currentIndex() == 0 else "metadata")
        cfg.set("lrc_same_folder", self._chk_same_folder.isChecked())
        cfg.set("lrc_output_folder", self._lrc_folder_edit.text())
        cfg.set("prefer_plain_lyrics", self._chk_prefer_plain.isChecked())

        sources = []
        if self._chk_lrclib.isChecked():
            sources.append("lrclib")
        if self._chk_netease.isChecked():
            sources.append("netease")
        cfg.set("lyrics_sources", sources)

        cfg.set("artwork_save_cover_png", self._chk_save_png.isChecked())
        cfg.set("artwork_embed_metadata", self._chk_embed_art.isChecked())
        cfg.set("artwork_resize_cover", self._chk_resize.isChecked())
        cfg.set("artwork_cover_max_size", self._spin_cover_size.value())
        cfg.set("artwork_overwrite", self._chk_overwrite.isChecked())

        art_sources = []
        if self._chk_coverart.isChecked():
            art_sources.append("coverart")
        if self._chk_itunes.isChecked():
            art_sources.append("itunes")
        cfg.set("artwork_sources", art_sources)

        cfg.set("hires_sample_rate_threshold", self._spin_samplerate.value())
        cfg.set("hires_bit_depth_threshold", self._spin_bitdepth.value())
        cfg.set("musicbrainz_useragent", self._mb_useragent.text())
        cfg.set("language", self._combo_lang.currentData())

        device_id = self._combo_audio_device.currentData()
        cfg.set("audio_output_device", device_id)

        self.accept()
