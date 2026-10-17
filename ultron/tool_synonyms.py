"""Multilingual synonym map: ANY phrasing -> candidate tool(s).

Covers English, Hindi (Devanagari), Urdu (Arabic script), Roman Urdu and
Roman Hindi (Latin script) for the common actions users actually say, e.g.
"camera kholo", "mera camera open karo", "camera khol do", "कैमरा खोलो",
"کیمرہ کھولو" all map to the camera action (tool ``open_app`` + name "Camera").

ROLE — routing hints ONLY, never dispatch:
  * ``match_synonyms(query)`` returns candidate (tool, suggested args) pairs.
  * ``tool_router.select_tools`` unions these tools into the set sent to the LLM.
  * The LLM ALWAYS makes the final tool choice. Nothing here executes anything,
    and no exact-string match ever bypasses the LLM + tool router.

HONEST GAPS (documented, not papered over):
  * There is NO native PC screen-brightness tool in the registry. Brightness
    phrases therefore route to ``open_app`` (Settings, where Windows brightness
    lives) plus ``ha_set_brightness`` (smart-home lights) and the LLM picks
    whichever fits the request. "Light brightness" phrases only add the
    smart-light tool.
  * Camera / browser / notepad / calculator / settings / WhatsApp / YouTube all
    go through the generic ``open_app`` tool (which resolves friendly names,
    aliases and the installed-app index). The suggested ``name`` arg is a hint
    the LLM can use; the router only guarantees the tool is in the candidate set.
"""
from __future__ import annotations
import re
import unicodedata

