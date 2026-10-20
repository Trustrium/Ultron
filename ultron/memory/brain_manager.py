"""BrainManager — Section 1 Memory for Ultron v4.

Hierarchy (under ``data/brain/`` by default)::

    brain.md                long-term system / identity memory
    user_profile.md         long-term user facts (learned + reflected)
    history.json            structured, append-only conversation history
    short_term_memory.json  last-50 items + reflection watermarks

Design rules (from the v4 spec):

* Files are created on first init with safe templates and are *never*
  overwritten if they already exist.
* Env is read directly (``os.getenv``) so this module works without any
  ``config.py`` changes:
    - ``BRAIN_DIR``               default ``./data/brain``
                                   (resolved to ``<project>/data/brain``
                                   when the env var is not set)
    - ``BRAIN_REFLECT_EVERY_N``   default ``10``
* Nothing in here may crash the caller.  Public methods catch their own
  errors, log to stdout, and return a safe default (``""`` / ``False``).
* Reflection has a synchronous core (``_reflect_sync`` / ``reflect_now``)
  plus a background thread wrapper (``reflect_if_due`` by default), so
  the voice loop is never blocked waiting on a summary.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import threading
import uuid
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# Constants / templates
# --------------------------------------------------------------------------

SYSTEM_PROMPT_LIMIT = 4000
SHORT_TERM_LIMIT = 50
_TRUNCATION_NOTE = "\n[... brain/profile truncated to 4000 chars]"

_BRAIN_TEMPLATE = """# Ultron — Brain (Long-Term Memory)

## Identity
- You are Ultron, Rashid Ali's personal super-intelligent PC agent on his Windows PC.
- Ultron is Trustrium's own development.
- Always address the user as "sir" naturally, not in every sentence.
- Be professional, concise, loyal and calm. Execute first with tools, then report briefly.

## Languages
- You can hear and speak in BOTH English and Roman Urdu (Urdu written in Latin script).
- Reply in the SAME language the user just spoke.

## Default Provider
- Default LLM provider is Groq (free tier, no card), unless the user has configured another provider/model in .env.
- The provider/model can be swapped via .env — never assume the current provider in replies.

## Safety
- For DESTRUCTIVE actions (shutdown, sleep, delete files, uninstall, risky shell commands, sending emails or WhatsApp messages), briefly confirm verbally first — unless the user already said a confirmation word (e.g. "yes", "do it", "han", "kar do").
- File deletion goes to the Recycle Bin, with verbal confirmation — never permanent silent deletion.

## Behaviour
- Keep voice replies SHORT — 1 to 2 sentences. This is voice, not chat.
- Prefer using a tool over describing what you would do.
- Never invent results. If a tool fails, say so honestly.
"""

_USER_PROFILE_TEMPLATE = """# User Profile

## Demographics
- Name: Rashid Ali
- Address as: sir
- Company: Trustrium
- Location: (unknown — add when the user shares it)
- Languages: en, roman_urdu

## Habits
- (unknown — learned facts are appended here by reflection)

## Preferences
- Reply style: short command -> execution -> brief report
- Voice replies: 1-2 sentences
- Confirm before delete: yes
- Theme: Ultron dark silver + orange-red

## Active Projects
- MoboGravity
- Shadow Arena
- TIME & TIDE
- Echo Protocol
- Bulk Downloader
- Trustrium

