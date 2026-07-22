"""Where the app keeps its files — run from source or installed.

Two situations, two answers:

* **From source** (a developer, or ``python main.py``) nothing moves. The
  database, the company registry and the resources all stay next to the code,
  exactly as before, so an existing ``construction.db`` keeps working and the
  app stays self-contained on a USB stick.

* **Installed** (frozen into an .exe by PyInstaller) the code lives inside a
  read-only bundle in Program Files, so it cannot be written to. Writable data
  moves to a per-user folder under ``%LOCALAPPDATA%`` — no admin rights, one
  copy per Windows user — and the bundled resources are read from the frozen
  bundle's unpack directory.

Every writable path in the app funnels through ``data_dir()`` (the database,
its WAL sidecars, the company registry, new firm/year files, restore-safety
copies), and every read-only bundled file through ``resource_base()``. Point
those two here and the rest follows.

Stdlib only, no local imports, so this module can be imported before anything
else without a cycle.
"""

import os
import sys

# The per-user folder name under %LOCALAPPDATA% for an installed build.
# Legacy installs used "Construction OS"; we still open that folder if present
# so existing books are not stranded after the ACO rebrand.
APP_DIR_NAME = 'ACO'
_LEGACY_APP_DIR_NAMES = ('Construction OS',)


def is_frozen():
    """True when running from a PyInstaller (or similar) frozen build."""
    return getattr(sys, 'frozen', False)


def _source_dir():
    return os.path.dirname(os.path.abspath(__file__))


def resource_base():
    """Directory holding read-only bundled files (the ``resources/`` folder).

    Under PyInstaller the bundle is unpacked to ``sys._MEIPASS``; from source it
    is the ``construction_app/`` directory this module lives in.
    """
    if is_frozen():
        return getattr(sys, '_MEIPASS', _source_dir())
    return _source_dir()


def data_dir():
    """Writable directory for the database, company registry and sidecars.

    Installed: ``%LOCALAPPDATA%\\ACO`` (per user, created on first
    use, no admin). If that folder does not exist yet but a legacy
    ``Construction OS`` data folder does, that legacy path is reused so an
    upgrade does not orphan the book. From source: the code directory,
    preserving the self-contained behaviour the developer already relies on.
    If the per-user folder cannot be created for any reason, falls back to the
    code directory rather than failing to start.
    """
    if not is_frozen():
        return _source_dir()
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    target = os.path.join(base, APP_DIR_NAME)
    if os.path.isdir(target):
        return target
    for legacy in _LEGACY_APP_DIR_NAMES:
        legacy_path = os.path.join(base, legacy)
        if os.path.isdir(legacy_path):
            return legacy_path
    try:
        os.makedirs(target, exist_ok=True)
        return target
    except OSError:
        return _source_dir()


def data_path(name):
    """A file inside the writable data directory."""
    return os.path.join(data_dir(), name)


def resource_path(*parts):
    """A read-only bundled file, e.g. ``resource_path('resources', 'app.ico')``."""
    return os.path.join(resource_base(), *parts)


def app_install_dir():
    """The directory the app is installed/running in.

    Distinct from ``resource_base()``: under PyInstaller that is the unpacked
    bundle (``sys._MEIPASS``), but a **large, optional** payload — the inbuilt
    AI model's multi-hundred-MB GGUF — is deliberately laid down *next to the
    executable* by the installer rather than packed into the frozen bundle (so
    PyInstaller never has to hash/compress a gigabyte). This points there: the
    folder holding ``ConstructionOS.exe`` when frozen, or the code directory
    from source.
    """
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return _source_dir()
