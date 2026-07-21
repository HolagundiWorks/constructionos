# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Ollama Manager.

A small companion app to Construction OS: install and run Ollama, manage
models, and set the model Construction OS should use. Separate from the main
app because a contractor who does not want the optional AI assistant never
needs it. Pure stdlib + tkinter, so PyInstaller only bundles the runtime,
Tcl/Tk and the four flat modules.

Build (from installer/):  pyinstaller --noconfirm --clean OllamaManager.spec
"""

import os

OM = os.path.abspath(os.path.join(SPECPATH, '..', 'ollama_manager'))
# Reuse the Construction OS icon so the two apps look like a set.
ICON = os.path.abspath(os.path.join(SPECPATH, '..', 'construction_app',
                                    'resources', 'app.ico'))

a = Analysis(
    [os.path.join(OM, 'main.py')],
    pathex=[OM],
    binaries=[],
    datas=[],
    hiddenimports=['api', 'config', 'service', 'catalog'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['pytest', 'tests'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OllamaManager',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='OllamaManager',
)