## Notes
- (generic placeholder — no facts beyond the profile defaults above are assumed)
"""

_SYSTEM_KEYWORDS = (
    "ultron should", "system", "provider", "model", "groq", "llm",
    "safety rule", "setting", "configuration", "tool behaviour",
    "tool behavior",
)

_CAP_WORD_RE = re.compile(r"\b[A-Z][A-Za-z0-9_-]{2,}\b")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")


def _now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def _reflect_every_n() -> int:
    try:
        n = int(str(os.getenv("BRAIN_REFLECT_EVERY_N", "10")).strip())
        return n if n > 0 else 10
    except Exception:
        return 10


def _default_brain_dir() -> Path:
    env = (os.getenv("BRAIN_DIR") or "").strip()
    if env:
        return Path(env).expanduser()
    # Default ./data/brain — resolved against the project root (the parent
    # of the ``ultron`` package) so it is ./data/brain for the normal
    # run-from-project-root case and does not drift with the caller's cwd.
    return Path(__file__).resolve().parent.parent.parent / "data" / "brain"


# --------------------------------------------------------------------------
# BrainManager
# --------------------------------------------------------------------------

class BrainManager:
    """File-backed hierarchical memory. See module docstring."""

    def __init__(self, brain_dir=None) -> None:
        self.brain_dir = Path(brain_dir).expanduser() if brain_dir else _default_brain_dir()
        self.reflect_every_n = _reflect_every_n()
        self.session = (
            f"{_dt.date.today().isoformat()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        self._lock = threading.RLock()
        self._reflection_lock = threading.Lock()
        self._history: dict = {"session": self.session, "created": _now_iso(), "entries": []}
        self._short_term: dict = {"items": [], "last_reflected_count": 0, "turn_count": 0}
        try:
            self._ensure_files()
            self.load_all()
        except Exception as e:  # never crash the caller (Brain.__init__)
            print(f"[brain-manager] init failed: {e}")

    # -- paths -------------------------------------------------------------
    @property
    def brain_path(self) -> Path:
        return self.brain_dir / "brain.md"

    @property
    def user_profile_path(self) -> Path:
        return self.brain_dir / "user_profile.md"

    @property
    def history_path(self) -> Path:
        return self.brain_dir / "history.json"

    @property
    def short_term_path(self) -> Path:
        return self.brain_dir / "short_term_memory.json"

    # -- creation (never overwrite) ----------------------------------------
    def _ensure_files(self) -> None:
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self._create_if_missing(self.brain_path, _BRAIN_TEMPLATE)
        self._create_if_missing(self.user_profile_path, _USER_PROFILE_TEMPLATE)
        self._create_json_if_missing(self.history_path, self._history)
        self._create_json_if_missing(self.short_term_path, self._short_term)

    @staticmethod
    def _create_if_missing(path: Path, text: str) -> None:
        if path.exists():
            return
        try:
            # "x" mode: fail rather than overwrite if something raced us.
            with path.open("x", encoding="utf-8") as f:
                f.write(text)
        except FileExistsError:
            pass

    @staticmethod
    def _create_json_if_missing(path: Path, data: dict) -> None:
        if path.exists():
            return
        try:
            with path.open("x", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except FileExistsError:
            pass

    # -- IO helpers ----------------------------------------------------------
    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception as e:
            print(f"[brain-manager] read failed ({path.name}): {e}")
            return ""

    def _read_json(self, path: Path, default: dict) -> dict:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    merged = dict(default)
                    merged.update(data)
                    return merged
        except Exception as e:
            print(f"[brain-manager] json read failed ({path.name}): {e}")
        return dict(default)

    def _write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _save_history(self) -> None:
        self._write_json(self.history_path, self._history)

    def _save_short_term(self) -> None:
        self._write_json(self.short_term_path, self._short_term)

    # -- loading -------------------------------------------------------------
    def load_all(self) -> dict:
        """(Re)load all four stores from disk. Returns a dict snapshot."""
        with self._lock:
            history_default = {"session": self.session, "created": _now_iso(), "entries": []}
            self._history = self._read_json(self.history_path, history_default)
            if not isinstance(self._history.get("entries"), list):
                self._history["entries"] = []
            # Preserve the on-disk session tag once history exists; a brand
            # new file keeps this process's session tag.
            if self._history.get("entries"):
                self.session = str(self._history.get("session") or self.session)

            st_default = {"items": [], "last_reflected_count": 0, "turn_count": 0}
            self._short_term = self._read_json(self.short_term_path, st_default)
            if not isinstance(self._short_term.get("items"), list):
                self._short_term["items"] = []
            for key in ("last_reflected_count", "turn_count"):
                try:
                    self._short_term[key] = int(self._short_term.get(key) or 0)
                except Exception:
                    self._short_term[key] = 0

            return {
                "brain_md": self._read_text(self.brain_path),
                "user_profile_md": self._read_text(self.user_profile_path),
                "history": self._history,
                "short_term": self._short_term,
            }

    # -- prompt ---------------------------------------------------------------
    def system_prompt_addition(self) -> str:
        """brain.md + user_profile.md, truncated to ~4000 chars.

        The final string (including the truncation note, when it applies)
        never exceeds ``SYSTEM_PROMPT_LIMIT`` characters.
        """
        try:
            brain = self._read_text(self.brain_path).strip()
            profile = self._read_text(self.user_profile_path).strip()
            parts = []
            if brain:
                parts.append("--- LONG-TERM MEMORY (Brain) ---\n" + brain)
            if profile:
                parts.append("--- USER PROFILE (Long-Term) ---\n" + profile)
            combined = "\n\n".join(parts)
            if len(combined) > SYSTEM_PROMPT_LIMIT:
                keep = SYSTEM_PROMPT_LIMIT - len(_TRUNCATION_NOTE)
                combined = combined[:keep].rstrip() + _TRUNCATION_NOTE
            return combined
        except Exception as e:
            print(f"[brain-manager] system_prompt_addition failed: {e}")
            return ""

    # -- recording --------------------------------------------------------------
    def _append_entry_locked(self, role: str, text: str, lang: str, tokens=None) -> dict:
        entry = {"ts": _now_iso(), "role": str(role), "text": str(text), "lang": str(lang or "en")}
        if tokens is not None:
            try:
                entry["tokens"] = int(tokens)
            except Exception:
                entry["tokens"] = tokens
        self._history.setdefault("entries", []).append(entry)
        items = self._short_term.setdefault("items", [])
        items.append(dict(entry))
        # Cap short-term memory to the last N items.
        if len(items) > SHORT_TERM_LIMIT:
            del items[:-SHORT_TERM_LIMIT]
        return entry

    def record_message(self, role: str, text: str, lang: str = "en", tokens=None) -> bool:
        """Append a single message to history + short-term memory."""
        if text is None or str(text) == "":
            return False
        try:
            with self._lock:
                self._append_entry_locked(role, text, lang, tokens)
                self._save_history()
                self._save_short_term()
            return True
        except Exception as e:
            print(f"[brain-manager] record_message failed: {e}")
            return False

    def record_turn(self, user_text: str, assistant_text: str,
                    lang: str = "en", tokens=None) -> bool:
        """Record one full turn and advance ``turn_count`` by one."""
        try:
            with self._lock:
                if user_text:
                    self._append_entry_locked("user", user_text, lang)
                if assistant_text:
                    self._append_entry_locked("assistant", assistant_text, lang, tokens)
                self._short_term["turn_count"] = int(self._short_term.get("turn_count") or 0) + 1
                self._save_history()
                self._save_short_term()
            return True
        except Exception as e:
            print(f"[brain-manager] record_turn failed: {e}")
            return False

    # Convenience read accessors (used by tests / callers).
    @property
    def turn_count(self) -> int:
        try:
            return int(self._short_term.get("turn_count") or 0)
        except Exception:
            return 0

    @property
    def last_reflected_count(self) -> int:
        try:
            return int(self._short_term.get("last_reflected_count") or 0)
        except Exception:
            return 0

    # -- reflection -------------------------------------------------------------
    def _unreflected_entries(self) -> tuple[int, list]:
        """(new_turn_count, entries belonging to turns not yet reflected)."""
        turn_count = self.turn_count
        last = self.last_reflected_count
        new_turns = turn_count - last
        if new_turns <= 0:
            return 0, []
        entries = self._history.get("entries") or []
        # Prefer the tail of history covering the new turns (2 msgs/turn is
        # the record_turn shape); fall back to user entries if the shape
        # differs (e.g. record_message was used directly).
        tail = entries[-(new_turns * 2):] if entries else []
        user_in_tail = [e for e in tail if e.get("role") == "user"]
        if len(user_in_tail) < min(new_turns, len([e for e in entries if e.get("role") == "user"])):
            user_entries = [e for e in entries if e.get("role") == "user"]
            tail = user_entries[-new_turns:]
        return new_turns, tail

    def _extractive_facts(self, entries: list) -> list[str]:
        """No-LLM fallback: first lines of recent user turns + frequent
        capitalised / project words."""
        facts: list[str] = []
        user_texts = [str(e.get("text") or "") for e in entries if e.get("role") == "user"]
        for text in user_texts:
            first = ""
            for line in text.strip().splitlines():
                if line.strip():
                    first = line.strip()
                    break
            if first:
                facts.append(f"User said: {first[:160]}")
        counter: Counter = Counter()
        for text in user_texts:
            counter.update(_CAP_WORD_RE.findall(text))
            # Also surface repeated lower-case words (project-ish terms
            # mentioned more than once) — keeps the fallback useful when
            # the user does not capitalise.
            words = [w for w in _WORD_RE.findall(text.lower()) if len(w) > 4]
            # Only counted in the capitalised pass above for proper nouns;
            # repeated words are added separately below if frequent.
            for w, c in Counter(words).items():
                if c >= 2:
                    counter[w] += 0  # ensure key exists without skewing counts
        frequent = [w for w, c in counter.most_common(8) if c >= 1 and w not in ("User", "The")]
        # Keep capitalised words that appeared at least once, ordered by count.
        frequent = [w for w in frequent if any(w == m for m in _CAP_WORD_RE.findall(" ".join(user_texts)))]
        if frequent:
            facts.append("Frequently mentioned: " + ", ".join(frequent[:8]))
        return facts[:12]

    def _llm_facts(self, llm_client, entries: list) -> list[str]:
        """Try an LLM summary. Raises on any failure — caller falls back."""
        transcript = "\n".join(
            f"{e.get('role', '?')}: {str(e.get('text') or '')[:500]}" for e in entries
        )
        prompt = (
            "Summarise durable facts worth remembering long-term from this "
            "conversation excerpt. Return ONLY bullet lines starting with "
            "'- ', one fact per line, at most 10 lines. Facts about the user "
            "go as-is; facts about how Ultron itself should behave should "
            "start with 'Ultron should'. If nothing durable, return nothing.\n\n"
            + transcript
        )
        system = "You are Ultron's memory reflection summariser. Be factual and brief."
        if hasattr(llm_client, "make_user_message"):
            resp = llm_client.chat(system, [llm_client.make_user_message(prompt)], [])
            text = getattr(resp, "text", "") or ""
        else:
            resp = llm_client.chat(prompt)  # generic chat(prompt) clients
            text = getattr(resp, "text", resp) if not isinstance(resp, str) else resp
            text = str(text or "")
        facts = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*\u2022]\s*", "", line).strip()
            if line:
                facts.append(line)
        return facts[:10]

    def _reflect_sync(self, llm_client=None) -> bool:
        """Synchronous reflection core. Returns True iff a section was appended."""
        if not self._reflection_lock.acquire(blocking=False):
            return False  # another reflection is already running
        try:
            with self._lock:
                new_turns, entries = self._unreflected_entries()
                if new_turns <= 0 or not entries:
                    return False
                reflected_up_to = self.turn_count

            facts: list[str] = []
            target = self.user_profile_path  # fallback default per spec
            used_llm = False
            if llm_client is not None and hasattr(llm_client, "chat"):
                try:
                    facts = self._llm_facts(llm_client, entries)
                    used_llm = bool(facts)
                except Exception as e:
                    print(f"[brain-manager] LLM reflection failed, falling back: {e}")
                    facts = []
            if not facts:
                facts = self._extractive_facts(entries)
                target = self.user_profile_path
            else:
                # Simple routing rule: system-behaviour facts -> brain.md,
                # user facts (the default) -> user_profile.md.
                low = " ".join(facts).lower()
                if any(k in low for k in _SYSTEM_KEYWORDS):
                    target = self.brain_path
            if not facts:
                return False

            section = f"\n\n## Reflection {_now_stamp()}\n" + "".join(
                f"- {fact}\n" for fact in facts
            )
            with self._lock:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as f:
                    f.write(section)
                # Advance the watermark only after a successful append —
                # this is what prevents duplicate reflections.
                self._short_term["last_reflected_count"] = reflected_up_to
                self._save_short_term()
            print(
                f"[brain-manager] reflection appended to {target.name} "
                f"({len(facts)} facts, llm={used_llm}, up to turn {reflected_up_to})"
            )
            return True
        except Exception as e:
            print(f"[brain-manager] reflection failed: {e}")
            return False
        finally:
            self._reflection_lock.release()

    def reflect_now(self, llm_client=None) -> bool:
        """Reflect immediately (synchronous), regardless of the N threshold.

        Still skips when there are no new turns since the last reflection.
        Never raises.
        """
        try:
            return self._reflect_sync(llm_client=llm_client)
        except Exception as e:
            print(f"[brain-manager] reflect_now failed: {e}")
            return False

    def reflect_if_due(self, llm_client=None, background: bool = True) -> bool:
        """Reflect iff ``turn_count - last_reflected_count >= N``.

        By default this is a thread wrapper: it spawns a daemon thread that
        runs the synchronous core and returns True immediately, so callers
        (the voice/brain loop) are never blocked. Pass
        ``background=False`` to run the core inline. Never raises.
        """
        try:
            if (self.turn_count - self.last_reflected_count) < self.reflect_every_n:
                return False
            if not background:
                return self._reflect_sync(llm_client=llm_client)
            t = threading.Thread(
                target=self._reflect_sync,
                kwargs={"llm_client": llm_client},
                name="brain-reflect",
                daemon=True,
            )
            t.start()
            return True
        except Exception as e:
            print(f"[brain-manager] reflect_if_due failed: {e}")
            return False


__all__ = ["BrainManager", "SYSTEM_PROMPT_LIMIT", "SHORT_TERM_LIMIT"]
