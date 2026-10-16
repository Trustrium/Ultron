"""Ultron entry point with three modes.

Usage:
    python run.py            # default: wake-word mode ("Hey Ultron")
    python run.py text       # text mode — type commands, no mic needed (BEST FOR TESTING)
    python run.py handsfree  # always-listening — just talk, no ENTER, no wake word
    python run.py voice      # press-ENTER-to-talk mode (good for testing mic + STT)
    python run.py wake       # explicit wake-word mode

Pipeline (voice/wake modes):
    activate -> record until silence -> Whisper STT -> Groq brain (with tools) -> Edge TTS
"""
from __future__ import annotations
import sys
import time
import traceback

import numpy as np
import sounddevice as sd

from ultron.config import assert_keys, FOLLOWUP_SECONDS
from ultron.voice.listen import (
    listen, record_until_silence, transcribe, SAMPLE_RATE, calibrate_silence,
)
from ultron.voice.speak import speak
from ultron.brain import Brain
from ultron.tools.reminders import ReminderScheduler
from ultron.conversation_log import log as conv_log


FOLLOWUP_VOICE_RMS = 0.025


def on_reminder_fire(reminder: dict) -> None:
    text = reminder["text"]
    lang = reminder.get("lang", "en")
    prefix = "Yaad-dihani: " if lang in ("roman_urdu", "ur") else ("Reminder: " if not lang.startswith("ta") else "Reminder: ")
    print(f"\n[REMINDER] {text}")
    conv_log("reminder", text, lang)
    try:
        speak(prefix + text, lang)
    except Exception as e:
        print(f"[reminder] speak failed: {e}")


def _wait_for_voice(seconds: float) -> bool:
    detected = {"v": False}
    deadline = time.time() + seconds

    def cb(indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata ** 2)))
        if rms > FOLLOWUP_VOICE_RMS:
            detected["v"] = True

    try:
        with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=cb, dtype="float32"):
            while time.time() < deadline and not detected["v"]:
                sd.sleep(80)
    except Exception as e:
        print(f"[followup] voice-detect error: {e}")
        return False
    return detected["v"]


def _process_user_turn(brain: Brain, text: str, lang: str, speak_reply: bool = True) -> None:
    print(f"[heard:{lang}] {text}")
    conv_log("user", text, lang)
    try:
        reply = brain.think(text, lang=lang)
    except Exception as e:
        traceback.print_exc()
        reply = f"Sorry, something broke: {e}"
    print(f"[reply:{lang}] {reply}")
    conv_log("ultron", reply, lang)
    if speak_reply:
        speak(reply, lang)


# ===== MODE: TEXT (no mic, type commands) =====

def run_text_mode(brain: Brain, speak_replies: bool) -> int:
    print("\n=== TEXT MODE ===")
    print("Type a command and press ENTER. Replies print in console" +
          (" and are spoken aloud." if speak_replies else "."))
    print("Type 'quit' or Ctrl+C to exit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[exit] bye.")
            return 0
        if not text:
            continue
        if text.lower() in {"quit", "exit", "bye"}:
            return 0
        # Language detection: Tamil unicode -> ta, Roman Urdu phrases -> roman_urdu, else en.
        try:
            from ultron.voice.roman_urdu import detect_roman_urdu as _detect_ru
        except Exception:
            _detect_ru = None
        if any("\u0b80" <= c <= "\u0bff" for c in text):
            lang = "ta"
        elif _detect_ru and _detect_ru(text):
            lang = "roman_urdu"
        else:
            lang = "en"
        _process_user_turn(brain, text, lang, speak_reply=speak_replies)


# ===== MODE: HANDS-FREE (always listening, no ENTER, no wake word) =====

def run_handsfree_mode(brain: Brain) -> int:
    """Continuous listening: just talk and Ultron responds. No ENTER, no wake word.

    Robustness:
      - Waits for the mic to actually pick up speech before recording, so silent
        15-second polls don't trigger phantom replies.
      - Drops common Whisper hallucinations on near-silence ("you", "thanks", ".").
      - Pauses briefly after speaking so the mic doesn't catch the TTS tail.
    """
    from ultron.conversation import is_exit_phrase, farewell

    HALLUCINATIONS = {"you", "thanks", "thank you", "thank you.", "ok", "okay",
                      "the", "uh", "um", "hmm", "."}

    def _has_real_speech(audio) -> bool:
        if audio.size == 0:
            return False
        return float(np.max(np.abs(audio))) >= 0.015   # peak gate above ambient

    def _is_hallucinated(text: str) -> bool:
        s = text.strip().lower().rstrip(".!?,")
        if len(s) < 4:
            return True
        return s in HALLUCINATIONS

    print("\n=== HANDS-FREE MODE (just talk — no ENTER, no wake word) ===")
    calibrate_silence()
    speak("Hands-free mode active, sir. Just talk to me whenever you like.", "en")
    time.sleep(0.4)   # let the TTS tail settle before opening the mic
    print("[listening] speak any time. Say 'that's all' to pause, Ctrl+C to quit.\n")

    while True:
        try:
            audio = record_until_silence()
            if not _has_real_speech(audio):
                continue                       # silence / nothing said
            text, lang = transcribe(audio)
            if not text.strip() or _is_hallucinated(text):
                continue                       # ignore Whisper noise-hallucinations
            print(f"[heard:{lang}] {text}")
            if is_exit_phrase(text):
                speak(farewell(lang), lang)
                time.sleep(0.4)
                continue
            _process_user_turn(brain, text, lang)
            time.sleep(0.4)                    # post-speak settle so we don't hear ourselves
        except (EOFError, KeyboardInterrupt):
            print("\n[exit] bye.")
            return 0


