"""Ultron Aura v2 theme — premium dark purple-gradient styling.

Adapted from the mobile AI-app references: dark purple gradient
background, glass cards, 18px rounding, soft glows, clean Segoe UI.
Applied on top of the existing WINDOW_STYLESHEET; Aura widgets use
the AURA_* constants. No network, no new dependencies.
"""
from __future__ import annotations

AURA_COLORS = {
    "bg_top": "#14101F",
    "bg_bottom": "#1E1433",
    "glass": "#241B3D",
    "glass_light": "#2D2350",
    "card": "#221A3B",
    "border": "#3B2F66",
    "border_glow": "#8B5CF6",
    "text": "#FFFFFF",
    "text_muted": "#C4B8E8",
    "text_dim": "#8E83B8",
    "purple": "#7C3AED",
    "violet": "#8B5CF6",
    "pink": "#EC4899",
    "orange": "#FF6A00",
    "green": "#33AA66",
    "red": "#CC3333",
}

AURA_GRADIENT = ("#7C3AED", "#8B5CF6", "#EC4899", "#FF6A00")

AURA_STATE_COLORS = {
    "idle": "#8B5CF6",
    "starting": "#CC9933",
    "listening": "#FF6A00",
    "thinking": "#A855F7",
    "speaking": "#EC4899",
    "error": "#CC3333",
}

AURA_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #14101F;
    color: #FFFFFF;
    font-family: "Segoe UI", sans-serif;
}
QFrame#auraHeader {
    background-color: #221A3B;
    border: 1px solid #3B2F66;
    border-radius: 18px;
}
QFrame#historyPanel, QFrame#centerPanel, QFrame#auraPanel {
    background-color: #221A3B;
    border: 1px solid #3B2F66;
    border-radius: 18px;
}
QLabel#auraTitle {
    color: #FFFFFF;
    font-size: 24px;
    font-weight: 900;
    letter-spacing: 3px;
}
QLabel#auraSubtitle {
    color: #C4B8E8;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
}
QPushButton#auraModeCard {
    background-color: #2D2350;
    color: #FFFFFF;
    border: 1px solid #3B2F66;
    border-radius: 18px;
    padding: 14px 12px;
    font-size: 13px;
    font-weight: 800;
    text-align: left;
}
QPushButton#auraModeCard:hover {
    border-color: #8B5CF6;
    background-color: #372A5E;
}
QPushButton#auraModeCard:pressed {
    background-color: #8B5CF6;
}
QPushButton#auraSendBtn {
    background-color: #8B5CF6;
    color: #FFFFFF;
    border: none;
    border-radius: 16px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 800;
}
QPushButton#auraSendBtn:hover { background-color: #A855F7; }
QPushButton#auraMicBtn {
    background-color: #2D2350;
    color: #FFFFFF;
    border: 1px solid #3B2F66;
    border-radius: 16px;
    padding: 10px 14px;
    font-size: 14px;
}
QPushButton#auraMicBtn:hover { border-color: #EC4899; }
QPushButton#auraChipBtn, QPushButton#chipBtn {
    background-color: #2D2350;
    color: #E8E8E8;
    border: 1px solid #3B2F66;
    border-radius: 16px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#auraChipBtn:hover, QPushButton#chipBtn:hover {
    border-color: #8B5CF6;
    color: #FFFFFF;
    background-color: #372A5E;
}
QLineEdit#auraInput {
    background-color: #1A1330;
    color: #FFFFFF;
    border: 1px solid #3B2F66;
    border-radius: 16px;
    padding: 10px 14px;
    font-size: 12px;
    selection-background-color: #8B5CF6;
}
QLineEdit#auraInput:focus { border-color: #8B5CF6; }
QListWidget#auraHistory {
    background-color: #1A1330;
    border: 1px solid #3B2F66;
    border-radius: 12px;
    padding: 4px;
    font-size: 11px;
}
QListWidget#auraHistory::item { padding: 8px; border-radius: 10px; }
QListWidget#auraHistory::item:selected {
    background-color: #372A5E;
    color: #FFFFFF;
}
QListWidget#auraHistory::item:hover { background-color: #2D2350; }
QTextEdit#chatView {
    background-color: #1A1330;
    border: 1px solid #3B2F66;
    border-radius: 16px;
    padding: 8px;
}
QPushButton#talkBtn {
    background-color: #FF6A00;
    color: #14101F;
    border: none;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 800;
}
"""


def get_aura_stylesheet() -> str:
    return AURA_STYLESHEET
