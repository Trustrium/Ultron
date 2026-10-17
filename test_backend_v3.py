"""Backend v3 tests — latency + any-language any-phrasing.

No LLM key, no mic, no network. Run: python test_backend_v3.py
Exit 0 = all non-skipped checks passed. Brain tests need the normal
requirements installed (dotenv, rank_bm25, ...); if Brain can't be imported,
those checks are SKIPPED (not failed) with the reason printed.
"""
import inspect
import sys

P, F, S = [], [], []


def chk(name, cond, detail=""):
    (P if cond else F).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name:58s} {detail if not cond else ''}")


def skip(name, reason):
    S.append(name)
    print(f"  SKIP  {name:58s} {reason}")


print("=" * 78)
print(" ULTRON BACKEND v3 — LATENCY + ANY-LANGUAGE TESTS")
print("=" * 78)

# ---------- 1. Paraphrase routing (real tool registry) ----------
print("\n[ROUTING] paraphrases -> expected tool (14 phrases, 4 scripts)")
try:
    from ultron.brain import Brain, TOOLS  # noqa: F401  (loads plugins too)
    from ultron.tool_router import select_tools, diagnose_routing, MAX_TOOLS
    from ultron.tool_synonyms import match_synonyms, synonym_tool_names
    from ultron.brain import fast_path_eligible  # noqa: F401

    # (phrase, expected tool, script label)
    PARAPHRASES = [
        # English
        ("open camera", "open_app", "EN"),
        ("please open Chrome", "open_app", "EN"),
        ("take a screenshot", "screenshot", "EN"),
        ("turn the volume up", "volume_up", "EN"),
        # Roman Urdu
        ("camera kholo", "open_app", "RomanUrdu"),
        ("mera camera open karo", "open_app", "RomanUrdu"),
        ("screenshot le lo", "screenshot", "RomanUrdu"),
        ("volume badhao", "volume_up", "RomanUrdu"),
        # Hindi (Devanagari)
        ("कैमरा खोलो", "open_app", "Hindi"),
        ("स्क्रीनशॉट ले लो", "screenshot", "Hindi"),
        ("वॉल्यूम बढ़ाओ", "volume_up", "Hindi"),
        # Urdu (Arabic script)
        ("کیمرہ کھولو", "open_app", "Urdu"),
        ("اسکرین شاٹ لو", "screenshot", "Urdu"),
        ("آواز بڑھاؤ", "volume_up", "Urdu"),
    ]
    for phrase, expected, label in PARAPHRASES:
        chosen = {t["name"] for t in select_tools(phrase, TOOLS)}
        syn = synonym_tool_names(phrase)
        ok_router = expected in chosen
        ok_syn = expected in syn
        chk(f"[{label}] router {phrase!r} -> {expected}",
            ok_router, f"chosen={sorted(chosen)[:12]}...")
        chk(f"[{label}] synonym {phrase!r} -> {expected}",
            ok_syn, f"synonyms={sorted(syn)}")
        chk(f"[{label}] router never empty/tiny for {phrase!r}",
            5 <= len(chosen) <= MAX_TOOLS, f"len={len(chosen)}")

    # Synonym args: camera must suggest name="Camera".
    m = match_synonyms("mera camera open karo")
    chk("synonym args camera -> name='Camera'",
        any(x["tool"] == "open_app" and x["args"].get("name") == "Camera" for x in m),
        f"matches={m}")
    # Every synonym tool name must exist in the real registry (plugins loaded).
    from ultron.tool_registry import TOOLS as REG_TOOLS, _load_plugins_once
    _load_plugins_once()
    reg_names = {t["name"] for t in REG_TOOLS}
    from ultron.tool_synonyms import SYNONYM_ENTRIES
    missing = {tool for _, tool, _ in SYNONYM_ENTRIES if tool not in reg_names}
    chk("all synonym tool names exist in registry", not missing, f"missing={missing}")

    # Low-confidence fallback: Devanagari query has no English BM25 match.
    diag = diagnose_routing("कैमरा खोलो", TOOLS)
    chk("Devanagari query flagged low-confidence (BM25 ~0)",
        diag["low_confidence"], f"diag={diag}")
    chk("Devanagari diag still finds synonym open_app",
        "open_app" in diag["synonym_tools"], f"diag={diag}")
    diag_en = diagnose_routing("open camera", TOOLS)
    chk("English query finds synonym open_app",
        "open_app" in diag_en["synonym_tools"], f"diag={diag_en}")

    # ---------- 2. Fast-path eligibility ----------
    print("\n[FAST-PATH] eligibility (conservative: 1-tool direct only)")
    import ultron.config as _cfg
    _old_fast = _cfg.LLM_FAST_PATH
    try:
        _cfg.LLM_FAST_PATH = False
        chk("fast path OFF by default (opt-in)", not fast_path_eligible("camera kholo"))
        _cfg.LLM_FAST_PATH = True
        for phrase in ("camera kholo", "open camera", "mera camera open karo"):
            chk(f"eligible: {phrase!r}", fast_path_eligible(phrase))
        for phrase, why in (
            ("camera kholo aur screenshot lo", "multi-step"),
            ("pc band karo", "destructive shutdown"),
            ("kya camera khula hai", "question"),
            ("camera kholo?", "question mark"),
            ("hello, how are you today my friend", "not a command / long"),
            ("open camera and then take a screenshot and send it", "multi-step"),
        ):
            chk(f"ineligible ({why}): {phrase!r}", not fast_path_eligible(phrase))
    finally:
        _cfg.LLM_FAST_PATH = _old_fast

    # ---------- 3. Brain end-to-end with fake clients (no network) ----------
    print("\n[BRAIN] think() with fake clients — API preserved, streaming, lang")
    from ultron.llm.base import LLMClient, AssistantResponse, ToolCall
    from ultron.brain import Brain as _Brain

    class FakeMain(LLMClient):
        def __init__(self, text="Ho gaya, sir."):
            self.text = text
            self.calls = 0

        def chat(self, system, history, tools):
            self.calls += 1
            return AssistantResponse(text=self.text, tool_calls=[])

        def make_user_message(self, text):
            return {"role": "user", "content": text}

        def make_assistant_message(self, response):
            return {"role": "assistant", "content": response.text or ""}

        def make_tool_results(self, results):
            return [{"role": "tool", "tool_call_id": i, "content": r} for i, r in results]

        def has_unresolved_tool_calls(self, msg):
            return False

    sig = inspect.signature(_Brain.think)
    chk("think() keeps old signature (user_text, lang) + adds callbacks",
        "user_text" in sig.parameters and "lang" in sig.parameters
        and "on_token" in sig.parameters and "on_status" in sig.parameters,
        f"sig={sig}")

    fake = FakeMain()
    brain = _Brain(client=fake)
    toks, stats = [], []
    reply = brain.think("hello", lang="en",
                        on_token=lambda t: toks.append(t),
                        on_status=lambda s: stats.append(s))
    chk("think() returns same value with callbacks", reply == "Ho gaya, sir.", f"got={reply!r}")
    chk("on_token received the reply text", "".join(toks) == "Ho gaya, sir.", f"toks={toks}")
    chk("on_status got understanding + replying",
        "understanding" in stats and "replying" in stats, f"stats={stats}")

    # Per-turn language directive.
    chk("system(urdu) forces Urdu script reply",
        "Urdu" in brain._system("urdu") and "ہو گیا" in brain._system("urdu"))
    chk("system(hindi) forces Devanagari reply",
        "Devanagari" in brain._system("hindi") and "हो गया" in brain._system("hindi"))
    chk("system(roman_urdu) forces Latin-script reply",
        "Roman Urdu" in brain._system("roman_urdu"))
    chk("system(en) replies in English",
        "Reply in English" in brain._system("en"))

    # Streaming default: base chat_stream calls on_token once with full text.
    got = []
    resp = fake.chat_stream("sys", [], [], on_token=lambda t: got.append(t))
    chk("base chat_stream default: on_token once + full response",
        got == ["Ho gaya, sir."] and resp.text == "Ho gaya, sir.", f"got={got}")

    # Fast-path end-to-end: fast client emits 1 tool call, main replies.
    from ultron import tool_registry as _reg
    _old_handler = _reg.TOOL_HANDLERS.get("open_app")
    tool_calls_seen = []

    def _stub_open_app(args):
        tool_calls_seen.append(dict(args or {}))
        return "opened (stub)"

    class FakeFast(LLMClient):
        def __init__(self, tool_calls):
            self.tool_calls = tool_calls
            self.calls = 0

        def chat(self, system, history, tools):
            self.calls += 1
            return AssistantResponse(text="", tool_calls=list(self.tool_calls))

        def make_user_message(self, text):
            return {"role": "user", "content": text}

        def make_assistant_message(self, response):
            return {"role": "assistant", "content": response.text or ""}

        def make_tool_results(self, results):
            return [{"role": "tool", "tool_call_id": i, "content": r} for i, r in results]

        def has_unresolved_tool_calls(self, msg):
            return False

    try:
        _reg.TOOL_HANDLERS["open_app"] = _stub_open_app
        _cfg.LLM_FAST_PATH = True
        fast = FakeFast([ToolCall(id="1", name="open_app", arguments={"name": "Camera"})])
        brain2 = _Brain(client=FakeMain(text="Camera khol diya, sir."))
        brain2._get_fast_client = lambda: fast
        reply2 = brain2.think("camera kholo", lang="roman_urdu")
        chk("fast path: tool executed + main model replies",
            reply2 == "Camera khol diya, sir." and tool_calls_seen == [{"name": "Camera"}],
            f"reply={reply2!r} calls={tool_calls_seen} fast_calls={fast.calls}")
        chk("fast path: fast client used exactly once", fast.calls == 1, f"calls={fast.calls}")

        # Fast-path MISS: fast client returns no tool call -> main model retries.
        fast_miss = FakeFast([])
        main2 = FakeMain(text="Main model reply, sir.")
        brain3 = _Brain(client=main2)
        brain3._get_fast_client = lambda: fast_miss
        reply3 = brain3.think("camera kholo", lang="roman_urdu")
        chk("fast-path miss: discarded, main model answers",
            reply3 == "Main model reply, sir." and main2.calls == 1,
            f"reply={reply3!r} main_calls={main2.calls} fast_calls={fast_miss.calls}")
    finally:
        if _old_handler is not None:
            _reg.TOOL_HANDLERS["open_app"] = _old_handler
        _cfg.LLM_FAST_PATH = _old_fast

