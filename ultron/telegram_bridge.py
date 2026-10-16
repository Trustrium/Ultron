"""Telegram bridge — use Ultron from your phone via a Telegram bot.

Ultron keeps running on your PC (with all tools); you message its bot from your
phone and it replies. Uses long-polling (getUpdates) so no public server / port
forwarding is needed.

Setup (one time):
  1. In Telegram, message @BotFather -> /newbot -> get a bot TOKEN.
  2. Put it in .env / Settings: TELEGRAM_BOT_TOKEN=123456:ABC...
  3. (Recommended) Lock it to you: message your bot once, note the chat id it
     prints in the console, then set TELEGRAM_CHAT_ID=<that id>.

Run it: `python run.py telegram`  (or it auto-starts in the GUI if a token is set).
"""
from __future__ import annotations
import json
import threading
import urllib.parse
import urllib.request

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramBridge(threading.Thread):
    def __init__(self, token: str = "", allowed_chat_id: str = ""):
        super().__init__(daemon=True)
        self.token = (token or TELEGRAM_BOT_TOKEN).strip()
        self.allowed = (allowed_chat_id or TELEGRAM_CHAT_ID).strip()
        self._stop = threading.Event()
        self._offset = 0
        self._brain = None

    # --- Telegram API ---
    def _api(self, method: str, params: dict | None = None, timeout: int = 35) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = urllib.parse.urlencode(params or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _send(self, chat_id, text: str) -> None:
        # Telegram caps messages at 4096 chars.
        for chunk_start in range(0, len(text) or 1, 4000):
            try:
                self._api("sendMessage", {"chat_id": chat_id, "text": text[chunk_start:chunk_start+4000] or "(no reply)"}, timeout=15)
            except Exception as e:
                print(f"[telegram] send failed: {e}")
                return

    # --- main loop ---
    def run(self) -> None:
        if not self.token:
            print("[telegram] no TELEGRAM_BOT_TOKEN set — bridge not started.")
            return
        from .brain import Brain
        self._brain = Brain()
        print("[telegram] bridge online — message your bot from your phone.")
        while not self._stop.is_set():
            try:
                resp = self._api("getUpdates", {"offset": self._offset, "timeout": 30})
            except Exception as e:
                print(f"[telegram] poll error: {e}")
                self._stop.wait(5)
                continue
            for upd in resp.get("result", []):
                self._offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat = msg.get("chat", {})
                chat_id = str(chat.get("id", ""))
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                if self.allowed and chat_id != self.allowed:
                    print(f"[telegram] ignoring message from non-allowed chat {chat_id}")
                    continue
                if not self.allowed:
                    print(f"[telegram] tip: lock the bot to you with TELEGRAM_CHAT_ID={chat_id}")
                self._handle(chat_id, text)

    def _handle(self, chat_id, text: str) -> None:
        lang = "ta" if any("஀" <= c <= "௿" for c in text) else "en"
        try:
            reply = self._brain.think(text, lang=lang)
        except Exception as e:
            reply = f"Sorry, something broke: {e}"
        try:
            from .conversation_log import log as conv_log
            conv_log("you(tg)", text, lang)
            conv_log("ultron(tg)", reply, lang)
        except Exception:
            pass
        self._send(chat_id, reply)

    def stop(self) -> None:
        self._stop.set()


def run_bridge() -> int:
    """Blocking entry point for `python run.py telegram`."""
    from .config import TELEGRAM_BOT_TOKEN as tok
    if not tok:
        print("Set TELEGRAM_BOT_TOKEN in .env first (get one from @BotFather).")
        return 1
    b = TelegramBridge()
    b.start()
    print("Telegram bridge running. Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        b.stop()
        print("\n[telegram] stopped.")
    return 0
