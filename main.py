"""LyricsManager — Audiophile Edition entry point."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from config import get_config
from i18n import set_language
from ui.theme import build_stylesheet


def main() -> None:
    cfg = get_config()
    set_language(cfg.get("language") or "es")

    app = QApplication(sys.argv)
    app.setApplicationName("LyricsManager")
    app.setOrganizationName("AudiophileTools")

    _base = str(Path(__file__).parent)
    app.setStyleSheet(build_stylesheet(_base))

    # Import after QApplication is created (PyQt6 requirement)
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
        if folder.is_dir():
            window._scan_folder(folder)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
