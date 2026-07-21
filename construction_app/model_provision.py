"""Register the *inbuilt* assistant model into Ollama — with no download.

The installer lays a small folder next to the app::

    <install>/ai/Modelfile
    <install>/ai/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf

On first run, if that bundled model is not yet registered in the local Ollama,
the app runs an **offline** ``ollama create`` to import the GGUF. After that the
AI assistant answers fully offline, on a machine that has never touched the
internet — the whole point of "inbuilt". A plain ``ollama pull
qwen2.5-coder:1.5b`` yields the very same model name, so the pull-it-yourself
path and the bundled path converge and nothing is done twice.

The heavy lifting (running Ollama, importing a gigabyte GGUF) belongs to Ollama;
this module only *locates* the bundled files, decides whether work is needed,
and drives the one command. The pure, side-effect-free parts (locating the
folder, building the command, deciding "already registered") are split out so
they can be unit-tested without Ollama installed.
"""

import os
import subprocess
import sys

import paths
import ollama_client
import ollama_service as service

# The tag the bundled model is registered under — identical to what a real
# `ollama pull` would produce, so the app's DEFAULT_MODEL matches either way.
MODEL_NAME = 'qwen2.5-coder:1.5b'
GGUF_NAME = 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf'
MODELFILE_NAME = 'Modelfile'
_AI_SUBDIR = 'ai'


def _candidate_dirs():
    """Folders that might hold the bundled model, most-likely first.

    Installed: ``<install>/ai`` (the installer's drop point) and the frozen
    bundle. From source: ``construction_app/ai`` and the repo's
    ``installer/ai`` (where the Modelfile is committed and a developer may drop
    a GGUF to test)."""
    seen, out = set(), []
    for base in (paths.app_install_dir(), paths.resource_base()):
        d = os.path.join(base, _AI_SUBDIR)
        if d not in seen:
            seen.add(d)
            out.append(d)
    # repo installer/ai, when running from source (…/construction_app/..)
    repo_ai = os.path.join(os.path.dirname(paths.resource_base()),
                           'installer', _AI_SUBDIR)
    if repo_ai not in seen:
        out.append(repo_ai)
    return out


def ai_dir():
    """The folder holding the bundled Modelfile — the first candidate that has
    one, else the primary drop point (so callers can report where to put it)."""
    for d in _candidate_dirs():
        if os.path.exists(os.path.join(d, MODELFILE_NAME)):
            return d
    return _candidate_dirs()[0]


def modelfile_path():
    return os.path.join(ai_dir(), MODELFILE_NAME)


def gguf_path():
    return os.path.join(ai_dir(), GGUF_NAME)


def bundled():
    """True when both the Modelfile and the GGUF are present — i.e. this build
    actually carries the inbuilt model (a lean build won't)."""
    return os.path.exists(modelfile_path()) and os.path.exists(gguf_path())


def is_registered(installed_names, name=MODEL_NAME):
    """Pure: is ``name`` already among the installed model names? Matches an
    exact tag or the bare model (``qwen2.5-coder:1.5b`` vs ``qwen2.5-coder``)."""
    base = name.split(':', 1)[0]
    for n in installed_names or []:
        n = (n or '').strip()
        if n == name or n.split(':', 1)[0] == base:
            return True
    return False


def create_command(ollama='ollama', modelfile=None, name=MODEL_NAME):
    """The exact offline import command: ``ollama create <name> -f Modelfile``.
    Run it with ``cwd=ai_dir()`` so the Modelfile's relative ``FROM ./<gguf>``
    resolves."""
    return [ollama, 'create', name, '-f', modelfile or MODELFILE_NAME]


def registered_now(host=None):
    """Query the live Ollama for whether the inbuilt model is already there."""
    host = host or ollama_client.DEFAULT_HOST
    return is_registered(ollama_client.list_models(host))


def _no_window():
    if sys.platform.startswith('win') and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def provision(log=None, host=None, timeout=1200):
    """Import the bundled model into Ollama if it isn't there yet.

    Returns ``(ok, message)``. Fails soft with a plain message for every case
    the app can't fix itself (no bundle, no Ollama, server won't start), so the
    caller just shows it. ``log`` (optional) receives progress lines as Ollama
    imports — a slow copy of a gigabyte, worth showing."""
    host = host or ollama_client.DEFAULT_HOST

    def say(msg):
        if log:
            try:
                log(msg)
            except Exception:                                # noqa: BLE001
                pass

    if not bundled():
        return False, ('No inbuilt model is bundled with this build. Use '
                       'Get a model to download one instead.')
    if not service.installed():
        return False, ('Ollama is not installed yet. Set it up first (Install '
                       'Ollama), then try again.')
    if registered_now(host):
        return True, 'The inbuilt model is already set up.'

    # The import talks to the server; make sure it's up.
    if not ollama_client.available(host):
        say('Starting the Ollama server…')
        service.start_server()
        _wait_available(host)

    ollama = service.binary_path() or 'ollama'
    cmd = create_command(ollama=ollama)
    say('Importing {} (this copies ~1 GB and can take a minute)…'.format(
        MODEL_NAME))
    try:
        proc = subprocess.Popen(
            cmd, cwd=ai_dir(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, **_no_window())
    except Exception as exc:                                  # noqa: BLE001
        return False, 'Could not run "ollama create": {}'.format(exc)
    try:
        for line in iter(proc.stdout.readline, ''):
            line = line.strip()
            if line:
                say(line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return False, 'Setting up the model took too long and was stopped.'
    except Exception as exc:                                  # noqa: BLE001
        return False, 'Model setup failed: {}'.format(exc)

    if proc.returncode == 0 or registered_now(host):
        return True, 'Inbuilt model "{}" is ready.'.format(MODEL_NAME)
    return False, ('Model setup did not complete (ollama create exited {}). '
                   'You can still download a model under Get a model.'.format(
                       proc.returncode))


def _wait_available(host, tries=20, delay=0.5):
    """Poll the server briefly after starting it. Uses the stdlib only; no busy
    spin beyond a short bounded wait."""
    import time
    for _ in range(max(1, tries)):
        if ollama_client.available(host):
            return True
        time.sleep(delay)
    return False
