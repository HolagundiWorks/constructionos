#!/usr/bin/env python3
"""Soft-fail stub HTTP server for OCR / STT / VLM sidecars (local L8 floor).

Stdlib only. Binds **127.0.0.1** only. Answers:

* ``GET /health`` → ``{"ok": true, "kind": "<ocr|stt|vlm>", "stub": true}``
* ``POST /extract`` → ``{"fields": {}, "confidence": {}, "stub": true}``

so ``sidecar_bridge`` and the WinUI Capture page can be exercised **without**
installing multi-GB model weights. Replace the handler body when a real
extractor is present locally.

Run from repo root::

    python sidecars/stub_server.py --kind ocr   # :8765
    python sidecars/stub_server.py --kind stt   # :8766
    python sidecars/stub_server.py --kind vlm   # :8767

Or::

    python -c "import runpy; runpy.run_path('sidecars/stub_server.py')" -- --kind ocr
"""

from __future__ import print_function

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORTS = {
    'ocr': 8765,
    'stt': 8766,
    'vlm': 8767,
}


def extract_response(kind, body):
    """Build the soft-fail extract payload (testable without a socket)."""
    fields = {}
    confidence = {}
    if isinstance(body, dict):
        # Echo any caller-supplied preview fields so UI probes can see round-trip.
        preview = body.get('fields') or body.get('preview') or {}
        if isinstance(preview, dict):
            for k, v in preview.items():
                fields[str(k)] = v
                confidence[str(k)] = 0.0
    return {
        'fields': fields,
        'confidence': confidence,
        'stub': True,
        'kind': kind,
        'note': 'stub_server — install real weights locally for OCR/STT/VLM',
    }


def make_handler(kind):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("[%s] %s\n" % (kind, fmt % args))

        def _send(self, code, payload):
            raw = json.dumps(payload).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = (self.path or '/').split('?', 1)[0]
            if path in ('/health', '/'):
                self._send(200, {'ok': True, 'kind': kind, 'stub': True})
            else:
                self._send(404, {'error': 'not found', 'path': path})

        def do_POST(self):
            path = (self.path or '/').split('?', 1)[0]
            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if length > 0 else b''
            try:
                body = json.loads(raw.decode('utf-8') or '{}')
            except (ValueError, UnicodeDecodeError):
                body = {}
            if path == '/extract':
                self._send(200, extract_response(kind, body))
            else:
                self._send(404, {'error': 'not found', 'path': path})

    return Handler


def main(argv=None):
    p = argparse.ArgumentParser(description='Construction OS sidecar stub server')
    p.add_argument('--kind', choices=sorted(PORTS), default='ocr')
    p.add_argument('--host', default='127.0.0.1',
                   help='Bind address (default loopback only)')
    p.add_argument('--port', type=int, default=None)
    args = p.parse_args(argv)
    if args.host not in ('127.0.0.1', 'localhost', '::1'):
        print('Refusing non-loopback host %r — sidecars must stay local.'
              % args.host, file=sys.stderr)
        return 2
    port = args.port or PORTS[args.kind]
    server = HTTPServer((args.host, port), make_handler(args.kind))
    print('stub %s listening on http://%s:%d  (Ctrl+C to stop)'
          % (args.kind, args.host, port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped', flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