except ImportError as e:
    skip("brain/router end-to-end tests", f"missing dep in this env: {e}")

# ---------- 4. Language helpers (light deps only) ----------
print("\n[LANGUAGE] codes + script detection")
try:
    from ultron.voice.language import normalize_language_code, detect_text_language
    for raw, want in (("hi", "hindi"), ("ur", "urdu"), ("en", "en"), ("ta", "ta"),
                      ("roman_urdu", "roman_urdu"), ("", "en")):
        chk(f"normalize {raw!r} -> {want}",
            normalize_language_code(raw) == want, f"got={normalize_language_code(raw)!r}")
    for text, want in (
        ("कैमरा खोलो", "hindi"),
        ("کیمرہ کھولو", "urdu"),
        ("camera kholo", "roman_urdu"),
        ("mera camera open karo", "roman_urdu"),
        ("open camera", "en"),
        ("வணக்கம்", "ta"),
    ):
        chk(f"detect {text!r} -> {want}", detect_text_language(text) == want,
            f"got={detect_text_language(text)!r}")
except ImportError as e:
    skip("language tests", f"missing dep: {e}")

# ---------- 5. Conversation: multilingual exit + farewell ----------
print("\n[CONVERSATION] exit phrases + farewells")
try:
    from ultron.conversation import is_exit_phrase, farewell
    for phrase in ("bas karo", "बस", "بس کرو", "khuda hafiz", "khatam", "bye"):
        chk(f"exit: {phrase!r}", is_exit_phrase(phrase))
    chk("non-exit not matched", not is_exit_phrase("camera kholo"))
    chk("farewell urdu uses Urdu script", "ٹھیک ہے" in farewell("urdu"))
    chk("farewell hindi uses Devanagari", "ठीक है" in farewell("hindi"))
    chk("farewell roman_urdu uses Latin script", "Theek hai" in farewell("roman_urdu"))
