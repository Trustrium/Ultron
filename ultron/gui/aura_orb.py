"""Ultron Aura — fluid gradient orb widget (Aura v2).

A large central animated gradient blob: purple -> violet -> pink ->
orange, like the Voice Assessment screen in the mobile references.
Organic pulsing / flowing, reacts to assistant state:

    idle      -> slow breathing, soft glow
    starting  -> gentle swell
    listening -> fast ripple + bright mic ring, reacts to mic level
    thinking  -> swirling blobs, faster rotation
    speaking  -> pulsing waves, radius oscillates with level
    error     -> red tint, slow pulse

Vector-only QPainter, QTimer ~30 fps, never blocks, never does I/O.
Public API mirrors HudCoreWidget: set_state(str), set_level(0..1).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
)
from PySide6.QtWidgets import QWidget

_STATE = {
    "idle": "idle",
    "starting": "starting",
    "listening": "listening",
    "thinking": "thinking",
    "speaking": "speaking",
    "error": "error",
}

# Base tint per state (orb itself is always the purple->pink->orange gradient;
# the tint shifts the glow / ring colour).
_STATE_TINT = {
    "idle": "#8B5CF6",
    "starting": "#CC9933",
    "listening": "#FF6A00",
    "thinking": "#A855F7",
    "speaking": "#EC4899",
    "error": "#CC3333",
}

_GRADIENT_STOPS = (
    (0.0, "#7C3AED"),   # deep purple core
    (0.35, "#8B5CF6"),  # violet
    (0.65, "#EC4899"),  # pink
    (1.0, "#FF6A00"),   # orange edge
)


def _with_alpha(hex_color: str, alpha: int) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


class AuraOrbWidget(QWidget):
    """Fluid gradient blob orb."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 240)
        self.setMaximumSize(420, 420)
        self._state = "idle"
        self._level = 0.0
        self._target_level = 0.0
        self._phase = 0.0
        self._swirl = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 fps — smooth micro-interactions
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # -- public API -------------------------------------------------
    def set_state(self, state: str) -> None:
        state = (state or "idle").lower()
        if state not in _STATE:
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

        return QSize(300, 300)

    # -- animation --------------------------------------------------
    def _tick(self) -> None:
        diff = self._target_level - self._level
        self._level += diff * 0.25
        if abs(diff) < 0.002:
            self._level = self._target_level
        # Speed per state: idle slow, listening/thinking fast.
        speed = {
            "idle": 0.05,
            "starting": 0.07,
            "listening": 0.14,
            "thinking": 0.18,
            "speaking": 0.12,
            "error": 0.05,
        }.get(self._state, 0.05)
        self._phase += speed
        self._swirl = (self._swirl + speed * 1.6) % 360.0
        self.update()

    # -- painting ---------------------------------------------------
    def paintEvent(self, _evt):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        cx = rect.width() / 2.0
        cy = rect.height() / 2.0
        size = min(rect.width(), rect.height())
        radius = size / 2.0 - 10.0
        if radius <= 10:
            return
        tint = _STATE_TINT.get(self._state, "#8B5CF6")
        active = self._state in ("listening", "thinking", "speaking", "starting")

        # Breathing: idle slow, speaking/listening stronger.
        breathe = 1.0 + 0.04 * math.sin(self._phase * 2.0)
        if self._state == "speaking":
            breathe += self._level * 0.10 * math.sin(self._phase * 6.0)
        if self._state == "listening":
            breathe += self._level * 0.06

        # Outer glow halo.
        halo = QRadialGradient(QPointF(cx, cy), radius * 1.25)
        halo.setColorAt(0.0, _with_alpha(tint, 0))
        halo.setColorAt(0.6, _with_alpha(tint, 42 if active else 26))
        halo.setColorAt(1.0, _with_alpha(tint, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), radius * 1.25, radius * 1.25)

        # Listening mic ring: bright ring that ripples outward.
        if self._state == "listening":
            ripple = (self._phase * 2.0) % 1.0
            ring_r = radius * (0.9 + ripple * 0.35)
            alpha = int(160 * (1.0 - ripple))
            p.setPen(QPen(_with_alpha("#FFFFFF", max(0, alpha)), 2.0))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)
            p.setPen(QPen(_with_alpha(tint, 200), 2.5))
            p.drawEllipse(QPointF(cx, cy), radius * 1.02, radius * 1.02)

        # Organic blobs: 3 offset gradient circles orbiting slowly.
        # Each blob is a radial gradient; overlapping them reads as one
        # flowing fluid shape.
        for i, (frac, scale, hue) in enumerate((
            (0.0, 0.92, "#7C3AED"),
            (0.33, 0.78, "#EC4899"),
            (0.66, 0.64, "#FF6A00"),
        )):
            ang = math.radians(self._swirl + i * 120.0 + frac * 360.0)
            wob = 1.0 + 0.05 * math.sin(self._phase * 3.0 + i * 2.1)
            bx = cx + math.cos(ang) * radius * 0.14 * wob
            by = cy + math.sin(ang) * radius * 0.14 * wob
            br = radius * scale * breathe * wob
            g = QRadialGradient(QPointF(bx, by), br)
            g.setColorAt(0.0, _with_alpha(hue, 200))
            g.setColorAt(0.55, _with_alpha(hue, 120))
            g.setColorAt(1.0, _with_alpha(hue, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(bx, by), br, br)

        # Main blob: full gradient, softly deformed by sine edge.
        # Approximate the wobble by drawing the gradient in a circle whose
        # radius breathes; the overlapping blobs above give the organic feel.
        main_r = radius * 0.86 * breathe
        main = QRadialGradient(QPointF(cx, cy), main_r)
        for stop, color in _GRADIENT_STOPS:
            main.setColorAt(stop, _with_alpha(color, 235))
        p.setBrush(QBrush(main))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), main_r, main_r)

        # Inner highlight (top-left gloss).
        gloss = QRadialGradient(
            QPointF(cx - main_r * 0.35, cy - main_r * 0.4), main_r * 0.7
        )
        gloss.setColorAt(0.0, _with_alpha("#FFFFFF", 120))
        gloss.setColorAt(1.0, _with_alpha("#FFFFFF", 0))
        p.setBrush(QBrush(gloss))
        p.drawEllipse(
            QPointF(cx - main_r * 0.35, cy - main_r * 0.4),
            main_r * 0.7, main_r * 0.7,
        )

        # Speaking wave rings: expanding faint rings.
        if self._state == "speaking":
            for k in range(2):
                prog = ((self._phase * 1.5) + k * 0.5) % 1.0
                wr = main_r * (1.0 + prog * 0.45)
                alpha = int(110 * (1.0 - prog) * (0.4 + self._level * 0.6))
                p.setPen(QPen(_with_alpha("#FFFFFF", max(0, alpha)), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(cx, cy), wr, wr)

        # Center white core dot (subtle, keeps the orb readable).
        core_r = main_r * 0.16
        p.setBrush(QBrush(_with_alpha("#FFFFFF", 210)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_r, core_r)
        p.end()


# Aliases.
AuraOrb = AuraOrbWidget
FluidOrbWidget = AuraOrbWidget
AuraOrbWidgetV2 = AuraOrbWidget
