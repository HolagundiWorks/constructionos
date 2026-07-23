"""Bundled brand assets (logos) and helpers.

The logo files live in ``resources/`` next to the code. This module is stdlib
only (no tkinter): it exposes file paths and a base64 ``data:`` URI builder for
embedding the logo in the printable HTML documents. GUI code loads the PNGs into
``tk.PhotoImage`` directly from these paths (Tk 8.6+ reads PNG natively) and is
expected to fail soft if the file or Tk PNG support is missing.
"""

import base64
import os

import paths

# Resources are read-only. From source they sit next to the code; in an
# installed (frozen) build they are read from the bundle's unpack dir.
RES_DIR = paths.resource_path('resources')

LOGO_SQUARE = os.path.join(RES_DIR, 'logo_square.png')
LOGO_RECT = os.path.join(RES_DIR, 'logo_rectangle.png')
# Dark-background variants: the mark/wordmark in white (initials kept Radiant
# Orange) so they read on the dark rail. All brand art is generated vector-crisp
# from one source, branding/make-brand.ps1.
LOGO_SQUARE_WHITE = os.path.join(RES_DIR, 'logo_square_white.png')
LOGO_RECT_WHITE = os.path.join(RES_DIR, 'logo_rectangle_white.png')
# Vertical lockup (mark over the stacked wordmark) for tall / square contexts —
# splash, document headers, share cards.
LOGO_VERTICAL = os.path.join(RES_DIR, 'logo_vertical.png')
LOGO_VERTICAL_WHITE = os.path.join(RES_DIR, 'logo_vertical_white.png')
# The bare gauge-C mark (Radiant Orange on transparent) for light surfaces, and
# the browser-tab favicon (orange mark on white).
LOGO_MARK = os.path.join(RES_DIR, 'logo_mark.png')
FAVICON = os.path.join(RES_DIR, 'favicon.png')
APP_ICON = os.path.join(RES_DIR, 'app.ico')


def _mime_for(raw):
    """Sniff the image type from its magic bytes so a firm can upload a PNG,
    JPEG or GIF and the data: URI still declares the right type."""
    if raw[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if raw[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    return 'image/png'          # default; browsers content-sniff anyway


def data_uri(path):
    """Return a ``data:<mime>;base64,...`` URI for an image, or '' if missing."""
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except OSError:
        return ''
    return 'data:{};base64,{}'.format(
        _mime_for(raw), base64.b64encode(raw).decode('ascii'))


def logo_rect_uri():
    return data_uri(LOGO_RECT)


# ---------------------------------------------------------------- firm logo
# The contractor's own logo for the printed letterhead, kept in the data folder
# (so it survives an app upgrade and is per-company-file-independent). When set,
# it replaces the bundled app logo on every printed document; the on-screen rail
# keeps the app's own brand.
_FIRM_LOGO = 'firm_logo.png'          # fixed slot; contents may be PNG/JPEG/GIF


def firm_logo_path():
    """The firm's uploaded logo, or None if none has been set."""
    p = paths.data_path(_FIRM_LOGO)
    return p if os.path.exists(p) else None


def _is_supported_image(raw):
    return (raw[:8] == b'\x89PNG\r\n\x1a\n'          # PNG
            or raw[:3] == b'\xff\xd8\xff'            # JPEG
            or raw[:6] in (b'GIF87a', b'GIF89a'))    # GIF


def set_firm_logo(src_path):
    """Store ``src_path`` as the firm logo. Returns ``(ok, message)``."""
    try:
        with open(src_path, 'rb') as fh:
            raw = fh.read()
    except OSError as exc:
        return False, 'Could not read that file: {}'.format(exc)
    if not _is_supported_image(raw):
        return False, 'Please choose a PNG, JPG or GIF image.'
    try:
        with open(paths.data_path(_FIRM_LOGO), 'wb') as fh:
            fh.write(raw)
    except OSError as exc:
        return False, 'Could not save the logo: {}'.format(exc)
    return True, 'Firm logo saved.'


def clear_firm_logo():
    """Remove the firm logo (documents fall back to the bundled app logo)."""
    p = paths.data_path(_FIRM_LOGO)
    try:
        if os.path.exists(p):
            os.remove(p)
    except OSError:
        pass


def brand_logo_html(height=46):
    """The letterhead ``<img>``: the firm's uploaded logo if set, else the
    bundled app logo, or '' if neither is available."""
    fp = firm_logo_path()
    uri = data_uri(fp) if fp else logo_rect_uri()
    if not uri:
        return ''
    return '<img src="{}" alt="ACO" style="height:{}px;" />'.format(uri, height)


def logo_html(height=46):
    """An ``<img>`` tag for the (bundled) rectangular logo, or '' if missing."""
    uri = logo_rect_uri()
    if not uri:
        return ''
    return '<img src="{}" alt="ACO" style="height:{}px;" />'.format(uri, height)
