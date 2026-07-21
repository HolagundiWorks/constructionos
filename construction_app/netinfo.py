"""Find this machine's LAN addresses, so the web launcher can tell the user the
exact ``http://<ip>:<port>`` their colleagues type into a browser.

Pure standard library (``socket``). No packet is actually sent: the primary-IP
trick opens a UDP socket "towards" a public address and reads back which local
interface the OS *would* use — enough to learn the LAN IP, without traffic.
"""

import socket


def primary_ip():
    """The LAN IP the OS would use to reach the outside world, or '' if offline.

    A UDP socket is connectionless, so ``connect`` here sends nothing — it just
    binds a route and lets us read the chosen local address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except OSError:
        return ''
    finally:
        s.close()


def _hostname_ips():
    out = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       family=socket.AF_INET):
            out.append(info[4][0])
    except OSError:
        pass
    return out


def local_ips(include_loopback=False):
    """Every IPv4 address this machine answers on, best (routable LAN) first.

    Loopback (127.*) is excluded by default — colleagues can't reach it — but
    kept available for a same-machine test."""
    ordered = []
    seen = set()

    def add(ip):
        if not ip or ip in seen:
            return
        if ip.startswith('127.') and not include_loopback:
            return
        seen.add(ip)
        ordered.append(ip)

    add(primary_ip())
    for ip in _hostname_ips():
        add(ip)
    if include_loopback:
        add('127.0.0.1')
    return ordered


def urls(port, include_loopback=True):
    """Browser URLs to reach a server on this machine at ``port``.

    LAN addresses first (what colleagues use), then localhost (this machine)."""
    port = int(port)
    out = ['http://{}:{}/'.format(ip, port) for ip in local_ips()]
    if include_loopback:
        out.append('http://127.0.0.1:{}/'.format(port))
    return out
