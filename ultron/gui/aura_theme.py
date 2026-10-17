"""Ultron Aura v3 theme — professional agency-grade styling.

Design language (original work, informed by widely used SaaS / AI
assistant patterns — 8px grid, glassmorphism, Inter/Segoe typography,
generous whitespace, subtle shadows, 60fps-feel micro-interactions):

  * 8px spacing scale: every margin / gap is a multiple of 8
    (8 / 16 / 24 / 32). Panel padding 16–24, card radius 16,
    pill radius 999, button radius 12, input radius 16.
  * Typography hierarchy: display 24/900, section 16/700, body
    11/400, caption 9/700 uppercase with 2px letter-spacing,
    labels 10/600. Tight (-0.5px-ish) headings via letter-spacing 0.
  * Surfaces: deep plum-charcoal canvas, elevated glass cards
    (semi-transparent + 1px border), near-white text, muted
    secondary text. Orange (#FF6A00) is the primary action accent;
    violet (#8B5CF6) is the secondary / brand accent.
  * States everywhere: hover / pressed / disabled / focus /
    selected are all styled — no control ever looks dead or
    unresponsive. Focus rings use the accent border.
  * Status pills + stage pills give immediate feedback for
    listening / understanding / doing. Skeleton bars + typing
    dots cover the waiting states; the streaming frame shows
    live tokens while a reply is being generated.

Applied on top of the existing WINDOW_STYLESHEET; Aura widgets use
the AURA_* constants. No network, no new dependencies.
"""
from __future__ import annotations

AURA_COLORS = {
    "bg_top": "#12101D",
    "bg_bottom": "#1A1630",
    "glass": "#241F42",
    "glass_light": "#2D2450",
    "card": "#1B1730",
    "border": "#322B5C",
    "border_glow": "#8B5CF6",
    "text": "#FFFFFF",
    "text_muted": "#C4B8E8",
    "text_dim": "#8E83B8",
    "purple": "#7C3AED",
    "violet": "#8B5CF6",
    "pink": "#EC4899",
    "orange": "#FF6A00",
    "orange_soft": "#FF8C42",
    "green": "#34D399",
    "amber": "#F59E0B",
    "red": "#F87171",
    # v3 additions
    "surface": "#1B1730",
    "surface_elevated": "#241F42",
    "surface_hover": "#2D2450",
    "border_subtle": "#2A2450",
    "input_bg": "#16122A",
    "bubble_you": "#3A2E7A",
    "bubble_ultron": "#241F42",
    "bubble_system": "#1B1730",
}

AURA_GRADIENT = ("#7C3AED", "#8B5CF6", "#EC4899", "#FF6A00")

AURA_STATE_COLORS = {
    "idle": "#8B5CF6",
    "starting": "#F59E0B",
    "listening": "#FF6A00",
    "thinking": "#A855F7",
    "speaking": "#EC4899",
    "error": "#F87171",
}

# 8px spacing scale (px). Layouts should use only these values.
AURA_SPACING = {"xs": 8, "sm": 16, "md": 24, "lg": 32}

# Typography scale: (family, size pt, weight).
AURA_TYPE = {
    "display": ("Inter", 24, 900),
    "title": ("Inter", 16, 700),
    "body": ("Inter", 11, 400),
    "label": ("Inter", 10, 600),
    "caption": ("Inter", 9, 700),
}

