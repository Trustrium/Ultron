# ULTRON — Personal AGI PC Agent by Trustrium

> **"At your service, sir."**
> Ultron is Trustrium's personal super-intelligent PC agent for Windows.
> Type or speak one command — Ultron plans it, does it, verifies it, and reports back in 1–2 sentences.
> English + Roman Urdu. Free Groq brain. No card needed.

![Trustrium](https://img.shields.io/badge/By-Trustrium-orange)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Voice](https://img.shields.io/badge/Voice-English%20%2B%20Roman%20Urdu-purple)

---

## Why Ultron is different

Most voice assistants answer. **Ultron executes.**

| | Ordinary assistant | Ultron |
|---|---|---|
| Command | "Open Chrome" → explains how | Opens Chrome, verifies the window |
| Multi-step | One step at a time | **Commander** plans the whole task, then runs it |
| Memory | Forgets you | **Ultron Memory** remembers you, your projects, your style |
| Language | English only | **English + Roman Urdu** — reply matches what you spoke |
| Safety | Deletes forever | Delete → Recycle Bin + verbal confirmation |
| Cost | Paid API | **Groq free tier** by default |

### Unique to Ultron

- **Ultron Commander** (`ultron/core/commander.py`) — Understand → Plan → Execute → Verify → Report. Every command becomes a checked plan. Risky steps pause for your confirmation.
- **Ultron Memory** (`ultron/memory/profile.py`) — Persistent profile: Rashid Ali, Trustrium, your projects, your preferences. Stored locally in `data/ultron_profile.json`, never sent anywhere.
- **Command Center** (`plugins/ultron_command_center.py`) — One command shows system health + reminders + projects + profile. Try: *"command center"*.
- **Autopilot** (`plugins/ultron_autopilot.py`) — Morning briefing, end-of-day summary, and Downloads auto-organize (preview first, executes only on confirm).
- **Trustrium Tools** (`plugins/ultron_trustrium.py`) — Briefing, open project, project status for MoboGravity, Shadow Arena, TIME & TIDE, Echo Protocol, Bulk Downloader.
- **Roman Urdu brain** — Say *"Chrome kholo"*, *"screenshot lo"*, *"yaad dilao"* — Ultron understands and replies in Roman Urdu.

---

## What Ultron can do

**Talk** — Wake word *"Hey Ultron"*, hotkey `Ctrl+Alt+J`, or just type. Voice presets. Personalities: Ultron, Butler, Casual, Concise, Witty, Professional.

**Control your PC** — Open any installed app (fuzzy-matched), volume / mute / lock / sleep / shutdown, screenshot, media keys, type / click / hotkeys / scroll, window management, system health, kill processes, network info.

**Files & data** — Find files by name or content; copy / move / rename / delete (→ Recycle Bin); read & write code; run PowerShell (blocklisted) + sandboxed Python; spreadsheet Q&A (CSV/Excel); document Q&A (PDF/text); knowledge base — index a folder, ask across all docs.

**Stay organized** — Reminders (recurring + proactive), notes, clipboard, long-term memory, daily briefing, timers, scheduled routines.

**Information** — Real web search, fetch + summarize any URL, deep research, news, weather, stocks, cricket scores, currency + unit conversion, translate.

**Communication** — Gmail (read / search / send / draft), WhatsApp (read / send), Google Calendar (view / add).

**Create & see** — Generate images (saves to Desktop), OCR from screen or image, screen vision (*"what's on my screen?"*).

**Agentic** — Autonomous multi-step agent, computer-use (sees screen, clicks, types, re-checks), self-extension (writes its own new tools on request), plugins (drop a `.py` into `plugins/`).

---

## Quick start (Windows, 5 minutes)

### 1. Clone

```powershell
git clone https://github.com/Trustrium/Ultron.git
cd Ultron
```

### 2. Get a free API key

**Groq is free and fast (recommended):** https://console.groq.com/keys — free, no card.
Or: Google Gemini (free), or local Ollama (no key, no internet).

### 3. Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Requires **Python 3.11+** (3.12 / 3.13 work). First run downloads small voice models.

### 4. Configure

```powershell
copy .env.example .env
```

Open `.env` and paste your key as `LLM_API_KEY`. Defaults are already Ultron:

```
ASSISTANT_NAME=Ultron
WAKE_WORD=Hey Ultron
LANGUAGE=en+roman_urdu
LLM_PROVIDER=groq
```

### 5. Run

```powershell
python ultron_app.py     # Desktop GUI (recommended) — first-run setup wizard
```

Or CLI:

```powershell
python run.py text       # type commands, no mic (best first test)
python run.py voice      # press ENTER, then speak
python run.py wake       # always-on "Hey Ultron"
```

### 6. First-run wizard (GUI)

1. Pick provider → paste API key → **Test connection** ✅
2. **Voice tab** → choose a voice (Ultron default) → ▶ Preview
3. Save → you'll hear *"At your service, sir."*

Gmail / Calendar / WhatsApp need a one-time login (see Optional setup below).

---

## Example commands

```
open Chrome
find report.pdf
morning briefing
command center
remind me in 10 minutes to call back
what's on my screen?
Chrome kholo
screenshot lo
Downloads organize karo
```

Ultron executes, verifies, and reports: *"Done, sir."*

---

## Choosing a provider

Set in the GUI (Settings → Brain) or in `.env`:

```
LLM_PROVIDER=groq
LLM_API_KEY=<redacted>
# LLM_MODEL=   # optional — defaults are sensible per provider
```

| Provider | Free? | Notes |
|---|---|---|
| **Groq** | ✅ free tier | Fast; default |
| **Gemini** | ✅ free tier | Good fallback |
| **Ollama** | ✅ local | No internet, no key |
| OpenAI / Anthropic / OpenRouter / Together | 💳 paid | Optional |

Fallback: if the primary provider rate-limits, Ultron auto-switches to your fallback provider (e.g. Groq + Gemini, both free).

---

## Optional setup

### Gmail + Calendar (Google)

1. https://console.cloud.google.com → new project (free)
2. Enable **Gmail API** + **Google Calendar API**
3. OAuth consent screen → External → add yourself as a **Test user**
4. Credentials → OAuth client ID → **Desktop app** → download JSON
5. Save it as `data/gmail_credentials.json`
6. First use opens a browser to grant access (token cached after)

### WhatsApp Web

1. Have **Google Chrome** installed
2. First WhatsApp command opens web.whatsapp.com → scan QR with your phone
3. Session saved in `data/wa_chrome_profile/` (one-time)

### Local OCR (optional)

Install Tesseract + `pip install pytesseract` for fast local OCR. Otherwise Ultron falls back to LLM vision automatically.

---

## Tech stack

| Layer | Tech |
|---|---|
| Brain | Any of 8 LLM providers (OpenAI-compatible + Anthropic) |
| Commander | Ultron Core — plan / execute / verify (stdlib only) |
| Memory | Ultron Memory — local JSON profile |
| Wake word | openWakeWord (local) — *"Hey Ultron"* label; custom wake model recommended for true hands-free |
| Speech-to-text | faster-whisper (English + Roman Urdu) |
| Text-to-speech | Edge TTS (free neural voices) |
| Vision | Multimodal LLM |
| Automation | pyautogui + pygetwindow |
| GUI | PySide6 (tray + window + settings) + Ultron theme (dark silver + orange-red glow) |

---

## Run modes

| Command | Mode |
|---|---|
| `python ultron_app.py` | GUI desktop app + system tray |
| `python run.py text` | Type commands (no mic) |
| `python run.py voice` | Press ENTER to talk |
| `python run.py wake` | Always-on "Hey Ultron" |

Build a standalone `.exe`: `.\build_exe.ps1` → `dist\Ultron\Ultron.exe`

---

## Safety

- Destructive actions (shutdown, delete, send email/WhatsApp, uninstall, kill process) require **verbal confirmation**.
- Deletes go to the **Recycle Bin** — never permanent.
- Shell commands are screened by a **blocklist** (refuses `Remove-Item -Recurse`, `Format-Volume`, fork bombs, remote-code execution, etc.).
- Self-written plugins are sandbox-validated (no `os.system` / `subprocess` / file deletion).
- Wake-word audio is processed **locally** — nothing leaves your PC until you talk.
- Every turn is logged to `data/conversation.log`. Profile stays in `data/ultron_profile.json`.

---

## Project layout

```
Ultron/
├── ultron_app.py          GUI entry (window + tray + wizard)
├── run.py                 CLI entry (text / voice / wake)
├── test_all.py            full feature test harness
├── audit.py               validation battery
├── ultron/
│   ├── brain.py           LLM brain + tool registry
│   ├── core/              Ultron Commander (plan / execute / verify)
│   ├── memory/            Ultron Memory (persistent profile)
│   ├── agent.py           autonomous multi-step agent
│   ├── routines.py        scheduled autonomous routines
│   ├── llm/               provider adapters
│   ├── voice/             wake word, STT, TTS, voice presets, Roman Urdu
│   ├── gui/               window, settings, tray, waveform, worker, Ultron theme
│   └── tools/             ~40 tool modules (apps, files, web, vision, ...)
└── plugins/               drop-in user plugins (auto-loaded)
    ├── ultron_command_center.py
    ├── ultron_autopilot.py
    ├── ultron_trustrium.py
    └── weather.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add tools and plugins.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No module named X` | Activate venv: `.\.venv\Scripts\Activate.ps1` |
| Mic not working | Windows Settings → Privacy → Microphone → on |
| Wake word won't trigger | Run `python mic_check.py`; custom "Hey Ultron" wake model recommended |
| Whisper slow | Set `WHISPER_MODEL=tiny` in `.env` |
| Rate limited (Groq) | Free tier has a daily token cap; wait or switch provider |
| Run validation | `python test_all.py` or `python audit.py` |

---

## License

MIT — Copyright (c) 2026 Trustrium. See [LICENSE](LICENSE).

**Developed by Trustrium** for Rashid Ali. Ultron — at your service, sir.
