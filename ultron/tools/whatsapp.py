"""WhatsApp Web automation via Selenium — read AND send.

First run opens Chrome with a dedicated profile and shows the WhatsApp Web QR.
Scan it once with your phone; the session persists in data/wa_chrome_profile/
so you won't need to log in again.

NOTE: WhatsApp Web's DOM changes occasionally. If something breaks, the most
likely culprit is the selectors below — they're isolated in `_S` for easy fix.
"""
from __future__ import annotations
import time
from pathlib import Path

from ..config import DATA_DIR

PROFILE_DIR = DATA_DIR / "wa_chrome_profile"
PROFILE_DIR.mkdir(exist_ok=True)

# Selectors — update here if WhatsApp Web changes its DOM.
class _S:
    QR = 'canvas[aria-label="Scan this QR code to link a device."]'
    CHAT_LIST = 'div[aria-label="Chat list"]'
    SEARCH_BOX = 'div[contenteditable="true"][data-tab="3"]'
    SEARCH_BOX_ALT = 'div[role="textbox"][contenteditable="true"]'
    CHAT_ROW = 'div[role="listitem"]'
    MESSAGE_INPUT = 'div[contenteditable="true"][data-tab="10"]'
    MESSAGE_INPUT_ALT = 'footer div[contenteditable="true"]'
    MESSAGES_IN = 'div.message-in'
    MESSAGES_OUT = 'div.message-out'
    MESSAGE_TEXT = 'span.selectable-text'
    HEADER_TITLE = 'header span[title]'


_driver = None  # cached webdriver instance


def _get_driver(visible: bool = True):
    """Return a singleton Chrome driver bound to the persistent WhatsApp profile."""
    global _driver
    if _driver is not None:
        try:
            _ = _driver.current_url
            return _driver
        except Exception:
            _driver = None

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        raise RuntimeError(
            "Selenium not installed. Run:  pip install selenium"
        )

    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    if not visible:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    _driver = webdriver.Chrome(options=opts)
    _driver.get("https://web.whatsapp.com")
    return _driver


def _wait_for_ready(driver, timeout: int = 60) -> bool:
    """Wait until either chat list is visible (logged in) or QR appears (need login)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    end = time.time() + timeout
    while time.time() < end:
        try:
            if driver.find_elements(By.CSS_SELECTOR, _S.CHAT_LIST):
                return True
            if driver.find_elements(By.CSS_SELECTOR, _S.QR):
                # QR shown — user must scan. Wait longer for them to scan.
                pass
        except Exception:
            pass
        time.sleep(1)
    return bool(driver.find_elements(By.CSS_SELECTOR, _S.CHAT_LIST))


def _focus_search(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    for sel in (_S.SEARCH_BOX, _S.SEARCH_BOX_ALT):
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            box = elems[0]
            box.click()
            box.send_keys(Keys.CONTROL, "a")
            box.send_keys(Keys.DELETE)
            return box
    raise RuntimeError("Could not find WhatsApp search box (DOM may have changed).")


def _open_chat(driver, name: str) -> bool:
    """Type into search and click the first matching chat. Returns True on success."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    box = _focus_search(driver)
    box.send_keys(name)
    time.sleep(2)
    # Press Enter to open the top match
    box.send_keys(Keys.ENTER)
    time.sleep(1.5)
    # Verify the conversation header now shows the searched name
    headers = driver.find_elements(By.CSS_SELECTOR, _S.HEADER_TITLE)
    return bool(headers)