# (phrase, tool_name, suggested args) — phrases are matched as substrings
# against the normalized query, longest phrase wins per tool.
SYNONYM_ENTRIES: list[tuple[str, str, dict]] = [
    # ---- camera -> open_app("Camera") ----
    ("open camera", "open_app", {"name": "Camera"}),
    ("open the camera", "open_app", {"name": "Camera"}),
    ("turn on camera", "open_app", {"name": "Camera"}),
    ("start camera", "open_app", {"name": "Camera"}),
    ("launch camera", "open_app", {"name": "Camera"}),
    ("show camera", "open_app", {"name": "Camera"}),
    ("camera on", "open_app", {"name": "Camera"}),
    ("camera kholo", "open_app", {"name": "Camera"}),
    ("camera khol do", "open_app", {"name": "Camera"}),
    ("mera camera open karo", "open_app", {"name": "Camera"}),
    ("mera camera kholo", "open_app", {"name": "Camera"}),
    ("camera open karo", "open_app", {"name": "Camera"}),
    ("camera chala do", "open_app", {"name": "Camera"}),
    ("camera chalao", "open_app", {"name": "Camera"}),
    ("camera on karo", "open_app", {"name": "Camera"}),
    ("camera dikhao", "open_app", {"name": "Camera"}),
    ("कैमरा खोलो", "open_app", {"name": "Camera"}),
    ("कैमरा खोल दो", "open_app", {"name": "Camera"}),
    ("मेरा कैमरा खोलो", "open_app", {"name": "Camera"}),
    ("कैमरा चालू करो", "open_app", {"name": "Camera"}),
    ("कैमरा ऑन करो", "open_app", {"name": "Camera"}),
    ("कैमरा दिखाओ", "open_app", {"name": "Camera"}),
    ("کیمرہ کھولو", "open_app", {"name": "Camera"}),
    ("کیمرہ کھول دو", "open_app", {"name": "Camera"}),
    ("میرا کیمرہ کھولو", "open_app", {"name": "Camera"}),
    ("کیمرہ چالو کرو", "open_app", {"name": "Camera"}),
    ("کیمرہ آن کرو", "open_app", {"name": "Camera"}),
    ("کیمرہ دکھاؤ", "open_app", {"name": "Camera"}),
    # ---- chrome / browser -> open_app("Google Chrome") ----
    ("open chrome", "open_app", {"name": "Google Chrome"}),
    ("open google chrome", "open_app", {"name": "Google Chrome"}),
    ("open browser", "open_app", {"name": "Google Chrome"}),
    ("open the browser", "open_app", {"name": "Google Chrome"}),
    ("launch chrome", "open_app", {"name": "Google Chrome"}),
    ("launch browser", "open_app", {"name": "Google Chrome"}),
    ("start browser", "open_app", {"name": "Google Chrome"}),
    ("chrome kholo", "open_app", {"name": "Google Chrome"}),
    ("chrome khol do", "open_app", {"name": "Google Chrome"}),
    ("browser kholo", "open_app", {"name": "Google Chrome"}),
    ("browser khol do", "open_app", {"name": "Google Chrome"}),
    ("chrome open karo", "open_app", {"name": "Google Chrome"}),
    ("browser open karo", "open_app", {"name": "Google Chrome"}),
    ("browser chalao", "open_app", {"name": "Google Chrome"}),
    ("chrome chalao", "open_app", {"name": "Google Chrome"}),
    ("क्रोम खोलो", "open_app", {"name": "Google Chrome"}),
    ("ब्राउज़र खोलो", "open_app", {"name": "Google Chrome"}),
    ("ब्राउज़र खोल दो", "open_app", {"name": "Google Chrome"}),
    ("क्रोम चालू करो", "open_app", {"name": "Google Chrome"}),
    ("کروم کھولو", "open_app", {"name": "Google Chrome"}),
    ("براؤزر کھولو", "open_app", {"name": "Google Chrome"}),
    ("کروم چالو کرو", "open_app", {"name": "Google Chrome"}),
    ("براؤزر کھول دو", "open_app", {"name": "Google Chrome"}),
    # edge / firefox (same open_app tool, different hint)
    ("open edge", "open_app", {"name": "Edge"}),
    ("edge kholo", "open_app", {"name": "Edge"}),
    ("एज खोलो", "open_app", {"name": "Edge"}),
    ("ایڈج کھولو", "open_app", {"name": "Edge"}),
    ("open firefox", "open_app", {"name": "Firefox"}),
    ("firefox kholo", "open_app", {"name": "Firefox"}),
    # ---- screenshot ----
    ("take screenshot", "screenshot", {}),
    ("take a screenshot", "screenshot", {}),
    ("screenshot lo", "screenshot", {}),
    ("screenshot le lo", "screenshot", {}),
    ("screenshot le", "screenshot", {}),
    ("screenshot banao", "screenshot", {}),
    ("screen shot lo", "screenshot", {}),
    ("screen ki photo lo", "screenshot", {}),
    ("screen ka screenshot lo", "screenshot", {}),
    ("स्क्रीनशॉट लो", "screenshot", {}),
    ("स्क्रीनशॉट ले लो", "screenshot", {}),
    ("स्क्रीन की फोटो लो", "screenshot", {}),
    ("اسکرین شاٹ لو", "screenshot", {}),
    ("اسکرین کی تصویر لو", "screenshot", {}),
    ("اسکرین شاٹ لے لو", "screenshot", {}),
    # ---- volume up ----
    ("volume up", "volume_up", {"steps": "5"}),
    ("volume badhao", "volume_up", {"steps": "5"}),
    ("volume tez karo", "volume_up", {"steps": "5"}),
    ("awaz badhao", "volume_up", {"steps": "5"}),
    ("awaz tez karo", "volume_up", {"steps": "5"}),
    ("aawaz badhao", "volume_up", {"steps": "5"}),
    ("आवाज़ बढ़ाओ", "volume_up", {"steps": "5"}),
    ("वॉल्यूम बढ़ाओ", "volume_up", {"steps": "5"}),
    ("आवाज़ तेज़ करो", "volume_up", {"steps": "5"}),
    ("آواز بڑھاؤ", "volume_up", {"steps": "5"}),
    ("والیوم بڑھاؤ", "volume_up", {"steps": "5"}),
    ("آواز تیز کرو", "volume_up", {"steps": "5"}),
    # ---- volume down ----
    ("volume down", "volume_down", {"steps": "5"}),
    ("volume kam karo", "volume_down", {"steps": "5"}),
    ("volume kam kar do", "volume_down", {"steps": "5"}),
    ("awaz kam karo", "volume_down", {"steps": "5"}),
    ("aawaz kam karo", "volume_down", {"steps": "5"}),
    ("आवाज़ कम करो", "volume_down", {"steps": "5"}),
    ("वॉल्यूम कम करो", "volume_down", {"steps": "5"}),
    ("آواز کم کرو", "volume_down", {"steps": "5"}),
    ("والیوم کم کرو", "volume_down", {"steps": "5"}),
    # ---- mute ----
    ("mute karo", "mute_toggle", {}),
    ("mute kar do", "mute_toggle", {}),
    ("awaz band karo", "mute_toggle", {}),
    ("volume band karo", "mute_toggle", {}),
    ("म्यूट करो", "mute_toggle", {}),
    ("आवाज़ बंद करो", "mute_toggle", {}),
    ("میوٹ کرو", "mute_toggle", {}),
    ("آواز بند کرو", "mute_toggle", {}),
    # ---- brightness (see module docstring: no native PC tool) ----
    ("brightness badhao", "open_app", {"name": "Settings"}),
    ("brightness barhao", "open_app", {"name": "Settings"}),
    ("brightness zyada karo", "open_app", {"name": "Settings"}),
    ("brightness kam karo", "open_app", {"name": "Settings"}),
    ("brightness kam kar do", "open_app", {"name": "Settings"}),
    ("brightness up", "open_app", {"name": "Settings"}),
    ("brightness down", "open_app", {"name": "Settings"}),
    ("screen brightness", "open_app", {"name": "Settings"}),
    ("screen ki roshni badhao", "open_app", {"name": "Settings"}),
    ("screen ki roshni kam karo", "open_app", {"name": "Settings"}),
    ("ब्राइटनेस बढ़ाओ", "open_app", {"name": "Settings"}),
    ("ब्राइटनेस कम करो", "open_app", {"name": "Settings"}),
    ("स्क्रीन की रोशनी बढ़ाओ", "open_app", {"name": "Settings"}),
    ("برائٹنیس بڑھاؤ", "open_app", {"name": "Settings"}),
    ("برائٹنیس کم کرو", "open_app", {"name": "Settings"}),
    ("اسکرین کی روشنی بڑھاؤ", "open_app", {"name": "Settings"}),
    ("اسکرین کی روشنی کم کرو", "open_app", {"name": "Settings"}),
    # light / lamp brightness -> smart-home tool (only when a light is named)
    ("light brightness", "ha_set_brightness", {"query": "light"}),
    ("light ki brightness", "ha_set_brightness", {"query": "light"}),
    ("batti ki roshni", "ha_set_brightness", {"query": "light"}),
    ("बत्ती की रोशनी", "ha_set_brightness", {"query": "light"}),
    ("بتی کی روشنی", "ha_set_brightness", {"query": "light"}),
    # ---- notepad ----
    ("open notepad", "open_app", {"name": "Notepad"}),
    ("notepad kholo", "open_app", {"name": "Notepad"}),
    ("notepad khol do", "open_app", {"name": "Notepad"}),
    ("notepad open karo", "open_app", {"name": "Notepad"}),
    ("नोटपैड खोलो", "open_app", {"name": "Notepad"}),
    ("نوٹ پیڈ کھولو", "open_app", {"name": "Notepad"}),
    # ---- calculator ----
    ("open calculator", "open_app", {"name": "Calculator"}),
    ("calculator kholo", "open_app", {"name": "Calculator"}),
    ("calculator khol do", "open_app", {"name": "Calculator"}),
    ("कैलकुलेटर खोलो", "open_app", {"name": "Calculator"}),
    ("کیلکولیٹر کھولو", "open_app", {"name": "Calculator"}),
    # ---- settings ----
    ("open settings", "open_app", {"name": "Settings"}),
    ("settings kholo", "open_app", {"name": "Settings"}),
    ("settings khol do", "open_app", {"name": "Settings"}),
    ("सेटिंग्स खोलो", "open_app", {"name": "Settings"}),
    ("سیٹنگز کھولو", "open_app", {"name": "Settings"}),
    # ---- youtube ----
    ("open youtube", "play_on_youtube", {"query": ""}),
    ("youtube kholo", "play_on_youtube", {"query": ""}),
    ("youtube khol do", "play_on_youtube", {"query": ""}),
    ("यूट्यूब खोलो", "play_on_youtube", {"query": ""}),
    ("یوٹیوب کھولو", "play_on_youtube", {"query": ""}),
    # ---- whatsapp ----
    ("open whatsapp", "open_app", {"name": "WhatsApp"}),
    ("whatsapp kholo", "open_app", {"name": "WhatsApp"}),
    ("whatsapp khol do", "open_app", {"name": "WhatsApp"}),
    ("व्हाट्सऐप खोलो", "open_app", {"name": "WhatsApp"}),
    ("واٹس ایپ کھولو", "open_app", {"name": "WhatsApp"}),
    # ---- lock / shutdown ----
    ("lock pc", "lock_pc", {}),
    ("lock karo", "lock_pc", {}),
    ("pc lock karo", "lock_pc", {}),
    ("पीसी लॉक करो", "lock_pc", {}),
    ("پی سی لاک کرو", "lock_pc", {}),
    ("shutdown pc", "shutdown_pc", {}),
    ("shutdown karo", "shutdown_pc", {}),
    ("pc band karo", "shutdown_pc", {}),
    ("पीसी बंद करो", "shutdown_pc", {}),
    ("پی سی بند کرو", "shutdown_pc", {}),
    # ---- time ----
    ("what time", "current_time", {}),
    ("time kya hai", "current_time", {}),
    ("kitne baje", "current_time", {}),
    ("kitne baje hain", "current_time", {}),
    ("टाइम क्या है", "current_time", {}),
    ("कितने बजे", "current_time", {}),
    ("ٹائم کیا ہے", "current_time", {}),
    ("کتنے بجے", "current_time", {}),
    ("کتنے بجے ہیں", "current_time", {}),
    # ---- reminder ----
    ("remind me", "add_reminder", {}),
    ("yaad dilao", "add_reminder", {}),
    ("yaad dila do", "add_reminder", {}),
    ("reminder lagao", "add_reminder", {}),
    ("मुझे याद दिलाओ", "add_reminder", {}),
    ("یاد دلاؤ", "add_reminder", {}),
    ("یاد دلا دو", "add_reminder", {}),
    # ---- music ----
    ("play music", "media_play_pause", {}),
    ("music chalao", "media_play_pause", {}),
    ("gaana chalao", "media_play_pause", {}),
    ("gana chalao", "media_play_pause", {}),
    ("गाना चलाओ", "media_play_pause", {}),
    ("گانا چلاؤ", "media_play_pause", {}),
    ("pause karo", "media_play_pause", {}),
    # ---- weather ----
    ("weather", "get_weather", {}),
    ("mausam", "get_weather", {}),
    ("mausam kaisa hai", "get_weather", {}),
    ("मौसम", "get_weather", {}),
    ("मौसम कैसा है", "get_weather", {}),
    ("موسم", "get_weather", {}),
    ("موسم کیسا ہے", "get_weather", {}),
]

