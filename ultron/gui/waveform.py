"""Simple live audio level widget — bouncing bar driven by a worker signal.

Used by MainWindow while Ultron is listening so the user has visible feedback.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush
from PySide6.QtWidgets import QWidget


class LiveWaveform(QWidget):
    """Bouncing bar visualizer. Call `set_level(0..1)` to drive it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(28)
        self._level = 0.0
        self._target = 0.0
        self._enabled = False
        # Smooth animation tick.
        self._timer = QTimer(self)
        self._timer.setInterval(33)   # ~30 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_enabled_view(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self._target = 0.0
        self.update()

    def set_level(self, level: float) -> None:
        # Clamp + soft compression for visual stability.
        level = max(0.0, min(1.0, level))
        self._target = level

    def _tick(self) -> None:
        # Ease toward target.
        diff = self._target - self._level
        self._level += diff * 0.25
        if abs(diff) > 0.005:
            self.update()

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)

        # Background pill
        bg = QColor("#222") if self._enabled else QColor("#1a1a1a")
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        # Filled portion
        if self._level > 0.01 and self._enabled:
            fill_rect = rect.adjusted(2, 2, -2, -2)
            fill_rect.setWidth(int(fill_rect.width() * self._level))
            grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            grad.setColorAt(0.0, QColor("#3a82ff"))
            grad.setColorAt(0.7, QColor("#7be0a6"))
            grad.setColorAt(1.0, QColor("#ffd84d"))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, 4, 4)
        p.end()
