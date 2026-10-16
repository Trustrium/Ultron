"""Microphone recording + speech-to-text via faster-whisper. Auto-detects English / Roman Urdu / Tamil."""
import os
import queue
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from ..config import WHISPER_MODEL, MAX_LISTEN_SECONDS

SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.012      # RMS below this is "silence" — overridden by calibrate_silence()
SILENCE_DURATION = 0.8         # seconds of silence to stop (lower = snappier response)
MIN_SPEECH_SECONDS = 0.5

_current_silence_threshold = SILENCE_THRESHOLD


def calibrate_silence(seconds: float = 0.8) -> float:
    """Sample ambient noise and set the silence threshold above it. Returns the chosen threshold."""
    import time
    global _current_silence_threshold
    samples_rms: list[float] = []
    end = time.time() + seconds
    try:
        with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, dtype="float32", blocksize=1024) as stream:
            while time.time() < end:
                pcm, _ = stream.read(1024)
                arr = np.asarray(pcm, dtype=np.float32).flatten()
                samples_rms.append(float(np.sqrt(np.mean(arr ** 2))))
    except Exception as e:
        print(f"[listen] calibration failed: {e}. Using default {SILENCE_THRESHOLD}.")
        return _current_silence_threshold
    if not samples_rms:
        return _current_silence_threshold
    noise_floor = float(np.median(samples_rms))
    # Set threshold ~3x the noise floor, but never absurdly low or high.
    # Floor kept low (0.002) so quiet mics still register speech.
    threshold = max(0.002, min(0.05, noise_floor * 3.0))
    _current_silence_threshold = threshold
    print(f"[listen] ambient noise={noise_floor:.4f} -> silence threshold set to {threshold:.4f}")
    return threshold

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"[listen] loading whisper '{WHISPER_MODEL}' (first time only)...")
        # Use several CPU cores for faster transcription (capped to avoid
        # oversubscription overhead on the tiny model).
        threads = min(8, os.cpu_count() or 4)
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8",
                              cpu_threads=threads)
    return _model


def record_until_silence() -> np.ndarray:
    """Record from mic until user pauses. Returns float32 mono PCM."""
    chunks: list[np.ndarray] = []
    q: queue.Queue[np.ndarray] = queue.Queue()

    def cb(indata, frames, time_info, status):
        q.put(indata.copy())

    start = time.time()
    last_voice = time.time()
    started_speaking = False

    with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=cb, dtype="float32"):
        while True:
            try:
                buf = q.get(timeout=0.2)
            except queue.Empty:
                buf = None

            now = time.time()
            if now - start > MAX_LISTEN_SECONDS:
                break

            if buf is None:
                continue

            chunks.append(buf)
            rms = float(np.sqrt(np.mean(buf ** 2)))

            if rms > _current_silence_threshold:
                last_voice = now
                started_speaking = True
            elif started_speaking and (now - last_voice) > SILENCE_DURATION:
                if (now - start) > MIN_SPEECH_SECONDS:
                    break

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks, axis=0).flatten()


def _normalize_audio(audio: np.ndarray, target_peak: float = 0.35,
                     max_gain: float = 20.0) -> np.ndarray:
    """Amplify quiet recordings to a usable level for Whisper. Only boosts (never
    attenuates) and caps the gain so near-silence isn't blown up into noise."""
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if 0 < peak < target_peak:
        gain = min(target_peak / peak, max_gain)
        audio = np.clip(audio * gain, -1.0, 1.0)
    return audio


def transcribe(audio: np.ndarray) -> tuple[str, str]:
    """Return (text, language_code). language_code is 'ta', 'en', 'roman_urdu', etc. Whisper returns 'ur' for Urdu speech — map it to roman_urdu."""
    if audio.size == 0:
        return "", "en"
    audio = _normalize_audio(audio)
    model = _get_model()
    try:
        segments, info = model.transcribe(
            audio,
            beam_size=1,
            vad_filter=True,
            language=None,  # auto-detect (English / Roman Urdu / Tamil)
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        _lg = (info.language or "en").lower()
        if _lg in ("ur", "urdu"):
            _lg = "roman_urdu"
        return text, _lg
    except Exception as e:
        # VAD model download failure or any other transcribe error — retry without VAD.
        print(f"[listen] transcribe with VAD failed ({e}); retrying without VAD.")
        try:
            segments, info = model.transcribe(audio, beam_size=1, vad_filter=False, language=None)
            text = " ".join(s.text.strip() for s in segments).strip()
            _lg2 = (info.language or "en").lower()
            if _lg2 in ("ur", "urdu"):
                _lg2 = "roman_urdu"
            return text, _lg2
        except Exception as e2:
            print(f"[listen] transcribe failed: {e2}")
            return "", "en"


def listen() -> tuple[str, str]:
    """Convenience: record + transcribe."""
    audio = record_until_silence()
    return transcribe(audio)
