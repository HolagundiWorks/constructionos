"""Extract text from a PDF via local ``pdftotext`` (soft-fail, no pip).

Same spirit as ``pdf_render``: use a tool on PATH if present; never bundle a
native binary. Output feeds ``boq_import`` / ``grn_draft`` / ``text_extract``.
"""

import os
import shutil
import subprocess
import sys
import tempfile


def _no_window():
    if sys.platform.startswith('win') and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def available():
    return shutil.which('pdftotext') is not None


def install_hint():
    return ('Install Poppler (pdftotext) to extract text from PDFs. '
            'On Windows: scoop/choco install poppler. '
            'Or export the schedule as CSV and use BOQ import.')


def extract_text(path, max_pages=None, timeout=60):
    """Return ``{ok, text, reason}``. Soft-fails when the tool or file is missing.

    ``max_pages`` is best-effort (``-l``); ignored when the binary rejects it.
    """
    path = os.path.abspath(path or '')
    if not path or not os.path.isfile(path):
        return {'ok': False, 'text': '', 'reason': 'file not found'}
    if not available():
        return {'ok': False, 'text': '', 'reason': install_hint()}
    out_fd, out_path = tempfile.mkstemp(suffix='.txt')
    os.close(out_fd)
    try:
        cmd = ['pdftotext', '-layout', '-enc', 'UTF-8']
        if max_pages:
            try:
                cmd.extend(['-l', str(int(max_pages))])
            except (TypeError, ValueError):
                pass
        cmd.extend([path, out_path])
        subprocess.run(cmd, check=False, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       **_no_window())
        with open(out_path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        return {'ok': True, 'text': text, 'reason': None}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'text': '',
                'reason': 'pdftotext failed ({})'.format(type(exc).__name__)}
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
