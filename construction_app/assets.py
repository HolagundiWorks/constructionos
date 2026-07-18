"""Bundled brand assets (logos) and helpers.

The logo files live in ``resources/`` next to the code. This module is stdlib
only (no tkinter): it exposes file paths and a base64 ``data:`` URI builder for
embedding the logo in the printable HTML documents. GUI code loads the PNGs into
``tk.PhotoImage`` directly from these paths (Tk 8.6+ reads PNG natively) and is
expected to fail soft if the file or Tk PNG support is missing.
"""

import base64
import os

RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')

LOGO_SQUARE = os.path.join(RES_DIR, 'logo_square.png')
LOGO_RECT = os.path.join(RES_DIR, 'logo_rectangle.png')
APP_ICON = os.path.join(RES_DIR, 'app.ico')


def data_uri(path):
    """Return a ``data:image/png;base64,...`` URI for a PNG, or '' if missing."""
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except OSError:
        return ''
    return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')


def logo_rect_uri():
    return data_uri(LOGO_RECT)


def logo_html(height=46):
    """An ``<img>`` tag for the rectangular logo, or '' if the file is missing."""
    uri = logo_rect_uri()
    if not uri:
        return ''
    return '<img src="{}" alt="logo" style="height:{}px;" />'.format(uri, height)