def normalize_query(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Unicode-safe: keeps
    letters AND combining marks (e.g. Devanagari vowel signs like ै in कै,
    which ``\\w`` does NOT match — a plain ``[^\\w\\s]`` strip would shred
    Devanagari phrases). Only Unicode punctuation / symbols / controls are
    replaced with spaces."""
    if not text:
        return ""
    # NFKC so full-width / compatibility forms match plain forms.
    t = unicodedata.normalize("NFKC", text).lower()
    kept = []
    for ch in t:
        cat = unicodedata.category(ch)
        kept.append(" " if cat[0] in ("P", "S", "C") else ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip()


def match_synonyms(query: str, limit: int = 8) -> list[dict]:
    """Return candidate tools for ``query``: [{tool, args, phrase}].

    Substring match on the normalized query, longest phrase first per tool.
    Returns [] when nothing matches — the router then uses BM25 / fallback.
    """
    norm = normalize_query(query)
    if not norm:
        return []
    best: dict[str, dict] = {}
    for phrase, tool, args in SYNONYM_ENTRIES:
        # Normalize the stored phrase the same way (Devanagari combining
        # marks must survive on both sides of the comparison).
        nphrase = normalize_query(phrase)
        if nphrase and nphrase in norm:
            prev = best.get(tool)
            # Keep the longest (most specific) matching phrase per tool.
            if prev is None or len(nphrase) > len(prev["phrase"]):
                best[tool] = {"tool": tool, "args": dict(args), "phrase": nphrase}
    ranked = sorted(best.values(), key=lambda m: len(m["phrase"]), reverse=True)
    return ranked[:limit]


def synonym_tool_names(query: str) -> set[str]:
    """Tool names the synonym map suggests for ``query`` (empty if none)."""
    return {m["tool"] for m in match_synonyms(query)}
