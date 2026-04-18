"""Minimal dark theme — clean, neutral, audiophile-inspired."""

# Palette
BG = "#1c1c1c"
SURFACE = "#242424"
SURFACE2 = "#2d2d2d"
BORDER = "#383838"
BORDER_FOCUS = "#0078d4"
ACCENT = "#0078d4"
ACCENT_HOVER = "#1a88e0"
ACCENT_PRESSED = "#005fa3"
TEXT = "#e0e0e0"
TEXT_MUTED = "#888888"
TEXT_DISABLED = "#505050"
SUCCESS = "#4caf50"
WARNING = "#e5a50a"
ERROR = "#e05252"

_DARK_STYLESHEET_BASE = f"""
* {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QDialog {{
    background-color: {BG};
}}

QWidget {{
    background-color: {BG};
    color: {TEXT};
}}

/* ── Menu ── */
QMenuBar {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item:selected {{ background-color: {SURFACE2}; border-radius: 3px; }}
QMenu {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: 3px; }}
QMenu::item:selected {{ background-color: {SURFACE2}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 0; }}

/* ── Toolbar ── */
QToolBar {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
    spacing: 2px;
    padding: 4px 8px;
}}
QToolButton {{
    background-color: transparent;
    color: {TEXT};
    border: none;
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 12px;
}}
QToolButton:hover {{ background-color: {SURFACE2}; }}
QToolButton:pressed {{ background-color: {BORDER}; }}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-top: none;
    background-color: {BG};
}}
QTabBar::tab {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    padding: 7px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    margin-right: 1px;
}}
QTabBar::tab:selected {{
    background-color: {BG};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background-color: {SURFACE2};
    color: {TEXT};
}}

/* ── Tree / List ── */
QTreeView, QListView, QTreeWidget, QListWidget {{
    background-color: {SURFACE};
    alternate-background-color: {BG};
    border: none;
    selection-background-color: {SURFACE2};
    selection-color: {TEXT};
    outline: none;
}}
QTreeView::item, QListView::item {{
    padding: 3px 4px;
    border-radius: 3px;
}}
QTreeView::item:selected, QListView::item:selected {{
    background-color: {SURFACE2};
    color: {TEXT};
    border-left: 2px solid {ACCENT};
}}
QTreeView::item:hover:!selected, QListView::item:hover:!selected {{
    background-color: {SURFACE2};
}}
QHeaderView::section {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    padding: 5px 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QTreeView::branch {{
    background-color: {SURFACE};
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    min-width: 70px;
}}
QPushButton:hover {{
    background-color: {BORDER};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PRESSED};
    color: white;
    border-color: {ACCENT_PRESSED};
}}
QPushButton:disabled {{
    background-color: {SURFACE};
    color: {TEXT_DISABLED};
    border-color: {SURFACE2};
}}
QPushButton[primary="true"] {{
    background-color: {ACCENT};
    color: white;
    border: none;
}}
QPushButton[primary="true"]:hover {{
    background-color: {ACCENT_HOVER};
}}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {BORDER_FOCUS};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {BG};
    color: {TEXT_DISABLED};
}}

QComboBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    min-width: 80px;
}}
QComboBox:focus {{ border-color: {BORDER_FOCUS}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {SURFACE2};
}}

QSpinBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}
QSpinBox:focus {{ border-color: {BORDER_FOCUS}; }}

QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {BORDER};
    background-color: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    /*%%CHECK_IMAGE%%*/
}}

/* ── Slider ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {SURFACE2};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ── GroupBox ── */
QGroupBox {{
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-size: 12px;
    padding: 0 8px;
}}

/* ── Progress bar ── */
QProgressBar {{
    background-color: {SURFACE2};
    border: none;
    border-radius: 3px;
    height: 4px;
    text-align: center;
    font-size: 10px;
    color: {TEXT_MUTED};
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ── Frame ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {BORDER};
}}

/* ── Tooltips ── */
QToolTip {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    border-radius: 4px;
}}

/* ── Dialog button box ── */
QDialogButtonBox QPushButton {{ min-width: 80px; }}
"""


def build_stylesheet(base_dir: str = "") -> str:
    """Return the full dark stylesheet, resolving asset paths from *base_dir*."""
    import os
    if base_dir:
        _check = os.path.join(base_dir, "assets", "check.svg").replace("\\", "/")
        check_image = f"image: url({_check});"
    else:
        check_image = ""
    return _DARK_STYLESHEET_BASE.replace("/*%%CHECK_IMAGE%%*/", check_image)


# Backward-compat alias (used by any import that doesn't pass base_dir)
DARK_STYLESHEET = build_stylesheet()


# Badge styles (applied inline, not via stylesheet object names)
BADGE_STYLES = {
    "Hi-Res":   f"background:{WARNING}; color:#1c1c1c; border-radius:3px; padding:1px 6px; font-size:11px; font-weight:bold;",
    "Lossless": f"background:{ACCENT}; color:white; border-radius:3px; padding:1px 6px; font-size:11px; font-weight:bold;",
    "DSD":      f"background:#c07000; color:white; border-radius:3px; padding:1px 6px; font-size:11px; font-weight:bold;",
    "MQA":      f"background:#8b5cf6; color:white; border-radius:3px; padding:1px 6px; font-size:11px; font-weight:bold;",
    "Lossy":    f"background:{SURFACE2}; color:{TEXT_MUTED}; border-radius:3px; padding:1px 6px; font-size:11px;",
}


def apply_badge(label, quality_label: str) -> None:
    style = BADGE_STYLES.get(quality_label, BADGE_STYLES["Lossy"])
    label.setStyleSheet(style)
    label.setText(quality_label)
