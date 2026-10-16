"""Conversation history viewer — reads data/conversation.log with filter + search."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QTextEdit,
    QComboBox, QLabel,
)

from ..config import CONVERSATION_LOG


ROLE_COLORS = {
    "you": "#3366cc",
    "user": "#3366cc",
    "ultron": "#2a8a2a",
    "reminder": "#cc9933",
    "system": "#888",
    "error": "#cc3333",
}


class ConversationViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ultron — Conversation history")
        self.resize(820, 560)

        root = QVBoxLayout(self)

        title = QLabel("📜  Conversation history")
        f = QFont(); f.setBold(True); f.setPointSize(13); title.setFont(f)
        root.addWidget(title)

        # Filter row
        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search text...")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["all roles", "you", "ultron", "reminder", "system"])
        self.refresh_btn = QPushButton("🔄  Reload")
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.role_combo)
        filter_row.addWidget(self.refresh_btn)
        root.addLayout(filter_row)

        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(QFont("Segoe UI", 10))
        root.addWidget(self.view, 1)

        bottom_row = QHBoxLayout()
        self.count_label = QLabel("")
        bottom_row.addWidget(self.count_label, 1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        root.addLayout(bottom_row)

        self.search_edit.textChanged.connect(self._render)
        self.role_combo.currentIndexChanged.connect(self._render)
        self.refresh_btn.clicked.connect(self._render)

        self._render()

    def _load_lines(self) -> list[str]:
        p = Path(CONVERSATION_LOG)
        if not p.exists():
            return []
        try:
            return p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            return [f"(error reading log: {e})"]

    def _render(self):
        query = self.search_edit.text().strip().lower()
        role_filter = self.role_combo.currentText()
        lines = self._load_lines()

        self.view.clear()
        cursor = self.view.textCursor()

        shown = 0
        for line in lines:
            # Line format: "YYYY-MM-DD HH:MM:SS ROLE[lang]: text"
            try:
                ts_end = 19
                ts = line[:ts_end]
                rest = line[ts_end:].lstrip()
                if ":" not in rest:
                    continue
                role_part, _, text = rest.partition(":")
                role = role_part.split("[")[0].strip().lower()
            except Exception:
                continue

            if role_filter != "all roles" and role != role_filter:
                continue
            if query and query not in line.lower():
                continue

            color = ROLE_COLORS.get(role, "#444")
            ts_fmt = QTextCharFormat(); ts_fmt.setForeground(QColor("#999"))
            cursor.insertText(ts + "  ", ts_fmt)
            role_fmt = QTextCharFormat(); role_fmt.setForeground(QColor(color)); role_fmt.setFontWeight(QFont.Bold)
            cursor.insertText(f"{role}: ", role_fmt)
            body_fmt = QTextCharFormat(); body_fmt.setForeground(QColor("#222"))
            cursor.insertText(text.strip() + "\n", body_fmt)
            shown += 1

        self.count_label.setText(f"Showing {shown} of {len(lines)} lines")
        # Scroll to bottom
        cursor.movePosition(QTextCursor.End)
        self.view.setTextCursor(cursor)
