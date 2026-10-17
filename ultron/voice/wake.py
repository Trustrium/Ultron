"""Wake-word detection using openWakeWord — fully local, no API key.

Ultron's wake phrase is "Hey Ultron". Honest note: openWakeWord ships NO
"hey_ultron" acoustic model, so until a custom Hey Ultron model is trained,
the detector loads the bundled "hey_jarvis" model — it listens for the
sound of "Hey Jarvis". The GUI, logs and prompts still say "Hey Ultron",
and text / voice / handsfree modes do not need the wake word at all.
If a hey_ultron*.onnx file is ever present (custom model), it is preferred.
"""
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
FRAME_LENGTH = 1280            # 80 ms @ 16 kHz — openWakeWord's expected chunk size
DETECTION_THRESHOLD = 0.4      # 0.0-1.0; higher = fewer false positives
DEBUG_PRINT_SCORES = True      # Set False once wake word is reliable.
DEBUG_PRINT_FLOOR = 0.15       # Print scores above this so you can see "almost" hits.


def _find_hey_ultron_onnx() -> str:
    """Locate a wake-word ONNX model inside the openwakeword package.

    Prefers a custom hey_ultron model if one is ever bundled; otherwise
    falls back to the bundled hey_jarvis model that openWakeWord actually
    ships. Previously this searched for hey_ultron only and raised
    FileNotFoundError on every real install, so wake mode never started.
    """
    import openwakeword
    pkg_dir = Path(openwakeword.__file__).parent
    for stem in ("hey_ultron", "hey_jarvis"):
        for candidate in (
            pkg_dir / "resources" / "models" / f"{stem}_v0.1.onnx",
            pkg_dir / "models" / f"{stem}_v0.1.onnx",
        ):
            if candidate.exists():
                return str(candidate)
        # Search fallback in case the layout changes.
        for path in sorted(pkg_dir.rglob(f"{stem}*.onnx")):
            return str(path)
    raise FileNotFoundError(
        "Could not locate a hey_ultron or hey_jarvis .onnx model inside the "
        "openwakeword package. Run: python -c \"import openwakeword.utils; "
        "openwakeword.utils.download_models()\""
    )


def wake_spoken_phrase(model_path: str) -> str:
    """The phrase the loaded acoustic model actually listens for."""
    return "Hey Ultron" if "ultron" in Path(model_path).name.lower() else "Hey Jarvis"


class WakeWordListener:
    def __init__(self, keyword: str | None = None) -> None:
        # `keyword` accepted for API compatibility; this listener is hardcoded to hey_ultron.
        _ = keyword
        try:
            import openwakeword
            import openwakeword.utils
            from openwakeword.model import Model
        except ImportError as e:
            raise RuntimeError(
                "openwakeword not installed. Run: pip install openwakeword onnxruntime"
            ) from e

        # Ensure models are downloaded once (cached afterward).
        try:
            openwakeword.utils.download_models()
        except Exception as e:
            print(f"[wake] model download note: {e}")

        model_path = _find_hey_ultron_onnx()
        try:
            # Load ONLY one wake-word model. Massive speed win vs. loading all defaults.
            self.model = Model(wakeword_models=[model_path], inference_framework="onnx")
        except Exception as e:
            raise RuntimeError(f"Failed to load wake-word model from {model_path}: {e}") from e

        self.target_key = next(iter(self.model.models.keys()))
        self.spoken_phrase = wake_spoken_phrase(model_path)
        print(f"[wake] listening for: '{self.spoken_phrase}' (detector model: '{self.target_key}', 1 model loaded)")
        if self.spoken_phrase != "Hey Ultron":
            print("[wake] note: no custom Hey Ultron acoustic model ships with openWakeWord yet — "
                  "say 'Hey Jarvis' for wake mode. Text / voice / handsfree modes need no wake word.")

    def wait_for_wake(self) -> None:
        """Block until the wake word is detected."""
        peak = 0.0
        with sd.InputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            dtype="int16",
            blocksize=FRAME_LENGTH,
        ) as stream:
            while True:
                pcm, _overflow = stream.read(FRAME_LENGTH)
                samples = np.asarray(pcm, dtype=np.int16).flatten()
                scores = self.model.predict(samples)
                score = scores.get(self.target_key, 0.0)
                if DEBUG_PRINT_SCORES and score >= DEBUG_PRINT_FLOOR:
                    if score > peak:
                        peak = score
                        print(f"[wake-debug] score={score:.2f} (peak={peak:.2f}, threshold={DETECTION_THRESHOLD})")
                if score >= DETECTION_THRESHOLD:
                    return

    def close(self) -> None:
        return
