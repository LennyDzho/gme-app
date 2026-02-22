"""Application runner."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from gme_app.config import load_config
from gme_app.ui.main_window import MainWindow
from gme_app.ui.styles import APP_STYLE


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GME App")
    app.setOrganizationName("GME")
    app.setStyleSheet(APP_STYLE)

    config = load_config()
    window = MainWindow(config)

    screen = app.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        width = max(980, int(geometry.width() * 0.88))
        height = max(680, int(geometry.height() * 0.88))
        window.resize(min(width, geometry.width()), min(height, geometry.height()))
    else:
        window.resize(1280, 820)

    window.show()
    return app.exec()
