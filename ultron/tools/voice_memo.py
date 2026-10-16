"""Voice memos — record audio for N seconds, save a WAV to Desktop, and transcribe it
using the same faster-whisper model the assistant already uses.
"""
from __future__ import annotations
import datetime as _dt
import wave
from pathlib import Path


def _desktop() -> Path:
    home = Path.home()
    for c in (home / "OneDrive" / "Desktop", home / "Desktop", home):
        if c.exists():
            return c
    return home


def record_voice_memo(seconds: int = 15, transcribe: bool = True) -> str:
    """Record `seconds` of audio, save WAV to Desktop, optionally transcribe."""
    try:
        seconds = max(1, min(int(seconds), 300))
    except (TypeError, ValueError):
        seconds = 15
    try:
        import sounddevice as sd
        import numpy as np
    except Exception as e:
        return f"Audio libraries unavailable: {e}"

    rate = 16000
    try:
        print(f"[memo] recording {seconds}s...")
        audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="int16")
        sd.wait()
    except Exception as e:
        return f"Recording failed: {e}"

    out = _desktop() / f"voice_memo_{_dt.datetime.now():%Y%m%d_%H%M%S}.wav"
    try:
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(audio.tobytes())
    except Exception as e:
        return f"Could not save memo: {e}"

    result = f"Voice memo saved to {out}"
    if transcribe:
        try:
            from ..voice.listen import transcribe as _stt
            import numpy as np
            text, lang = _stt(audio.flatten().astype("float32") / 32768.0)
            if text.strip():
                result += f"\nTranscript ({lang}): {text}"
        except Exception as e:
            result += f"\n(transcription failed: {e})"
    return result
