"""Headless entry point for the browser/LAN server.

Run this on an always-on office machine so colleagues reach ACO (Accelerated Construction Operations) in a
browser — no client to install, no desktop window:

    python web_main.py                 # 0.0.0.0:8080, every LAN interface
    python web_main.py --port 9000
    python web_main.py --host 127.0.0.1 --port 8080   # this machine only

It serves the SAME database the desktop app uses (``%LOCALAPPDATA%\\Construction
OS\\construction.db`` when installed, or the file beside the code from source).
Login is required; the first visit creates the administrator.
"""

import branding

import argparse

import db
import netinfo
import webserver


def main(argv=None):
    parser = argparse.ArgumentParser(description=branding.WINDOW_TITLE + ' — LAN web server')
    parser.add_argument('--host', default='0.0.0.0',
                        help='bind address (default 0.0.0.0 = all interfaces)')
    parser.add_argument('--port', type=int, default=8080,
                        help='port (default 8080)')
    args = parser.parse_args(argv)

    db.init_db()      # make sure the schema exists before the first request

    print(branding.APP_NAME + ' — web / LAN server')
    print('Serving database: {}'.format(db.DB_PATH))
    if args.host in ('0.0.0.0', '::'):
        print('Open in a browser on this network:')
        for url in netinfo.urls(args.port):
            print('   ' + url)
    else:
        print('   http://{}:{}/'.format(args.host, args.port))
    print('Login is required (first visit creates the admin). Ctrl-C to stop.')
    webserver.serve(args.host, args.port)


if __name__ == '__main__':
    main()
