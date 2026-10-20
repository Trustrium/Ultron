"""ElevenLabs streaming TTS engine for Ultron (Section 2).

Optional alternative to Edge TTS. Selected via TTS_PROVIDER=elevenlabs in
speak.py; this module itself only reads env vars directly (no config.py
dependency) so the coordinator can wire config centrally later:

  ELEVENLABS_API_KEY     - required
  ELEVENLABS_VOICE_ID    - required (falls back to DEFAULT_VOICE_ID)
  DEFAULT_VOICE_ID       - fallback voice id if ELEVENLABS_VOICE_ID unset
  ELEVENLABS_MODEL       - optional, default "eleven_flash_v2_5"

Contract:
- speak_elevenlabs() returns True only on successful playback, False on
  any failure (missing key/voice, HTTP error, empty audio, playback error).
  It NEVER raises to the caller - speak.py relies on False to fall back
  to Edge TTS so Ultron never goes silent.
- No real network call is made when key/voice are missing.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

try:
    import requests
except Exception:  # pragma: no cover - requests missing in some envs
    requests = None  # type: ignore[assignment]

try:
    import pygame
except Exception:  # pragma: no cover
    pygame = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Module-level queue / lock state
# ---------------------------------------------------------------------------
# A single lock serialises all ElevenLabs playback so sequential speak()
# calls from different threads don't overlap. Threads calling
# speak_elevenlabs() block on this lock - that blocking *is* the simple
# queue: calls are served in arrival order, one at a time.
_speak_lock = threading.Lock()

# Playback bookkeeping for get_current_level() - an HONEST estimate only.
_playback_state: dict = {
    "started_at": 0.0,      # time.time() when current playback started
    "duration_est": 0.0,    # estimated seconds (from mp3 size / bitrate)
    "playing": False,
}

_mixer_state: dict = {"ok": False, "error": None, "warned": False}

_DEFAULT_MODEL = "eleven_flash_v2_5"
_API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"


def _api_key() -> str:
    return (os.getenv("ELEVENLABS_API_KEY", "") or "").strip()


def _voice_id(explicit: str | None = None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    return (
        (os.getenv("ELEVENLABS_VOICE_ID", "") or "").strip()
        or (os.getenv("DEFAULT_VOICE_ID", "") or "").strip()
    )


def _model_id() -> str:
    return (os.getenv("ELEVENLABS_MODEL", "") or "").strip() or _DEFAULT_MODEL


def is_configured(voice_id: str | None = None) -> bool:
    """True only when both an API key and a voice id are available."""
    return bool(_api_key() and _voice_id(voice_id))


def _ensure_mixer() -> bool:
    """Lazily init pygame mixer, mirroring speak.py's playback pattern.

    Duplicated here (rather than imported from speak.py) to avoid a
    circular import: speak.py imports this module.
    Failure is not cached permanently - retried on the next call.
    """
    if pygame is None:
        print("[elevenlabs] pygame not available, cannot play audio")
        return False
    if _mixer_state["ok"]:
        return True
    try:
        pygame.mixer.init()
        _mixer_state["ok"] = True
        _mixer_state["error"] = None
        return True
    except Exception as e:
        _mixer_state["error"] = str(e)
        if not _mixer_state["warned"]:
            print(f"[elevenlabs] WARNING: pygame.mixer.init failed: {e}. "
                  "Pick a default audio output in Windows Sound settings.")
            _mixer_state["warned"] = True
        return False


def _estimate_duration_seconds(file_size: int, text: str) -> float:
    """Rough duration estimate for level metering only.

    ElevenLabs mp3 streams are typically ~128 kbps (~16 KB/s). If the
    size-based estimate looks wrong, fall back to ~15 chars/sec speech.
    """
    try:
        if file_size and file_size > 0:
            est = file_size / 16000.0
            if 0.3 <= est <= 600:
                return est
    except Exception:
        pass
    return max(0.5, len(text or "") / 15.0)


def speak_elevenlabs(text: str, voice_id: str | None = None, lang: str = "en") -> bool:
    """Speak `text` via ElevenLabs streaming TTS. Returns True on success.

    `lang` is accepted for signature compatibility with speak.py; ElevenLabs
    voice/model selection is driven by voice_id + ELEVENLABS_MODEL, and the
    flash model infers language from the text itself.

    Never raises: every exception is logged and reported as False so the
    caller can fall back to Edge TTS.
    """
    try:
        text = (text or "").strip()
        if not text:
            return False

        api_key = _api_key()
        resolved_voice = _voice_id(voice_id)
        if not api_key:
            print("[elevenlabs] ELEVENLABS_API_KEY not set, skipping")
            return False
        if not resolved_voice:
            print("[elevenlabs] No voice id (ELEVENLABS_VOICE_ID / DEFAULT_VOICE_ID) set, skipping")
            return False
        if requests is None:
            print("[elevenlabs] `requests` package not available, skipping")
            return False

        model_id = _model_id()
        url = f"{_API_BASE}/{resolved_voice}/stream"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        # Serialise playback: sequential speaks queue on this lock.
        with _speak_lock:
            tmp_path: Path | None = None
            try:
                response = requests.post(
                    url, headers=headers, json=payload, stream=True, timeout=30
                )
                # Support mocked responses without status_code attr gracefully.
                status = getattr(response, "status_code", None)
                if status is not None and status != 200:
                    print(f"[elevenlabs] API returned HTTP {status}, falling back")
                    try:
                        response.close()
                    except Exception:
                        pass
                    return False

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = Path(f.name)
                    total = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                try:
                    response.close()
                except Exception:
                    pass

                if total == 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
                    print("[elevenlabs] API returned no audio, falling back")
                    return False

                if not _ensure_mixer():
                    print("[elevenlabs] mixer unavailable, falling back")
                    return False

                # Playback - same pattern as speak.py's Edge path:
                # load -> play -> wait while busy -> unload.
                _playback_state["duration_est"] = _estimate_duration_seconds(total, text)
                _playback_state["started_at"] = time.time()
                _playback_state["playing"] = True
                try:
                    pygame.mixer.music.load(str(tmp_path))
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(60)
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
                finally:
                    _playback_state["playing"] = False
                return True

            except Exception as e:
                print(f"[elevenlabs] speak failed: {e}")
                _playback_state["playing"] = False
                return False
            finally:
                if tmp_path is not None:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
    except Exception as e:
        # Outer guard: never raise to caller, per contract.
        print(f"[elevenlabs] unexpected error: {e}")
        return False


def stop_speaking() -> None:
    """Stop any current ElevenLabs (pygame mixer) playback. Never raises."""
    try:
        _playback_state["playing"] = False
        if pygame is not None and _mixer_state.get("ok"):
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            try:
                pygame.mixer.stop()
            except Exception:
                pass
    except Exception as e:
        print(f"[elevenlabs] stop_speaking failed: {e}")


def get_current_level() -> float:
    """Return an estimated audio level in 0.0..1.0.

    HONEST ESTIMATE ONLY: this is NOT a Web Audio FFT / real waveform
    analysis. There is no sample-level metering here. The value is derived
    purely from `pygame.mixer.music.get_busy()` plus an elapsed-vs-estimated-
    duration guess: while busy it returns a mid-high value that decays as
    playback nears its estimated end, and 0.0 when idle. Good enough to
    drive a pulsing orb / level indicator, not for audio engineering.
    """
    try:
        if pygame is None or not _mixer_state.get("ok"):
            return 0.0
        try:
            busy = bool(pygame.mixer.music.get_busy())
        except Exception:
            busy = bool(_playback_state.get("playing"))
        if not busy:
            _playback_state["playing"] = False
            return 0.0
        started = float(_playback_state.get("started_at") or 0.0)
        duration = float(_playback_state.get("duration_est") or 0.0)
        if started and duration and duration > 0:
            progress = min(1.0, max(0.0, (time.time() - started) / duration))
            # Start around 0.75, decay toward 0.25 as the clip nears its end.
            return round(max(0.0, min(1.0, 0.75 - 0.5 * progress)), 3)
        return 0.65
    except Exception as e:
        print(f"[elevenlabs] get_current_level failed: {e}")
        return 0.0
