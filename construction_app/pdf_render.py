"""Render a PDF page to a PNG using an external tool, so the takeoff canvas can
show a drawing that was issued as a PDF.

tkinter can display a PNG but not a PDF, and the standard library has no PDF
renderer. Rather than take on a pip dependency, this detects a renderer already
on the machine — **poppler** (``pdftoppm``) or **Ghostscript** — and drives it
with ``subprocess``. If neither is present it says so plainly and the user can
install one, or simply export the page to a PNG and open that. Same spirit as
the AI-engine (Foundry Local) integration: use a local tool if it's there,
never bundle a big native program.
"""

import os
import shutil
import subprocess
import sys
import tempfile

_RENDERERS = ('pdftoppm', 'gswin64c', 'gswin32c', 'gs')


def _no_window():
    if sys.platform.startswith('win') and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def renderer():
    """The first available PDF→image tool on PATH, or None."""
    for tool in _RENDERERS:
        if shutil.which(tool):
            return tool
    return None


def available():
    return renderer() is not None


def install_hint():
    return ('To open PDFs here, install a PDF renderer — poppler (which '
            'provides pdftoppm) or Ghostscript — or export the drawing page to '
            'a PNG and open that instead.')


def render_page(pdf_path, page=1, dpi=150, out_dir=None):
    """Render one page of ``pdf_path`` to a PNG and return its path.

    Higher ``dpi`` gives a crisper, larger image (better for precise takeoff)
    at the cost of memory. Raises ``RuntimeError`` with a helpful message when
    no renderer is installed or the render fails."""
    tool = renderer()
    if not tool:
        raise RuntimeError(install_hint())
    out_dir = out_dir or tempfile.mkdtemp(prefix='cos_takeoff_')
    page = max(1, int(page or 1))
    dpi = int(dpi or 150)
    base = os.path.basename(tool).lower()
    if base.startswith('pdftoppm'):
        prefix = os.path.join(out_dir, 'page')
        _run([tool, '-png', '-r', str(dpi), '-f', str(page), '-l', str(page),
              '-singlefile', pdf_path, prefix])
        out = prefix + '.png'
    else:                                  # ghostscript
        out = os.path.join(out_dir, 'page.png')
        _run([tool, '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER',
              '-sDEVICE=png16m', '-r' + str(dpi),
              '-dFirstPage=' + str(page), '-dLastPage=' + str(page),
              '-o', out, pdf_path])
    if not os.path.exists(out):
        raise RuntimeError('The PDF renderer produced no image.')
    return out


def _run(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                             **_no_window())
    except Exception as exc:                                # noqa: BLE001
        raise RuntimeError('PDF render failed to start: {}'.format(exc))
    if res.returncode != 0:
        raise RuntimeError('PDF render failed: {}'.format(
            (res.stderr or res.stdout or 'unknown error')[:300]))
