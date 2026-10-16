"""Mic + wake-word diagnostic. Run it, then say 'Hey Ultron' a few times when prompted.

    python mic_wake_test.py
"""
import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
SECONDS = 12

print("=" * 60)
print(" MIC + WAKE-WORD DIAGNOSTIC")
print("=" * 60)
print(f" default input device: [{sd.default.device[0]}] "
      f"{sd.query_devices(sd.default.device[0])['name']}")
print()
print(" >>> When you see 'RECORDING NOW', say 'HEY ULTRON' clearly 3 times. <<<")
for i in (3, 2, 1):
    print(f"   starting in {i}...")
    time.sleep(1)

print(f"\n   RECORDING NOW — say 'Hey Ultron' several times! ({SECONDS} seconds)")
audio = sd.rec(int(SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
sd.wait()
print("   ...done recording.\n")

samples = audio.flatten()
rms = float(np.sqrt(np.mean((samples.astype(np.float64) / 32768.0) ** 2)))
peak = float(np.max(np.abs(samples)) / 32768.0)
print(f"[MIC LEVEL] rms={rms:.4f}  peak={peak:.4f}")
if peak < 0.01:
    print("  -> MIC IS SILENT. Windows isn't capturing audio from this device.")
    print("     Check: Settings > Sound > Input device + level, and mic privacy permission.")
else:
    print("  -> mic is capturing audio OK.")

# Run wake model over the recording
print("\n[WAKE SCORE]")
try:
    from ultron.voice.wake import _find_hey_ultron_onnx
    from openwakeword.model import Model
    m = Model(wakeword_models=[_find_hey_ultron_onnx()], inference_framework="onnx")
    key = next(iter(m.models.keys()))
    FRAME = 1280
    max_score = 0.0
    for start in range(0, len(samples) - FRAME, FRAME):
        frame = samples[start:start + FRAME]
        sc = m.predict(frame).get(key, 0.0)
        if sc > max_score:
            max_score = sc
    print(f"  highest 'hey_ultron' score in your recording: {max_score:.3f}")
    print(f"  current detection threshold: 0.4")
    if max_score >= 0.4:
        print("  -> Detection WORKS. (If live failed, it's a timing/streaming issue.)")
    elif max_score >= 0.2:
        print("  -> CLOSE. Lowering the threshold to ~0.3 should make it trigger.")
    else:
        print("  -> Model barely reacted. Try saying it more clearly, or mic level is low.")
except Exception as e:
    import traceback; traceback.print_exc()
    print(f"  wake model error: {e}")

# Whisper STT — what did it actually hear? (more important than wake word)
print("\n[WHISPER STT] what Ultron heard:")
try:
    from ultron.voice.listen import transcribe
    audio_f = (samples.astype("float32") / 32768.0)
    text, lang = transcribe(audio_f)
    print(f"  text: {text!r}")
    print(f"  lang: {lang}")
    if text.strip():
        print("  -> STT WORKS. Ultron understood your speech.")
    else:
        print("  -> heard nothing intelligible (speak louder / closer).")
except Exception as e:
    import traceback; traceback.print_exc()
    print(f"  STT error: {e}")

print("=" * 60)
