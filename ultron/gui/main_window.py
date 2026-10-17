"""Main Ultron window — Aura v2 edition.

Desktop adaptation of the mobile AI-app references (Echo Mind / AI
writer style): hero fluid Aura orb, Chat / Talk mode cards, modern chat
bubbles + input bar, History sidebar, Topics / Quick-action chips,
premium dark purple-gradient styling. NOT a literal phone portrait —
a 1020x680 desktop window.

Public behavior preserved from the Jarvis HUD window:
  MainWindow, worker signals (status_changed, message_logged, error,
  level_changed), _on_status / _on_log / _on_error / _on_level, mode combo
  values wake/voice, Start/Stop, Talk now (request_voice_turn), Settings
  dialog, History viewer, Ctrl+Alt+J hotkey, autostart sync, usage status bar.

Text input: the old GUI had NO text-injection channel into the worker,
so typed chat runs on a small GUI-owned text runner (same real Brain,
same Brain.think / speak / conversation-log path the worker uses for
voice turns). It never fakes a reply. While a voice session is running
we do NOT start a second Brain — Chat asks you to press Stop first.
"""
from __future__ import annotations

import datetime as _dt
import html
import inspect
import threading
import traceback

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QStatusBar, QFrame, QSizePolicy, QLineEdit,
    QListWidget, QListWidgetItem,
)
from PySide6.QtGui import QFont, QColor, QIcon

from .worker import UltronWorker
from .settings_dialog import SettingsDialog
from .conversation_viewer import ConversationViewer
from .waveform import LiveWaveform
from ..settings import load as load_settings, save as save_settings
from ..hotkey import GlobalHotkey
from .. import autostart
from .. import usage as usage_mod

# Aura orb is the new default visual; Jarvis core stays as fallback.
try:
    from .aura_orb import AuraOrbWidget
except Exception:  # pragma: no cover - fallback if Aura import fails
    from .hud_core import HudCoreWidget as AuraOrbWidget


STATUS_COLOR = {
    "idle": "#8B5CF6",
    "starting": "#cc9933",
    "listening": "#FF6A00",
    "thinking": "#A855F7",
    "speaking": "#EC4899",
    "error": "#cc3333",
}


STATUS_LABEL = {
    "idle": "Idle — click Start when ready",
    "starting": "Starting up...",
    "listening": "🎤  Listening...",
    "thinking": "🧠  Thinking...",
    "speaking": "🔊  Speaking...",
    "error": "❌  Error",
}

# Status-pill styling per state: (pill border, dot color). The pill
# updates immediately from every worker status signal — no polling.
_STATUS_PILL_STYLE = {
    "idle": ("#322B5C", "#8B5CF6"),
    "starting": ("#F59E0B", "#F59E0B"),
    "listening": ("#FF6A00", "#FF6A00"),
    "thinking": ("#A855F7", "#A855F7"),
    "speaking": ("#EC4899", "#EC4899"),
    "error": ("#F87171", "#F87171"),
}

# Stage pills: Listening -> Understanding -> Doing. Exactly one is
# "active" at a time, driven by _on_status.
_STAGE_ORDER = ("listening", "thinking", "speaking")
_STAGE_TITLES = {
    "listening": "●  Listening",
    "thinking": "●  Understanding",
    "speaking": "●  Doing",
}


