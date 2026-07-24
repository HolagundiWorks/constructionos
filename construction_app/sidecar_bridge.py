"""Localhost bridge to OCR / STT / VLM sidecars (E1 · L8) — soft-fail.

No tkinter, no pip. Heavy models live outside the stdlib core (see
``docs/AI-MODELS-AND-DEPLOYMENT.md`` and ``sidecars/*/README.md``). This module
is the deterministic floor: probe whether a sidecar answers, POST an extract
request, and stage the result through ``capture.build_draft``.

When a sidecar is missing or errors, callers get ``ok=False`` and an empty
draft — never an exception into the books. Nothing is written here.
"""

import json
import os
import urllib.error
import urllib.request

import capture

# Default localhost ports (sidecars bind loopback only — never 0.0.0.0).
DEFAULTS = {
    'ocr': 'http://127.0.0.1:8765',
    'stt': 'http://127.0.0.1:8766',
    'vlm': 'http://127.0.0.1:8767',
}

KINDS = tuple(DEFAULTS.keys())


def _repo_sidecars_root():
    """``<repo>/sidecars`` next to ``construction_app/`` when run from source."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, '..', 'sidecars'))


def stub_present(kind):
    """True if the in-repo stub folder for ``kind`` exists (README only until
    weights are installed locally)."""
    if kind not in DEFAULTS:
        return False
    return os.path.isdir(os.path.join(_repo_sidecars_root(), kind))


def base_url(kind, host=None):
    if kind not in DEFAULTS:
        return None
    return (host or DEFAULTS[kind]).rstrip('/')


def available(kind, host=None, timeout=1.0):
    """True if the sidecar answers GET /health at its localhost URL."""
    url = base_url(kind, host)
    if not url:
        return False
    try:
        with urllib.request.urlopen(url + '/health', timeout=timeout) as r:
            return 200 <= getattr(r, 'status', 200) < 300
    except Exception:
        return False


def status(host_map=None, timeout=1.0):
    """Per-kind readiness: stub folder + live HTTP probe."""
    host_map = host_map or {}
    out = {}
    for kind in KINDS:
        live = available(kind, host=host_map.get(kind), timeout=timeout)
        out[kind] = {
            'kind': kind,
            'stub': stub_present(kind),
            'available': live,
            'url': base_url(kind, host_map.get(kind)),
        }
    return out


def _post_json(url, body, timeout=30):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'},
        method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode('utf-8')
    return json.loads(raw) if raw else {}


def extract(kind, payload=None, host=None, timeout=30):
    """Ask a sidecar to extract fields; stage a ``capture`` draft.

    ``payload`` is sidecar-specific (e.g. ``{path: …}`` or ``{audio_b64: …}``).
    Returns::

        {
          'ok': bool,
          'kind': str,
          'reason': str|None,   # when ok is False
          'draft': capture draft (may be empty),
          'needs_review': bool,
        }
    """
    if kind not in DEFAULTS:
        return {
            'ok': False, 'kind': kind, 'reason': 'unknown kind',
            'draft': capture.build_draft({}), 'needs_review': True,
        }
    url = base_url(kind, host) + '/extract'
    try:
        raw = _post_json(url, payload or {}, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            'ok': False, 'kind': kind,
            'reason': 'sidecar unavailable ({})'.format(
                getattr(exc, 'reason', None) or type(exc).__name__),
            'draft': capture.build_draft({}), 'needs_review': True,
        }
    fields = raw.get('fields') or raw.get('extracted') or {}
    confidence = raw.get('confidence') or {}
    if not isinstance(fields, dict):
        fields = {}
    # Phase D: VLM / vector sidecars may return geometry drafts separately.
    elements = raw.get('elements')
    if elements is not None and 'elements' not in fields:
        fields = dict(fields)
        fields['elements'] = elements
    draft = capture.build_draft(fields, confidence=confidence,
                                source=capture.AI)
    out = {
        'ok': True, 'kind': kind, 'reason': None,
        'draft': draft,
        'needs_review': capture.needs_review(draft),
    }
    if isinstance(elements, list):
        out['elements'] = elements
        out['element_count'] = len(elements)
    return out
