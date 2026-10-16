"""Ultron desktop app entry point.

Usage:
    python ultron_app.py              # opens GUI (main window + tray)
    python ultron_app.py --minimized  # start in tray only

Behavior:
    1. Apply persisted settings (overrides .env if present).
    2. On first run (no API key), show the setup wizard.
    3. Show main window + install tray icon.
    4. Close window -> hides to tray. Tray menu -> Quit to actually exit.
"""
from __future__ import annotations
import sys


def main() -> int:
    # 1) Apply settings.json -> os.environ BEFORE importing ultron.config.
    from ultron import settings
    settings.apply_to_environ()

    # 2) Qt app
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # tray keeps the app alive

    # 3) First-run wizard
    from ultron.gui.wizard import needs_first_run, run_first_run_wizard
    if needs_first_run():
        if not run_first_run_wizard():
            QMessageBox.information(None, "Ultron", "Setup cancelled. Quitting.")
            return 0
        # Reload env from new settings.
        settings.apply_to_environ()
        # config module already imported with old values; force reload.
        import importlib
        import ultron.config as jc
        importlib.reload(jc)

    # 4) Main window + tray
    from ultron.gui.main_window import MainWindow
    from ultron.gui.tray import install_tray
    window = MainWindow()
    tray = install_tray(window, app)

    if "--minimized" not in sys.argv or not tray:
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