def _supports_on_token(fn) -> bool:
    """True if fn accepts an on_token= keyword (or **kwargs).

    Defensive probe only — never calls fn, never crashes on builtins
    or callables without a signature.
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if "on_token" in params:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

# Quick command chips: label -> spoken/typed command text.
_QUICK_COMMANDS = [
    ("📋  Briefing", "morning briefing"),
    ("🌐  Open Chrome", "open Chrome"),
    ("📸  Screenshot", "take a screenshot"),
    ("🎛️  Command Center", "command center"),
]

# Topics: label -> starter prompt.
_TOPICS = [
    ("📈  Finance", "Briefing on Finance"),
    ("💚  Health", "Briefing on Health"),
    ("💻  Develop", "Briefing on Develop"),
    ("💼  Business", "Briefing on Business"),
]

_BUBBLE_STYLE = {
    "you": ("#3A2E7A", "#FFFFFF", "right"),
    "ultron": ("#241F42", "#FFFFFF", "left"),
    "system": ("#1B1730", "#C4B8E8", "center"),
    "reminder": ("#3A2E14", "#FFD84D", "left"),
    "error": ("#4A1A1A", "#FF8A8A", "left"),
}


def _app_icon() -> QIcon:
    """Window icon from assets/ultron.ico, with a safe empty fallback."""
    try:
        from .ultron_theme import find_app_icon

        path = find_app_icon()
        if path:
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    except Exception:
        pass
    return QIcon()


class MainWindow(QMainWindow):
    # Text-runner signals (GUI-thread safe updates from the text thread).
    _text_log = Signal(str, str)
    _text_status = Signal(str)
    _text_typing = Signal(bool)
    _text_stages = Signal(str)
    # Streaming signals (defensive: only emitted when the backend
    # exposes an on_token callback; otherwise never fired).
    _text_stream_begin = Signal()
    _text_token = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultron — Aura")
        self.setWindowIcon(_app_icon())
        try:
            from .ultron_theme import WINDOW_STYLESHEET as _ULTRON_SS
            self.setStyleSheet(_ULTRON_SS)
        except Exception:
            pass
        self.resize(1080, 720)
        self.setMinimumSize(960, 640)

        s = load_settings()
        self.worker = UltronWorker(self)
        self.worker.status_changed.connect(self._on_status)
        self.worker.message_logged.connect(self._on_log)
        self.worker.error.connect(self._on_error)
        self.worker.level_changed.connect(self._on_level)
        # Streaming from the voice worker (no-op if the backend has no
        # token callback — getattr keeps old workers working).
        _token_begin = getattr(self.worker, "token_stream_started", None)
        if _token_begin is not None:
            _token_begin.connect(self._begin_streaming)
        _token_changed = getattr(self.worker, "token_changed", None)
        if _token_changed is not None:
            _token_changed.connect(self._append_stream_token)
        # Text-runner signals -> same slots as the voice worker.
        self._text_log.connect(self._on_log)
        self._text_status.connect(self._on_status)
        self._text_typing.connect(self._set_typing_direct)
        self._text_stages.connect(self._set_stages_direct)
        self._text_stream_begin.connect(self._begin_streaming)
        self._text_token.connect(self._append_stream_token)
        self._text_busy = False
        self._text_cancel = False
        # Streaming state: partial tokens accumulate here until the
        # full reply arrives via _on_log, which then replaces them.
        self._streaming = False
        self._stream_text = ""
        self._typing_dots = 0
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(400)
        self._typing_timer.timeout.connect(self._tick_typing_dots)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(8)
        self.setCentralWidget(central)

        # ---- Header: Trustrium branding + status pill ---------------
        header = QFrame()
        header.setObjectName("auraHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(16)

        # Brand mark: orange rounded tile with a white "U".
        brand_mark = QFrame()
        brand_mark.setObjectName("brandMark")
        brand_mark.setFixedSize(40, 40)
        brand_layout = QHBoxLayout(brand_mark)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_letter = QLabel("U")
        brand_letter.setObjectName("brandMarkLetter")
        brand_letter.setAlignment(Qt.AlignCenter)
        brand_layout.addWidget(brand_letter)
        header_layout.addWidget(brand_mark)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        eyebrow_label = QLabel("TRUSTRIUM  •  AGI ASSISTANT")
        eyebrow_label.setObjectName("brandEyebrow")
        title_label = QLabel("ULTRON")
        title_label.setObjectName("auraTitle")
        subtitle_label = QLabel("AURA  •  PLAN → EXECUTE → VERIFY")
        subtitle_label.setObjectName("auraSubtitle")
        title_col.addWidget(eyebrow_label)
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header_layout.addLayout(title_col)
        header_layout.addStretch(1)

        # Status pill: dot + text in a bordered pill (preserved
        # attribute names status_dot / status_text).
        status_pill = QFrame()
        status_pill.setObjectName("statusPill")
        pill_layout = QHBoxLayout(status_pill)
        pill_layout.setContentsMargins(12, 8, 12, 8)
        pill_layout.setSpacing(8)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusPillDot")
        self.status_dot.setStyleSheet("color: #8B5CF6;")
        self.status_text = QLabel("Idle")
        self.status_text.setObjectName("statusPillText")
        pill_layout.addWidget(self.status_dot)
        pill_layout.addWidget(self.status_text)
        header_layout.addWidget(status_pill)
        header_layout.addStretch(1)

        # Mode picker + Settings / History (preserved widgets).
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Wake word (Hey Ultron)", "wake")
        self.mode_combo.addItem("Voice (manual trigger)", "voice")
        cur_mode = s.get("default_mode", "wake")
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == cur_mode:
                self.mode_combo.setCurrentIndex(i)
                break
        self.settings_btn = QPushButton("⚙  Settings")
        self.history_btn = QPushButton("📜  History")
        header_layout.addWidget(self.mode_combo)
        header_layout.addWidget(self.settings_btn)
        header_layout.addWidget(self.history_btn)
        root.addWidget(header)

        # ---- Body: History sidebar + center ---------------------------
        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        # Left sidebar: History + system mini panel.
        left = QFrame()
        left.setObjectName("historyPanel")
        left.setFixedWidth(232)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(8)
        hist_title = QLabel("HISTORY")
        hist_title.setObjectName("sectionLabel")
        left_layout.addWidget(hist_title)
        self.history_list = QListWidget()
        self.history_list.setObjectName("auraHistory")
        left_layout.addWidget(self.history_list, 1)
        self.history_refresh_btn = QPushButton("🔄  Refresh history")
        self.history_refresh_btn.setObjectName("auraChipBtn")
        left_layout.addWidget(self.history_refresh_btn)
        sys_title = QLabel("SYSTEM")
        sys_title.setObjectName("sectionLabel")
        left_layout.addWidget(sys_title)
        self.cpu_label = QLabel("CPU: —")
        self.ram_label = QLabel("RAM: —")
        self.batt_label = QLabel("Battery: —")
        for lbl in (self.cpu_label, self.ram_label, self.batt_label):
            lbl.setStyleSheet("color: #FFFFFF; font-size: 10px; font-weight: 700;")
            left_layout.addWidget(lbl)
        left_layout.addStretch(1)
        body.addWidget(left)

        # Center panel: orb + mode cards + chat + input.
        center = QFrame()
        center.setObjectName("centerPanel")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(16, 16, 16, 16)
        center_layout.setSpacing(8)
        body.addWidget(center, 1)

        # Aura orb (hero). Alias hud_core -> same object for compatibility
        # with the old _on_status / _on_level code paths.
        self.aura_orb = AuraOrbWidget()
        self.hud_core = self.aura_orb
        orb_row = QHBoxLayout()
        orb_row.addStretch(1)
        orb_row.addWidget(self.aura_orb)
        orb_row.addStretch(1)
        center_layout.addLayout(orb_row)

        # Listening banner (voice screen state).
        self.listening_banner = QFrame()
        self.listening_banner.setObjectName("auraPanel")
        banner_layout = QHBoxLayout(self.listening_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self.listening_label = QLabel("Go ahead, I'm listening…")
        self.listening_label.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 700;")
        self.cancel_btn = QPushButton("✕  Cancel")
        self.cancel_btn.setObjectName("auraChipBtn")
        banner_layout.addWidget(self.listening_label, 1)
        banner_layout.addWidget(self.cancel_btn)
        self.listening_banner.setVisible(False)
        center_layout.addWidget(self.listening_banner)

        # Live spectrum visualizer (preserved attribute name: waveform).
        self.waveform = LiveWaveform()
        center_layout.addWidget(self.waveform)

        # AGI stages line: Thinking -> Acting -> Verifying (never faked).
        self.agi_label = QLabel("Thinking → Acting → Verifying")
        self.agi_label.setObjectName("agiLabel")
        self.agi_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.agi_label)

        # Stage pills: Listening / Understanding / Doing — exactly one
        # lights up per worker status, for immediate feedback.
        stage_row = QHBoxLayout()
        stage_row.setSpacing(8)
        stage_row.addStretch(1)
        self._stage_pills: dict[str, QLabel] = {}
        for key in _STAGE_ORDER:
            pill = QLabel(_STAGE_TITLES[key])
            pill.setObjectName("stagePill")
            pill.setAlignment(Qt.AlignCenter)
            stage_row.addWidget(pill)
            self._stage_pills[key] = pill
        stage_row.addStretch(1)
        center_layout.addLayout(stage_row)

        # Mode cards: Chat / Talk (Echo Mind style).
        cards = QHBoxLayout()
        cards.setSpacing(8)
        self.chat_card = QPushButton("💬  Chat with Ultron\nType — keyboard")
        self.chat_card.setObjectName("auraModeCard")
        self.chat_card.setMinimumHeight(64)
        self.talk_card = QPushButton("🎤  Talk with Ultron\nVoice — mic")
        self.talk_card.setObjectName("auraModeCard")
        self.talk_card.setMinimumHeight(64)
        cards.addWidget(self.chat_card, 1)
        cards.addWidget(self.talk_card, 1)
        center_layout.addLayout(cards)

        # Chat-bubble conversation view.
        self.log_view = QTextEdit()
        self.log_view.setObjectName("chatView")
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Segoe UI", 10))
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center_layout.addWidget(self.log_view, 1)

        # Typing indicator (hidden unless thinking) + skeleton bars.
        self.typing_label = QLabel("Ultron is thinking…")
        self.typing_label.setObjectName("typingLabel")
        self.typing_label.setVisible(False)
        center_layout.addWidget(self.typing_label)
        self.skeleton_frame = QFrame()
        skeleton_layout = QVBoxLayout(self.skeleton_frame)
        skeleton_layout.setContentsMargins(0, 0, 0, 0)
        skeleton_layout.setSpacing(8)
        self._skeleton_bars: list[QFrame] = []
        for width in (280, 220, 180):
            bar = QFrame()
            bar.setObjectName("skeletonBar")
            bar.setFixedSize(width, 12)
            skeleton_layout.addWidget(bar)
            self._skeleton_bars.append(bar)
        self.skeleton_frame.setVisible(False)
        center_layout.addWidget(self.skeleton_frame)

        # Streaming frame: shows partial tokens live while a reply is
        # being generated. Hidden again when the full reply lands.
        self.stream_frame = QFrame()
        self.stream_frame.setObjectName("streamFrame")
        stream_layout = QVBoxLayout(self.stream_frame)
        stream_layout.setContentsMargins(16, 16, 16, 16)
        stream_layout.setSpacing(8)
        stream_header = QLabel("ULTRON  •  LIVE")
        stream_header.setObjectName("streamHeader")
        stream_layout.addWidget(stream_header)
        stream_body = QHBoxLayout()
        stream_body.setSpacing(0)
        self.stream_label = QLabel("")
        self.stream_label.setObjectName("streamText")
        self.stream_label.setWordWrap(True)
        self.stream_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.stream_cursor = QLabel("▍")
        self.stream_cursor.setObjectName("streamCursor")
        stream_body.addWidget(self.stream_label, 1)
        stream_body.addWidget(self.stream_cursor)
        stream_layout.addLayout(stream_body)
        self.stream_frame.setVisible(False)
        center_layout.addWidget(self.stream_frame)

        # Quick actions + Topics chips above the input bar.
        chips_label = QLabel("QUICK ACTIONS  •  TOPICS")
        chips_label.setObjectName("sectionLabel")
        center_layout.addWidget(chips_label)
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        self.chip_buttons: list[QPushButton] = []
        for label, command in _QUICK_COMMANDS:
            btn = QPushButton(label)
            btn.setObjectName("auraChipBtn")
            btn.clicked.connect(lambda _c=False, cmd=command: self._quick_command(cmd))
            self.chip_buttons.append(btn)
            chips_row.addWidget(btn)
        for label, prompt in _TOPICS:
            btn = QPushButton(label)
            btn.setObjectName("auraChipBtn")
            btn.clicked.connect(lambda _c=False, pr=prompt: self._quick_command(pr))
            self.chip_buttons.append(btn)
            chips_row.addWidget(btn)
        chips_row.addStretch(1)
        center_layout.addLayout(chips_row)

        # Input bar: text + mic + send, inside a polished pill frame.
        input_bar = QFrame()
        input_bar.setObjectName("inputBar")
        input_row = QHBoxLayout(input_bar)
        input_row.setContentsMargins(8, 8, 8, 8)
        input_row.setSpacing(8)
        self.input_edit = QLineEdit()
        self.input_edit.setObjectName("auraInput")
        self.input_edit.setPlaceholderText("Send a message…")
        self.input_edit.returnPressed.connect(self._send_text_from_input)
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setObjectName("auraMicBtn")
        self.mic_btn.setToolTip("Talk — start Voice mode + Talk now (or Ctrl+Alt+J)")
        self.send_btn = QPushButton("➤  Send")
        self.send_btn.setObjectName("auraSendBtn")
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.mic_btn)
        input_row.addWidget(self.send_btn)
        center_layout.addWidget(input_bar)

        # Talk / Start / Stop row (preserved widgets).
        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.talk_btn = QPushButton("🎤  Talk now")
        self.talk_btn.setObjectName("talkBtn")
        self.talk_btn.setEnabled(False)
        self.talk_btn.setMinimumHeight(44)
        self.start_btn = QPushButton("▶  Start")
        self.start_btn.setObjectName("startBtn")
        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.talk_btn, 1)
        controls.addWidget(self.start_btn, 1)
        controls.addWidget(self.stop_btn, 1)
        center_layout.addLayout(controls)

        hint = QLabel("Tip: Chat → type + Send. Talk → Talk card or Talk now / Ctrl+Alt+J. Wake mode is still broken — use Voice / Chat.")
        hint.setStyleSheet("color: #8E83B8; font-size: 10px;")
        hint.setWordWrap(True)
        center_layout.addWidget(hint)

        self.setStatusBar(QStatusBar(self))
        self._refresh_status_bar()

        # Refresh usage every 5 s while running.
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(5000)
        self._usage_timer.timeout.connect(self._refresh_status_bar)
        self._usage_timer.start()

        # Refresh system stats every 2 s (cheap, non-blocking).
        self._sys_timer = QTimer(self)
        self._sys_timer.setInterval(2000)
        self._sys_timer.timeout.connect(self._refresh_system_panel)
        self._sys_timer.start()
        self._refresh_system_panel()

        # History sidebar.
        self._history_sessions: list[tuple[str, list[tuple[str, str]]]] = []
        self._load_history()
        self.history_refresh_btn.clicked.connect(self._load_history)
        self.history_list.itemClicked.connect(self._show_history_session)

        # Global push-to-talk hotkey.
        self._hotkey = GlobalHotkey(s.get("ptt_hotkey", "ctrl+alt+j"), self._on_hotkey)
        if s.get("ptt_enabled", True):
            self._hotkey.start()

        # Sync auto-start preference with the Windows registry (best-effort).
        try:
            autostart.sync_with(bool(s.get("auto_start_on_boot", False)))
        except Exception:
            pass

        # Wire
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.settings_btn.clicked.connect(self._open_settings)
        self.history_btn.clicked.connect(self._open_history)
        self.talk_btn.clicked.connect(lambda: self.worker.request_voice_turn())
        self.chat_card.clicked.connect(self._chat_card_clicked)
        self.talk_card.clicked.connect(self._talk_card_clicked)
        self.mic_btn.clicked.connect(self._mic_clicked)
        self.send_btn.clicked.connect(self._send_text_from_input)
        self.cancel_btn.clicked.connect(self._cancel_listening)

    # --- hotkey handling ---
    def _on_hotkey(self):
        """Global push-to-talk: if running, trigger a voice turn; else start in voice mode."""
        from PySide6.QtCore import QTimer
        if self.worker.is_running():
            self.worker.request_voice_turn()
        else:
            for i in range(self.mode_combo.count()):
                if self.mode_combo.itemData(i) == "voice":
                    self.mode_combo.setCurrentIndex(i)
                    break
            self._start()
            QTimer.singleShot(800, self.worker.request_voice_turn)

    def _open_history(self):
        dlg = ConversationViewer(self)
        dlg.exec()

    def _refresh_status_bar(self):
        s = load_settings()
        provider = s.get("llm_provider", "?")
        model = s.get("llm_model") or "(default)"
        usage_str = usage_mod.format_summary_short() or "Today: 0 tokens"
        msg = f"Provider: {provider}  |  Model: {model}  |  {usage_str}"
        try:
            import psutil  # type: ignore

            cpu = psutil.cpu_percent(interval=0)
            mem = psutil.virtual_memory().percent
            msg += f"  |  CPU {cpu:.0f}%  RAM {mem:.0f}%"
        except Exception:
            pass
        self.statusBar().showMessage(msg)

    def _refresh_system_panel(self):
        """Update CPU / RAM / Battery labels. Never raises, never blocks."""
        try:
            import psutil  # type: ignore

            try:
                cpu = psutil.cpu_percent(interval=0)
                self.cpu_label.setText(f"CPU: {cpu:.0f}%")
            except Exception:
                self.cpu_label.setText("CPU: —")
            try:
                mem = psutil.virtual_memory()
                self.ram_label.setText(
                    f"RAM: {mem.percent:.0f}%  ({mem.used // (1024 ** 2)} / {mem.total // (1024 ** 2)} MB)"
                )
            except Exception:
                self.ram_label.setText("RAM: —")
            try:
                batt = psutil.sensors_battery()
                if batt is None:
                    self.batt_label.setText("Battery: — (desktop / unknown)")
                else:
                    state = "Charging" if batt.power_plugged else "On battery"
                    self.batt_label.setText(f"Battery: {batt.percent:.0f}%  •  {state}")
            except Exception:
                self.batt_label.setText("Battery: —")
        except Exception:
            self.cpu_label.setText("CPU: —")
            self.ram_label.setText("RAM: —")
            self.batt_label.setText("Battery: —")

    # --- mode cards ------------------------------------------------
    def _chat_card_clicked(self):
        """Chat card: focus the text input. Chat needs no worker."""
        self.input_edit.setFocus()
        self._append("system", "Chat mode — type below and press Send.")

    def _talk_card_clicked(self):
        """Talk card: start Voice mode + trigger one voice turn."""
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == "voice":
                self.mode_combo.setCurrentIndex(i)
                break
        if not self.worker.is_running():
            self._start()
        # Give the voice loop a moment to arm, then trigger.
        QTimer.singleShot(800, self.worker.request_voice_turn)
        self.listening_banner.setVisible(True)
        self.listening_label.setText("Go ahead, I'm listening…")

    def _mic_clicked(self):
        """Input-bar mic: same as Talk now / Talk card."""
        if self.worker.is_running():
            self.worker.request_voice_turn()
        else:
            self._talk_card_clicked()

    def _cancel_listening(self):
        """Cancel button: best-effort. Hides the banner; a recording already
        in progress finishes on its own — we never fake a transcript."""
        self._text_cancel = True
        self.listening_banner.setVisible(False)
        self._append("system", "Listening cancelled (a recording already in progress will finish on its own).")

    # --- actions ---
    def _start(self):
        mode = self.mode_combo.currentData()
        save_settings({"default_mode": mode})
        self.worker.start(mode)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.mode_combo.setEnabled(False)
        self.talk_btn.setEnabled(mode == "voice")
        self._append("system", f"Starting in {mode} mode...")

    def _stop(self):
        self.worker.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.mode_combo.setEnabled(True)
        self.talk_btn.setEnabled(False)
        self.listening_banner.setVisible(False)
        self._append("system", "Stop requested. (May need to close window to fully exit wake mode.)")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            s = load_settings()
            self.statusBar().showMessage(
                f"Provider: {s.get('llm_provider','?')}  |  Model: {s.get('llm_model') or '(default)'}"
            )

    # --- chat text path (GUI-owned text runner) --------------------
    def _send_text_from_input(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self._send_text(text)

    def _send_text(self, text: str):
        """Send typed text as a real brain turn (never faked)."""
        text = (text or "").strip()
        if not text:
            return
        if self._text_busy:
            self._append("system", "Ultron is already thinking — please wait.")
            return
        if self.worker.is_running():
            self._append(
                "system",
                "Voice session is running — press Stop first to use Chat, "
                "or use Talk now for voice.",
            )
            return
        self._text_busy = True
        self._text_cancel = False
        self._append("you", text)
        self._text_typing.emit(True)
        self._text_stages.emit("🧠 Thinking…")
        self._text_status.emit("thinking")
        t = threading.Thread(target=self._run_text_turn, args=(text,), daemon=True)
        t.start()

    def _run_text_turn(self, text: str):
        """Runs in a background thread. UI updates go through signals only."""
        try:
            from ultron.config import assert_keys
            try:
                assert_keys()
            except RuntimeError as exc:
                self._text_log.emit("error", str(exc))
                self._text_status.emit("error")
                return
            from ultron.brain import Brain
            from ultron.voice.speak import speak
            from ultron.conversation_log import log as conv_log

            # Language: Roman Urdu detection if available, else English.
            lang = "en"
            try:
                from ..voice.roman_urdu import detect_roman_urdu

                if detect_roman_urdu(text):
                    lang = "roman_urdu"
            except Exception:
                pass
            conv_log("user", text, lang)
            self._text_stages.emit("🧠 Thinking → ⚙️ Acting — calling tools…")
            brain = Brain()
            # Streaming (defensive): if the backend exposes an
            # on_token callback, show partial tokens live as they
            # arrive. Otherwise fall back to the full-reply path —
            # never crash, never hang, never fake a reply.
            reply: str
            if _supports_on_token(brain.think):
                self._text_stream_begin.emit()

                def _on_token(token, _self=self) -> None:
                    try:
                        _self._text_token.emit(str(token))
                    except Exception:
                        pass

                try:
                    reply = brain.think(text, lang=lang, on_token=_on_token)
                except TypeError as exc:
                    # Only retry when the TypeError is actually about
                    # on_token; a TypeError inside the backend must
                    # surface as the turn error, not a double turn.
                    if "on_token" in str(exc):
                        reply = brain.think(text, lang=lang)
                    else:
                        raise
            else:
                reply = brain.think(text, lang=lang)
            if self._text_cancel:
                self._text_log.emit("system", "Cancelled.")
                self._text_status.emit("idle")
                return
            self._text_stages.emit("✓ Verifying → 🔊 Speaking…")
            self._text_log.emit("ultron", reply)
            conv_log("ultron", reply, lang)
            self._text_status.emit("speaking")
            try:
                speak(reply, lang)
            except Exception as exc:
                self._text_log.emit("error", f"TTS failed: {exc}")
            self._text_status.emit("idle")
            self._text_stages.emit("Done — Thinking → Acting → Verifying ✓")
        except Exception:
            traceback.print_exc()
            self._text_log.emit("error", f"Sorry, something broke: {traceback.format_exc(limit=1).strip()}")
            self._text_status.emit("error")
        finally:
            self._text_typing.emit(False)
            self._text_busy = False

    def _quick_command(self, command: str):
        """Quick / Topic chip.

        If a voice session is running, use the voice path (trigger a voice
        turn and let the user speak the command). Otherwise send it as a
        real typed brain turn — no faked replies.
        """
        if self.worker.is_running():
            self._append("system", f"Quick command ready — say: “{command}”")
            self.worker.request_voice_turn()
        else:
            self._send_text(command)

    # --- history sidebar -------------------------------------------
    def _load_history(self):
        """Parse data/conversation.log into sessions. Never crashes."""
        self._history_sessions = []
        try:
            from ..config import CONVERSATION_LOG

            path = CONVERSATION_LOG
            if not path.exists():
                self.history_list.clear()
                return
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            self.history_list.clear()
            return
        sessions: list[tuple[str, list[tuple[str, str]]]] = []
        current: list[tuple[str, str]] = []
        current_label = ""
        for line in lines:
            try:
                ts = line[:19]
                rest = line[19:].lstrip()
                if ":" not in rest:
                    continue
                role_part, _, text = rest.partition(":")
                role = role_part.split("[")[0].strip().lower()
                text = text.strip()
                if not text:
                    continue
                if role in ("user", "you"):
                    if current:
                        sessions.append((current_label, current))
                    current_label = f"{ts[11:16]} — {text[:60]}"
                    current = [("you", text)]
                elif current:
                    if role == "ultron":
                        current.append(("ultron", text))
                    elif role in ("system", "reminder", "error"):
                        current.append((role, text))
            except Exception:
                continue
        if current:
            sessions.append((current_label, current))
        # Keep the newest 50 sessions.
        self._history_sessions = sessions[-50:]
        self.history_list.clear()
        for label, _turns in reversed(self._history_sessions):
            self.history_list.addItem(QListWidgetItem(label or "(conversation)"))

    def _show_history_session(self, item: QListWidgetItem):
        """Show one past session in the chat view (non-destructive)."""
        try:
            row = self.history_list.row(item)
            # List is reversed-newest-first; map back to sessions.
            idx = len(self._history_sessions) - 1 - row
            if idx < 0 or idx >= len(self._history_sessions):
                return
            label, turns = self._history_sessions[idx]
            self._append("system", f"— History: {label} —")
            for role, text in turns:
                self._append(role, text)
        except Exception:
            pass

    # --- signals from worker ---
    def _on_status(self, s: str):
        self.status_text.setText(STATUS_LABEL.get(s, s.capitalize()))
        border, dot = _STATUS_PILL_STYLE.get(s, ("#322B5C", "#8B5CF6"))
        self.status_dot.setStyleSheet(f"color: {dot};")
        # Drive Aura visuals: orb + spectrum tint + enabled state.
        try:
            self.aura_orb.set_state(s)
        except Exception:
            pass
        try:
            self.waveform.set_color(dot)
        except Exception:
            pass
        self.waveform.set_enabled_view(s == "listening")
        # Stage pills: immediate listening / understanding / doing.
        self._update_stage_pills(s)
        # Typing + skeleton: on while thinking, off otherwise.
        if s == "thinking":
            self._set_typing_direct(True)
        elif s in ("speaking", "idle", "error"):
            self._set_typing_direct(False)
        # Voice-screen state: full listening banner.
        try:
            self.listening_banner.setVisible(s == "listening")
            if s == "listening":
                self.listening_label.setText("Go ahead, I'm listening…")
        except Exception:
            pass
        if s == "thinking":
            self._set_stages_direct("🧠 Thinking…")
        elif s == "speaking":
            self._set_stages_direct("✓ Verifying → 🔊 Speaking…")
        elif s == "idle":
            pass  # keep the last stages line; next turn overwrites it.

    def _update_stage_pills(self, state: str) -> None:
        """Light exactly one stage pill (listening/thinking/speaking)."""
        for key, pill in self._stage_pills.items():
            pill.setObjectName("stagePillActive" if key == state else "stagePill")
            # Object-name change needs a re-polish to take effect.
            try:
                pill.style().unpolish(pill)
                pill.style().polish(pill)
            except Exception:
                pass

    def _on_level(self, level: float):
        self.waveform.set_level(level)
        try:
            self.aura_orb.set_level(level)
        except Exception:
            pass

    def _on_log(self, role: str, text: str):
        # A finished reply replaces any live streaming preview —
        # never show both the partial tokens and the full bubble.
        if role == "ultron":
            self._finish_streaming()
            self._set_typing_direct(False)
        elif role == "you":
            self._finish_streaming()
        self._append(role, text)

    def _on_error(self, msg: str):
        self._append("error", msg)
        self._on_status("error")

    # --- typing / stages / streaming (GUI thread) -------------------
    def _set_typing_direct(self, on: bool):
        try:
            self.typing_label.setVisible(bool(on))
            if on:
                self._typing_dots = 0
                self.typing_label.setText("Ultron is thinking")
                if not self._typing_timer.isActive():
                    self._typing_timer.start()
            else:
                self._typing_timer.stop()
            try:
                self.skeleton_frame.setVisible(bool(on))
            except Exception:
                pass
        except Exception:
            pass

    def _tick_typing_dots(self) -> None:
        """Animate the typing indicator: . -> .. -> ... (400 ms)."""
        try:
            if not self.typing_label.isVisible():
                return
            self._typing_dots = (self._typing_dots + 1) % 4
            self.typing_label.setText(
                "Ultron is thinking" + "." * self._typing_dots
            )
        except Exception:
            pass

    def _begin_streaming(self) -> None:
        """Show the live streaming frame; tokens append via _append_stream_token."""
        try:
            self._streaming = True
            self._stream_text = ""
            self.stream_label.setText("")
            self.stream_frame.setVisible(True)
            self._set_typing_direct(False)
            scrollbar = self.log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception:
            pass

    def _append_stream_token(self, token: str) -> None:
        """Append one partial token to the live streaming bubble."""
        try:
            if not token:
                return
            if not self._streaming:
                self._begin_streaming()
            self._stream_text += token
            # Cap the live preview so a runaway stream can't grow
            # the label without bound; the full reply still lands
            # in the chat bubble via _on_log.
            preview = self._stream_text
            if len(preview) > 4000:
                preview = preview[:4000] + "…"
            self.stream_label.setText(preview)
        except Exception:
            pass

    def _finish_streaming(self) -> None:
        """Hide the live streaming frame (full reply replaces it)."""
        try:
            self._streaming = False
            self._stream_text = ""
            self.stream_frame.setVisible(False)
        except Exception:
            pass

    def _set_stages_direct(self, text: str):
        try:
            self.agi_label.setText(text or "Thinking → Acting → Verifying")
        except Exception:
            pass

    # --- helpers ---
    def _append(self, role: str, text: str):
        """Append one chat bubble with avatar dot + timestamp."""
        bg, fg, align = _BUBBLE_STYLE.get(role, ("#221A3B", "#FFFFFF", "left"))
        label = {
            "you": "YOU",
            "ultron": "ULTRON",
            "system": "SYSTEM",
            "reminder": "REMINDER",
            "error": "ERROR",
        }.get(role, role.upper())
        ts = _dt.datetime.now().strftime("%H:%M")
        dot = "●"
        safe = html.escape(text or "").replace("\n", "<br>")
        head = f'<b style="font-size: 9px; letter-spacing: 1px;">{dot} {label} &nbsp;·&nbsp; {ts}</b><br>{safe}'
        if align == "right":
            block = (
                f'<div style="text-align: right; margin: 4px 2px;">'
                f'<span style="display: inline-block; text-align: left; '
                f'background-color: {bg}; color: {fg}; '
                f'border-radius: 16px; padding: 8px 12px; max-width: 88%;">'
                f"{head}</span></div>"
            )
        elif align == "center":
            block = (
                f'<div style="text-align: center; margin: 4px 2px;">'
                f'<span style="display: inline-block; background-color: {bg}; color: {fg}; '
                f'border-radius: 12px; padding: 6px 12px; font-size: 10px;">'
                f"{safe}</span></div>"
            )
        else:
            block = (
                f'<div style="margin: 4px 2px;">'
                f'<span style="display: inline-block; background-color: {bg}; color: {fg}; '
                f'border-radius: 16px; padding: 8px 12px; max-width: 88%;">'
                f"{head}</span></div>"
            )
        self.log_view.append(block)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # --- close behavior ---
    def closeEvent(self, event):
        # Hide to tray instead of quitting if tray icon is visible
        if hasattr(self, "_hide_on_close") and self._hide_on_close:
            event.ignore()
            self.hide()
        else:
            self.worker.stop()
            super().closeEvent(event)
