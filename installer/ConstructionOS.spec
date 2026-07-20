# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Construction OS.

Build (from the installer/ directory):
    pyinstaller --noconfirm --clean ConstructionOS.spec

Produces a one-folder build in dist/ConstructionOS/ — an offline, self-contained
tkinter app that needs no Python on the target machine. The app is pure stdlib,
so there is no third-party import surface; PyInstaller only has to bundle the
CPython runtime, Tcl/Tk (for tkinter), the flat local modules, and resources/.
"""

import glob
import os

# SPECPATH is injected by PyInstaller: the directory holding this spec.
APP = os.path.abspath(os.path.join(SPECPATH, '..', 'construction_app'))

# The app is a flat directory of top-level modules (no package), and several
# tabs are imported lazily inside functions (tab_kpi pulls tab_plant / tab_
# compliance / tab_timeline on demand, etc.). List every module explicitly so
# static analysis cannot leave one out and a tab dead at runtime.
hidden = sorted(
    os.path.splitext(os.path.basename(f))[0]
    for f in glob.glob(os.path.join(APP, '*.py'))
    if os.path.basename(f) != 'main.py'
)

a = Analysis(
    [os.path.join(APP, 'main.py')],
    pathex=[APP],
    binaries=[],
    # Ship the logos and the .ico; paths.resource_base() reads them back from
    # the frozen bundle at runtime.
    datas=[(os.path.join(APP, 'resources'), 'resources')],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    # The test suite and the separate ollama_manager app are not part of the
    # shipped product.
    excludes=['pytest', 'tests'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ConstructionOS',
    debug=False,
    strip=False,
    upx=False,
    console=False,                       # a GUI app — no console window
    icon=os.path.join(APP, 'resources', 'app.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='ConstructionOS',
)
