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
import threading
import traceback

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QStatusBar, QFrame, QSizePolicy, QLineEdit,
    QListWidget, QListWidgetItem,
)
from PySide6.QtGui import QFont, QColor

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
    "you": ("#4C2E85", "#FFFFFF", "right"),
    "ultron": ("#2D2350", "#FFE2F0", "left"),
    "system": ("#221A3B", "#C4B8E8", "center"),
    "reminder": ("#3A2E14", "#FFD84D", "left"),
    "error": ("#4A1A1A", "#FF8A8A", "left"),
}


class MainWindow(QMainWindow):
    # Text-runner signals (GUI-thread safe updates from the text thread).
    _text_log = Signal(str, str)
    _text_status = Signal(str)
    _text_typing = Signal(bool)
    _text_stages = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultron — Aura")
        try:
            from .ultron_theme import WINDOW_STYLESHEET as _ULTRON_SS
            self.setStyleSheet(_ULTRON_SS)
        except Exception:
            pass
        self.resize(1020, 680)
        self.setMinimumSize(940, 620)

        s = load_settings()
        self.worker = UltronWorker(self)
        self.worker.status_changed.connect(self._on_status)
        self.worker.message_logged.connect(self._on_log)
        self.worker.error.connect(self._on_error)
        self.worker.level_changed.connect(self._on_level)
        # Text-runner signals -> same slots as the voice worker.
        self._text_log.connect(self._on_log)
        self._text_status.connect(self._on_status)
        self._text_typing.connect(self._set_typing_direct)
        self._text_stages.connect(self._set_stages_direct)
        self._text_busy = False
        self._text_cancel = False

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)
        self.setCentralWidget(central)

        # ---- Header ---------------------------------------------------
        header = QFrame()
        header.setObjectName("auraHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_label = QLabel("ULTRON")
        title_label.setObjectName("auraTitle")
        subtitle_label = QLabel("TRUSTRIUM  •  AURA  •  AGI")
        subtitle_label.setObjectName("auraSubtitle")
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header_layout.addLayout(title_col)
        header_layout.addStretch(1)

        # Status pill: dot + text (preserved attribute names).
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #8B5CF6; font-size: 20px;")
        self.status_text = QLabel("Idle")
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        self.status_text.setFont(f)
        header_layout.addWidget(self.status_dot)
        header_layout.addWidget(self.status_text)
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
        body.setSpacing(12)
        root.addLayout(body, 1)

        # Left sidebar: History + system mini panel.
        left = QFrame()
        left.setObjectName("historyPanel")
        left.setFixedWidth(230)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        hist_title = QLabel("HISTORY")
        hist_title.setStyleSheet("color: #8E83B8; font-size: 9px; font-weight: 700; letter-spacing: 2px;")
        left_layout.addWidget(hist_title)
        self.history_list = QListWidget()
        self.history_list.setObjectName("auraHistory")
        left_layout.addWidget(self.history_list, 1)
        self.history_refresh_btn = QPushButton("🔄  Refresh history")
        self.history_refresh_btn.setObjectName("auraChipBtn")
        left_layout.addWidget(self.history_refresh_btn)
        sys_title = QLabel("SYSTEM")
        sys_title.setStyleSheet("color: #8E83B8; font-size: 9px; font-weight: 700; letter-spacing: 2px;")
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
        center_layout.setContentsMargins(14, 14, 14, 12)
        center_layout.setSpacing(10)
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
        self.agi_label.setStyleSheet("color: #8E83B8; font-size: 10px;")
        self.agi_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.agi_label)

        # Mode cards: Chat / Talk (Echo Mind style).
        cards = QHBoxLayout()
        cards.setSpacing(10)
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

        # Typing indicator (hidden unless thinking).
        self.typing_label = QLabel("Ultron is thinking…")
        self.typing_label.setStyleSheet("color: #C4B8E8; font-size: 11px; font-style: italic;")
        self.typing_label.setVisible(False)
        center_layout.addWidget(self.typing_label)

        # Quick actions + Topics chips above the input bar.
        chips_label = QLabel("QUICK ACTIONS  •  TOPICS")
        chips_label.setStyleSheet("color: #8E83B8; font-size: 9px; font-weight: 700; letter-spacing: 2px;")
        center_layout.addWidget(chips_label)
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
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

        # Input bar: text + mic + send.
        input_row = QHBoxLayout()
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
        center_layout.addLayout(input_row)

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
        color = STATUS_COLOR.get(s, "#8B5CF6")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 20px;")
        # Drive Aura visuals: orb + spectrum tint + enabled state.
        try:
            self.aura_orb.set_state(s)
        except Exception:
            pass
        try:
            self.waveform.set_color(color)
        except Exception:
            pass
        self.waveform.set_enabled_view(s == "listening")
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

    def _on_level(self, level: float):
        self.waveform.set_level(level)
        try:
            self.aura_orb.set_level(level)
        except Exception:
            pass

    def _on_log(self, role: str, text: str):
        self._append(role, text)

    def _on_error(self, msg: str):
        self._append("error", msg)
        self._on_status("error")

    # --- typing / stages (GUI thread) -------------------------------
    def _set_typing_direct(self, on: bool):
        try:
            self.typing_label.setVisible(bool(on))
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
