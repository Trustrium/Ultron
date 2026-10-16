# Contributing to Ultron

Ultron is developed by Trustrium for Rashid Ali's personal use, and contributions that make it safer, faster, and more useful are welcome.

## How to contribute

1. Clone `Trustrium/Ultron` and create a feature branch.
2. Keep changes small and focused. One feature per pull request.
3. Add or update tests where behaviour changes (`test_logic.py`, `test_all.py`).
4. Run `python -m py_compile` on changed files and `python test_logic.py` before opening a PR.
5. Never commit secrets (`.env`, API keys, tokens, Gmail credentials, WhatsApp profiles). They are git-ignored for a reason.

## Safety rules (non-negotiable)

- Destructive actions (delete, shutdown, send, kill, uninstall) must require verbal confirmation.
- Deletes go to the Recycle Bin — never permanent delete.
- Shell commands stay blocklisted (no `Remove-Item -Recurse`, `Format-Volume`, fork bombs, remote-code execution).
- Self-written plugins are sandbox-validated: no `os.system` / `subprocess` / file deletion.
- Wake-word audio is processed locally.

## Code style

- Python 3.11+, type hints where practical, short functions, plain English names.
- New tools: add to `ultron/tool_registry.py` or as a plugin in `plugins/` with `TOOLS` + `HANDLERS`.
- New plugins: return plain strings, keep JSON schemas simple.

Thank you for making Ultron better, sir.
