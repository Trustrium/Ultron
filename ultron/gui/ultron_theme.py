"""Ultron theme — Jarvis HUD edition.

Dark silver / dark grey with glowing orange-red accents, plus a full
Jarvis HUD palette: state colors, glow styles, panel / chip / bubble
styles. Main window applies WINDOW_STYLESHEET; other dialogs can import
COLORS as needed.

Backwards compatible: COLORS, STATUS_COLORS, WINDOW_STYLESHEET and
get_stylesheet() keep their original names and meanings.
"""
from __future__ import annotations

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
