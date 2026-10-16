"""Live spectrum / waveform widget — spectrum bars driven by a worker signal.

Used by MainWindow while Ultron is listening so the user has visible
feedback. Upgraded from a single fill bar to Jarvis-style spectrum bars.

Backwards compatible API:
    LiveWaveform.set_level(0..1)        -- drive from mic level
    LiveWaveform.set_enabled_view(bool) -- light up only while listening
Extra:
    LiveWaveform.set_color("#RRGGBB")   -- tint bars by assistant state
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen
from PySide6.QtWidgets import QWidget

_BAR_COUNT = 28


class LiveWaveform(QWidget):
    """Spectrum-bar visualizer. Call `set_level(0..1)` to drive it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.setMaximumHeight(72)
        self._level = 0.0
        self._target = 0.0
        self._enabled = False
        self._color = QColor("#FF6A00")
        self._phase = 0.0
        # Per-bar smoothed heights + deterministic variation seeds.
        self._bars = [0.0] * _BAR_COUNT
        self._seeds = [(i * 0.37) % 1.0 for i in range(_BAR_COUNT)]
        random.seed(42)
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
        try:
            level = float(level)
        except Exception:
            level = 0.0
        self._target = max(0.0, min(1.0, level))

    def set_color(self, hex_color: str) -> None:
        try:
            c = QColor(hex_color)
            if c.isValid():
                self._color = c
        except Exception:
            pass

    def _tick(self) -> None:
        # Ease overall level toward target.
        diff = self._target - self._level
        self._level += diff * 0.25
        if abs(diff) < 0.002:
            self._level = self._target
        self._phase += 0.12
        # Per-bar heights: center bars tallest, edges quieter; add a
        # gentle idle shimmer when enabled so the HUD never looks dead.
        for i in range(_BAR_COUNT):
            center = 1.0 - abs(i - (_BAR_COUNT - 1) / 2.0) / ((_BAR_COUNT - 1) / 2.0)
            envelope = 0.25 + 0.75 * (center ** 1.4)
            if self._enabled:
                shimmer = 0.06 + 0.05 * math.sin(self._phase * 2.0 + self._seeds[i] * 6.28)
                target = max(shimmer, self._level * envelope)
                # Add per-bar texture so bars don't move in lockstep.
                target *= 0.75 + 0.25 * math.sin(self._phase + i * 0.55)
                target = max(0.05, min(1.0, target))
            else:
                target = 0.0
            # Ease each bar toward its target.
            self._bars[i] += (target - self._bars[i]) * 0.35
        self.update()

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)

        # Background pill.
        bg = QColor("#14171F") if self._enabled else QColor("#10131A")
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor("#2C3444"), 1))
        p.drawRoundedRect(rect, 8, 8)

        # Spectrum bars, centered vertically.
        gap = 3
        total_gap = gap * (_BAR_COUNT - 1)
        bar_w = max(3.0, (rect.width() - total_gap) / _BAR_COUNT)
        mid_y = rect.center().y()
        max_h = rect.height() - 10
        for i, h_frac in enumerate(self._bars):
            h = max(2.0, h_frac * max_h)
            x = rect.left() + i * (bar_w + gap)
            # Gradient: dim at bottom, bright at top.
            grad = QLinearGradient(0, mid_y + h / 2, 0, mid_y - h / 2)
            dim = QColor(self._color)
            dim.setAlpha(90)
            bright = QColor("#FFFFFF")
            grad.setColorAt(0.0, dim)
            grad.setColorAt(0.65, self._color)
            grad.setColorAt(1.0, bright)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(
                x, mid_y - h / 2, bar_w, h, bar_w / 2, bar_w / 2,
            )
        p.end()


# Alias: the HUD spectrum is the same widget.
SpectrumWaveform = LiveWaveform