except ImportError as e:
    skip("conversation tests", f"missing dep: {e}")

# ---------- 6. Worker immediate feedback (source check — PySide6 absent here) ----------
print("\n[WORKER] immediate status feedback (source-level, PySide6 not imported)")
try:
    import pathlib
    src = pathlib.Path("ultron/gui/worker.py").read_text(encoding="utf-8")
    proc = src[src.index("def _process_turn"):src.index("def _run_voice_mode")]
    chk("worker emits Understanding… before brain.think()",
        "Understanding" in proc and proc.index("Understanding") < proc.index("brain.think(text"))
    chk("worker passes on_status to brain.think",
        "on_status" in proc and "brain.think(text, lang=lang, **kwargs)" in proc)
    chk("worker emits Doing… on doing-status",
        "Doing" in proc)
    chk("worker emits listening in request_voice_turn",
        'def request_voice_turn' in src
        and 'listening' in src[src.index("def request_voice_turn"):src.index("def _run_wake_mode")])
except Exception as e:
    chk("worker source checks", False, str(e))

# ---------- 7. OpenAI-compat streaming API present ----------
print("\n[LLM] streaming API surface")
try:
    from ultron.llm.openai_compat import OpenAICompatClient
    chk("OpenAICompatClient has chat_stream",
        callable(getattr(OpenAICompatClient, "chat_stream", None)))
    chk("OpenAICompatClient has clone_with_model",
        callable(getattr(OpenAICompatClient, "clone_with_model", None)))
    from ultron.llm.factory import make_fast_llm_client
    chk("factory exposes make_fast_llm_client", callable(make_fast_llm_client))
    from ultron import config as _cfg2
    chk("config has LLM_FAST_MODEL + LLM_FAST_PATH + listen timings",
        hasattr(_cfg2, "LLM_FAST_MODEL") and hasattr(_cfg2, "LLM_FAST_PATH")
        and hasattr(_cfg2, "LISTEN_SILENCE_SECONDS"))
    chk("listen silence default tightened to 0.5s",
        abs(float(getattr(_cfg2, "LISTEN_SILENCE_SECONDS", -1)) - 0.5) < 1e-9,
        f"got={getattr(_cfg2, 'LISTEN_SILENCE_SECONDS', None)}")
except ImportError as e:
    skip("LLM API surface tests", f"missing dep: {e}")

print("\n" + "=" * 78)
print(f"RESULT: {len(P)} passed, {len(F)} failed, {len(S)} skipped")
if F:
    print("FAILED:", *F, sep="\n  - ")
    sys.exit(1)
print("ALL NON-SKIPPED CHECKS PASSED")
