"""Quick diagnostic: lists audio inputs, records 5s, shows volume + the wake-word score curve.

Run with:  python mic_check.py
Speak "Hey Ultron" 3-4 times during the recording.
"""
import time
import numpy as np
import sounddevice as sd

from ultron.voice.wake import WakeWordListener, SAMPLE_RATE, FRAME_LENGTH


def main() -> None:
    print("\n=== Audio Input Devices ===")
    devices = sd.query_devices()
    default_in = sd.default.device[0] if sd.default.device[0] is not None else -1
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            marker = "  <-- DEFAULT" if i == default_in else ""
            print(f"  [{i}] {d['name']} ({d['max_input_channels']} ch, {d['default_samplerate']} Hz){marker}")
    print(f"\nUsing default input device index: {default_in}")

    print("\n=== Loading wake-word model ===")
    w = WakeWordListener()

    print("\n=== Recording 8 seconds ===")
    print("Say 'Hey Ultron' 3-4 times during the recording.\n")
    duration = 8
    peak_rms = 0.0
    peak_score = 0.0
    score_log = []

    end = time.time() + duration
    with sd.InputStream(
        channels=1, samplerate=SAMPLE_RATE, dtype="int16", blocksize=FRAME_LENGTH,
    ) as stream:
        while time.time() < end:
            pcm, _ = stream.read(FRAME_LENGTH)
            samples = np.asarray(pcm, dtype=np.int16).flatten()
            rms = float(np.sqrt(np.mean((samples / 32768.0) ** 2)))
            peak_rms = max(peak_rms, rms)
            scores = w.model.predict(samples)
            s = scores.get(w.target_key, 0.0)
            peak_score = max(peak_score, s)
            if s > 0.15:
                score_log.append(s)

    print(f"\n=== Results ===")
    print(f"Peak mic volume (RMS): {peak_rms:.4f}")
    print(f"   - If < 0.005: mic is too quiet or muted -> check Windows mic settings")
    print(f"   - If > 0.02:  mic is hearing you fine")
    print(f"Peak wake-word score: {peak_score:.3f}")
    print(f"   - Threshold for wake: 0.4")
    print(f"   - If peak > 0.4: would have triggered")
    print(f"   - If peak < 0.2: model not recognizing 'Hey Ultron' - try saying it louder/clearer")
    if score_log:
        print(f"Scores > 0.15 during recording: {len(score_log)} samples, max={max(score_log):.3f}")
    else:
        print("No detection candidates above 0.15. Either silence, or model isn't recognizing the phrase.")


if __name__ == "__main__":
    main()
