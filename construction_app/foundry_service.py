"""Microsoft **Foundry Local** process control over the standard library.

Wraps the ``foundry`` CLI — server ``start`` / ``stop`` / ``status`` and model
``download`` / ``load`` / ``unload`` — so the app can turn the built-in
assistant on and off without a terminal. The daemon exposes an OpenAI-compatible
service on a **dynamically-chosen** localhost port, discovered from
``foundry status``. Fails soft when Foundry Local isn't installed.

Replaces the earlier ``ollama_service`` / ``ollama_api`` / ``model_provision``
trio: same "start the local runtime, ensure the one built-in model" job, now via
the Foundry Local CLI.
"""

import json
import shutil
import subprocess
import sys

_WINDOWS = sys.platform.startswith('win')


def _no_window():
    """Popen/run kwargs that keep a console from flashing up on Windows."""
    if _WINDOWS and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def installed():
    """True if the ``foundry`` CLI is on PATH."""
    return shutil.which('foundry') is not None


def _run(args, timeout=30):
    # Decode as UTF-8 (the foundry CLI emits ●/progress glyphs) with replacement,
    # not the Windows locale codepage — else a reader thread raises
    # UnicodeDecodeError on non-cp1252 bytes and the output is lost.
    return subprocess.run(
        ['foundry'] + args, capture_output=True,
        encoding='utf-8', errors='replace',
        timeout=timeout, **_no_window())


def cli_version(timeout=5):
    if not installed():
        return ''
    try:
        out = _run(['--version'], timeout=timeout)
        lines = (out.stdout or '').strip().splitlines()
        return lines[0].strip() if out.returncode == 0 and lines else ''
    except Exception:
        return ''


def status(timeout=8):
    """Parsed ``foundry status -o json`` (daemon + model diagnostics), or {}."""
    if not installed():
        return {}
    try:
        out = _run(['status', '-o', 'json'], timeout=timeout)
        text = (out.stdout or '').strip()
        return json.loads(text) if out.returncode == 0 and text else {}
    except Exception:
        return {}


def endpoint(timeout=8):
    """The running daemon's OpenAI base URL (``service.webUrls[0]``), or None."""
    svc = status(timeout).get('service') or {}
    urls = svc.get('webUrls') or []
    return urls[0] if urls else None


def server_ready(timeout=8):
    """True if the daemon reports itself ready to serve."""
    return bool((status(timeout).get('service') or {}).get('ready'))


def models_loaded(timeout=8):
    """How many models are loaded in the running daemon (0 if none/unknown)."""
    try:
        return int((status(timeout).get('models') or {}).get('loaded', 0) or 0)
    except (TypeError, ValueError):
        return 0


def start_server(timeout=90):
    """``foundry server start`` — start the daemon + OpenAI service. Best-effort."""
    if not installed():
        return False
    try:
        out = _run(['server', 'start'], timeout=timeout)
        return out.returncode == 0 or 'ready' in (out.stdout or '').lower()
    except Exception:
        return False


def stop_server(timeout=30):
    """``foundry server stop``."""
    if not installed():
        return False
    try:
        return _run(['server', 'stop'], timeout=timeout).returncode == 0
    except Exception:
        return False


def download_model(alias, timeout=3600):
    """``foundry model download`` — fetch the optimized build into the local
    cache. Long timeout: the one-time download can be ~1–2 GB. Idempotent (a
    no-op when already cached). Returns True on success."""
    if not installed():
        return False
    try:
        return _run(['model', 'download', alias], timeout=timeout).returncode == 0
    except Exception:
        return False


def load_model(alias, timeout=300):
    """``foundry model load`` — load a downloaded model into the daemon."""
    if not installed():
        return False
    try:
        return _run(['model', 'load', alias], timeout=timeout).returncode == 0
    except Exception:
        return False


def unload_model(alias, timeout=60):
    """``foundry model unload`` — free the model's memory."""
    if not installed():
        return False
    try:
        return _run(['model', 'unload', alias], timeout=timeout).returncode == 0
    except Exception:
        return False


def provision(alias, timeout=3600):
    """Ensure ``alias`` is downloaded **and** loaded (idempotent). This is the
    one-time model set-up the AI Engine tab runs on first Start."""
    if not installed():
        return False
    if not download_model(alias, timeout=timeout):
        return False
    return load_model(alias)
