# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Ultron desktop app.

Build with:
    pip install pyinstaller
    pyinstaller ultron.spec --clean --noconfirm

Outputs to dist\\Ultron\\ (folder mode) — faster startup than --onefile,
and ships with all native deps (ctranslate2, PortAudio, ONNX runtime, Qt).
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# Heavy packages that PyInstaller's analyzer misses
all_datas = []
all_binaries = []
all_hiddenimports = []

for pkg in [
    "openwakeword",       # bundles its ONNX models
    "faster_whisper",     # native ctranslate2 libs
    "edge_tts",
    "PySide6",
]:
    d, b, h = collect_all(pkg)
    all_datas += d
    all_binaries += b
    all_hiddenimports += h

# Sub-packages PyInstaller sometimes misses
all_hiddenimports += [
    "openai",
    "anthropic",
    "groq",
    "google.api_core",
    "google.auth",
    "google.oauth2",
    "googleapiclient",
    "googleapiclient.discovery",
    "selenium",
    "selenium.webdriver",
    "PIL",
    "PIL.ImageGrab",
    "sounddevice",
    "scipy",
    "scipy._lib",
    "scipy._lib.messagestream",
    "numpy",
    "pygame",
    "pygame.mixer",
    "win32api",
    "win32con",
    "pywintypes",
]

a = Analysis(
    ["ultron_app.py"],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas + [("assets/ultron.ico", "assets")],
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],   # save space
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ultron",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                       # windowed app, no console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/ultron.ico",            # professional Ultron app icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Ultron",
)