AURA_STYLESHEET = """
/* ---- Base: typography + canvas (8px grid) ---- */
QMainWindow, QWidget {
    background-color: #12101D;
    color: #FFFFFF;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 11pt;
}
QToolTip {
    background-color: #241F42;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 10pt;
}
QMenu {
    background-color: #1B1730;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 8px;
}
QMenu::item { padding: 8px 16px; border-radius: 8px; }
QMenu::item:selected { background-color: #2D2450; }
QMenu::separator { height: 1px; background: #322B5C; margin: 8px 0; }

/* ---- Panels: glass cards, 16px radius, 16–24px padding ---- */
QFrame#auraHeader {
    background-color: rgba(36, 31, 66, 0.92);
    border: 1px solid #322B5C;
    border-radius: 16px;
}
QFrame#historyPanel, QFrame#centerPanel, QFrame#auraPanel {
    background-color: rgba(27, 23, 48, 0.92);
    border: 1px solid #322B5C;
    border-radius: 16px;
}
QFrame#statusPill {
    background-color: rgba(45, 36, 80, 0.9);
    border: 1px solid #322B5C;
    border-radius: 12px;
}
QLabel#statusPillText {
    color: #FFFFFF;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#statusPillDot { font-size: 14pt; }
QLabel#brandEyebrow {
    color: #FF8C42;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QFrame#brandMark {
    background-color: #FF6A00;
    border-radius: 12px;
    border: 1px solid #FF8C42;
}
QLabel#brandMarkLetter {
    color: #FFFFFF;
    font-size: 16pt;
    font-weight: 900;
}
QLabel#auraTitle {
    color: #FFFFFF;
    font-size: 24pt;
    font-weight: 900;
    letter-spacing: 1px;
}
QLabel#auraSubtitle {
    color: #C4B8E8;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#sectionLabel {
    color: #8E83B8;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#stagePill {
    background-color: #241F42;
    color: #8E83B8;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#stagePillActive {
    background-color: rgba(255, 106, 0, 0.16);
    color: #FF8C42;
    border: 1px solid #FF6A00;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 9pt;
    font-weight: 700;
}

/* ---- Buttons: primary / secondary / ghost, full states ---- */
QPushButton {
    background-color: #241F42;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 11pt;
    font-weight: 600;
}
QPushButton:hover {
    border-color: #8B5CF6;
    background-color: #2D2450;
}
QPushButton:pressed { background-color: #372A5E; }
QPushButton:disabled {
    color: #8E83B8;
    background-color: #1B1730;
    border-color: #2A2450;
}
QPushButton:focus { border-color: #8B5CF6; }
QPushButton#auraModeCard {
    background-color: #241F42;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 16px;
    padding: 16px;
    font-size: 13pt;
    font-weight: 700;
    text-align: left;
}
QPushButton#auraModeCard:hover {
    border-color: #8B5CF6;
    background-color: #2D2450;
}
QPushButton#auraModeCard:pressed { background-color: #8B5CF6; }
QPushButton#auraModeCard:disabled {
    color: #8E83B8;
    background-color: #1B1730;
    border-color: #2A2450;
}
QPushButton#auraSendBtn {
    background-color: #FF6A00;
    color: #FFFFFF;
    border: 1px solid #FF6A00;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 11pt;
    font-weight: 700;
}
QPushButton#auraSendBtn:hover { background-color: #FF8C42; border-color: #FF8C42; }
QPushButton#auraSendBtn:pressed { background-color: #E55A00; }
QPushButton#auraSendBtn:disabled {
    background-color: #2A2450;
    color: #8E83B8;
    border-color: #2A2450;
}
QPushButton#auraMicBtn {
    background-color: #241F42;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 14pt;
}
QPushButton#auraMicBtn:hover { border-color: #EC4899; background-color: #2D2450; }
QPushButton#auraMicBtn:pressed { background-color: #EC4899; }
QPushButton#auraMicBtn:disabled {
    color: #8E83B8;
    background-color: #1B1730;
    border-color: #2A2450;
}
QPushButton#auraChipBtn, QPushButton#chipBtn {
    background-color: #241F42;
    color: #E8E8E8;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 10pt;
    font-weight: 600;
}
QPushButton#auraChipBtn:hover, QPushButton#chipBtn:hover {
    border-color: #8B5CF6;
    color: #FFFFFF;
    background-color: #2D2450;
}
QPushButton#auraChipBtn:pressed, QPushButton#chipBtn:pressed { background-color: #372A5E; }
QPushButton#auraChipBtn:disabled, QPushButton#chipBtn:disabled {
    color: #8E83B8;
    background-color: #1B1730;
    border-color: #2A2450;
}

/* ---- Inputs: polished bar, visible focus ring ---- */
QFrame#inputBar {
    background-color: #16122A;
    border: 1px solid #322B5C;
    border-radius: 16px;
}
QLineEdit#auraInput {
    background-color: transparent;
    color: #FFFFFF;
    border: none;
    border-radius: 16px;
    padding: 8px 8px;
    font-size: 11pt;
    selection-background-color: #8B5CF6;
}
QLineEdit#auraInput:focus { border: none; }
QLineEdit#auraInput:disabled { color: #8E83B8; }
QComboBox {
    background-color: #241F42;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 10pt;
    font-weight: 600;
    selection-background-color: #8B5CF6;
}
QComboBox:hover { border-color: #8B5CF6; }
QComboBox:focus { border-color: #8B5CF6; }
QComboBox:disabled { color: #8E83B8; background-color: #1B1730; border-color: #2A2450; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #1B1730;
    color: #FFFFFF;
    border: 1px solid #322B5C;
    border-radius: 8px;
    selection-background-color: #8B5CF6;
    padding: 8px;
}

/* ---- History + chat ---- */
QListWidget#auraHistory {
    background-color: #16122A;
    border: 1px solid #322B5C;
    border-radius: 12px;
    padding: 8px;
    font-size: 11pt;
    outline: none;
}
QListWidget#auraHistory::item { padding: 8px; border-radius: 8px; }
QListWidget#auraHistory::item:selected {
    background-color: #372A5E;
    color: #FFFFFF;
}
QListWidget#auraHistory::item:hover { background-color: #241F42; }
QTextEdit#chatView {
    background-color: #16122A;
    border: 1px solid #322B5C;
    border-radius: 16px;
    padding: 8px;
    selection-background-color: #8B5CF6;
}
QTextEdit#chatView:focus { border-color: #8B5CF6; }

/* ---- Streaming / skeleton / typing states ---- */
QFrame#streamFrame {
    background-color: rgba(36, 31, 66, 0.92);
    border: 1px solid #8B5CF6;
    border-radius: 16px;
}
QLabel#streamHeader {
    color: #C4B8E8;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#streamText {
    color: #FFFFFF;
    font-size: 11pt;
}
QLabel#streamCursor { color: #FF8C42; font-size: 11pt; font-weight: 700; }
QFrame#skeletonBar {
    background-color: #241F42;
    border-radius: 8px;
}
QLabel#typingLabel {
    color: #C4B8E8;
    font-size: 11pt;
    font-style: italic;
}
QLabel#agiLabel {
    color: #8E83B8;
    font-size: 10pt;
}

/* ---- Talk / Start / Stop ---- */
QPushButton#talkBtn {
    background-color: #FF6A00;
    color: #FFFFFF;
    border: 1px solid #FF6A00;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 12pt;
    font-weight: 700;
}
QPushButton#talkBtn:hover { background-color: #FF8C42; }
QPushButton#talkBtn:pressed { background-color: #E55A00; }
QPushButton#talkBtn:disabled {
    background-color: #2A2450;
    color: #8E83B8;
    border-color: #2A2450;
}
QPushButton#startBtn {
    background-color: #FF6A00;
    color: #FFFFFF;
    border: 1px solid #FF6A00;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 12pt;
    font-weight: 700;
}
QPushButton#startBtn:hover { background-color: #FF8C42; }
QPushButton#startBtn:pressed { background-color: #E55A00; }
QPushButton#startBtn:disabled {
    background-color: #2A2450;
    color: #8E83B8;
    border-color: #2A2450;
}

/* ---- Scrollbars: slim, subtle, accent on hover ---- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #322B5C;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: #8B5CF6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal { background: #322B5C; border-radius: 4px; }
QScrollBar::handle:horizontal:hover { background: #8B5CF6; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { color: #8E83B8; background-color: transparent; font-size: 10pt; }
"""


def get_aura_stylesheet() -> str:
    return AURA_STYLESHEET