# ===== MODE: VOICE (press ENTER to talk, no wake word) =====

def run_voice_mode(brain: Brain) -> int:
    print("\n=== VOICE MODE (press ENTER to talk) ===")
    calibrate_silence()
    speak("Voice mode. Press enter and then talk.", "en")
    while True:
        try:
            input("\n[Press ENTER to start listening, Ctrl+C to quit] ")
        except (EOFError, KeyboardInterrupt):
            print("\n[exit] bye.")
            return 0
        print("Listening... speak now.")
        try:
            import winsound; winsound.Beep(900, 120)
        except Exception:
            pass
        audio = record_until_silence()
        text, lang = transcribe(audio)
        if not text.strip():
            print("(nothing heard)")
            speak("I didn't catch that.", "en")
            continue
        _process_user_turn(brain, text, lang)


# ===== MODE: WAKE (wake-word + voice) =====

def run_wake_mode(brain: Brain) -> int:
    from ultron.voice.wake import WakeWordListener
    print("\n=== WAKE MODE ===")
    try:
        wake = WakeWordListener()
    except Exception as e:
        print(f"[wake] Failed to start wake-word listener: {e}")
        print("Tip: try 'python run.py voice' (press-ENTER mode) to test the rest of the pipeline.")
        return 1

    calibrate_silence()
    speak("Good day, sir. Ultron online and at your service.", "en")

    try:
        while True:
            print("\n[idle] waiting for 'Hey Ultron'...")
            wake.wait_for_wake()
            print("[wake] detected. Listening...")
            try:
                import winsound; winsound.Beep(900, 120)
            except Exception:
                pass

            text, lang = listen()
            if not text:
                speak("I didn't catch that.", "en")
                continue
            from ultron.conversation import is_exit_phrase, farewell
            if is_exit_phrase(text):
                speak(farewell(lang), lang); continue
            _process_user_turn(brain, text, lang)

            # Natural conversation: keep talking until the user says they're done
            # (or two silences in a row). No need to repeat "Hey Ultron".
            misses = 0
            while True:
                print(f"[conversation] listening...")
                if not _wait_for_voice(FOLLOWUP_SECONDS):
                    misses += 1
                    if misses >= 2:
                        print("[conversation] ending — back to wake word.")
                        break
                    continue
                misses = 0
                audio = record_until_silence()
                text, lang = transcribe(audio)
                if not text.strip():
                    continue
                if is_exit_phrase(text):
                    speak(farewell(lang), lang)
                    break
                _process_user_turn(brain, text, lang)
    finally:
        try:
            wake.close()
        except Exception:
            pass
    return 0


# ===== MAIN =====

def main() -> int:
    try:
        assert_keys()
    except RuntimeError as e:
        print(str(e))
        return 1

    mode = (sys.argv[1].lower() if len(sys.argv) > 1 else "wake").strip()
    # Friendly aliases for the always-listening mode.
    if mode in {"handsfree", "hands-free", "listen", "auto"}:
        mode = "handsfree"
    no_speak = "--no-speak" in sys.argv
    if mode not in {"text", "voice", "wake", "telegram", "handsfree"}:
        print(f"Unknown mode '{mode}'. Use: text | voice | wake | handsfree | telegram")
        return 1

    if mode == "telegram":
        from ultron.telegram_bridge import run_bridge
        return run_bridge()

    print("=" * 60)
    print(f" ULTRON — English + Roman Urdu voice assistant  (mode: {mode})")
    print(" Ctrl+C to quit.")
    print("=" * 60)

    brain = Brain()
    scheduler = ReminderScheduler(on_fire=on_reminder_fire)
    scheduler.start()

    try:
        if mode == "text":
            return run_text_mode(brain, speak_replies=not no_speak)
        if mode == "voice":
            return run_voice_mode(brain)
        if mode == "handsfree":
            return run_handsfree_mode(brain)
        return run_wake_mode(brain)
    except KeyboardInterrupt:
        print("\n[exit] shutting down.")
        return 0
    finally:
        scheduler.stop()


if __name__ == "__main__":
    sys.exit(main())
