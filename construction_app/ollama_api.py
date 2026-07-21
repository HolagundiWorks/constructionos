"""Ollama HTTP API over the standard library (no pip dependency).

Ollama exposes a local HTTP server (default http://127.0.0.1:11434). Everything
here speaks to that server with ``urllib``: list, pull, delete and inspect
models, and report what is loaded right now.

Two conventions worth knowing:

* Long operations (``pull``) stream **NDJSON** — one JSON object per line —
  rather than returning a single document, so callers get progress instead of a
  frozen window. ``pull`` therefore takes a callback and is meant to be run on
  a worker thread.
* The request field for a model name changed from ``name`` to ``model`` across
  Ollama versions. Requests send ``model`` and retry with ``name`` on a 400, so
  this works against both old and new servers.

Every call raises ``OllamaError`` with a message fit to show a user.
"""

import json
import urllib.error
import urllib.request

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 11434


class OllamaError(Exception):
    pass


def base_url(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Normalise host/port into a URL, tolerating a host typed with a scheme."""
    host = (str(host or DEFAULT_HOST)).strip().rstrip('/')
    if host.startswith('http://') or host.startswith('https://'):
        if ':' in host.split('//', 1)[1]:
            return host                     # already carries a port
        return '{}:{}'.format(host, port)
    return 'http://{}:{}'.format(host, port)


def _request(url, method='GET', payload=None, timeout=10):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'} if data else {}
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def _call(url, method='GET', payload=None, timeout=10):
    try:
        with urllib.request.urlopen(
                _request(url, method, payload), timeout=timeout) as resp:
            body = resp.read().decode('utf-8').strip()
        return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8')[:300]
        except Exception:                                   # noqa: BLE001
            pass
        raise OllamaError('Ollama returned {}: {}'.format(exc.code, detail or exc.reason))
    except urllib.error.URLError as exc:
        raise OllamaError(
            'Cannot reach Ollama at {} ({}). Is the server running?'.format(
                url, exc.reason))
    except ValueError as exc:
        raise OllamaError('Unexpected reply from Ollama: {}'.format(exc))


def is_running(url, timeout=1.5):
    """True if a server answers here. Never raises — used for polling."""
    try:
        _call(url + '/api/version', timeout=timeout)
        return True
    except OllamaError:
        return False


def version(url, timeout=3):
    return _call(url + '/api/version', timeout=timeout).get('version', '')


def list_models(url, timeout=10):
    """Installed models as dicts: name, size (bytes), modified, family, params."""
    data = _call(url + '/api/tags', timeout=timeout)
    out = []
    for m in data.get('models', []) or []:
        details = m.get('details') or {}
        out.append({
            'name': m.get('name') or m.get('model') or '',
            'size': m.get('size') or 0,
            'modified': (m.get('modified_at') or '')[:19].replace('T', ' '),
            'family': details.get('family') or '',
            'parameters': details.get('parameter_size') or '',
            'quantization': details.get('quantization_level') or '',
        })
    return sorted(out, key=lambda m: m['name'].lower())


def running_models(url, timeout=5):
    """Models currently loaded in memory (``/api/ps``). [] on older servers."""
    try:
        data = _call(url + '/api/ps', timeout=timeout)
    except OllamaError:
        return []
    return [m.get('name') or m.get('model') or ''
            for m in (data.get('models') or [])]


def show_model(url, name, timeout=15):
    """Model card: parameters, template, licence summary."""
    try:
        return _call(url + '/api/show', 'POST', {'model': name}, timeout)
    except OllamaError:
        return _call(url + '/api/show', 'POST', {'name': name}, timeout)


def delete_model(url, name, timeout=30):
    """Remove a model and free its disk space."""
    try:
        _call(url + '/api/delete', 'DELETE', {'model': name}, timeout)
    except OllamaError as exc:
        if '400' not in str(exc):
            raise
        _call(url + '/api/delete', 'DELETE', {'name': name}, timeout)
    return True


def pull_model(url, name, on_progress=None, timeout=3600, should_stop=None):
    """Download a model, reporting progress as it streams.

    ``on_progress(status, completed, total)`` is called for each NDJSON line —
    ``completed``/``total`` are bytes and may be 0 while Ollama is resolving the
    manifest. ``should_stop()`` is polled so the UI can cancel a download.

    Blocking and slow (models are gigabytes): call this on a worker thread.
    """
    payload = {'model': name, 'stream': True}
    req = _request(url + '/api/pull', 'POST', payload)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 400:                       # older server wants "name"
            req = _request(url + '/api/pull', 'POST', {'name': name, 'stream': True})
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.HTTPError as exc2:
                raise OllamaError('Could not pull {}: {}'.format(name, exc2.reason))
        else:
            detail = ''
            try:
                detail = exc.read().decode('utf-8')[:200]
            except Exception:                                # noqa: BLE001
                pass
            raise OllamaError('Could not pull {}: {}'.format(name, detail or exc.reason))
    except urllib.error.URLError as exc:
        raise OllamaError('Cannot reach Ollama at {} ({}).'.format(url, exc.reason))

    last_error = None
    with resp:
        for raw in resp:
            if should_stop is not None and should_stop():
                raise OllamaError('Download cancelled.')
            line = raw.decode('utf-8', 'replace').strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get('error'):
                last_error = msg['error']
                break
            if on_progress:
                on_progress(msg.get('status', ''),
                            msg.get('completed', 0) or 0,
                            msg.get('total', 0) or 0)
    if last_error:
        raise OllamaError(last_error)
    return True


def human_size(num_bytes):
    """Bytes as a short human string — model sizes are the headline number."""
    try:
        size = float(num_bytes or 0)
    except (TypeError, ValueError):
        return '-'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return '{:.0f} {}'.format(size, unit) if unit in ('B', 'KB') \
                else '{:.1f} {}'.format(size, unit)
        size /= 1024.0
    return '-'