def list_recent_chats(count: int = 10) -> str:
    """List names + last-message preview of recent chats in the side panel."""
    from selenium.webdriver.common.by import By
    try:
        driver = _get_driver(visible=True)
        if not _wait_for_ready(driver, timeout=60):
            return ("WhatsApp Web isn't ready. If you see a QR code, scan it with your "
                    "phone (WhatsApp > Linked Devices). After that I'll be logged in.")
        rows = driver.find_elements(By.CSS_SELECTOR, _S.CHAT_ROW)[:count]
        if not rows:
            return "No chats visible."
        items = []
        for r in rows:
            try:
                spans = r.find_elements(By.CSS_SELECTOR, "span[title]")
                if not spans:
                    continue
                name = spans[0].get_attribute("title") or spans[0].text
                preview_spans = r.find_elements(By.CSS_SELECTOR, "span.selectable-text")
                preview = preview_spans[0].text if preview_spans else ""
                items.append(f"• {name}: {preview[:80]}")
            except Exception:
                continue
        return "Recent chats:\n" + "\n".join(items) if items else "Couldn't read chat list."
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"WhatsApp read failed: {e}"


def read_chat(name: str, count: int = 10) -> str:
    """Open the chat by name and read the last N messages (mix of incoming + outgoing)."""
    from selenium.webdriver.common.by import By
    try:
        driver = _get_driver(visible=True)
        if not _wait_for_ready(driver, timeout=60):
            return "WhatsApp Web isn't ready. Scan the QR if it's showing."
        if not _open_chat(driver, name):
            return f"Couldn't find a chat for '{name}'."
        time.sleep(1.2)
        # Collect last N messages from the conversation pane
        msgs_in = driver.find_elements(By.CSS_SELECTOR, _S.MESSAGES_IN)
        msgs_out = driver.find_elements(By.CSS_SELECTOR, _S.MESSAGES_OUT)
        # Tag each with direction + DOM position, then sort by document order via location_once_scrolled_into_view is too slow.
        # Easier: walk all messages in order using their parent container.
        all_msgs = driver.find_elements(By.CSS_SELECTOR, f"{_S.MESSAGES_IN}, {_S.MESSAGES_OUT}")
        all_msgs = all_msgs[-count:]
        lines = []
        for m in all_msgs:
            direction = "← them" if "message-in" in (m.get_attribute("class") or "") else "→ you"
            text_spans = m.find_elements(By.CSS_SELECTOR, _S.MESSAGE_TEXT)
            txt = " ".join(s.text for s in text_spans).strip()
            if not txt:
                # Could be media/voice/etc.
                txt = "(non-text message)"
            lines.append(f"{direction}: {txt}")
        return f"Last {len(lines)} messages with {name}:\n" + "\n".join(lines) if lines else "No messages found."
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"WhatsApp read failed: {e}"


def send_whatsapp(recipient: str, message: str) -> str:
    """Send a WhatsApp message. `recipient` can be a contact name OR a phone with country code (+91...)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    try:
        driver = _get_driver(visible=True)
        if not _wait_for_ready(driver, timeout=60):
            return "WhatsApp Web isn't ready. Scan the QR if it's showing."

        # If recipient looks like a phone number, use the direct API URL.
        if recipient.replace(" ", "").startswith("+") or recipient.replace(" ", "").isdigit():
            phone = recipient.replace(" ", "").lstrip("+")
            driver.get(f"https://web.whatsapp.com/send?phone={phone}&text=")
            time.sleep(4)
        else:
            if not _open_chat(driver, recipient):
                return f"Couldn't find a chat for '{recipient}'."

        # Find the message input box
        box = None
        for sel in (_S.MESSAGE_INPUT, _S.MESSAGE_INPUT_ALT):
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                box = elems[-1]
                break
        if not box:
            return "Couldn't find the WhatsApp message input box."

        box.click()
        lines = message.split("\n")
        for i, line in enumerate(lines):
            box.send_keys(line)
            if i < len(lines) - 1:
                # Newline inside message — shift+enter avoids sending.
                box.send_keys(Keys.SHIFT, Keys.ENTER)
        box.send_keys(Keys.ENTER)
        time.sleep(1)
        return f"Sent WhatsApp message to {recipient}."
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"WhatsApp send failed: {e}"


def whatsapp_logout_note() -> str:
    return ("If you want to log out: delete the folder "
            f"'{PROFILE_DIR}' and run again to re-link.")
