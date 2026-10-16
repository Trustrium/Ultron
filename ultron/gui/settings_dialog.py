"""Settings dialog — pick provider, paste API key, pick a voice, preview it, save."""
from __future__ import annotations
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QLabel, QHBoxLayout, QDialogButtonBox, QMessageBox,
    QGroupBox, QTabWidget, QWidget, QCheckBox, QFileDialog,
)

from ..settings import load as load_settings, save as save_settings, PROVIDER_INFO, get_models_for
from ..voice.presets import ENGLISH_PRESETS, TAMIL_PRESETS, find_preset
from ..personality import PERSONALITY_PRESETS


class _TestWorker(QThread):
    finished_with = Signal(bool, str)

    def __init__(self, provider: str, api_key: str, model: str, base_url: str):
        super().__init__()
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def run(self):
        from ..llm.test_provider import test_provider
        ok, msg = test_provider(self.provider, self.api_key, self.model, self.base_url)
        self.finished_with.emit(ok, msg)


class _PreviewWorker(QThread):
    finished_with = Signal(str)   # path to mp3, or "" on failure

    def __init__(self, preset: dict):
        super().__init__()
        self.preset = preset

    def run(self):
        from ..voice.speak import preview_voice
        path = preview_voice(self.preset)
        self.finished_with.emit(path or "")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ultron — Settings")
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)
        self._test_thread: _TestWorker | None = None
        self._preview_thread: _PreviewWorker | None = None

        s = load_settings()
        outer = QVBoxLayout(self)

        title = QLabel("⚙️  Ultron Settings")
        f = QFont(); f.setPointSize(14); f.setBold(True); title.setFont(f)
        outer.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_brain_tab(s), "🧠  Brain")
        tabs.addTab(self._build_voice_tab(s), "🔊  Voice")
        tabs.addTab(self._build_advanced_tab(s), "⚙️  Advanced")
        outer.addWidget(tabs, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

        self._on_provider_changed()  # fill key hint

    # ===== BRAIN TAB =====
    def _build_brain_tab(self, s: dict) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "Pick an LLM provider and paste your API key. "
            "Most providers (Groq, Gemini) have a <b>free tier</b> — no credit card needed."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()

        self.provider_combo = QComboBox()
        for info in PROVIDER_INFO:
            self.provider_combo.addItem(info["label"], userData=info["id"])
        for idx in range(self.provider_combo.count()):
            if self.provider_combo.itemData(idx) == s.get("llm_provider"):
                self.provider_combo.setCurrentIndex(idx); break
        form.addRow("Provider:", self.provider_combo)

        self.key_edit = QLineEdit(s.get("llm_api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API key:", self.key_edit)

        self.key_link = QLabel()
        self.key_link.setOpenExternalLinks(True)
        self.key_link.setTextFormat(Qt.RichText)
        form.addRow("", self.key_link)

        # Model combo — editable so user can type a custom name too.
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.NoInsert)
        self.model_combo.setMinimumContentsLength(40)
        form.addRow("Model:", self.model_combo)

        self.url_edit = QLineEdit(s.get("llm_base_url", ""))
        self.url_edit.setPlaceholderText("(leave blank for provider default)")
        form.addRow("Base URL:", self.url_edit)

        layout.addLayout(form)

        # Test row
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("🧪  Test connection")
        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status, 1)
        layout.addLayout(test_row)

        # Fallback provider (resilience)
        fb_group = QGroupBox("Fallback provider (optional — used if the primary rate-limits)")
        fb_form = QFormLayout(fb_group)
        self.fb_provider_combo = QComboBox()
        self.fb_provider_combo.addItem("(none)", userData="")
        for info in PROVIDER_INFO:
            self.fb_provider_combo.addItem(info["label"], userData=info["id"])
        cur_fb = s.get("llm_fallback_provider", "")
        for i in range(self.fb_provider_combo.count()):
            if self.fb_provider_combo.itemData(i) == cur_fb:
                self.fb_provider_combo.setCurrentIndex(i); break
        fb_form.addRow("Fallback provider:", self.fb_provider_combo)
        self.fb_key_edit = QLineEdit(s.get("llm_fallback_api_key", ""))
        self.fb_key_edit.setEchoMode(QLineEdit.Password)
        self.fb_key_edit.setPlaceholderText("Fallback API key (e.g. a free Gemini key)")
        fb_form.addRow("Fallback key:", self.fb_key_edit)
        self.fb_model_edit = QLineEdit(s.get("llm_fallback_model", ""))
        self.fb_model_edit.setPlaceholderText("(leave blank for provider default)")
        fb_form.addRow("Fallback model:", self.fb_model_edit)
        fb_hint = QLabel("<small>Tip: primary <b>Groq</b> + fallback <b>Gemini</b> (both free) "
                         "means Ultron never goes down when one hits its daily limit. "
                         "Must be the same API family as the primary.</small>")
        fb_hint.setWordWrap(True); fb_hint.setStyleSheet("color:#666;")
        fb_form.addRow(fb_hint)
        layout.addWidget(fb_group)

        layout.addStretch(1)

        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.test_btn.clicked.connect(self._on_test)

        # Initialize model dropdown for the currently selected provider
        self._refresh_model_combo(initial_model=s.get("llm_model", ""))

        return page

    # ===== VOICE TAB =====
    def _build_voice_tab(self, s: dict) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "Pick how Ultron sounds. The default is a deep British voice — "
            "similar to Marvel's <b>J.A.R.V.I.S.</b>"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # English voice
        en_group = QGroupBox("English voice")
        en_layout = QVBoxLayout(en_group)

        en_row = QHBoxLayout()
        self.en_voice_combo = QComboBox()
        for p in ENGLISH_PRESETS:
            self.en_voice_combo.addItem(p["label"], userData=p["id"])
        cur_en = find_preset(ENGLISH_PRESETS, s.get("tts_voice_english", "ultron"))
        for i in range(self.en_voice_combo.count()):
            if self.en_voice_combo.itemData(i) == cur_en["id"]:
                self.en_voice_combo.setCurrentIndex(i); break
        self.en_preview_btn = QPushButton("▶  Preview")
        en_row.addWidget(self.en_voice_combo, 1)
        en_row.addWidget(self.en_preview_btn)
        en_layout.addLayout(en_row)

        self.en_description = QLabel(cur_en.get("description", ""))
        self.en_description.setWordWrap(True)
        self.en_description.setStyleSheet("color: #666; font-style: italic;")
        en_layout.addWidget(self.en_description)
        layout.addWidget(en_group)

        # Tamil voice
        ta_group = QGroupBox("Roman Urdu voice (legacy Tamil controls kept for compat)")
        ta_layout = QVBoxLayout(ta_group)

        ta_row = QHBoxLayout()
        self.ta_voice_combo = QComboBox()
        for p in TAMIL_PRESETS:
            self.ta_voice_combo.addItem(p["label"], userData=p["id"])
        cur_ta = find_preset(TAMIL_PRESETS, s.get("tts_voice_tamil", "tamil_male"))
        for i in range(self.ta_voice_combo.count()):
            if self.ta_voice_combo.itemData(i) == cur_ta["id"]:
                self.ta_voice_combo.setCurrentIndex(i); break
        self.ta_preview_btn = QPushButton("▶  Preview")
        ta_row.addWidget(self.ta_voice_combo, 1)
        ta_row.addWidget(self.ta_preview_btn)
        ta_layout.addLayout(ta_row)

        self.ta_description = QLabel(cur_ta.get("description", ""))
        self.ta_description.setWordWrap(True)
        self.ta_description.setStyleSheet("color: #666; font-style: italic;")
        ta_layout.addWidget(self.ta_description)
        layout.addWidget(ta_group)

        layout.addStretch(1)

        self.en_voice_combo.currentIndexChanged.connect(
            lambda: self._update_voice_desc(self.en_voice_combo, ENGLISH_PRESETS, self.en_description)
        )
        self.ta_voice_combo.currentIndexChanged.connect(
            lambda: self._update_voice_desc(self.ta_voice_combo, TAMIL_PRESETS, self.ta_description)
        )
        self.en_preview_btn.clicked.connect(lambda: self._preview(self.en_voice_combo, ENGLISH_PRESETS))
        self.ta_preview_btn.clicked.connect(lambda: self._preview(self.ta_voice_combo, TAMIL_PRESETS))

        return page

    # ===== ADVANCED TAB =====
    def _build_advanced_tab(self, s: dict) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # System behavior group
        sys_group = QGroupBox("System behavior")
        sys_layout = QFormLayout(sys_group)

        self.autostart_check = QCheckBox("Start Ultron automatically when Windows boots")
        self.autostart_check.setChecked(bool(s.get("auto_start_on_boot", False)))
        sys_layout.addRow(self.autostart_check)

        self.ptt_check = QCheckBox("Enable push-to-talk hotkey")
        self.ptt_check.setChecked(bool(s.get("ptt_enabled", True)))
        sys_layout.addRow(self.ptt_check)

        self.ptt_edit = QLineEdit(s.get("ptt_hotkey", "ctrl+alt+j"))
        self.ptt_edit.setPlaceholderText("e.g. ctrl+alt+j  or  ctrl+shift+space")
        sys_layout.addRow("Hotkey:", self.ptt_edit)

        self.routing_check = QCheckBox("Smart tool routing (faster + fewer tokens per request)")
        self.routing_check.setChecked(bool(s.get("tool_routing", True)))
        sys_layout.addRow(self.routing_check)

        layout.addWidget(sys_group)

        # Personality + proactive
        pers_group = QGroupBox("Personality + proactive heads-ups")
        pform = QFormLayout(pers_group)
        self.personality_combo = QComboBox()
        for pid, info in PERSONALITY_PRESETS.items():
            self.personality_combo.addItem(info["label"], userData=pid)
        cur_pers = s.get("personality", "ultron")
        for i in range(self.personality_combo.count()):
            if self.personality_combo.itemData(i) == cur_pers:
                self.personality_combo.setCurrentIndex(i); break
        pform.addRow("Personality:", self.personality_combo)
        self.proactive_edit = QLineEdit(str(s.get("proactive_lead_minutes", 10)))
        pform.addRow("Heads-up minutes before event:", self.proactive_edit)
        layout.addWidget(pers_group)

        # Voice loop timing
        timing_group = QGroupBox("Voice loop timing")
        form = QFormLayout(timing_group)
        self.whisper_combo = QComboBox()
        for w in ("tiny", "base", "small", "medium", "large-v3"):
            self.whisper_combo.addItem(w)
        cur = s.get("whisper_model", "tiny")
        if cur in {self.whisper_combo.itemText(i) for i in range(self.whisper_combo.count())}:
            self.whisper_combo.setCurrentText(cur)
        form.addRow("Speech recognition (Whisper):", self.whisper_combo)

        self.followup_edit = QLineEdit(str(s.get("followup_seconds", 8)))
        form.addRow("Follow-up seconds:", self.followup_edit)

        self.max_listen_edit = QLineEdit(str(s.get("max_listen_seconds", 15)))
        form.addRow("Max listen seconds:", self.max_listen_edit)
        layout.addWidget(timing_group)

        hint = QLabel(
            "<small><b>Whisper</b>: 'tiny' = fast (~0.3s), less accurate. 'small' = balanced. "
            "'large-v3' = best but ~3 GB and slower.<br>"
            "<b>Follow-up seconds</b>: after a reply, Ultron listens this many seconds for a "
            "continuation without needing the wake word again.<br>"
            "<b>Hotkey</b>: works system-wide. Examples: <i>ctrl+alt+j</i>, <i>ctrl+shift+space</i>, "
            "<i>f9</i>.</small>"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        # Backup / restore / update row
        maintenance_group = QGroupBox("Maintenance")
        maint = QHBoxLayout(maintenance_group)
        self.backup_btn = QPushButton("💾  Export backup...")
        self.restore_btn = QPushButton("↩  Restore backup...")
        self.update_btn = QPushButton("🔄  Check for updates")
        maint.addWidget(self.backup_btn)
        maint.addWidget(self.restore_btn)
        maint.addWidget(self.update_btn)
        layout.addWidget(maintenance_group)
        self.backup_btn.clicked.connect(self._do_export_backup)
        self.restore_btn.clicked.connect(self._do_import_backup)
        self.update_btn.clicked.connect(self._do_check_update)

        layout.addStretch(1)
        return page

    # ===== Maintenance handlers =====
    def _do_export_backup(self):
        from pathlib import Path
        from .. import backup as bak
        suggested = str(Path.home() / "Desktop" / "ultron_backup.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Save Ultron backup",
                                              suggested, "Zip archive (*.zip)")
        if not path:
            return
        try:
            out = bak.export_backup(path)
            QMessageBox.information(self, "Backup saved", f"Saved to:\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Backup failed", str(e))

    def _do_import_backup(self):
        from .. import backup as bak
        path, _ = QFileDialog.getOpenFileName(self, "Choose a Ultron backup",
                                              "", "Zip archive (*.zip)")
        if not path:
            return
        confirm = QMessageBox.question(
            self, "Restore backup",
            "This will overwrite your local settings, memory, reminders, notes, "
            "and conversation log with the backup contents.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            msg = bak.import_backup(path)
            QMessageBox.information(self, "Restore complete", msg)
        except Exception as e:
            QMessageBox.warning(self, "Restore failed", str(e))

    def _do_check_update(self):
        from .. import updater
        QMessageBox.information(self, "Update status", updater.update_summary())

    # ===== Helpers =====
    def _update_voice_desc(self, combo: QComboBox, presets: list[dict], label: QLabel):
        chosen_id = combo.currentData()
        for p in presets:
            if p["id"] == chosen_id:
                label.setText(p.get("description", ""))
                return

    def _preview(self, combo: QComboBox, presets: list[dict]):
        if self._preview_thread and self._preview_thread.isRunning():
            return
        chosen_id = combo.currentData()
        preset = next((p for p in presets if p["id"] == chosen_id), presets[0])
        combo.parent().setCursor(Qt.WaitCursor)
        self._preview_thread = _PreviewWorker(preset)
        self._preview_thread.finished_with.connect(self._on_preview_done)
        self._preview_thread.start()

    def _on_preview_done(self, path: str):
        self.setCursor(Qt.ArrowCursor)
        if not path:
            QMessageBox.warning(self, "Preview failed",
                                "Could not generate the voice sample (network or audio issue).")
            return
        from ..voice.speak import play_audio_file
        # Play in another thread so UI doesn't freeze.
        import threading
        threading.Thread(target=play_audio_file, args=(path,), daemon=True).start()

    def _current_provider_info(self) -> dict:
        pid = self.provider_combo.currentData()
        for info in PROVIDER_INFO:
            if info["id"] == pid:
                return info
        return {}

    def _on_provider_changed(self):
        info = self._current_provider_info()
        url = info.get("key_url", "")
        if url:
            self.key_link.setText(f'<a href="{url}">📋  Click here to get your API key</a>')
        else:
            self.key_link.setText("")
        prefix = info.get("key_prefix", "")
        if prefix:
            self.key_edit.setPlaceholderText(f"Paste your API key here (starts with {prefix})")
        else:
            self.key_edit.setPlaceholderText("Paste your API key here")
        # Reset model list to match the new provider.
        self._refresh_model_combo(initial_model="")

    def _refresh_model_combo(self, initial_model: str = "") -> None:
        """Populate the model dropdown for the currently selected provider."""
        provider = self.provider_combo.currentData() or ""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        # First entry: provider default (blank model_id, friendly label).
        self.model_combo.addItem("◆  Provider default", userData="")
        for model_id, label in get_models_for(provider):
            self.model_combo.addItem(label, userData=model_id)
        # Pick the saved model if present, else fall back to provider default.
        chosen_index = 0
        if initial_model:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == initial_model:
                    chosen_index = i
                    break
            else:
                # Not in catalog — show it as the editable text so user keeps their custom choice.
                self.model_combo.setEditText(initial_model)
                self.model_combo.blockSignals(False)
                return
        self.model_combo.setCurrentIndex(chosen_index)
        # When index = 0 (provider default), keep edit text empty.
        if chosen_index == 0:
            self.model_combo.setEditText("")
        self.model_combo.blockSignals(False)

    def _current_model(self) -> str:
        """Return the model id from the combo — either dropdown selection or typed text."""
        idx = self.model_combo.currentIndex()
        data = self.model_combo.itemData(idx) if idx >= 0 else None
        typed = self.model_combo.currentText().strip()
        # If user picked a real catalog item, prefer its model_id.
        if data:
            # If they typed something different from the label, treat as custom.
            return data if typed == self.model_combo.itemText(idx) else typed
        # Default-item or custom typed.
        return typed

    def _on_test(self):
        if self._test_thread and self._test_thread.isRunning():
            return
        info = self._current_provider_info()
        self.test_status.setText("⏳  Testing...")
        self.test_status.setStyleSheet("color: #666;")
        self.test_btn.setEnabled(False)
        self._test_thread = _TestWorker(
            provider=info["id"],
            api_key=self.key_edit.text().strip(),
            model=self._current_model(),
            base_url=self.url_edit.text().strip(),
        )
        self._test_thread.finished_with.connect(self._on_test_done)
        self._test_thread.start()

    def _on_test_done(self, ok: bool, msg: str):
        self.test_btn.setEnabled(True)
        if ok:
            self.test_status.setText(f"✅  {msg}")
            self.test_status.setStyleSheet("color: #2a8a2a;")
        else:
            self.test_status.setText(f"❌  {msg}")
            self.test_status.setStyleSheet("color: #b22222;")

    def _safe_int(self, text: str, default: int) -> int:
        try:
            return int(text)
        except ValueError:
            return default

    def _on_save(self):
        info = self._current_provider_info()
        save_settings({
            "llm_provider": info["id"],
            "llm_api_key": self.key_edit.text().strip(),
            "llm_model": self._current_model(),
            "llm_base_url": self.url_edit.text().strip(),
            "tts_voice_english": self.en_voice_combo.currentData(),
            "tts_voice_tamil": self.ta_voice_combo.currentData(),
            "whisper_model": self.whisper_combo.currentText(),
            "followup_seconds": self._safe_int(self.followup_edit.text(), 8),
            "max_listen_seconds": self._safe_int(self.max_listen_edit.text(), 15),
            "auto_start_on_boot": self.autostart_check.isChecked(),
            "ptt_enabled": self.ptt_check.isChecked(),
            "ptt_hotkey": self.ptt_edit.text().strip() or "ctrl+alt+j",
            "personality": self.personality_combo.currentData() or "ultron",
            "proactive_lead_minutes": self._safe_int(self.proactive_edit.text(), 10),
            "llm_fallback_provider": self.fb_provider_combo.currentData() or "",
            "llm_fallback_api_key": self.fb_key_edit.text().strip(),
            "llm_fallback_model": self.fb_model_edit.text().strip(),
            "tool_routing": self.routing_check.isChecked(),
        })
        # Apply auto-start immediately so user sees it work.
        try:
            from .. import autostart
            autostart.sync_with(self.autostart_check.isChecked())
        except Exception:
            pass
        QMessageBox.information(
            self, "Saved",
            "Settings saved.\n\nIf Ultron is currently running, click <b>Stop</b> then <b>Start</b> "
            "to apply the new voice + model."
        )
        self.accept()
