"""One-shot validation battery for Ultron. Not committed to git (in .gitignore via *.py? no — exclude manually)."""
import importlib

print('=' * 70)
print('ULTRON — COMPREHENSIVE VALIDATION')
print('=' * 70)

# [1] MODULE IMPORTS
print('\n[1] MODULE IMPORTS')
modules = [
    'ultron', 'ultron.config', 'ultron.settings', 'ultron.conversation_log',
    'ultron.brain',
    'ultron.llm', 'ultron.llm.base', 'ultron.llm.openai_compat',
    'ultron.llm.anthropic_provider', 'ultron.llm.factory', 'ultron.llm.test_provider',
    'ultron.voice.listen', 'ultron.voice.speak', 'ultron.voice.wake', 'ultron.voice.presets',
    'ultron.tools.apps', 'ultron.tools.system', 'ultron.tools.reminders',
    'ultron.tools.memory', 'ultron.tools.code', 'ultron.tools.winget',
    'ultron.tools.vision', 'ultron.tools.whatsapp', 'ultron.tools.gmail',
    'ultron.gui.main_window', 'ultron.gui.settings_dialog', 'ultron.gui.tray',
    'ultron.gui.wizard', 'ultron.gui.worker',
]
fails = []
for m in modules:
    try:
        importlib.import_module(m)
    except Exception as e:
        fails.append((m, str(e)))
print(f'  {len(modules)-len(fails)}/{len(modules)} imported OK')
for m, e in fails:
    print(f'  FAIL: {m}: {e}')

# [2] SETTINGS ROUND-TRIP
print('\n[2] SETTINGS ROUND-TRIP')
from ultron import settings as S
orig = S.load()
S.save({'llm_model': 'audit_test_model_xyz'})
reread = S.load()
ok = reread.get('llm_model') == 'audit_test_model_xyz'
print(f'  save+load: {"OK" if ok else "FAIL"}')
S.save({'llm_model': orig.get('llm_model', '')})

# [3] MODEL CATALOG
print('\n[3] MODEL CATALOG')
from ultron.settings import PROVIDER_INFO, get_models_for
for info in PROVIDER_INFO:
    models = get_models_for(info['id'])
    print(f'  {info["id"]:15s} -> {len(models)} models')

# [4] TOOL WIRING
print('\n[4] TOOL WIRING')
from ultron.brain import TOOLS, TOOL_HANDLERS
tool_names = {t['name'] for t in TOOLS}
handler_names = set(TOOL_HANDLERS.keys())
missing_handlers = tool_names - handler_names
orphan_handlers = handler_names - tool_names
print(f'  Tools declared:  {len(tool_names)}')
print(f'  Handlers wired:  {len(handler_names)}')
print(f'  Missing handler: {missing_handlers if missing_handlers else "(none)"}')
print(f'  Orphan handler:  {orphan_handlers if orphan_handlers else "(none)"}')

# [5] BRAIN END-TO-END
print('\n[5] BRAIN END-TO-END (Groq)')
from ultron.brain import Brain
try:
    b = Brain()
    print(f'  Client: {type(b.client).__name__}')
    r = b.think('Reply with just the word ACK.', 'en')
    print(f'  Reply: {r[:80]!r}')
except Exception as e:
    print(f'  FAIL: {type(e).__name__}: {e}')

# [6] HISTORY TRIM
print('\n[6] HISTORY TRIM SAFETY')
from ultron.brain import Brain, MAX_HISTORY_MESSAGES
b2 = Brain()
for i in range(100):
    b2.history.append({'role': 'user', 'content': f'msg {i}'})
    b2.history.append({'role': 'assistant', 'content': f'reply {i}'})
b2._trim_history()
print(f'  After 100 turns trimmed to: {len(b2.history)} (cap={MAX_HISTORY_MESSAGES})')

