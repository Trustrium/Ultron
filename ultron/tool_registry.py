"""Tool registry — the full catalog of Ultron tools (definitions + handlers).

Split out of brain.py so the brain's run-loop and the tool catalog are separate
concerns. Brain imports TOOLS / TOOL_HANDLERS / _load_plugins_once from here.
"""
from __future__ import annotations
from typing import Any

from .tools import apps as t_apps
from .tools import system as t_system
from .tools import reminders as t_reminders
from .tools import memory as t_memory
from .tools import code as t_code
from .tools import winget as t_winget
from .tools import vision as t_vision
from .tools import whatsapp as t_whatsapp
from .tools import gmail as t_gmail
from .tools import briefing as t_briefing
from .tools import notes as t_notes
from .tools import clipboard as t_clipboard
from .tools import translate as t_translate
from .tools import file_search as t_file_search
from .tools import calendar_gcal as t_calendar
from .tools import recall_similar as t_recall
from .tools import web_fetch as t_web
from .tools import news as t_news
from .tools import document as t_doc
from .tools import skills as t_skills
from .tools import python_exec as t_pyexec
from .tools import image_gen as t_img
from .tools import file_ops as t_fileops
from .tools import convert as t_convert
from .tools import web_search_real as t_websearch
from .tools import ocr as t_ocr
from .tools import quotes as t_quotes
from .tools import automation as t_auto
from .tools import windows_mgmt as t_win
from .tools import timer as t_timer
from .tools import research as t_research
from .tools import vision_click as t_vclick
from .tools import email_draft as t_edraft
from .tools import planner as t_planner
from . import routines as t_routines
from .tools import system_monitor as t_sysmon
from .tools import network as t_net
from .tools import spreadsheet as t_sheet
from .tools import computer_use as t_compuse
from .tools import self_extend as t_selfext
from .tools import knowledge as t_know
from .tools import documents_create as t_doccreate
from .tools import qr as t_qr
from .tools import git_tools as t_git
from .tools import tasks as t_tasks
from .tools import contacts as t_contacts
from .tools import expenses as t_expenses
from .tools import shopping as t_shopping
from .tools import maps as t_maps
from .tools import habits as t_habits
from .tools import health as t_health
from .tools import journal as t_journal
from .tools import voice_memo as t_memo
from .tools import image_edit as t_imgedit
from .tools import pdf_tools as t_pdf
from .tools import organize as t_organize
from .tools import local_music as t_music
from .tools import focus as t_focus
from .tools import scheduling as t_sched
from .tools import profile as t_profile
from .tools import excel as t_excel
from .tools import smart_home as t_ha
from .tools import phone as t_phone
from . import watchers as t_watch
from .plugins_loader import load_plugins, reserved_names_check
from . import settings as _settings


def _tool(name: str, description: str, properties: dict, required: list | None = None) -> dict:
    # Two robustness fixes for strict tool-call validators (Groq/Llama):
    #  1. Strip JSON-Schema 'default' — its presence makes some models emit
    #     numbers as strings, which then fail validation.
    #  2. Declare integer/number params as 'string' in the SCHEMA. Models reliably
    #     emit strings; our handlers already coerce via _int()/float(). This avoids
    #     "expected number, but got string" 400s entirely. (A note is added to the
    #     param description so the model still knows it's numeric.)
    cleaned_props = {}
    for k, v in properties.items():
        prop = {kk: vv for kk, vv in v.items() if kk != "default"}
        if prop.get("type") in ("integer", "number"):
            kind = prop["type"]
            prop["type"] = "string"
            desc = prop.get("description", "")
            prop["description"] = (desc + f" ({kind} value as a string)").strip()
        cleaned_props[k] = prop
    params: dict = {"type": "object", "properties": cleaned_props}
    if required:
        params["required"] = required
    return {"name": name, "description": description, "parameters": params}


