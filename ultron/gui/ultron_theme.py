"""Ultron theme — dark silver / dark grey with glowing orange-red accents.

Kept in one place so the GUI can share the same palette. Main window applies
WINDOW_STYLESHEET; other dialogs can import COLORS as needed.
"""
from __future__ import annotations

COLORS = {
    "background": "#1A1A1E",
    "surface": "#232329",
    "surface_light": "#2E2E36",
    "silver": "#C0C0C0",
    "silver_light": "#E8E8E8",
    "accent": "#FF6A00",
    "accent_red": "#FF3B00",
    "accent_glow": "#FF8C42",
    "text": "#F2F2F2",
    "text_muted": "#A8A8B0",
    "success": "#33AA66",
    "warning": "#CC9933",
    "error": "#CC3333",
    "info": "#3366CC",
}

STATUS_COLORS = {
    "idle": "#888888",
    "starting": "#CC9933",
    "listening": "#FF6A00",
    "thinking": "#9933CC",
    "speaking": "#33AA66",
    "error": "#CC3333",
}

WINDOW_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1A1A1E;
    color: #F2F2F2;
}
QPushButton {
    background-color: #2E2E36;
    color: #F2F2F2;
    border: 1px solid #3A3A44;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover {
    border-color: #FF6A00;
}
QPushButton:pressed {
    background-color: #FF6A00;
    color: #1A1A1E;
}
QTextEdit, QComboBox, QLineEdit {
    background-color: #232329;
    color: #F2F2F2;
    border: 1px solid #3A3A44;
    border-radius: 4px;
}
QStatusBar {
    color: #A8A8B0;
}
"""


def get_stylesheet() -> str:
    return WINDOW_STYLESHEET