# [7] VOICE PRESETS
print('\n[7] VOICE PRESETS')
from ultron.voice.presets import ENGLISH_PRESETS, TAMIL_PRESETS
print(f'  English: {len(ENGLISH_PRESETS)}  Tamil: {len(TAMIL_PRESETS)}')
bad = []
for plist in (ENGLISH_PRESETS, TAMIL_PRESETS):
    for p in plist:
        required = {'id', 'label', 'voice', 'rate', 'pitch', 'description'}
        if not required.issubset(p.keys()):
            bad.append(('missing-keys', p.get('id')))
        if p['rate'] and p['rate'][0] not in '+-':
            bad.append(('unsigned-rate', p.get('id'), p['rate']))
        if p['pitch'] and p['pitch'][0] not in '+-':
            bad.append(('unsigned-pitch', p.get('id'), p['pitch']))
print(f'  Issues: {bad if bad else "(none)"}')

# [8] ANTHROPIC ADAPTER
print('\n[8] ANTHROPIC ADAPTER')
from ultron.llm.anthropic_provider import AnthropicClient
from ultron.llm.base import LLMClient
print(f'  Subclass of LLMClient: {"OK" if issubclass(AnthropicClient, LLMClient) else "FAIL"}')
required_methods = {'chat', 'make_user_message', 'make_assistant_message',
                    'make_tool_results', 'has_unresolved_tool_calls'}
missing = required_methods - set(dir(AnthropicClient))
print(f'  Missing methods: {missing if missing else "(none)"}')

# [9] TOOL SANITY
print('\n[9] TOOL SANITY')
from ultron.tools import system as ts, memory as tm, code as tc
print(f'  current_time: {ts.current_time()[:50]}')
tm.remember('audit-test-key', 'audit-test-value')
v = tm.recall('audit-test-key')
print(f'  remember+recall: {"OK" if "audit-test-value" in v else "FAIL"}')
tm.forget('audit-test-key')

# [10] SHELL BLOCKLIST
print('\n[10] SHELL BLOCKLIST')
from ultron.tools.code import _is_dangerous
test_cases = [
    ('rm -rf /', True),
    ('Remove-Item -Recurse C:/Users', True),
    ('format c:', True),
    ('shutdown /r /t 0', True),
    ('Format-Volume', True),
    ('Clear-RecycleBin', True),
    ('echo hello', False),
    ('dir', False),
    ('Get-ChildItem', False),
]
fails = []
for cmd, should_block in test_cases:
    blocked = _is_dangerous(cmd)
    if blocked != should_block:
        fails.append((cmd, should_block, blocked))
print(f'  Correct: {len(test_cases)-len(fails)}/{len(test_cases)}')
for cmd, expected, got in fails:
    print(f'  WRONG: {cmd!r} expected block={expected} got={got}')

# [11] REMINDER PARSING
print('\n[11] REMINDER PARSING')
from ultron.tools.reminders import _parse_due
tests = [
    'in 5 minutes', 'in 2 hours', 'tomorrow 9am', 'today 6pm',
    '2026-12-31 23:59', 'tomorrow', 'tomorrow 09:30', 'in 3 days',
]
all_parsed = True
for t in tests:
    d = _parse_due(t)
    if d is None:
        all_parsed = False
        print(f'  FAIL: {t!r} -> None')
    else:
        print(f'  OK   {t:25s} -> {d}')
print(f'  All parsed: {"OK" if all_parsed else "FAIL"}')

# [12] CONFIG LOADING
print('\n[12] CONFIG LOADING')
from ultron import config
print(f'  LLM_PROVIDER: {config.LLM_PROVIDER}')
print(f'  LLM_API_KEY set: {bool(config.LLM_API_KEY)}')
print(f'  LLM_MODEL: {config.LLM_MODEL!r}')
print(f'  WHISPER_MODEL: {config.WHISPER_MODEL}')
print(f'  TTS_VOICE_ENGLISH: {config.TTS_VOICE_ENGLISH}')

print('\n' + '=' * 70)
print('AUDIT COMPLETE')
print('=' * 70)
