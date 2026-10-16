"""First-run wizard — friendly welcome → settings → save → optional greeting."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from ..settings import load as load_settings
from .settings_dialog import SettingsDialog


WELCOME = """
<h2>👋  Welcome to Ultron</h2>

<p>A personal AI voice assistant for your PC — Tamil + English,
30+ tools (open apps, send WhatsApp, read email, set reminders, control music, ...).</p>

<p><b>Two things to do in the next screen:</b></p>
<ol>
  <li>Pick a free LLM provider (Groq is recommended — no credit card)</li>
  <li>Paste your API key and click <i>Test connection</i></li>
</ol>

<p>Voice is preset to a deep British <i>Ultron</i> tone by default — you can change it on the
<i>Voice</i> tab.</p>
"""


def needs_first_run() -> bool:
    s = load_settings()
    if s.get("llm_api_key"):
        return False
    from .. import config
    return not bool(config.LLM_API_KEY)


def run_first_run_wizard(parent=None) -> bool:
    """Returns True if user finished setup (saved settings), False if cancelled."""
    msg = QMessageBox(parent)
    msg.setWindowTitle("Welcome to Ultron")
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.setText(WELCOME)
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    msg.setDefaultButton(QMessageBox.Ok)
    if msg.exec() != QMessageBox.Ok:
        return False
    dlg = SettingsDialog(parent)
    saved = bool(dlg.exec())
    if saved:
        # Optional: speak a hello so user hears the new voice immediately.
        try:
            from ..voice.speak import speak
            import threading
            threading.Thread(
                target=lambda: speak("Good evening. I am Ultron. At your service.", "en"),
                daemon=True,
            ).start()
        except Exception:
            pass
    return saved
