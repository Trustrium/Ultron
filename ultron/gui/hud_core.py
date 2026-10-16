"""Jarvis HUD glowing core widget — animated, non-blocking.

A central arc-reactor-style core: concentric pulsing rings, rotating
arc segments, tick marks, and a glowing center core. Color follows the
assistant state:

    idle      -> grey / silver
    starting  -> amber
    listening -> orange (#FF6A00)
    thinking  -> purple (#9933CC)
    speaking  -> green (#33AA66)
    error     -> red (#CC3333)

Animation runs on a QTimer at ~30 fps and only repaints; it never
blocks the UI thread and never does I/O.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QFont,
)
from PySide6.QtWidgets import QWidget

try:
    from .ultron_theme import HUD_STATE_COLORS as _STATE_COLORS
except Exception:  # pragma: no cover - theme import fallback
    _STATE_COLORS = {
        "idle": "#9AA3B2",
        "starting": "#CC9933",
        "listening": "#FF6A00",
        "thinking": "#9933CC",
        "speaking": "#33AA66",
        "error": "#CC3333",
    }

_STATE_LABEL = {
    "idle": "ULTRON",
    "starting": "STARTING",
    "listening": "LISTENING",
    "thinking": "THINKING",
    "speaking": "SPEAKING",
    "error": "ERROR",
}


def _with_alpha(hex_color: str, alpha: int) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


class HudCoreWidget(QWidget):
    """Animated Jarvis-style glowing core."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.setMaximumSize(340, 340)
        self._state = "idle"
        self._level = 0.0
        self._target_level = 0.0
        self._phase = 0.0
        self._rotation = 0.0
        self._rotation2 = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # -- public API -----------------------------------------------------
    def set_state(self, state: str) -> None:
        state = (state or "idle").lower()
        if state not in _STATE_COLORS:
            state = "idle"
        if state != self._state:
            self._state = state
            self.update()

    def state(self) -> str:
        return self._state

    def set_level(self, level: float) -> None:
        try:
            level = float(level)
        except Exception:
            level = 0.0
        self._target_level = max(0.0, min(1.0, level))

    def sizeHint(self):  # noqa: N802 - Qt API
        from PySide6.QtCore import QSize

        return QSize(280, 280)

    # -- animation ------------------------------------------------------
    def _tick(self) -> None:
        # Smooth level easing.
        diff = self._target_level - self._level
        self._level += diff * 0.25
        if abs(diff) < 0.002:
            self._level = self._target_level
        self._phase += 0.08
        # Rotation speed scales slightly with activity.
        speed = 1.6 + self._level * 3.0
        self._rotation = (self._rotation + speed) % 360.0
        self._rotation2 = (self._rotation2 - speed * 0.7) % 360.0
        # Repaint every tick; paint is cheap (vector only).
        self.update()

    # -- painting -------------------------------------------------------
    def paintEvent(self, _evt):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        cx = rect.width() / 2.0
        cy = rect.height() / 2.0
        size = min(rect.width(), rect.height())
        radius = size / 2.0 - 8.0
        if radius <= 10:
            return

        base = QColor(_STATE_COLORS.get(self._state, "#9AA3B2"))
        active = self._state in ("listening", "thinking", "speaking", "starting")
        pulse = 0.5 + 0.5 * math.sin(self._phase * 2.0)
        # Activity boost: listening / speaking react to mic level.
        boost = 0.35 + self._level * 0.65 if active else 0.30 + pulse * 0.15

        # Outer faint halo.
        halo = QRadialGradient(QPointF(cx, cy), radius * 1.05)
        halo.setColorAt(0.0, _with_alpha(base.name(), 0))
        halo.setColorAt(0.65, _with_alpha(base.name(), int(28 * boost)))
        halo.setColorAt(1.0, _with_alpha(base.name(), 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), radius * 1.05, radius * 1.05)

        # Tick ring — small marks around the circle.
        p.setPen(QPen(_with_alpha(base.name(), 90), 1.5))
        for i in range(48):
            ang = math.radians(i * 7.5)
            long_tick = (i % 4 == 0)
            r1 = radius * (0.96 if long_tick else 0.985)
            r2 = radius * 1.0
            x1 = cx + math.cos(ang) * r1
            y1 = cy + math.sin(ang) * r1
            x2 = cx + math.cos(ang) * r2
            y2 = cy + math.sin(ang) * r2
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Pulsing concentric rings.
        for idx, frac in enumerate((0.92, 0.78, 0.64)):
            wobble = 1.0 + 0.02 * math.sin(self._phase * 2.0 + idx * 1.3)
            r = radius * frac * wobble
            alpha = int(40 + 70 * boost - idx * 18)
            p.setPen(QPen(_with_alpha(base.name(), max(12, alpha)), 1.6 if idx == 0 else 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # Rotating arc segments — two arcs rotating in opposite directions.
        for rotation, span, width, alpha in (
            (self._rotation, 70, 4.0, 220),
            (self._rotation2, 110, 2.5, 150),
        ):
            arc_rect = QRectF(cx - radius * 0.86, cy - radius * 0.86,
                              radius * 1.72, radius * 1.72)
            pen = QPen(_with_alpha(base.name(), alpha), width)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            # Qt drawArc: angles in 1/16 degree, 0 = 3 o'clock, CCW positive.
            p.drawArc(arc_rect, int(-rotation * 16), int(span * 16))
            p.drawArc(arc_rect, int((-rotation + 180) * 16), int(span * 16))

        # Center core — radial glow + solid core.
        core_r = radius * 0.38 * (1.0 + 0.06 * pulse + self._level * 0.12)
        grad = QRadialGradient(QPointF(cx, cy), core_r * 1.6)
        grad.setColorAt(0.0, QColor("#FFFFFF"))
        grad.setColorAt(0.25, _with_alpha(base.name(), 255))
        grad.setColorAt(0.6, _with_alpha(base.name(), int(140 * boost + 60)))
        grad.setColorAt(1.0, _with_alpha(base.name(), 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_r * 1.6, core_r * 1.6)

        # Solid inner disc.
        p.setBrush(QBrush(_with_alpha(base.name(), 235)))
        p.setPen(QPen(QColor("#FFFFFF"), 1.2))
        p.drawEllipse(QPointF(cx, cy), core_r * 0.62, core_r * 0.62)

        # Center label.
        label = _STATE_LABEL.get(self._state, "ULTRON")
        p.setPen(QPen(QColor("#FFFFFF"), 1))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        font.setLetterSpacing(QFont.PercentageSpacing, 140)
        p.setFont(font)
        text_rect = QRectF(cx - radius * 0.5, cy - 11, radius, 22)
        p.drawText(text_rect, Qt.AlignCenter, label)

        # Small level readout under the core.
        if active:
            p.setPen(QPen(_with_alpha("#FFFFFF", 170), 1))
            small = QFont("Segoe UI", 7)
            p.setFont(small)
            sub = f"LEVEL {int(self._level * 100)}%"
            p.drawText(QRectF(cx - radius * 0.5, cy + core_r * 0.9, radius, 16),
                       Qt.AlignCenter, sub)
        p.end()


# Friendly alias — both names refer to the same widget.
JarvisCoreWidget = HudCoreWidget
JarvisHUDCore = HudCoreWidget
