"""Minimal Ollama client over the standard library (no pip dependency).

Ollama runs a local HTTP server (default http://localhost:11434), so this stays
within the project's constraints: offline (localhost) and stdlib-only (urllib).
The assistant requires the user to have Ollama installed and a model pulled;
everything here fails soft so the rest of the app is unaffected when it isn't.
"""

import json
import shutil
import subprocess
import urllib.request
import urllib.error

DEFAULT_HOST = 'http://localhost:11434'
# The app's inbuilt default: Qwen2.5-Coder 1.5B — tuned for code/SQL (the
# assistant's NL→SQL job), ~1 GB, runs on CPU in ~2 GB RAM, Apache-2.0 so it
# can be bundled offline. The installer registers this exact tag from a bundled
# GGUF (see model_provision.py), and a plain `ollama pull` produces the same
# name, so both the inbuilt and pull-it-yourself paths converge here.
DEFAULT_MODEL = 'qwen2.5-coder:1.5b'


def installed():
    """True if the ``ollama`` binary is on PATH (so we can offer to start it)."""
    return shutil.which('ollama') is not None


def start_server():
    """Best-effort launch of ``ollama serve`` detached. Returns True if started.

    We can't embed Ollama in the app (it's a large native binary + multi-GB
    models), but if it's installed we can spawn its local server so the user
    never opens a terminal. Fails soft when it isn't installed.
    """
    if not installed():
        return False
    try:
        kwargs = {'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
        subprocess.Popen(['ollama', 'serve'], **kwargs)
        return True
    except Exception:
        return False


class OllamaError(Exception):
    pass


def _url(host, path):
    return host.rstrip('/') + path


def available(host=DEFAULT_HOST, timeout=1.5):
    """True if an Ollama server answers at ``host``."""
    try:
        with urllib.request.urlopen(_url(host, '/api/tags'), timeout=timeout) as r:
            return 200 <= getattr(r, 'status', 200) < 300
    except Exception:
        return False


def list_models(host=DEFAULT_HOST, timeout=3):
    """Return the installed model names, or [] if unreachable."""
    try:
        with urllib.request.urlopen(_url(host, '/api/tags'), timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
        return [m.get('name', '') for m in data.get('models', [])]
    except Exception:
        return []


def generate(prompt, model=DEFAULT_MODEL, host=DEFAULT_HOST, system=None,
             timeout=120, temperature=0.0):
    """Call Ollama's /api/generate and return the response text.

    Raises OllamaError with a plain-language message on any failure so callers
    can show it to the user.
    """
    body = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': temperature},
    }
    if system:
        body['system'] = system
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        _url(host, '/api/generate'), data=data,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8')
        except Exception:
            pass
        if exc.code == 404:
            raise OllamaError(
                "Model '{}' is not installed. Run:  ollama pull {}".format(model, model))
        raise OllamaError('Ollama error {}: {}'.format(exc.code, detail[:200]))
    except urllib.error.URLError as exc:
        raise OllamaError(
            'Cannot reach Ollama at {} ({}). Is it running?  '
            'Start it with: ollama serve'.format(host, exc.reason))
    except Exception as exc:                       # noqa: BLE001
        raise OllamaError('Ollama request failed: {}'.format(exc))
    return payload.get('response', '')
