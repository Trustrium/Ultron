"""Comprehensive feature test — exercises every tool's safe path.

Categories:
  LOCAL   — pure local, always runs
  NET     — needs internet (web/news/currency/stocks/weather)
  LLM     — needs the LLM API (may hit rate limits)
  WIRED   — destructive/hardware: verify wired + importable only, don't fire
"""
import sys
import tempfile
from pathlib import Path

PASS, FAIL, SKIP = [], [], []


def ok(name, detail=""):
    PASS.append(name); print(f"  PASS  {name:42s} {detail}")


def bad(name, detail=""):
    FAIL.append(name); print(f"  FAIL  {name:42s} {detail}")


def skip(name, detail=""):
    SKIP.append(name); print(f"  SKIP  {name:42s} {detail}")


def check(name, cond, detail="", category="LOCAL"):
    (ok if cond else bad)(name, detail)


print("=" * 80)
print(" ULTRON — FULL FEATURE TEST")
print("=" * 80)

# ===== Brain wiring =====
print("\n[WIRING] brain tools <-> handlers")
from ultron.brain import TOOLS, TOOL_HANDLERS
names = {t["name"] for t in TOOLS}
check("every tool has a handler", names == set(TOOL_HANDLERS), f"{len(names)} tools")
check("no duplicate tool names", len(names) == len(TOOLS), f"{len(TOOLS)} declared")

# ===== LOCAL tools =====
print("\n[LOCAL] core tools")
from ultron.tools import system as ts
check("current_time", "20" in ts.current_time())
check("media keys exist", all(callable(getattr(ts, f, None)) for f in
      ["media_play_pause", "media_next", "media_prev", "media_stop"]))

from ultron.tools import memory as tm
tm.remember("test-fav", "dosa");
check("memory remember+recall", "dosa" in tm.recall("test-fav"))
tm.forget("test-fav")

from ultron.tools import notes as tn
import time as _t
tag = f"t{int(_t.time())}"
tn.add_note("test note", tag=tag)
check("notes add+list", tag in tn.list_notes(query=tag))

from ultron.tools import clipboard as tc
tc.write_clipboard("clip-test-xyz")
check("clipboard write+read", "clip-test-xyz" in tc.read_clipboard())

from ultron.tools import convert as tcv
check("unit convert km->mi", "3.10" in tcv.convert_unit(5, "km", "mi"))
check("temp convert F->C", "37.7" in tcv.convert_unit(100, "F", "C"))

from ultron.tools import reminders as tr
check("reminder parse bare time", tr._parse_due("5pm") is not None)
check("reminder recurrence", tr._next_occurrence(__import__("datetime").datetime(2026,5,21,9,0), "daily") is not None)

from ultron.tools import python_exec as tpe
check("python sandbox", "1024" in tpe.run_python("print(2**10)"))
check("python sandbox timeout", "timed out" in tpe.run_python("import time;time.sleep(5)", timeout=1))

from ultron.tools import code as tcode
check("shell blocklist", tcode._is_dangerous("Remove-Item -Recurse C:/"))
check("list_dir", "Contents" in tcode.list_dir("."))

from ultron.tools import skills as tsk
tsk.create_skill("t-skill", [{"tool": "current_time", "args": {}}])
check("skill create+list", "t-skill" in tsk.list_skills())
tsk.delete_skill("t-skill")

from ultron.tools import file_search as tfs
check("file_search", "ultron_app" in tfs.find_files("ultron_app", max_results=3).lower())

from ultron.tools import file_ops as tfo
tmp = Path(tempfile.mkdtemp())
(tmp / "a.txt").write_text("hi")
check("file copy", "Copied" in tfo.copy_file(str(tmp/"a.txt"), str(tmp/"b.txt")))
check("file rename", "Renamed" in tfo.rename_file(str(tmp/"b.txt"), "c.txt"))

from ultron import personality as tp
check("personality presets", len(tp.PERSONALITY_PRESETS) == 5)

