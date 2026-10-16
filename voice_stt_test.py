"""Self-paced voice (speech-to-text) test. No LLM, no tokens.

    python voice_stt_test.py

Press ENTER, speak a phrase, and it prints exactly what Whisper heard.
This isolates microphone + speech-to-text from the rest of Ultron.
"""
from ultron.voice.listen import record_until_silence, transcribe, calibrate_silence

SUGGESTED = [
    "what time is it",
    "hello Ultron how are you",
    "what is the weather today",
    "இன்று வானிலை எப்படி இருக்கும்",   # Tamil: how's the weather today
]

print("=" * 60)
print(" VOICE / SPEECH-TO-TEXT TEST  (no tokens used)")
print("=" * 60)
print(" Calibrating background noise — stay quiet for a second...")
try:
    calibrate_silence()
except Exception as e:
    print(f"  (calibration note: {e})")

print("\n Try saying these, one per turn:")
for s in SUGGESTED:
    print(f"   - {s}")
print("\n Press ENTER then speak. After you stop, it shows what it heard.")
print(" Type 'q' then ENTER to quit.\n")

turn = 0
while True:
    cmd = input("[ENTER to talk, q to quit] ").strip().lower()
    if cmd == "q":
        print("bye.")
        break
    turn += 1
    print("  >>> SPEAK NOW (listening; stop when done)...")
    try:
        audio = record_until_silence()
    except Exception as e:
        print(f"  recording error: {e}")
        continue
    try:
        text, lang = transcribe(audio)
    except Exception as e:
        print(f"  transcribe error: {e}")
        continue
    print(f"  [heard:{lang}] {text!r}")
    if not text.strip():
        print("  (nothing intelligible — speak a bit louder/closer, or check mic level)")
    else:
        print("  ✓ STT works — that's what Ultron would send to the brain.")
    print()
