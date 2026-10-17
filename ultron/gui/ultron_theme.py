"""Ultron theme — Jarvis HUD edition.

Dark silver / dark grey with glowing orange-red accents, plus a full
Jarvis HUD palette: state colors, glow styles, panel / chip / bubble
styles. Main window applies WINDOW_STYLESHEET; other dialogs can import
COLORS as needed.

Backwards compatible: COLORS, STATUS_COLORS, WINDOW_STYLESHEET and
get_stylesheet() keep their original names and meanings.
"""
from __future__ import annotations

import sys
from pathlib import Path


def find_app_icon() -> str | None:
    """Locate assets/ultron.ico for the window / tray icon.

    Checks the PyInstaller bundle dir, the repo layout, and the CWD.
    Returns a path string or None (caller falls back to a drawn icon).
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "assets" / "ultron.ico")
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidates.append(parent / "assets" / "ultron.ico")
    candidates.append(Path.cwd() / "assets" / "ultron.ico")
    for cand in candidates:
        try:
            if cand.is_file():
                return str(cand)
        except Exception:
            continue
    return None


# v3 design tokens (8px grid, typography hierarchy) — additive, safe to
# import from either ultron_theme or aura_theme.
SPACING = {"xs": 8, "sm": 16, "md": 24, "lg": 32}
TYPE_SCALE = {
    "display": ("Inter", 24, 900),
    "title": ("Inter", 16, 700),
    "body": ("Inter", 11, 400),
    "label": ("Inter", 10, 600),
    "caption": ("Inter", 9, 700),
}

COLORS = {
    "background": "#0B0D12",
    "surface": "#14171F",
    "surface_light": "#1E232E",
    "surface_glow": "#232A38",
    "silver": "#C0C0C0",
    "silver_light": "#E8E8E8",
    "accent": "#FF6A00",
    "accent_red": "#FF3B00",
    "accent_glow": "#FF8C42",
    "accent_cyan": "#3AD6FF",
    "accent_blue": "#3366CC",
    "text": "#F2F2F2",
    "text_muted": "#A8A8B0",
    "text_dim": "#7A8191",
    "success": "#33AA66",
    "warning": "#CC9933",
    "error": "#CC3333",
    "info": "#3366CC",
    "thinking": "#9933CC",
    "border": "#2C3444",
    "border_glow": "#FF6A00",
    "panel": "#12151D",
}

STATUS_COLORS = {
    "idle": "#888888",
    "starting": "#CC9933",
    "listening": "#FF6A00",
    "thinking": "#9933CC",
    "speaking": "#33AA66",
    "error": "#CC3333",
}

# Alias used by the HUD widgets: state -> hex color.
STATE_COLORS = dict(STATUS_COLORS)
# HUD core states: idle grey/silver, listening orange, thinking purple,
# speaking green, error red, starting amber.
HUD_STATE_COLORS = {
    "idle": "#9AA3B2",
    "starting": "#CC9933",
    "listening": "#FF6A00",
    "thinking": "#9933CC",
    "speaking": "#33AA66",
    "error": "#CC3333",
}

HUD_PALETTE = {
    "background": "#0B0D12",
    "panel": "#12151D",
    "panel_edge": "#2C3444",
    "core_ring": "#FF6A00",
    "core_inner": "#FF8C42",
    "text": "#F2F2F2",
    "muted": "#A8A8B0",
    "dim": "#7A8191",
    "chip_bg": "#1B2230",
    "chip_border": "#2C3444",
    "chip_hover": "#FF6A00",
    "bubble_you": "#1E3A5F",
    "bubble_ultron": "#2A1E14",
    "bubble_system": "#1A1D24",
    "bubble_error": "#3A1A1A",
    # --- v3 additions (additive keys; old keys untouched) ---
    "surface_elevated": "#241F42",
    "border_subtle": "#2A2450",
    "input_bg": "#16122A",
    "orange_soft": "#FF8C42",
    "green_soft": "#34D399",
    "amber_soft": "#F59E0B",
    "red_soft": "#F87171",
}

WINDOW_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0B0D12;
    color: #F2F2F2;
    font-family: "Segoe UI", "Inter", sans-serif;
}
QFrame#hudHeader {
    background-color: #12151D;
    border: 1px solid #2C3444;
    border-radius: 10px;
}
QFrame#hudPanel, QFrame#corePanel, QFrame#sysPanel, QFrame#chatPanel {
    background-color: #12151D;
    border: 1px solid #2C3444;
    border-radius: 12px;
}
QFrame#coreFrame {
    background-color: #0B0D12;
    border: 1px solid #2C3444;
    border-radius: 12px;
}
QLabel#hudTitle {
    color: #F2F2F2;
    font-size: 22px;
    font-weight: 900;
    letter-spacing: 3px;
}
QLabel#hudSubtitle {
    color: #FF8C42;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#hudStatus {
    color: #F2F2F2;
    font-size: 11px;
    font-weight: 700;
}
QLabel#sysLabel {
    color: #A8A8B0;
    font-size: 10px;
}
QLabel#sysValue {
    color: #F2F2F2;
    font-size: 10px;
    font-weight: 700;
}
QPushButton {
    background-color: #1E232E;
    color: #F2F2F2;
    border: 1px solid #2C3444;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    border-color: #FF6A00;
    background-color: #232A38;
}
QPushButton:pressed {
    background-color: #FF6A00;
    color: #0B0D12;
}
QPushButton:disabled {
    color: #7A8191;
    background-color: #171B24;
    border-color: #232A38;
}
QPushButton#startBtn {
    background-color: #FF6A00;
    color: #0B0D12;
    border: 1px solid #FF6A00;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 800;
}
QPushButton#startBtn:hover {
    background-color: #FF8C42;
}
QPushButton#startBtn:disabled {
    background-color: #3A3A44;
    color: #7A8191;
    border-color: #3A3A44;
}
QPushButton#talkBtn {
    background-color: #FF6A00;
    color: #0B0D12;
    border: 1px solid #FF8C42;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 800;
}
QPushButton#talkBtn:hover {
    background-color: #FF8C42;
}
QPushButton#talkBtn:disabled {
    background-color: #232A38;
    color: #7A8191;
    border-color: #2C3444;
}
QPushButton#chipBtn {
    background-color: #1B2230;
    color: #E8E8E8;
    border: 1px solid #2C3444;
    border-radius: 16px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#chipBtn:hover {
    border-color: #FF6A00;
    color: #FF8C42;
    background-color: #232A38;
}
QTextEdit, QComboBox, QLineEdit {
    background-color: #14171F;
    color: #F2F2F2;
    border: 1px solid #2C3444;
    border-radius: 8px;
    selection-background-color: #FF6A00;
    selection-color: #0B0D12;
}
QTextEdit#chatView {
    background-color: #0E1118;
    border: 1px solid #2C3444;
    border-radius: 10px;
    padding: 6px;
}
QComboBox {
    padding: 6px 10px;
}
QStatusBar {
    color: #A8A8B0;
    background-color: #0B0D12;
}
QScrollBar:vertical {
    background: #12151D;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #2C3444;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #FF6A00;
}
"""


