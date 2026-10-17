"""Background worker thread that runs the voice loop without freezing the UI.

The worker emits Qt signals as Ultron's status changes; the GUI displays them.
"""
from __future__ import annotations
import traceback
import time
import threading

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


def _supports_kw(fn, name: str) -> bool:
    """True if fn accepts a ``name``= keyword (or **kwargs).

    Defensive probe only — never calls fn, never raises.
    """
    import inspect

    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if name in params:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


def _supports_on_token(fn) -> bool:
    """True if fn accepts an on_token= keyword (or **kwargs).

    Defensive probe only — never calls fn, never raises.
    """
    return _supports_kw(fn, "on_token")


class UltronWorker(QObject):
    """Wraps the voice loop in a worker thread.

    Signals:
        status_changed(str)        -- 'idle' / 'listening' / 'thinking' / 'speaking' / 'error'
        message_logged(str, str)   -- role, text   (role in: 'you', 'ultron', 'reminder', 'system')
        error(str)
    """

    status_changed = Signal(str)
    message_logged = Signal(str, str)
    error = Signal(str)
    level_changed = Signal(float)        # 0.0 - 1.0 mic level, ~30/s while listening
    # Streaming (defensive): emitted only when the backend exposes an
    # on_token callback. GUIs connect via getattr so older workers
    # without these signals keep working. The full reply still arrives
    # via message_logged, which replaces the live preview.
    token_stream_started = Signal()
    token_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._mode: str = "wake"

    # ------- public control -------
    def start(self, mode: str = "wake") -> None:
        if self._thread and self._thread.is_alive():
            return
        self._mode = mode
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        # Best-effort: the wake-word listener is blocking on mic reads, so we just
        # mark stop and let the worker exit between iterations.

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------- internals -------
    def _emit_status(self, s: str) -> None:
        try:
            self.status_changed.emit(s)
        except Exception:
            pass

    def _emit_log(self, role: str, text: str) -> None:
        try:
            self.message_logged.emit(role, text)
        except Exception:
            pass

    def _run(self) -> None:
        try:
            self._emit_status("starting")
            # Local imports so Qt thread doesn't pull heavy modules until started.
            from ultron.config import assert_keys, FOLLOWUP_SECONDS
            from ultron.voice.listen import (
                listen, record_until_silence, transcribe, SAMPLE_RATE, calibrate_silence,
            )
            from ultron.voice.speak import speak
            from ultron.brain import Brain
            from ultron.tools.reminders import ReminderScheduler
            from ultron.conversation_log import log as conv_log

            try:
                assert_keys()
            except RuntimeError as e:
                self.error.emit(str(e))
                self._emit_status("error")
                return

            self._emit_log("system", "Loading models...")
            brain = Brain()
            scheduler = ReminderScheduler(on_fire=lambda r: self._on_reminder(r, speak, conv_log))
            scheduler.start()

            from ultron.proactive import ProactiveScheduler
            proactive = ProactiveScheduler(
                on_prenotify=lambda r, mins: self._on_prenotify(r, mins, speak, conv_log)
            )
            proactive.start()

            from ultron.routines import RoutineScheduler
            routines = RoutineScheduler(
                on_result=lambda name, text: self._on_routine(name, text, speak, conv_log)
            )
            routines.start()

            from ultron.proactive_insights import InsightEngine
            insights = InsightEngine(
                on_insight=lambda text: self._on_insight(text, speak, conv_log)
            )
            insights.start()

            from ultron.watchers import WatchEngine
            watch = WatchEngine(
                on_alert=lambda text: self._on_insight(text, speak, conv_log)
            )
            watch.start()

            tele = None
            try:
                from ultron.config import TELEGRAM_BOT_TOKEN
                if TELEGRAM_BOT_TOKEN:
                    from ultron.telegram_bridge import TelegramBridge
                    tele = TelegramBridge()
                    tele.start()
                    self._emit_log("system", "Telegram bridge online — message your bot from your phone.")
            except Exception as e:
                print(f"[telegram] not started: {e}")

            try:
                if self._mode == "wake":
                    self._run_wake_mode(brain, speak, listen, record_until_silence,
                                        transcribe, calibrate_silence, conv_log, FOLLOWUP_SECONDS)
                elif self._mode == "voice":
                    self._run_voice_mode(brain, speak, record_until_silence,
                                         transcribe, calibrate_silence, conv_log)
                else:
                    self.error.emit(f"Unknown mode '{self._mode}'")
            finally:
                scheduler.stop()
                try:
                    proactive.stop()
                except Exception:
                    pass
                try:
                    routines.stop()
                except Exception:
                    pass
                try:
                    insights.stop()
                except Exception:
                    pass
                try:
                    watch.stop()
                except Exception:
                    pass
                try:
                    if tele:
                        tele.stop()
                except Exception:
                    pass
                self._emit_status("idle")
        except Exception as e:
            traceback.print_exc()
            self.error.emit(f"{type(e).__name__}: {e}")
            self._emit_status("error")

    def _on_insight(self, text: str, speak, conv_log) -> None:
        """A proactive suggestion Ultron surfaces on its own."""
        self._emit_log("ultron", text)
        conv_log("ultron", text, "en")
        try:
            from ..notify import toast
            toast("Ultron", text[:200], timeout=8)
        except Exception:
            pass
        try:
            speak(text, "en")
        except Exception:
            pass

    def _on_prenotify(self, reminder: dict, minutes: int, speak, conv_log) -> None:
        """Heads-up before a reminder fires."""
        text = reminder["text"]
        lang = reminder.get("lang", "en")
        msg_voice = (f"{minutes} நிமிட நினைவூட்டல்: {text}"
                     if lang.startswith("ta")
                     else f"Heads up — in {minutes} minute{'s' if minutes != 1 else ''}: {text}")
        self._emit_log("system", f"[heads-up in {minutes} min] {text}")
        conv_log("system", f"heads-up in {minutes}m: {text}", lang)
        try:
            from ..notify import toast
            toast("Ultron — upcoming", f"In {minutes} min: {text}", timeout=8)
        except Exception:
            pass
        try:
            speak(msg_voice, lang)
        except Exception as e:
            print(f"[prenotify] speak failed: {e}")

    def _on_routine(self, name: str, text: str, speak, conv_log) -> None:
        """A scheduled routine finished — announce + log its result."""
        self._emit_log("system", f"[routine '{name}'] {text}")
        conv_log("routine", f"{name}: {text}", "en")
        try:
            from ..notify import toast
            toast(f"Ultron routine: {name}", text[:200], timeout=10)
        except Exception:
            pass
        try:
            speak(text, "en")
        except Exception as e:
            print(f"[routine] speak failed: {e}")

    def _on_reminder(self, reminder: dict, speak, conv_log) -> None:
        text = reminder["text"]
        lang = reminder.get("lang", "en")
        prefix = "நினைவூட்டல்: " if lang.startswith("ta") else "Reminder: "
        self._emit_log("reminder", text)
        conv_log("reminder", text, lang)
        # Native Windows toast in addition to voice.
        try:
            from ..notify import toast
            toast("Ultron Reminder", text, timeout=10)
        except Exception as e:
            print(f"[reminder] toast failed: {e}")
        try:
            speak(prefix + text, lang)
        except Exception as e:
            print(f"[reminder] speak failed: {e}")

    def _process_turn(self, brain, text, lang, speak, conv_log) -> None:
        self._emit_log("you", text)
        conv_log("user", text, lang)
        # IMMEDIATE feedback: emit BEFORE brain.think() blocks on the LLM call,
        # so the UI never sits silent during the ~1-10s think. The on_status
        # callback below adds "Doing…" / "Replying…" lines as the turn proceeds.
        self._emit_status("thinking")
        self._emit_log("system", "Understanding…")
        # Streaming (defensive): if the backend exposes on_token / on_status,
        # forward partial tokens + status live; otherwise the full-reply path
        # below runs unchanged. Never crashes if streaming is absent.
        try:
            kwargs: dict = {}
            if _supports_on_token(brain.think):
                try:
                    self.token_stream_started.emit()
                except Exception:
                    pass

                def _on_token(token) -> None:
                    try:
                        self.token_changed.emit(str(token))
                    except Exception:
                        pass

                kwargs["on_token"] = _on_token
            if _supports_kw(brain.think, "on_status"):
                def _on_status(s: str) -> None:
                    if s == "doing":
                        self._emit_log("system", "Doing…")
                    elif s == "replying":
                        self._emit_log("system", "Replying…")

                kwargs["on_status"] = _on_status
            try:
                reply = brain.think(text, lang=lang, **kwargs)
            except TypeError as exc:
                # Only retry when the TypeError is actually about a callback
                # kwarg; a TypeError inside the backend must surface as the
                # turn error, not a double turn.
                if "on_token" in str(exc) or "on_status" in str(exc):
                    reply = brain.think(text, lang=lang)
                else:
                    raise
        except Exception as e:
            traceback.print_exc()
            reply = f"Sorry, something broke: {e}"
        self._emit_log("ultron", reply)
        conv_log("ultron", reply, lang)
        self._emit_status("speaking")
        try:
            speak(reply, lang)
        except Exception as e:
            self.error.emit(f"TTS failed: {e}")
        self._emit_status("idle")

    def _run_voice_mode(self, brain, speak, record_until_silence, transcribe,
                        calibrate_silence, conv_log) -> None:
        """Voice mode here ≈ tray-driven: each time the user invokes 'Talk now', we record once."""
        calibrate_silence()
        self._emit_log("system", "Voice mode ready. Use 'Talk now' from the tray to record.")
        # In tray mode, the worker waits for an external trigger via a flag.
        # For simplicity we expose `request_voice_turn`.
        # If no external trigger, we just loop check.
        while not self._stop.is_set():
            if getattr(self, "_voice_trigger", False):
                self._voice_trigger = False
                self._emit_status("listening")
                audio = record_until_silence()
                text, lang = transcribe(audio)
                if not text.strip():
                    self._emit_log("system", "(nothing heard)")
                    self._emit_status("idle")
                    continue
                self._process_turn(brain, text, lang, speak, conv_log)
            time.sleep(0.1)

    def request_voice_turn(self) -> None:
        """Trigger a single voice turn from voice-mode worker."""
        self._voice_trigger = True
        # Immediate feedback: status flips the moment the user taps Talk,
        # not up to a poll interval later (loop polls every 0.1s, but the
        # emit here makes it synchronous with the tap).
        self._emit_status("listening")

    def _run_wake_mode(self, brain, speak, listen, record_until_silence,
                       transcribe, calibrate_silence, conv_log, followup_seconds) -> None:
        from ultron.voice.wake import WakeWordListener

        try:
            wake = WakeWordListener()
        except Exception as e:
            self.error.emit(f"Wake-word failed to load: {e}")
            return

        calibrate_silence()
        self._emit_log("system", "Wake-word ready. Say 'Hey Ultron'.")
        speak("Good day, sir. Ultron online and at your service.", "en")

        try:
            while not self._stop.is_set():
                self._emit_status("idle")
                # wake.wait_for_wake() blocks until detection. Stop won't be checked
                # mid-block — user must close the app or trigger a hotkey to exit.
                wake.wait_for_wake()
                if self._stop.is_set():
                    break
                self._emit_status("listening")
                text, lang = listen()
                if not text:
                    speak("I didn't catch that.", "en")
                    continue
                from ultron.conversation import is_exit_phrase, farewell
                if is_exit_phrase(text):
                    speak(farewell(lang), lang); continue
                self._process_turn(brain, text, lang, speak, conv_log)

                # Natural conversation — keep going until done / two silences.
                misses = 0
                while not self._stop.is_set():
                    if not self._wait_for_voice(followup_seconds):
                        misses += 1
                        if misses >= 2:
                            break
                        continue
                    misses = 0
                    self._emit_status("listening")
                    audio = record_until_silence()
                    text, lang = transcribe(audio)
                    if not text.strip():
                        continue
                    if is_exit_phrase(text):
                        speak(farewell(lang), lang)
                        break
                    self._process_turn(brain, text, lang, speak, conv_log)
        finally:
            try:
                wake.close()
            except Exception:
                pass

    def _wait_for_voice(self, seconds: float) -> bool:
        from ultron.voice.listen import SAMPLE_RATE
        detected = {"v": False}
        deadline = time.time() + seconds

        def cb(indata, frames, time_info, status):
            rms = float(np.sqrt(np.mean(indata ** 2)))
            # Drive the waveform widget — clip + soft-scale for visual range.
            try:
                self.level_changed.emit(min(1.0, rms * 12))
            except Exception:
                pass
            if rms > 0.025:
                detected["v"] = True

        try:
            with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=cb, dtype="float32"):
                while time.time() < deadline and not detected["v"]:
                    sd.sleep(80)
        except Exception:
            return False
        finally:
            try:
                self.level_changed.emit(0.0)
            except Exception:
                pass
        return detected["v"]
