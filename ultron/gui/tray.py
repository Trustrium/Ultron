"""System tray icon — keeps Ultron accessible without a visible window."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QBrush, QColor, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication


def _generate_icon() -> QIcon:
    """Tray icon: prefer the professional assets/ultron.ico; fall back
    to a drawn orange 'U' badge (no external asset needed)."""
    try:
        from .ultron_theme import find_app_icon

        path = find_app_icon()
        if path:
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    except Exception:
        pass
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#FF6A00")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 60, 60)
    p.setPen(QColor("white"))
    f = p.font(); f.setBold(True); f.setPointSize(28); p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, "U")
    p.end()
    return QIcon(pix)


def install_tray(window, app: QApplication) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(_generate_icon(), parent=app)
    tray.setToolTip("Ultron")

    menu = QMenu()
    show_action = QAction("Show window", menu)
    show_action.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
    menu.addAction(show_action)

    start_action = QAction("Start", menu)
    start_action.triggered.connect(window._start)
    menu.addAction(start_action)

    stop_action = QAction("Stop", menu)
    stop_action.triggered.connect(window._stop)
    menu.addAction(stop_action)

    settings_action = QAction("Settings...", menu)
    settings_action.triggered.connect(window._open_settings)
    menu.addAction(settings_action)

    menu.addSeparator()
    quit_action = QAction("Quit Ultron", menu)
    def _quit():
        window._hide_on_close = False
        try:
            window.worker.stop()
        except Exception:
            pass
        app.quit()
    quit_action.triggered.connect(_quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: (
        (window.show(), window.raise_(), window.activateWindow())
        if reason == QSystemTrayIcon.DoubleClick else None
    ))
    tray.show()

    # Tell window to hide-to-tray on close.
    window._hide_on_close = True
    return tray