def _int(value, default: int) -> int:
    """Coerce tool arguments to int (defensive against models that send '25' instead of 25)."""
    try:
        return int(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default


def _set_personality(personality_id: str) -> str:
    """Switch Ultron's tone for future replies — persists across sessions."""
    from .personality import PERSONALITY_PRESETS
    pid = (personality_id or "").lower().strip()
    if pid not in PERSONALITY_PRESETS:
        return (f"Unknown personality '{personality_id}'. Choose from: "
                f"{', '.join(PERSONALITY_PRESETS.keys())}")
    _settings.save({"personality": pid})
    return f"Personality switched to '{pid}'. New tone applies to the next reply."


TOOLS: list[dict] = [
    # --- apps / web ---
    _tool("open_app", "Open ANY installed app or website by name. Searches the full Start-menu + "
                      "Microsoft Store app list, so it works for apps beyond the common ones.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("list_apps", "List installed apps on this PC, optionally filtered by a search term.",
          {"query": {"type": "string"}, "limit": {"type": "integer"}}),
    _tool("refresh_apps", "Rebuild the installed-app index (use after installing new software).", {}),
    _tool("open_website", "Open a URL in the default browser.",
          {"url": {"type": "string"}}, ["url"]),
    _tool("web_search", "Open Google search results for the query.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("play_on_youtube", "Open YouTube search results for the query.",
          {"query": {"type": "string"}}, ["query"]),

    # --- reminders ---
    _tool("add_reminder",
          "Add a reminder. 'when' accepts 'YYYY-MM-DD HH:MM', 'in 30 minutes', 'in 2 hours', "
          "'tomorrow 9am', 'today 6pm', or a day-of-week like 'monday 9am'. "
          "'recurrence' is one of: once (default) | daily | weekly | weekdays | monthly | yearly.",
          {"text": {"type": "string"},
           "when": {"type": "string"},
           "recurrence": {"type": "string", "default": "once"}},
          ["text", "when"]),
    _tool("list_reminders", "List pending reminders.", {}),
    _tool("delete_reminder", "Delete a reminder by short id.",
          {"reminder_id": {"type": "string"}}, ["reminder_id"]),

    # --- system ---
    _tool("volume_up", "Increase volume.", {"steps": {"type": "integer", "default": 5}}),
    _tool("volume_down", "Decrease volume.", {"steps": {"type": "integer", "default": 5}}),
    _tool("mute_toggle", "Toggle mute.", {}),
    _tool("lock_pc", "Lock the PC.", {}),
    _tool("sleep_pc", "Put PC to sleep. Destructive — confirm first.", {}),
    _tool("shutdown_pc", "Shutdown PC. Destructive — confirm first.",
          {"seconds": {"type": "integer", "default": 30}}),
    _tool("cancel_shutdown", "Cancel pending shutdown.", {}),
    _tool("screenshot", "Save a screenshot to Desktop.", {}),
    _tool("current_time", "Get the current local time.", {}),

    # --- media keys ---
    _tool("media_play_pause", "Play or pause whatever is currently playing music or video (Spotify, YouTube, etc).", {}),
    _tool("media_next", "Skip to the next track.", {}),
    _tool("media_prev", "Go to the previous track.", {}),
    _tool("media_stop", "Stop media playback.", {}),

    # --- long-term memory ---
    _tool("remember",
          "Save a fact for later sessions. Use short kebab-case keys (e.g., 'birthday', 'amma-phone').",
          {"key": {"type": "string"}, "value": {"type": "string"}}, ["key", "value"]),
    _tool("recall", "Recall a saved fact by key, or list all if no key.", {"key": {"type": "string"}}),
    _tool("forget", "Delete a saved fact by key.", {"key": {"type": "string"}}, ["key"]),

    # --- code / files / shell ---
    _tool("read_file", "Read a text file from disk.", {"path": {"type": "string"}}, ["path"]),
    _tool("write_file", "Write content to a file (overwrites).",
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _tool("append_file", "Append content to a file.",
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _tool("list_dir", "List the contents of a directory.", {"path": {"type": "string", "default": "."}}),
    _tool("run_shell",
          "Run a PowerShell command on Windows. Dangerous commands are refused. Confirm with user first.",
          {"command": {"type": "string"}, "timeout": {"type": "integer", "default": 30}}, ["command"]),

    # --- winget ---
    _tool("winget_search", "Search winget for an app.", {"query": {"type": "string"}}, ["query"]),
    _tool("winget_install", "Install an app by winget package ID. Confirm with user first.",
          {"package_id": {"type": "string"}}, ["package_id"]),
    _tool("winget_uninstall", "Uninstall an app by winget package ID. Confirm with user first.",
          {"package_id": {"type": "string"}}, ["package_id"]),

    # --- vision ---
    _tool("describe_screen",
          "Take a screenshot and ask the vision model what's on it.",
          {"question": {"type": "string"}}),

    # --- whatsapp ---
    _tool("send_whatsapp",
          "Send a WhatsApp message via WhatsApp Web. Recipient can be a contact name OR phone with country code. Confirm first.",
          {"recipient": {"type": "string"}, "message": {"type": "string"}}, ["recipient", "message"]),
    _tool("list_whatsapp_chats", "List the most recent WhatsApp chats with last-message preview.",
          {"count": {"type": "integer", "default": 10}}),
    _tool("read_whatsapp_chat",
          "Open a WhatsApp chat by contact name and read the last N messages.",
          {"name": {"type": "string"}, "count": {"type": "integer", "default": 10}}, ["name"]),

    # --- gmail ---
    _tool("list_inbox", "List the latest N inbox emails.", {"max_results": {"type": "integer", "default": 5}}),
    _tool("search_emails", "Search Gmail. Examples: 'from:boss', 'is:unread', 'subject:invoice newer_than:7d'.",
          {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 5}}, ["query"]),
    _tool("send_email", "Send an email via Gmail. Confirm recipient + body with user first.",
          {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
          ["to", "subject", "body"]),

    # --- daily briefing ---
    _tool("daily_briefing",
          "Give a short voice-friendly daily briefing: greeting, today's reminders, "
          "and unread emails. Use when the user says 'good morning', 'brief me', "
          "'what's my day', or asks for a summary.",
          {}),

    # --- semantic recall + personality ---
    _tool("recall_similar",
          "Search the user's past conversations, notes, and saved memories for anything "
          "relevant to a query. Use when the user references something that might be in "
          "history ('what did I say about X?', 'I told you something about...').",
          {"query": {"type": "string"}, "k": {"type": "integer"}}, ["query"]),
    _tool("set_personality",
          "Change Ultron's tone of voice. personality_id is one of: "
          "ultron | casual | concise | witty | professional. "
          "Use when the user says 'be more X' or 'switch to Y mode'.",
          {"personality_id": {"type": "string"}}, ["personality_id"]),

    # --- v6: web + news + documents + skills + sandbox ---
    _tool("fetch_url",
          "Fetch a URL, extract the readable text, and answer a question about it "
          "(or summarize if no question). Use for 'what's on this page', "
          "'summarize this article', 'what does Wikipedia say about X'.",
          {"url": {"type": "string"}, "question": {"type": "string"}}, ["url"]),
    _tool("news_briefing",
          "Get top news headlines. Optional `topic` filters to a subject (e.g. 'AI', "
          "'Tamil Nadu', 'climate'). With no topic, returns Hacker News top + general world headlines.",
          {"topic": {"type": "string"}, "count": {"type": "integer"}}),
    _tool("ask_document",
          "Read a local file (PDF or text) and answer a question about its contents. "
          "Use when user asks 'what's in this file', 'summarize this PDF', 'what does X say about Y'.",
          {"path": {"type": "string"}, "question": {"type": "string"}}, ["path"]),
    _tool("create_skill",
          "Save a sequence of tool calls as a named skill the user can replay later. "
          "Steps is a list of {tool, args} dicts. Use when user says 'create a skill called X that does Y, Z'.",
          {"name": {"type": "string"}, "steps": {"type": "array"}}, ["name", "steps"]),
    _tool("run_skill",
          "Replay a previously saved skill by name. Use when user says 'run my morning routine' etc.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("list_skills", "List all saved skill macros.", {}),
    _tool("delete_skill", "Delete a saved skill by name.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("run_python",
          "Execute a Python snippet in an isolated subprocess for calculations / data "
          "manipulation / date math. Has a hard timeout. Use for things the LLM can't "
          "compute reliably (precise arithmetic, regex, date arithmetic).",
          {"code": {"type": "string"}, "timeout": {"type": "integer"}}, ["code"]),

    # ===== v7: image gen / file ops / convert / web search / OCR / quotes =====
    _tool("generate_image",
          "Generate an image from a text prompt (saves to Desktop). Uses Pollinations.ai (free).",
          {"prompt": {"type": "string"},
           "width": {"type": "integer"}, "height": {"type": "integer"}}, ["prompt"]),

    _tool("copy_file",   "Copy a file or directory. Confirm with user first.",
          {"src": {"type": "string"}, "dst": {"type": "string"}}, ["src", "dst"]),
    _tool("move_file",   "Move (or rename across folders) a file. Confirm with user first.",
          {"src": {"type": "string"}, "dst": {"type": "string"}}, ["src", "dst"]),
    _tool("rename_file", "Rename a file in place. Confirm with user first.",
          {"path": {"type": "string"}, "new_name": {"type": "string"}}, ["path", "new_name"]),
    _tool("make_dir",    "Create a directory (and any missing parents).",
          {"path": {"type": "string"}}, ["path"]),
    _tool("delete_file",
          "Delete a file. By default sends to Recycle Bin (reversible). "
          "Set permanent=true ONLY when the user explicitly says 'permanently delete'.",
          {"path": {"type": "string"}, "permanent": {"type": "boolean"}}, ["path"]),

    _tool("convert_currency",
          "Convert an amount from one currency to another using live FX rates.",
          {"amount": {"type": "number"},
           "from_currency": {"type": "string"}, "to_currency": {"type": "string"}},
          ["amount", "from_currency", "to_currency"]),
    _tool("convert_unit",
          "Convert between physical units. Supports length, mass, time, volume, temperature.",
          {"amount": {"type": "number"},
           "from_unit": {"type": "string"}, "to_unit": {"type": "string"}},
          ["amount", "from_unit", "to_unit"]),

    _tool("web_search_real",
          "Run a real web search and return top result titles + URLs + snippets. "
          "Different from `web_search` which only opens a browser tab.",
          {"query": {"type": "string"}, "max_results": {"type": "integer"}}, ["query"]),

    _tool("ocr_screen",
          "Take a screenshot and extract all visible text from it. Optional 'question' "
          "narrows the output to lines matching the question's keywords.",
          {"question": {"type": "string"}}),
    _tool("ocr_image",
          "Extract text from a local image file.",
          {"path": {"type": "string"}, "question": {"type": "string"}}, ["path"]),

    _tool("stock_quote",
          "Get current stock price + day change. Examples: AAPL, MSFT, TCS.NS, INFY.NS.",
          {"symbol": {"type": "string"}}, ["symbol"]),
    _tool("cricket_score",
          "Live cricket scores from cricbuzz. Optional `query` filters (e.g. 'India', 'IPL').",
          {"query": {"type": "string"}}),

    # ===== v8: screen automation / windows / timers =====
    _tool("type_text",
          "Type text into whatever currently has keyboard focus. Confirm with user before "
          "typing into anything sensitive.",
          {"text": {"type": "string"}}, ["text"]),
    _tool("press_keys",
          "Press a key or hotkey combo. Examples: 'enter', 'ctrl+s', 'alt+tab', 'win+d', 'ctrl+c'.",
          {"keys": {"type": "string"}}, ["keys"]),
    _tool("mouse_click",
          "Click the mouse. Provide x,y to click a specific point, or omit to click the current "
          "position. button = left|right|middle. Confirm before clicking.",
          {"x": {"type": "integer"}, "y": {"type": "integer"},
           "button": {"type": "string"}, "clicks": {"type": "integer"}}),
    _tool("scroll", "Scroll the active window. Negative = down, positive = up.",
          {"amount": {"type": "integer"}}),
    _tool("screen_size", "Get the screen resolution.", {}),

    _tool("list_windows", "List the titles of all open windows.", {}),
    _tool("active_window", "Get the title of the currently focused window.", {}),
    _tool("focus_window", "Bring a window to the front by a title substring.",
          {"title": {"type": "string"}}, ["title"]),
    _tool("minimize_window", "Minimize a window by title substring.",
          {"title": {"type": "string"}}, ["title"]),
    _tool("maximize_window", "Maximize a window by title substring.",
          {"title": {"type": "string"}}, ["title"]),
    _tool("close_window", "Close a window by title substring. Confirm with user first.",
          {"title": {"type": "string"}}, ["title"]),

    _tool("set_timer",
          "Set a countdown timer that fires like a reminder. Provide minutes and/or seconds.",
          {"minutes": {"type": "number"}, "seconds": {"type": "number"},
           "label": {"type": "string"}}),

    # ===== v9: agentic — research / vision-click / email drafting =====
    _tool("research",
          "Deep-research a topic: searches the web, reads the top results, and synthesizes "
          "a briefing with sources. Use for 'research X', 'find out about Y', 'compare Z'.",
          {"topic": {"type": "string"}, "depth": {"type": "integer"},
           "save_note": {"type": "boolean"}}, ["topic"]),
    _tool("find_on_screen",
          "Locate a UI element on screen by description and return its coordinates (no click).",
          {"description": {"type": "string"}}, ["description"]),
    _tool("click_on_screen",
          "Find a UI element by description (e.g. 'the blue Submit button', 'the search box') "
          "using screen vision, then click it. Confirm with the user before clicking.",
          {"description": {"type": "string"}, "button": {"type": "string"},
           "double": {"type": "boolean"}}, ["description"]),
    _tool("draft_email_reply",
          "Read a recent email (by Gmail query, default unread) and draft a reply for review. "
          "Does NOT send. `instructions` steers tone/content.",
          {"query": {"type": "string"}, "instructions": {"type": "string"}}),

    # ===== v10: autonomous agent =====
    _tool("accomplish",
          "Autonomously complete a COMPLEX multi-step goal end-to-end (plans, executes many "
          "tools, self-corrects). Use ONLY for genuinely multi-step tasks like 'research X and "
          "save a note', 'open Y, find Z, and do W'. For single actions, call the specific tool "
          "directly instead.",
          {"goal": {"type": "string"}, "max_steps": {"type": "integer"}}, ["goal"]),
    _tool("plan_task",
          "Produce a step-by-step plan for a goal WITHOUT executing it. Use when the user asks "
          "'how would you do X' or wants to review a plan first.",
          {"goal": {"type": "string"}}, ["goal"]),
    _tool("auto_pilot",
          "FULL HANDS-FREE mode: complete an entire complex task autonomously with NO further "
          "confirmation — plans, executes many tools (incl. screen control), self-corrects, and "
          "only reports at the end. Use when the user says 'do it all yourself', 'fully automatic', "
          "or gives a big task and won't be available. Hard safety limits still apply.",
          {"goal": {"type": "string"}, "max_steps": {"type": "integer"}}, ["goal"]),
    _tool("stop_autopilot", "Abort a running auto-pilot / autonomous run.", {}),

    # ===== v11: scheduled autonomous routines =====
    _tool("create_routine",
          "Create a recurring routine that autonomously runs a goal on a schedule. "
          "schedule_type: daily | hourly | weekly. time is 24h HH:MM. day is a weekday "
          "name (for weekly). Example goal: 'brief me on weather, news, and today reminders'.",
          {"name": {"type": "string"}, "goal": {"type": "string"},
           "schedule_type": {"type": "string"}, "time": {"type": "string"},
           "day": {"type": "string"}}, ["name", "goal"]),
    _tool("list_routines", "List all scheduled routines.", {}),
    _tool("delete_routine", "Delete a routine by name.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("run_routine_now", "Run a saved routine immediately (autonomously).",
          {"name": {"type": "string"}}, ["name"]),

    # ===== v12: system / network / data =====
    _tool("system_info", "Get a PC health snapshot: CPU, RAM, disk, battery, uptime.", {}),
    _tool("top_processes", "List the top processes by 'memory' or 'cpu' usage.",
          {"n": {"type": "integer"}, "by": {"type": "string"}}),
    _tool("find_process", "Find running processes matching a name.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("kill_process", "Terminate processes matching a name. Destructive — confirm first.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("network_info", "Full network summary: connectivity, local IP, public IP, WiFi.", {}),
    _tool("check_internet", "Quick check whether the internet is reachable + latency.", {}),
    _tool("analyze_spreadsheet",
          "Read a CSV or Excel file and answer a question about the data (or summarize it).",
          {"path": {"type": "string"}, "question": {"type": "string"}}, ["path"]),

    # ===== v13: frontier — computer-use, self-extension, knowledge base =====
    _tool("operate_computer",
          "AUTONOMOUSLY control the screen to accomplish a GUI goal: it screenshots, decides "
          "the next click/type/scroll/key, acts, re-observes, and repeats. Use for multi-step "
          "on-screen tasks ('fill this form', 'navigate to X and click Y'). Confirm with user first.",
          {"goal": {"type": "string"}, "max_steps": {"type": "integer"}}, ["goal"]),
    _tool("create_plugin",
          "Write a NEW tool/plugin for Ultron from a description, then load it live. Use when the "
          "user wants a capability that doesn't exist yet and it can be done with pure Python.",
          {"name": {"type": "string"}, "description": {"type": "string"}}, ["name", "description"]),
    _tool("index_folder",
          "Index a folder of documents (txt/md/pdf/csv) into a searchable knowledge base.",
          {"folder": {"type": "string"}}, ["folder"]),
    _tool("ask_knowledge",
          "Answer a question across all documents in a folder (auto-indexes if needed).",
          {"folder": {"type": "string"}, "question": {"type": "string"}}, ["folder", "question"]),

    # ===== v14: create documents / QR / git =====
    _tool("create_pdf", "Create a PDF document from text content (saves to Desktop by default).",
          {"content": {"type": "string"}, "title": {"type": "string"}, "path": {"type": "string"}},
          ["content"]),
    _tool("create_docx", "Create a Word (.docx) document from text content.",
          {"content": {"type": "string"}, "title": {"type": "string"}, "path": {"type": "string"}},
          ["content"]),
    _tool("create_markdown", "Create a Markdown (.md) file from text content.",
          {"content": {"type": "string"}, "title": {"type": "string"}, "path": {"type": "string"}},
          ["content"]),
    _tool("generate_qr", "Generate a QR code PNG encoding text or a URL.",
          {"data": {"type": "string"}, "path": {"type": "string"}}, ["data"]),
    _tool("generate_wifi_qr", "Generate a QR code that lets phones join a WiFi network.",
          {"ssid": {"type": "string"}, "password": {"type": "string"},
           "security": {"type": "string"}}, ["ssid", "password"]),
    _tool("git_status", "Show git status of a repo (default current dir).",
          {"repo": {"type": "string"}}),
    _tool("git_log", "Show recent git commits of a repo.",
          {"repo": {"type": "string"}, "n": {"type": "integer"}}),
    _tool("git_diff", "Show a git diff stat of a repo.",
          {"repo": {"type": "string"}, "staged": {"type": "boolean"}}),
    _tool("git_branches", "List branches of a repo.", {"repo": {"type": "string"}}),
    _tool("git_commit", "Stage all + commit a repo with a message. Confirm first. Does NOT push.",
          {"repo": {"type": "string"}, "message": {"type": "string"}}, ["message"]),

    # --- notes ---
    _tool("add_note",
          "Save a quick note to the user's notes file. Use when the user says "
          "'take a note', 'remember this', or wants to jot down something they don't "
          "need a reminder for. 'tag' is an optional category like 'idea' or 'todo'.",
          {"text": {"type": "string"}, "tag": {"type": "string", "default": ""}}, ["text"]),
    _tool("list_notes", "List recent notes, optionally filtered by a query.",
          {"max_results": {"type": "integer", "default": 10},
           "query": {"type": "string", "default": ""}}),

    # --- clipboard ---
    _tool("read_clipboard", "Read the current Windows clipboard contents.", {}),
    _tool("write_clipboard", "Replace clipboard contents with the given text.",
          {"text": {"type": "string"}}, ["text"]),
    _tool("append_clipboard", "Append text to the current clipboard contents.",
          {"text": {"type": "string"}}, ["text"]),

    # --- translation ---
    _tool("translate",
          "Translate text into a target language (e.g. 'tamil', 'english', 'hindi'). "
          "Use when user explicitly asks to translate something.",
          {"text": {"type": "string"},
           "target_language": {"type": "string", "default": "english"}}, ["text"]),

    # --- file search ---
    _tool("find_files",
          "Search the user's Desktop / Documents / Downloads for files by name "
          "(substring or glob like '*.pdf') and optionally by content. Use when "
          "user says 'find my resume', 'where is the X file', etc.",
          {"name_pattern": {"type": "string", "default": ""},
           "content_query": {"type": "string", "default": ""},
           "max_results": {"type": "integer", "default": 25}}),

    # --- google calendar ---
    _tool("list_today_events", "List today's events from the user's primary Google Calendar.", {}),
    _tool("list_week_events", "List events for the next 7 days from Google Calendar.", {}),
    _tool("add_calendar_event",
          "Add an event to the user's Google Calendar. start_time accepts "
          "'YYYY-MM-DD HH:MM'. duration_minutes defaults to 60. Confirm with user before adding.",
          {"summary": {"type": "string"},
           "start_time": {"type": "string"},
           "duration_minutes": {"type": "integer", "default": 60},
           "description": {"type": "string", "default": ""},
           "location": {"type": "string", "default": ""}},
          ["summary", "start_time"]),

    # ===== v17: personal life manager — tasks / contacts / expenses / shopping =====
    _tool("add_task", "Add a to-do task. priority is low | normal | high.",
          {"text": {"type": "string"}, "priority": {"type": "string"}}, ["text"]),
    _tool("list_tasks", "List pending to-do tasks (set include_done true to show completed).",
          {"include_done": {"type": "boolean"}}),
    _tool("complete_task", "Mark a task done by its id or text.",
          {"task_id": {"type": "string"}}, ["task_id"]),
    _tool("delete_task", "Delete a task by id or text.", {"task_id": {"type": "string"}}, ["task_id"]),

    _tool("add_contact", "Save a person's contact details.",
          {"name": {"type": "string"}, "phone": {"type": "string"},
           "email": {"type": "string"}, "notes": {"type": "string"}}, ["name"]),
    _tool("find_contact", "Look up a contact by name, phone, or email.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("list_contacts", "List all saved contacts.", {}),

    _tool("log_expense", "Log a spend. amount + optional category (food/travel/etc.) + note.",
          {"amount": {"type": "number"}, "category": {"type": "string"},
           "note": {"type": "string"}}, ["amount"]),
    _tool("expense_summary", "Summarize expenses by category for today | week | month | all.",
          {"period": {"type": "string"}}),

    _tool("add_shopping_item", "Add an item to the shopping list (optional quantity).",
          {"item": {"type": "string"}, "qty": {"type": "string"}}, ["item"]),
    _tool("list_shopping", "Show the shopping list.", {}),
    _tool("check_shopping_item", "Check off a shopping item as bought.",
          {"item": {"type": "string"}}, ["item"]),
    _tool("clear_shopping", "Clear the whole shopping list.", {}),

    # ===== v18: maps & directions =====
    _tool("map_distance", "Driving distance + time between two places.",
          {"origin": {"type": "string"}, "destination": {"type": "string"}},
          ["origin", "destination"]),
    _tool("map_directions", "Open turn-by-turn directions between two places in the browser.",
          {"origin": {"type": "string"}, "destination": {"type": "string"}},
          ["origin", "destination"]),
    _tool("find_place", "Locate a place/address and report coordinates.",
          {"query": {"type": "string"}}, ["query"]),

    # ===== v19: wellbeing — habits / health / journal =====
    _tool("add_habit", "Create a daily habit to track with streaks.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("check_habit", "Mark a habit done for today (builds the streak).",
          {"name": {"type": "string"}}, ["name"]),
    _tool("list_habits", "List habits with today's status + current streaks.", {}),
    _tool("delete_habit", "Delete a habit.", {"name": {"type": "string"}}, ["name"]),

    _tool("log_health",
          "Log a health metric: water | weight | mood | steps | medication | sleep.",
          {"metric": {"type": "string"}, "value": {"type": "string"},
           "note": {"type": "string"}}, ["metric"]),
    _tool("health_summary", "Summarize health logs for today | week | all.",
          {"period": {"type": "string"}}),

    _tool("add_journal_entry", "Write a journal entry (dated automatically).",
          {"text": {"type": "string"}}, ["text"]),
    _tool("read_journal", "Read journal entries: 'recent', 'today', or a date YYYY-MM-DD.",
          {"when": {"type": "string"}, "count": {"type": "integer"}}),

    # ===== v20: media & file utilities =====
    _tool("record_voice_memo",
          "Record a voice memo for N seconds, save it to Desktop, and transcribe it.",
          {"seconds": {"type": "integer"}, "transcribe": {"type": "boolean"}}),
    _tool("resize_image", "Resize an image (give width and/or height; keeps aspect if one).",
          {"path": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}},
          ["path"]),
    _tool("convert_image", "Convert an image to another format (png/jpg/webp/bmp/gif).",
          {"path": {"type": "string"}, "to_format": {"type": "string"}}, ["path"]),
    _tool("rotate_image", "Rotate an image by degrees (clockwise).",
          {"path": {"type": "string"}, "degrees": {"type": "integer"}}, ["path"]),
    _tool("merge_pdfs", "Merge multiple PDF files (in order) into one.",
          {"paths": {"type": "array"}, "output": {"type": "string"}}, ["paths"]),
    _tool("split_pdf", "Split a PDF into pages, or by ranges like '1-3,4-6'.",
          {"path": {"type": "string"}, "ranges": {"type": "string"}}, ["path"]),
    _tool("pdf_info", "Get page count + metadata of a PDF.", {"path": {"type": "string"}}, ["path"]),
    _tool("organize_folder",
          "Sort loose files in a folder into category subfolders (Images/Documents/Videos/...). "
          "Set dry_run true to preview the plan first.",
          {"folder": {"type": "string"}, "dry_run": {"type": "boolean"}}, ["folder"]),

    # ===== v21: music / focus / scheduling =====
    _tool("play_music", "Play a song from the user's Music/Downloads folders by name.",
          {"query": {"type": "string"}}),
    _tool("list_music", "List local music tracks, optionally filtered by a search term.",
          {"query": {"type": "string"}, "limit": {"type": "integer"}}),
    _tool("start_pomodoro",
          "Start a Pomodoro focus session: (work + break) x cycles, with a nudge at each "
          "transition. Defaults 25 work / 5 break / 4 cycles.",
          {"work_minutes": {"type": "integer"}, "break_minutes": {"type": "integer"},
           "cycles": {"type": "integer"}}),
    _tool("find_free_time",
          "Find free time slots in Google Calendar for 'today' | 'tomorrow' | YYYY-MM-DD, "
          "within working hours (default 09:00-21:00).",
          {"date": {"type": "string"}, "work_start": {"type": "string"},
           "work_end": {"type": "string"}, "min_slot_minutes": {"type": "integer"}}),

    # ===== Personal profile — Ultron knows you =====
    _tool("set_profile",
          "Save a structured fact about the user. field is one of: name, nickname, location, "
          "work, role, birthday, languages, family, preferences, goals, important_dates, notes.",
          {"field": {"type": "string"}, "value": {"type": "string"}}, ["field", "value"]),
    _tool("get_profile", "Show everything Ultron knows about the user.", {}),
    _tool("clear_profile_field", "Remove a profile field.",
          {"field": {"type": "string"}}, ["field"]),

    # ===== Real-time watchers =====
    _tool("add_watch",
          "Monitor something in the background and alert when it trips. "
          "kind=stock (target=SYMBOL, direction=above|below, value=price); "
          "kind=folder (target=folder path); kind=cpu|ram (direction, value=percent).",
          {"kind": {"type": "string"}, "target": {"type": "string"},
           "direction": {"type": "string"}, "value": {"type": "string"}}, ["kind"]),
    _tool("list_watches", "List active background watches.", {}),
    _tool("delete_watch", "Remove a watch by id.", {"watch_id": {"type": "string"}}, ["watch_id"]),

    # ===== Excel control =====
    _tool("create_excel", "Create a spreadsheet from rows (list of row-lists).",
          {"path": {"type": "string"}, "rows": {"type": "array"}, "sheet": {"type": "string"}},
          ["path", "rows"]),
    _tool("excel_append_row", "Append a row to a spreadsheet (creates it if missing).",
          {"path": {"type": "string"}, "row": {"type": "array"}, "sheet": {"type": "string"}},
          ["path", "row"]),
    _tool("excel_set_cell", "Set a single cell (e.g. cell 'B2').",
          {"path": {"type": "string"}, "cell": {"type": "string"}, "value": {"type": "string"},
           "sheet": {"type": "string"}}, ["path", "cell", "value"]),
    _tool("excel_read_cell", "Read a single cell value.",
          {"path": {"type": "string"}, "cell": {"type": "string"}, "sheet": {"type": "string"}},
          ["path", "cell"]),

    # ===== Smart home (Home Assistant) =====
    _tool("ha_list_devices", "List Home Assistant devices (optionally filter by domain like light/switch).",
          {"domain": {"type": "string"}}),
    _tool("ha_turn_on", "Turn ON a smart-home device by name (e.g. 'living room light').",
          {"query": {"type": "string"}}, ["query"]),
    _tool("ha_turn_off", "Turn OFF a smart-home device by name.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("ha_set_brightness", "Set a light's brightness percent (0-100).",
          {"query": {"type": "string"}, "percent": {"type": "integer"}}, ["query", "percent"]),
    _tool("ha_device_state", "Get the current state of a smart-home device.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("ha_activate_scene", "Activate a Home Assistant scene by name.",
          {"query": {"type": "string"}}, ["query"]),

    # ===== Phone calls + SMS (Twilio) =====
    _tool("send_sms",
          "Send a text message (SMS) via Twilio. Recipient can be a phone number or a saved "
          "contact name. ALWAYS read back recipient + message and confirm before sending.",
          {"to": {"type": "string"}, "message": {"type": "string"}}, ["to", "message"]),
    _tool("make_call",
          "Place a phone call (via Twilio) that reads a spoken message aloud to the recipient. "
          "Recipient can be a number or contact name. Confirm before calling.",
          {"to": {"type": "string"}, "message": {"type": "string"}}, ["to", "message"]),
]

TOOL_HANDLERS: dict[str, Any] = {
    "open_app": lambda i: t_apps.open_app(i["name"]),
    "list_apps": lambda i: __import__("ultron.tools.app_index", fromlist=["list_apps"]).list_apps(
        i.get("query", ""), _int(i.get("limit"), 30)
    ),
    "refresh_apps": lambda i: __import__("ultron.tools.app_index", fromlist=["refresh_apps"]).refresh_apps(),
    "open_website": lambda i: t_apps.open_website(i["url"]),
    "web_search": lambda i: t_apps.web_search(i["query"]),
    "play_on_youtube": lambda i: t_apps.play_on_youtube(i["query"]),
    "add_reminder": lambda i, lang="en": t_reminders.add_reminder(
        i["text"], i["when"], lang, i.get("recurrence", "once")
    ),
    "list_reminders": lambda i: t_reminders.list_reminders(),
    "delete_reminder": lambda i: t_reminders.delete_reminder(i["reminder_id"]),
    "volume_up": lambda i: t_system.volume_up(_int(i.get("steps"), 5)),
    "volume_down": lambda i: t_system.volume_down(_int(i.get("steps"), 5)),
    "mute_toggle": lambda i: t_system.mute_toggle(),
    "lock_pc": lambda i: t_system.lock_pc(),
    "sleep_pc": lambda i: t_system.sleep_pc(),
    "shutdown_pc": lambda i: t_system.shutdown_pc(_int(i.get("seconds"), 30)),
    "cancel_shutdown": lambda i: t_system.cancel_shutdown(),
    "screenshot": lambda i: t_system.screenshot(),
    "current_time": lambda i: t_system.current_time(),
    "media_play_pause": lambda i: t_system.media_play_pause(),
    "media_next": lambda i: t_system.media_next(),
    "media_prev": lambda i: t_system.media_prev(),
    "media_stop": lambda i: t_system.media_stop(),
    "remember": lambda i: t_memory.remember(i["key"], i["value"]),
    "recall": lambda i: t_memory.recall(i.get("key")),
    "forget": lambda i: t_memory.forget(i["key"]),
    "read_file": lambda i: t_code.read_file(i["path"]),
    "write_file": lambda i: t_code.write_file(i["path"], i["content"]),
    "append_file": lambda i: t_code.append_file(i["path"], i["content"]),
    "list_dir": lambda i: t_code.list_dir(i.get("path", ".")),
    "run_shell": lambda i: t_code.run_shell(i["command"], _int(i.get("timeout"), 30)),
    "winget_search": lambda i: t_winget.winget_search(i["query"]),
    "winget_install": lambda i: t_winget.winget_install(i["package_id"]),
    "winget_uninstall": lambda i: t_winget.winget_uninstall(i["package_id"]),
    "describe_screen": lambda i: t_vision.describe_screen(i.get("question", "")),
    "send_whatsapp": lambda i: t_whatsapp.send_whatsapp(i["recipient"], i["message"]),
    "list_whatsapp_chats": lambda i: t_whatsapp.list_recent_chats(_int(i.get("count"), 10)),
    "read_whatsapp_chat": lambda i: t_whatsapp.read_chat(i["name"], _int(i.get("count"), 10)),
    "list_inbox": lambda i: t_gmail.list_inbox(_int(i.get("max_results"), 5)),
    "search_emails": lambda i: t_gmail.search_emails(i["query"], _int(i.get("max_results"), 5)),
    "send_email": lambda i: t_gmail.send_email(i["to"], i["subject"], i["body"]),
    "daily_briefing": lambda i: t_briefing.daily_briefing(),
    "recall_similar": lambda i: t_recall.recall_similar(i["query"], _int(i.get("k"), 5)),
    "set_personality": lambda i: _set_personality(i["personality_id"]),
    "fetch_url": lambda i: t_web.fetch_url(i["url"], i.get("question", "")),
    "news_briefing": lambda i: t_news.news_briefing(i.get("topic", ""), _int(i.get("count"), 5)),
    "ask_document": lambda i: t_doc.ask_document(i["path"], i.get("question", "")),
    "create_skill": lambda i: t_skills.create_skill(i["name"], i.get("steps") or []),
    "run_skill": lambda i: t_skills.run_skill(i["name"]),
    "list_skills": lambda i: t_skills.list_skills(),
    "delete_skill": lambda i: t_skills.delete_skill(i["name"]),
    "run_python": lambda i: t_pyexec.run_python(i["code"], _int(i.get("timeout"), 5)),
    # v7
    "generate_image": lambda i: t_img.generate_image(
        i["prompt"], _int(i.get("width"), 1024), _int(i.get("height"), 1024)
    ),
    "copy_file":   lambda i: t_fileops.copy_file(i["src"], i["dst"]),
    "move_file":   lambda i: t_fileops.move_file(i["src"], i["dst"]),
    "rename_file": lambda i: t_fileops.rename_file(i["path"], i["new_name"]),
    "make_dir":    lambda i: t_fileops.make_dir(i["path"]),
    "delete_file": lambda i: t_fileops.delete_file(i["path"], bool(i.get("permanent", False))),
    "convert_currency": lambda i: t_convert.convert_currency(
        i["amount"], i["from_currency"], i["to_currency"]
    ),
    "convert_unit": lambda i: t_convert.convert_unit(
        i["amount"], i["from_unit"], i["to_unit"]
    ),
    "web_search_real": lambda i: t_websearch.web_search(i["query"], _int(i.get("max_results"), 5)),
    "ocr_screen": lambda i: t_ocr.ocr_screen(i.get("question", "")),
    "ocr_image":  lambda i: t_ocr.ocr_image(i["path"], i.get("question", "")),
    "stock_quote": lambda i: t_quotes.stock_quote(i["symbol"]),
    "cricket_score": lambda i: t_quotes.cricket_score(i.get("query", "")),
    "add_note": lambda i: t_notes.add_note(i["text"], i.get("tag", "")),
    "list_notes": lambda i: t_notes.list_notes(_int(i.get("max_results"), 10), i.get("query", "")),
    "read_clipboard": lambda i: t_clipboard.read_clipboard(),
    "write_clipboard": lambda i: t_clipboard.write_clipboard(i["text"]),
    "append_clipboard": lambda i: t_clipboard.append_clipboard(i["text"]),
    "translate": lambda i: t_translate.translate(i["text"], i.get("target_language", "english")),
    "find_files": lambda i: t_file_search.find_files(
        i.get("name_pattern", ""), i.get("content_query", ""), _int(i.get("max_results"), 25)
    ),
    "list_today_events": lambda i: t_calendar.list_today_events(),
    "list_week_events": lambda i: t_calendar.list_week_events(),
    "add_calendar_event": lambda i: t_calendar.add_event(
        i["summary"], i["start_time"], _int(i.get("duration_minutes"), 60),
        i.get("description", ""), i.get("location", "")
    ),
    # v8 — screen automation / windows / timers
    "type_text": lambda i: t_auto.type_text(i["text"]),
    "press_keys": lambda i: t_auto.press_keys(i["keys"]),
    "mouse_click": lambda i: t_auto.mouse_click(
        i.get("x"), i.get("y"), i.get("button", "left"), _int(i.get("clicks"), 1)
    ),
    "scroll": lambda i: t_auto.scroll(_int(i.get("amount"), -500)),
    "screen_size": lambda i: t_auto.screen_size(),
    "list_windows": lambda i: t_win.list_windows(),
    "active_window": lambda i: t_win.active_window(),
    "focus_window": lambda i: t_win.focus_window(i["title"]),
    "minimize_window": lambda i: t_win.minimize_window(i["title"]),
    "maximize_window": lambda i: t_win.maximize_window(i["title"]),
    "close_window": lambda i: t_win.close_window(i["title"]),
    "set_timer": lambda i, lang="en": t_timer.set_timer(
        i.get("minutes", 0), i.get("seconds", 0), i.get("label", "Timer"), lang
    ),
    # v9 — agentic
    "research": lambda i: t_research.research(
        i["topic"], _int(i.get("depth"), 3), bool(i.get("save_note", False))
    ),
    "find_on_screen": lambda i: t_vclick.find_on_screen(i["description"]),
    "click_on_screen": lambda i: t_vclick.click_on_screen(
        i["description"], i.get("button", "left"), bool(i.get("double", False))
    ),
    "draft_email_reply": lambda i: t_edraft.draft_email_reply(
        i.get("query", "is:unread"), i.get("instructions", "")
    ),
    # v10 — autonomous agent
    "accomplish": lambda i: __import__("ultron.agent", fromlist=["accomplish"]).accomplish(
        i["goal"], _int(i.get("max_steps"), 12)
    ),
    "plan_task": lambda i: t_planner.plan_task(i["goal"]),
    "auto_pilot": lambda i: __import__("ultron.agent", fromlist=["auto_pilot"]).auto_pilot(
        i["goal"], _int(i.get("max_steps"), 20)
    ),
    "stop_autopilot": lambda i: __import__("ultron.agent", fromlist=["stop_autopilot"]).stop_autopilot(),
    # v11 — routines
    "create_routine": lambda i: t_routines.create_routine(
        i["name"], i["goal"], i.get("schedule_type", "daily"),
        i.get("time", "08:00"), i.get("day", "monday")
    ),
    "list_routines": lambda i: t_routines.list_routines(),
    "delete_routine": lambda i: t_routines.delete_routine(i["name"]),
    "run_routine_now": lambda i: t_routines.run_routine_now(i["name"]),
    # v12 — system / network / data
    "system_info": lambda i: t_sysmon.system_info(),
    "top_processes": lambda i: t_sysmon.top_processes(_int(i.get("n"), 5), i.get("by", "memory")),
    "find_process": lambda i: t_sysmon.find_process(i["name"]),
    "kill_process": lambda i: t_sysmon.kill_process(i["name"]),
    "network_info": lambda i: t_net.network_info(),
    "check_internet": lambda i: t_net.check_internet(),
    "analyze_spreadsheet": lambda i: t_sheet.analyze_spreadsheet(i["path"], i.get("question", "")),
    # v13 — frontier
    "operate_computer": lambda i: t_compuse.operate_computer(
        i["goal"], _int(i.get("max_steps"), 10), progress=lambda m: print(m)
    ),
    "create_plugin": lambda i: t_selfext.create_plugin(i["name"], i["description"]),
    "index_folder": lambda i: t_know.index_folder(i["folder"]),
    "ask_knowledge": lambda i: t_know.ask_knowledge(i["folder"], i["question"]),
    # v14 — create / qr / git
    "create_pdf": lambda i: t_doccreate.create_pdf(i["content"], i.get("title", ""), i.get("path", "")),
    "create_docx": lambda i: t_doccreate.create_docx(i["content"], i.get("title", ""), i.get("path", "")),
    "create_markdown": lambda i: t_doccreate.create_markdown(i["content"], i.get("title", ""), i.get("path", "")),
    "generate_qr": lambda i: t_qr.generate_qr(i["data"], i.get("path", "")),
    "generate_wifi_qr": lambda i: t_qr.generate_wifi_qr(
        i["ssid"], i["password"], i.get("security", "WPA"), i.get("path", "")
    ),
    "git_status": lambda i: t_git.git_status(i.get("repo", ".")),
    "git_log": lambda i: t_git.git_log(i.get("repo", "."), _int(i.get("n"), 10)),
    "git_diff": lambda i: t_git.git_diff(i.get("repo", "."), bool(i.get("staged", False))),
    "git_branches": lambda i: t_git.git_branches(i.get("repo", ".")),
    "git_commit": lambda i: t_git.git_commit(i.get("repo", "."), i["message"]),
    # v17 — personal life manager
    "add_task": lambda i: t_tasks.add_task(i["text"], i.get("priority", "normal")),
    "list_tasks": lambda i: t_tasks.list_tasks(bool(i.get("include_done", False))),
    "complete_task": lambda i: t_tasks.complete_task(i["task_id"]),
    "delete_task": lambda i: t_tasks.delete_task(i["task_id"]),
    "add_contact": lambda i: t_contacts.add_contact(
        i["name"], i.get("phone", ""), i.get("email", ""), i.get("notes", "")
    ),
    "find_contact": lambda i: t_contacts.find_contact(i["query"]),
    "list_contacts": lambda i: t_contacts.list_contacts(),
    "log_expense": lambda i: t_expenses.log_expense(
        i["amount"], i.get("category", "general"), i.get("note", "")
    ),
    "expense_summary": lambda i: t_expenses.expense_summary(i.get("period", "month")),
    "add_shopping_item": lambda i: t_shopping.add_shopping_item(i["item"], i.get("qty", "")),
    "list_shopping": lambda i: t_shopping.list_shopping(),
    "check_shopping_item": lambda i: t_shopping.check_shopping_item(i["item"]),
    "clear_shopping": lambda i: t_shopping.clear_shopping(),
    # v18 — maps
    "map_distance": lambda i: t_maps.distance(i["origin"], i["destination"]),
    "map_directions": lambda i: t_maps.directions(i["origin"], i["destination"]),
    "find_place": lambda i: t_maps.find_place(i["query"]),
    # v19 — wellbeing
    "add_habit": lambda i: t_habits.add_habit(i["name"]),
    "check_habit": lambda i: t_habits.check_habit(i["name"]),
    "list_habits": lambda i: t_habits.list_habits(),
    "delete_habit": lambda i: t_habits.delete_habit(i["name"]),
    "log_health": lambda i: t_health.log_health(i["metric"], i.get("value", ""), i.get("note", "")),
    "health_summary": lambda i: t_health.health_summary(i.get("period", "today")),
    "add_journal_entry": lambda i: t_journal.add_journal_entry(i["text"]),
    "read_journal": lambda i: t_journal.read_journal(i.get("when", "recent"), _int(i.get("count"), 5)),
    # v20 — media & file utilities
    "record_voice_memo": lambda i: t_memo.record_voice_memo(
        _int(i.get("seconds"), 15), bool(i.get("transcribe", True))
    ),
    "resize_image": lambda i: t_imgedit.resize_image(
        i["path"], _int(i.get("width"), 0), _int(i.get("height"), 0)
    ),
    "convert_image": lambda i: t_imgedit.convert_image(i["path"], i.get("to_format", "png")),
    "rotate_image": lambda i: t_imgedit.rotate_image(i["path"], _int(i.get("degrees"), 90)),
    "merge_pdfs": lambda i: t_pdf.merge_pdfs(i.get("paths") or [], i.get("output", "")),
    "split_pdf": lambda i: t_pdf.split_pdf(i["path"], i.get("ranges", "")),
    "pdf_info": lambda i: t_pdf.pdf_info(i["path"]),
    "organize_folder": lambda i: t_organize.organize_folder(i["folder"], bool(i.get("dry_run", False))),
    # v21 — music / focus / scheduling
    "play_music": lambda i: t_music.play_music(i.get("query", "")),
    "list_music": lambda i: t_music.list_music(i.get("query", ""), _int(i.get("limit"), 20)),
    "start_pomodoro": lambda i, lang="en": t_focus.start_pomodoro(
        _int(i.get("work_minutes"), 25), _int(i.get("break_minutes"), 5),
        _int(i.get("cycles"), 4), lang
    ),
    "find_free_time": lambda i: t_sched.find_free_time(
        i.get("date", "today"), i.get("work_start", "09:00"),
        i.get("work_end", "21:00"), _int(i.get("min_slot_minutes"), 30)
    ),
    # Personal profile
    "set_profile": lambda i: t_profile.set_profile(i["field"], i["value"]),
    "get_profile": lambda i: t_profile.get_profile(),
    "clear_profile_field": lambda i: t_profile.clear_profile_field(i["field"]),
    # Watchers
    "add_watch": lambda i: t_watch.add_watch(
        i["kind"], i.get("target", ""), i.get("direction", "above"), i.get("value", "")
    ),
    "list_watches": lambda i: t_watch.list_watches(),
    "delete_watch": lambda i: t_watch.delete_watch(i["watch_id"]),
    # Excel
    "create_excel": lambda i: t_excel.create_excel(i["path"], i.get("rows") or [], i.get("sheet", "Sheet1")),
    "excel_append_row": lambda i: t_excel.append_row(i["path"], i.get("row") or [], i.get("sheet", "")),
    "excel_set_cell": lambda i: t_excel.set_cell(i["path"], i["cell"], i["value"], i.get("sheet", "")),
    "excel_read_cell": lambda i: t_excel.read_cell(i["path"], i["cell"], i.get("sheet", "")),
    # Smart home (Home Assistant)
    "ha_list_devices": lambda i: t_ha.list_devices(i.get("domain", "")),
    "ha_turn_on": lambda i: t_ha.turn_on(i["query"]),
    "ha_turn_off": lambda i: t_ha.turn_off(i["query"]),
    "ha_set_brightness": lambda i: t_ha.set_brightness(i["query"], _int(i.get("percent"), 100)),
    "ha_device_state": lambda i: t_ha.device_state(i["query"]),
    "ha_activate_scene": lambda i: t_ha.activate_scene(i["query"]),
    # Phone (Twilio)
    "send_sms": lambda i: t_phone.send_sms(i["to"], i["message"]),
    "make_call": lambda i: t_phone.make_call(i["to"], i["message"]),
}


_plugins_loaded_once = False


def _load_plugins_once() -> None:
    """Discover and merge plugins exactly once per process."""
    global _plugins_loaded_once
    if _plugins_loaded_once:
        return
    _plugins_loaded_once = True
    try:
        plugin_tools, plugin_handlers = load_plugins()
        builtin_names = {t["name"] for t in TOOLS}
        plugin_tools = reserved_names_check(builtin_names, plugin_tools)
        if plugin_tools:
            TOOLS.extend(plugin_tools)
            TOOL_HANDLERS.update({
                name: handler for name, handler in plugin_handlers.items()
                if name in {t["name"] for t in plugin_tools}
            })
            print(f"[brain] plugins loaded: +{len(plugin_tools)} tool(s)")
    except Exception as e:
        print(f"[brain] plugin load skipped: {e}")
