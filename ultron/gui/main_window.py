"""Main Ultron window — Jarvis HUD edition.

Layout:
  Header: ULTRON + TRUSTRIUM • JARVIS HUD + status + mode + Settings/History
  Left:   glowing HUD core + spectrum + Talk now + Start/Stop + quick chips
          + mini system panel (CPU / RAM / Battery)
  Right:  chat-bubble conversation view

Public behavior preserved from the original window:
  MainWindow, worker signals (status_changed, message_logged, error,
  level_changed), _on_status / _on_log / _on_error / _on_level, mode combo
  values wake/voice, Start/Stop, Talk now (request_voice_turn), Settings
  dialog, History viewer, Ctrl+Alt+J hotkey, autostart sync, usage status bar.
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QStatusBar, QFrame, QSizePolicy,
)
from PySide6.QtGui import QFont, QColor

from .worker import UltronWorker
from .settings_dialog import SettingsDialog
from .conversation_viewer import ConversationViewer
from .waveform import LiveWaveform
from .hud_core import HudCoreWidget
from ..settings import load as load_settings, save as save_settings
from ..hotkey import GlobalHotkey
from .. import autostart
from .. import usage as usage_mod


STATUS_COLOR = {
    "idle": "#9AA3B2",
    "starting": "#cc9933",
    "listening": "#FF6A00",
    "thinking": "#9933CC",
    "speaking": "#33AA66",
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

# Quick command chips: label -> spoken command text.
_QUICK_COMMANDS = [
    ("📋  Briefing", "morning briefing"),
    ("🌐  Open Chrome", "open Chrome"),
    ("📸  Screenshot", "take a screenshot"),
    ("🎛️  Command Center", "command center"),
]

_BUBBLE_STYLE = {
    "you": ("#1E3A5F", "#FFFFFF", "right"),
    "ultron": ("#2A1E14", "#FFE2C2", "left"),
    "system": ("#1A1D24", "#A8A8B0", "center"),
    "reminder": ("#2A2414", "#FFD84D", "left"),
    "error": ("#3A1A1A", "#FF8A8A", "left"),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultron — Jarvis HUD")
        try:
            from .ultron_theme import WINDOW_STYLESHEET as _ULTRON_SS
            self.setStyleSheet(_ULTRON_SS)
        except Exception:
            pass
        self.resize(900, 640)
        self.setMinimumSize(860, 600)

        s = load_settings()
        self.worker = UltronWorker(self)
        self.worker.status_changed.connect(self._on_status)
        self.worker.message_logged.connect(self._on_log)
        self.worker.error.connect(self._on_error)
        self.worker.level_changed.connect(self._on_level)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)
        self.setCentralWidget(central)

        # ---- Header ---------------------------------------------------
        header = QFrame()
        header.setObjectName("hudHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_label = QLabel("ULTRON")
        title_label.setObjectName("hudTitle")
        subtitle_label = QLabel("TRUSTRIUM  •  JARVIS HUD")
        subtitle_label.setObjectName("hudSubtitle")
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header_layout.addLayout(title_col)

        header_layout.addStretch(1)

        # Status pill: dot + text (preserved attribute names).
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #9AA3B2; font-size: 20px;")
        self.status_text = QLabel("Idle")
        self.status_text.setObjectName("hudStatus")
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

        # ---- Body: left HUD core + right chat -------------------------
        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        # Left panel: core + spectrum + Talk + Start/Stop + chips + system.
        left = QFrame()
        left.setObjectName("corePanel")
        left.setFixedWidth(330)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        self.hud_core = HudCoreWidget()
        # Center the core in the panel.
        core_row = QHBoxLayout()
        core_row.addStretch(1)
        core_row.addWidget(self.hud_core)
        core_row.addStretch(1)
        left_layout.addLayout(core_row)

        # Live spectrum visualizer (preserved attribute name: waveform).
        self.waveform = LiveWaveform()
        left_layout.addWidget(self.waveform)

        # Talk-now button (only relevant in voice mode).
        self.talk_btn = QPushButton("🎤  Talk now")
        self.talk_btn.setObjectName("talkBtn")
        self.talk_btn.setEnabled(False)
        self.talk_btn.setMinimumHeight(48)
        left_layout.addWidget(self.talk_btn)

        # Start / Stop row.
        self.start_btn = QPushButton("▶  Start")
        self.start_btn.setObjectName("startBtn")
        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setEnabled(False)
        start_stop = QHBoxLayout()
        start_stop.addWidget(self.start_btn, 1)
        start_stop.addWidget(self.stop_btn, 1)
        left_layout.addLayout(start_stop)

        # Quick command chips.
        chips_label = QLabel("QUICK COMMANDS")
        chips_label.setStyleSheet("color: #7A8191; font-size: 9px; font-weight: 700; letter-spacing: 2px;")
        left_layout.addWidget(chips_label)
        self.chip_buttons: list[QPushButton] = []
        chips_row1 = QHBoxLayout()
        chips_row2 = QHBoxLayout()
        for idx, (label, command) in enumerate(_QUICK_COMMANDS):
            btn = QPushButton(label)
            btn.setObjectName("chipBtn")
            btn.clicked.connect(lambda _checked=False, cmd=command: self._quick_command(cmd))
            self.chip_buttons.append(btn)
            (chips_row1 if idx < 2 else chips_row2).addWidget(btn, 1)
        left_layout.addLayout(chips_row1)
        left_layout.addLayout(chips_row2)

        # Mini system panel: CPU / RAM / Battery (psutil if available).
        sys_panel = QFrame()
        sys_panel.setObjectName("sysPanel")
        sys_layout = QVBoxLayout(sys_panel)
        sys_layout.setContentsMargins(10, 8, 10, 8)
        sys_layout.setSpacing(2)
        sys_title = QLabel("SYSTEM")
        sys_title.setStyleSheet("color: #7A8191; font-size: 9px; font-weight: 700; letter-spacing: 2px;")
        sys_layout.addWidget(sys_title)
        self.cpu_label = QLabel("CPU: —")
        self.cpu_label.setObjectName("sysValue")
        self.ram_label = QLabel("RAM: —")
        self.ram_label.setObjectName("sysValue")
        self.batt_label = QLabel("Battery: —")
        self.batt_label.setObjectName("sysValue")
        sys_layout.addWidget(self.cpu_label)
        sys_layout.addWidget(self.ram_label)
        sys_layout.addWidget(self.batt_label)
        left_layout.addWidget(sys_panel)
        left_layout.addStretch(1)
        body.addWidget(left)

        # Right panel: chat-bubble conversation view.
        right = QFrame()
        right.setObjectName("chatPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(6)
        chat_title = QLabel("CONVERSATION")
        chat_title.setStyleSheet("color: #7A8191; font-size: 9px; font-weight: 700; letter-spacing: 2px;")
        right_layout.addWidget(chat_title)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("chatView")
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Segoe UI", 10))
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.log_view, 1)
        hint = QLabel("Tip: Voice mode → Start → Talk now. Or press Ctrl+Alt+J anywhere.")
        hint.setStyleSheet("color: #7A8191; font-size: 10px;")
        hint.setWordWrap(True)
        right_layout.addWidget(hint)
        body.addWidget(right, 1)

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
        # Append a short system snapshot when psutil is available.
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
        self._append("system", "Stop requested. (May need to close window to fully exit wake mode.)")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            s = load_settings()
            self.statusBar().showMessage(
                f"Provider: {s.get('llm_provider','?')}  |  Model: {s.get('llm_model') or '(default)'}"
            )

    def _quick_command(self, command: str):
        """Quick chip: guide the user to speak this command.

        The GUI has no text input and the worker has no text-injection
        channel, so chips do not fake a turn. They tell the user exactly
        what to say and, if the worker is already running, trigger a
        voice turn so the user can say it immediately.
        """
        self._append("system", f"Quick command ready — say: “{command}”")
        if self.worker.is_running():
            self.worker.request_voice_turn()
        else:
            self._append("system", "Press Start first, then Talk now.")

    # --- signals from worker ---
    def _on_status(self, s: str):
        self.status_text.setText(STATUS_LABEL.get(s, s.capitalize()))
        color = STATUS_COLOR.get(s, "#9AA3B2")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 20px;")
        # Drive HUD visuals: core color + spectrum tint + enabled state.
        try:
            self.hud_core.set_state(s)
        except Exception:
            pass
        try:
            self.waveform.set_color(color)
        except Exception:
            pass
        # Light up the spectrum only while actively listening.
        self.waveform.set_enabled_view(s == "listening")

    def _on_level(self, level: float):
        self.waveform.set_level(level)
        try:
            self.hud_core.set_level(level)
        except Exception:
            pass

    def _on_log(self, role: str, text: str):
        self._append(role, text)

    def _on_error(self, msg: str):
        self._append("error", msg)
        self._on_status("error")

    # --- helpers ---
    def _append(self, role: str, text: str):
        """Append one chat bubble. Role in you/ultron/system/reminder/error."""
        bg, fg, align = _BUBBLE_STYLE.get(role, ("#1A1D24", "#F2F2F2", "left"))
        label = {
            "you": "YOU",
            "ultron": "ULTRON",
            "system": "SYSTEM",
            "reminder": "REMINDER",
            "error": "ERROR",
        }.get(role, role.upper())
        safe = html.escape(text or "").replace("\n", "<br>")
        if align == "right":
            # Right-aligned bubble via a right-aligned wrapper.
            block = (
                f'<div style="text-align: right; margin: 4px 2px;">'
                f'<span style="display: inline-block; text-align: left; '
                f'background-color: {bg}; color: {fg}; '
                f'border-radius: 12px; padding: 8px 12px; max-width: 88%;">'
                f'<b style="font-size: 9px; letter-spacing: 1px;">{label}</b><br>{safe}'
                f"</span></div>"
            )
        elif align == "center":
            block = (
                f'<div style="text-align: center; margin: 4px 2px;">'
                f'<span style="display: inline-block; background-color: {bg}; color: {fg}; '
                f'border-radius: 10px; padding: 6px 12px; font-size: 10px;">'
                f"{safe}</span></div>"
            )
        else:
            block = (
                f'<div style="margin: 4px 2px;">'
                f'<span style="display: inline-block; background-color: {bg}; color: {fg}; '
                f'border-radius: 12px; padding: 8px 12px; max-width: 88%;">'
                f'<b style="font-size: 9px; letter-spacing: 1px;">{label}</b><br>{safe}'
                f"</span></div>"
            )
        self.log_view.append(block)
        # Keep the newest bubble visible.
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
