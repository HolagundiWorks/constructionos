"""The HTTP plumbing around ``webapp`` — standard library only.

A ``ThreadingHTTPServer`` handles each browser request on its own thread; every
request opens and closes its own short-lived SQLite connection (WAL mode, busy
timeout), so many clients can read at once without stepping on each other. This
module only translates HTTP <-> ``webapp.Request``/``Response``; all the routing
and rendering lives in ``webapp``.

Two ways to run it:

* ``WebServer(host, port).start()`` — non-blocking, for the desktop app's
  "Web / LAN access" panel (runs in a background daemon thread).
* ``serve(host, port)`` — blocking, for the headless ``web_main`` entry point on
  an always-on office machine.
"""

import http.cookies
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import webapp

MAX_BODY = 2 * 1024 * 1024      # 2 MB cap on a POST body — forms are tiny


def _flatten(qs):
    """parse_qs gives {k:[v,...]}; the app wants {k:v} (last wins)."""
    return {k: v[-1] for k, v in qs.items() if v}


class _Handler(BaseHTTPRequestHandler):
    server_version = 'ConstructionOS'
    protocol_version = 'HTTP/1.1'

    # Quiet by default; the desktop panel doesn't want a request log on stderr.
    def log_message(self, *args):
        pass

    def _dispatch(self, method):
        parsed = urllib.parse.urlsplit(self.path)
        query = _flatten(urllib.parse.parse_qs(parsed.query))
        form, form_multi = {}, {}
        if method == 'POST':
            try:
                length = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                length = 0
            if length > MAX_BODY:
                self._send(webapp.Response('Request too large', status=413))
                return
            raw = self.rfile.read(length).decode('utf-8', 'replace') if length else ''
            ctype = (self.headers.get('Content-Type') or '')
            if 'application/x-www-form-urlencoded' in ctype:
                # keep_blank_values so repeated line-item columns stay aligned
                # by row index (an empty cell must not shorten its column).
                form_multi = urllib.parse.parse_qs(raw, keep_blank_values=True)
                form = _flatten(form_multi)

        cookies = {}
        raw_cookie = self.headers.get('Cookie')
        if raw_cookie:
            jar = http.cookies.SimpleCookie()
            try:
                jar.load(raw_cookie)
                cookies = {k: m.value for k, m in jar.items()}
            except http.cookies.CookieError:
                cookies = {}

        req = webapp.Request(
            method=method, path=parsed.path, query=query, form=form,
            form_multi=form_multi, cookies=cookies, headers=dict(self.headers),
            client=self.client_address[0] if self.client_address else '')
        try:
            resp = webapp.handle(req)
        except Exception as exc:                             # noqa: BLE001
            resp = webapp.Response(
                '<h1>Server error</h1><p>{}</p>'.format(
                    webapp.R.esc(exc)), status=500)
        self._send(resp)

    def _send(self, resp):
        body = resp.body if isinstance(resp.body, (bytes, bytearray)) \
            else str(resp.body).encode('utf-8')
        self.send_response(resp.status)
        for key, value in resp.headers.items():
            self.send_header(key, value)
        for cookie in resp.cookies:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        self._dispatch('GET')

    def do_POST(self):
        self._dispatch('POST')

    def do_HEAD(self):
        self._dispatch('GET')


class _ThreadingServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class WebServer:
    """A background HTTP server the desktop app can start and stop."""

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = int(port)
        self._httpd = None
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        """Bind and serve in a daemon thread. Raises OSError if the port is
        taken — the caller shows that to the user."""
        if self.running:
            return
        self._httpd = _ThreadingServer((self.host, self.port), _Handler)
        # If bound to port 0 (tests), learn the real port.
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name='cos-web', daemon=True)
        self._thread.start()

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        self._thread = None


def serve(host='0.0.0.0', port=8080):
    """Blocking server for the headless entry point. Ctrl-C stops it."""
    httpd = _ThreadingServer((host, int(port)), _Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