from ultron import routines as trt
trt.create_routine("t-routine", "do nothing", "daily", "08:00")
check("routine create+list", "t-routine" in trt.list_routines())
trt.delete_routine("t-routine")

from ultron import autostart, backup, usage
check("autostart bool", isinstance(autostart.is_enabled(), bool))
check("usage summary", isinstance(usage.today_summary(), dict))

from ultron.tools import app_index as tai
idx = tai.build_index()
check("app index discovers apps", len(idx) > 10, f"{len(idx)} apps")
check("app fuzzy match notepad", tai.find_app("notepad") is not None)

# ===== WIRED-only (don't fire) =====
print("\n[WIRED] destructive/hardware (import + signature only)")
from ultron.tools import automation as tau
check("automation importable", callable(tau.type_text) and callable(tau.mouse_click))
check("screen_size works", "x" in tau.screen_size())
from ultron.tools import windows_mgmt as twm
check("window list", "window" in twm.list_windows().lower() or "No open" in twm.list_windows())
from ultron.tools import vision_click as tvc
check("vision_click importable", callable(tvc.click_on_screen))
from ultron.tools import gmail as tg
check("gmail importable", callable(tg.send_email))
from ultron.tools import whatsapp as tw
check("whatsapp importable", callable(tw.send_whatsapp))
from ultron.tools import calendar_gcal as tcal
check("calendar importable", callable(tcal.add_event))
from ultron.agent import accomplish, Agent
check("agent importable", callable(accomplish))

# ===== NET tools =====
print("\n[NET] internet-dependent")
try:
    from ultron.tools import news
    n = news.news_briefing(count=2)
    check("news_briefing", "Hacker News" in n or "headlines" in n.lower(), n[:40])
except Exception as e:
    bad("news_briefing", str(e)[:50])

try:
    from ultron.tools import convert
    c = convert.convert_currency(100, "USD", "INR")
    check("currency convert (live)", "INR" in c and "fail" not in c.lower(), c[:50])
except Exception as e:
    bad("currency convert", str(e)[:50])

try:
    from ultron.tools import quotes
    q = quotes.stock_quote("AAPL")
    check("stock quote (live)", "AAPL" in q and "fail" not in q.lower(), q[:50])
except Exception as e:
    bad("stock quote", str(e)[:50])

try:
    from ultron.tools import web_search_real
    w = web_search_real.web_search("python", max_results=2)
    check("web search (live)", "results" in w.lower(), w[:40])
except Exception as e:
    bad("web search", str(e)[:50])

try:
    from plugins.weather import get_weather_handler
    wx = get_weather_handler({"location": "London"})
    check("weather plugin (live)", len(wx) > 10 and "fail" not in wx.lower(), wx[:40])
except Exception as e:
    bad("weather plugin", str(e)[:50])

# ===== LLM tools (may rate-limit) =====
print("\n[LLM] needs API tokens (may hit rate limit)")
try:
    from ultron.tools import translate
    t = translate.translate("hello", "tamil")
    if "fail" in t.lower() or "rate" in t.lower() or "429" in t:
        skip("translate", "rate limited / failed: " + t[:40])
    else:
        check("translate EN->TA", any("஀" <= ch <= "௿" for ch in t), "tamil chars")
except Exception as e:
    skip("translate", str(e)[:50])

try:
    from ultron.brain import Brain
    b = Brain()
    r = b.think("Reply with only the word PONG.", "en")
    if "rate" in r.lower() or "429" in r:
        skip("brain think()", "rate limited")
    else:
        check("brain think() end-to-end", len(r) > 0, repr(r[:30]))
except Exception as e:
    skip("brain think()", str(e)[:50])

# ===== Summary =====
print("\n" + "=" * 80)
print(f" RESULT: {len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
if FAIL:
    print(" FAILURES:")
    for f in FAIL:
        print(f"   - {f}")
print("=" * 80)
sys.exit(1 if FAIL else 0)