def get_stylesheet() -> str:
    return WINDOW_STYLESHEET


# --- Aura v2 (premium purple-gradient theme) -------------------------
# Re-exported here so existing `from .ultron_theme import ...` call sites
# keep working; the Aura widgets themselves live in aura_theme.py /
# aura_orb.py. Appended styles override the HUD defaults for Aura panels.
try:
    from .aura_theme import (  # noqa: F401
        AURA_COLORS,
        AURA_GRADIENT,
        AURA_STATE_COLORS,
        AURA_STYLESHEET,
    )

    WINDOW_STYLESHEET = WINDOW_STYLESHEET + "\n" + AURA_STYLESHEET
except Exception:  # pragma: no cover - Aura theme is optional
    AURA_COLORS = {}
    AURA_GRADIENT = ()
    AURA_STATE_COLORS = {}
    AURA_STYLESHEET = ""


# --- Ultron v3: agency-grade polish layer ---------------------------
# Original styling, applied LAST so it wins over HUD + Aura defaults
# for the shared controls. Covers states the earlier sheets missed:
# focus rings, disabled states, tooltips, menus, status/stage pills,
# streaming frame, skeleton bars, and the Trustrium brand header.
V3_STYLESHEET = """
QToolTip {
    background-color: #241F42;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 10pt;
}
QPushButton:focus { border-color: #8B5CF6; }
QPushButton:disabled {
    color: #8E83B8;
    background-color: #1B1730;
    border-color: #2A2450;
}
QFrame#statusPill {
    background-color: rgba(45, 36, 80, 0.9);
    border: 1px solid #322B5C;
    border-radius: 12px;
}
QLabel#statusPillText { color: #FFFFFF; font-size: 10pt; font-weight: 600; }
QLabel#brandEyebrow { color: #FF8C42; font-size: 9pt; font-weight: 700; letter-spacing: 2px; }
QFrame#brandMark { background-color: #FF6A00; border-radius: 12px; border: 1px solid #FF8C42; }
QLabel#brandMarkLetter { color: #FFFFFF; font-size: 16pt; font-weight: 900; }
QLabel#sectionLabel { color: #8E83B8; font-size: 9pt; font-weight: 700; letter-spacing: 2px; }
QFrame#inputBar { background-color: #16122A; border: 1px solid #322B5C; border-radius: 16px; }
QLineEdit#auraInput { background-color: transparent; border: none; }
QFrame#streamFrame { background-color: rgba(36, 31, 66, 0.92); border: 1px solid #8B5CF6; border-radius: 16px; }
QLabel#streamHeader { color: #C4B8E8; font-size: 9pt; font-weight: 700; letter-spacing: 2px; }
QLabel#streamText { color: #FFFFFF; font-size: 11pt; }
QLabel#streamCursor { color: #FF8C42; font-size: 11pt; font-weight: 700; }
QFrame#skeletonBar { background-color: #241F42; border-radius: 8px; }
QLabel#typingLabel { color: #C4B8E8; font-size: 11pt; font-style: italic; }
"""

WINDOW_STYLESHEET = WINDOW_STYLESHEET + "\n" + V3_STYLESHEET
