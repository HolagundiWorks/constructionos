"""Minimal Microsoft **Foundry Local** client over the standard library (no pip).

Foundry Local runs an on-device inference daemon with an **OpenAI-compatible**
REST API on localhost — its port is chosen dynamically and discovered from the
CLI (see :mod:`foundry_service`). This stays within the project's constraints:
offline (localhost only) and stdlib-only (``urllib``). Everything fails soft, so
the rest of the app is unaffected when Foundry Local isn't installed or running.

Replaces the earlier Ollama client: same job (the assistant's NL→SQL), same
single built-in model, now served by Foundry Local's OpenAI endpoint.
"""

import json
import shutil
import urllib.request
import urllib.error

import foundry_service

# The app's inbuilt default: **Qwen2.5-Coder 1.5B** — tuned for code/SQL (the
# assistant's NL→SQL job), ~1.8 GB, runs on CPU or the local GPU/NPU that
# Foundry Local auto-selects, Apache-2.0. Foundry Local downloads the optimized
# ONNX build from its own catalogue; there is **no picker** (one built-in model).
DEFAULT_MODEL = 'qwen2.5-coder-1.5b'
# Fallback base URL used only if the daemon's dynamic endpoint can't be
# discovered; the real endpoint comes from ``foundry_service.endpoint()``.
DEFAULT_HOST = 'http://127.0.0.1:5273'


class FoundryError(Exception):
    pass


def installed():
    """True if the ``foundry`` CLI is on PATH (so we can offer to start it)."""
    return shutil.which('foundry') is not None


def endpoint():
    """The running daemon's OpenAI base URL, or the fallback."""
    return foundry_service.endpoint() or DEFAULT_HOST


def _url(host, path):
    return host.rstrip('/') + path


def available(host=None, timeout=1.5):
    """True if the Foundry Local OpenAI endpoint answers at ``host``."""
    base = host or endpoint()
    try:
        with urllib.request.urlopen(_url(base, '/v1/models'), timeout=timeout) as r:
            return 200 <= getattr(r, 'status', 200) < 300
    except Exception:
        return False


def list_models(host=None, timeout=3):
    """The model ids the daemon currently serves (loaded), or []."""
    base = host or endpoint()
    try:
        with urllib.request.urlopen(_url(base, '/v1/models'), timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
        return [m.get('id', '') for m in data.get('data', [])]
    except Exception:
        return []


def generate(prompt, model=DEFAULT_MODEL, host=None, system=None,
             timeout=120, temperature=0.0):
    """One chat completion via the OpenAI-compatible ``/v1/chat/completions``.

    Returns the assistant's text. Raises :class:`FoundryError` with a
    plain-language message on any failure so callers can show it to the user.
    """
    base = host or endpoint()
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    body = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'stream': False,
    }
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        _url(base, '/v1/chat/completions'), data=data,
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
            raise FoundryError(
                "Model '{}' is not loaded. Load it with:  foundry model run {}"
                .format(model, model))
        raise FoundryError(
            'Foundry Local error {}: {}'.format(exc.code, detail[:200]))
    except urllib.error.URLError as exc:
        raise FoundryError(
            'Cannot reach Foundry Local at {} ({}). Start it with: '
            'foundry server start'.format(base, exc.reason))
    except Exception as exc:                       # noqa: BLE001
        raise FoundryError('Foundry Local request failed: {}'.format(exc))
    choices = payload.get('choices') or []
    if not choices:
        return ''
    return (choices[0].get('message') or {}).get('content', '') or ''
