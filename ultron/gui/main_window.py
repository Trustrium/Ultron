"""Main Ultron window — status display, controls, recent conversation log."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QStatusBar,
)
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

from PySide6.QtCore import QTimer

from .worker import UltronWorker
from .settings_dialog import SettingsDialog
from .conversation_viewer import ConversationViewer
from .waveform import LiveWaveform
from ..settings import load as load_settings, save as save_settings
from ..hotkey import GlobalHotkey
from .. import autostart
from .. import usage as usage_mod


STATUS_COLOR = {
    "idle":      "#888",
    "starting":  "#cc9933",
    "listening": "#3366cc",
    "thinking":  "#9933cc",
    "speaking":  "#33aa66",
    "error":     "#cc3333",
}


STATUS_LABEL = {
    "idle": "Idle — click Start when ready",
    "starting": "Starting up...",
    "listening": "🎤  Listening...",
    "thinking": "🧠  Thinking...",
    "speaking": "🔊  Speaking...",
    "error": "❌  Error",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultron")
        try:
            from .ultron_theme import WINDOW_STYLESHEET as _ULTRON_SS
            self.setStyleSheet(_ULTRON_SS)
        except Exception:
            pass
        self.resize(720, 560)

        s = load_settings()
        self.worker = UltronWorker(self)
        self.worker.status_changed.connect(self._on_status)
        self.worker.message_logged.connect(self._on_log)
        self.worker.error.connect(self._on_error)
        self.worker.level_changed.connect(self._on_level)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # Status row
        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #888; font-size: 22px;")
        self.status_text = QLabel("Idle")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        self.status_text.setFont(f)
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text, 1)

        # Mode picker + start/stop
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Wake word (Hey Ultron)", "wake")
        self.mode_combo.addItem("Voice (manual trigger)", "voice")
        cur_mode = s.get("default_mode", "wake")
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == cur_mode:
                self.mode_combo.setCurrentIndex(i); break
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.settings_btn = QPushButton("Settings...")

        status_row.addWidget(self.mode_combo)
        status_row.addWidget(self.start_btn)
        status_row.addWidget(self.stop_btn)
        status_row.addWidget(self.settings_btn)
        layout.addLayout(status_row)

        # Live mic level visualizer
        self.waveform = LiveWaveform()
        layout.addWidget(self.waveform)

        # Conversation log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.log_view, 1)

        # Talk-now button (only relevant in voice mode)
        self.talk_btn = QPushButton("🎤  Talk now")
        self.talk_btn.setEnabled(False)
        self.talk_btn.setMinimumHeight(40)
        layout.addWidget(self.talk_btn)

        self.setStatusBar(QStatusBar(self))
        self._refresh_status_bar()

        # Refresh usage every 5 s while running.
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(5000)
        self._usage_timer.timeout.connect(self._refresh_status_bar)
        self._usage_timer.start()

        # Conversation history button
        self.history_btn = QPushButton("📜  History")
        status_row.addWidget(self.history_btn)

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
        self.statusBar().showMessage(
            f"Provider: {provider}  |  Model: {model}  |  {usage_str}"
        )

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

    # --- signals from worker ---
    def _on_status(self, s: str):
        self.status_text.setText(STATUS_LABEL.get(s, s.capitalize()))
        color = STATUS_COLOR.get(s, "#888")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 22px;")
        # Light up the waveform only while actively listening.
        self.waveform.set_enabled_view(s == "listening")

    def _on_level(self, level: float):
        self.waveform.set_level(level)

    def _on_log(self, role: str, text: str):
        self._append(role, text)

    def _on_error(self, msg: str):
        self._append("error", msg)
        self._on_status("error")

    # --- helpers ---
    def _append(self, role: str, text: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        prefix_colors = {
            "you": "#3366cc",
            "ultron": "#FF6A00",
            "ultron": "#FF6A00",
            "reminder": "#cc9933",
            "system": "#888",
            "error": "#cc3333",
        }
        fmt.setForeground(QColor(prefix_colors.get(role, "#222")))
        fmt.setFontWeight(QFont.Bold)
        cursor.insertText(f"{role}: ", fmt)
        fmt2 = QTextCharFormat()
        fmt2.setForeground(QColor("#222"))
        cursor.insertText(text + "\n", fmt2)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    # --- close behavior ---
    def closeEvent(self, event):
        # Hide to tray instead of quitting if tray icon is visible
        if hasattr(self, "_hide_on_close") and self._hide_on_close:
            event.ignore()
            self.hide()
        else:
            self.worker.stop()
            super().closeEvent(event)
