"""Shared 'save HTML + open in browser' helper for printable reports.

Kept separate from the pure ``bill_export`` builders (this touches tkinter and
the filesystem). Used by the document/report tabs to write an export and open it
for print / Save-as-PDF.
"""

import os
import webbrowser
from tkinter import filedialog


def save_and_open_html(html, default_name):
    path = filedialog.asksaveasfilename(
        title='Save', defaultextension='.html', initialfile=default_name,
        filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    webbrowser.open('file://' + os.path.abspath(path))
