"""First-run setup wizard (Phase 4 — trust & ease).

The very first time the app opens with an empty book, a non-technical owner
shouldn't face a blank grid. This small modal captures the essentials — firm
details (for tax invoices), the first site, and the first client — writes them,
and marks setup done so it never nags again. Everything is optional: Skip closes
it and the app opens as before.

``maybe_run_setup(root, db_getter)`` is the entry point; it shows the wizard only
when setup is needed (empty masters and not previously completed/skipped).
"""

import tkinter as tk
import theme
from tkinter import ttk

import assets
import branding


def needs_setup(conn):
    """True on a fresh book: no sites, no clients, and not previously done."""
    done = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'setup_done'").fetchone()
    if done and done['value'] == '1':
        return False
    sites = conn.execute('SELECT COUNT(*) AS c FROM sites').fetchone()['c']
    clients = conn.execute('SELECT COUNT(*) AS c FROM clients').fetchone()['c']
    return sites == 0 and clients == 0


class SetupWizard:
    def __init__(self, root, db_getter):
        self.db_getter = db_getter
        self.win = tk.Toplevel(root)
        self.win.title('{} — Welcome'.format(branding.APP_NAME))
        self.win.resizable(False, False)
        self.win.transient(root)
        self.win.grab_set()

        frm = ttk.Frame(self.win, padding=20)
        frm.pack(fill='both', expand=True)
        try:
            self._logo = tk.PhotoImage(file=assets.LOGO_SQUARE)
            ttk.Label(frm, image=self._logo).grid(row=0, column=0, columnspan=2,
                                                  pady=(0, 8))
        except Exception:
            pass
        ttk.Label(frm, text='Welcome! Let\'s set up the basics.',
                  font=('TkDefaultFont', 13, 'bold')) \
            .grid(row=1, column=0, columnspan=2, pady=(0, 4), sticky='w')
        ttk.Label(frm, text='All fields are optional — you can add or change '
                            'everything later. This appears only once.',
                  foreground=theme.palette()['muted'], wraplength=340, justify='left') \
            .grid(row=2, column=0, columnspan=2, pady=(0, 10), sticky='w')

        self.vars = {}
        rows = [
            ('company_name', 'Firm Name'),
            ('seller_gstin', 'GSTIN'),
            ('seller_address', 'Address'),
            ('site_name', 'First Site / Project'),
            ('client_name', 'First Client'),
        ]
        for i, (key, label) in enumerate(rows, start=3):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky='w', pady=4)
            self.vars[key] = tk.StringVar()
            ttk.Entry(frm, textvariable=self.vars[key], width=28) \
                .grid(row=i, column=1, pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=3 + len(rows), column=0, columnspan=2, pady=(12, 0), sticky='e')
        ttk.Button(btns, text='Finish', command=self._finish).pack(side='left', padx=4)
        ttk.Button(btns, text='Skip', command=self._skip).pack(side='left')

        ttk.Label(frm, text='{} · {}'.format(branding.APP_NAME, branding.CREDIT),
                  foreground=theme.palette()['helper'], font=('TkDefaultFont', 8)) \
            .grid(row=4 + len(rows), column=0, columnspan=2, pady=(12, 0))

        self.win.protocol('WM_DELETE_WINDOW', self._skip)
        root.wait_window(self.win)

    def _finish(self):
        firm = {k: self.vars[k].get().strip()
                for k in ('company_name', 'seller_gstin', 'seller_address')}
        site = self.vars['site_name'].get().strip()
        client = self.vars['client_name'].get().strip()
        conn = self.db_getter()
        try:
            for key, val in firm.items():
                if val:
                    conn.execute(
                        'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                        'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                        (key, val))
            if site:
                conn.execute('INSERT INTO sites (name) VALUES (?)', (site,))
            if client:
                conn.execute('INSERT INTO clients (name) VALUES (?)', (client,))
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                ('setup_done', '1'))
            conn.commit()
        finally:
            conn.close()
        self.win.destroy()

    def _skip(self):
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                ('setup_done', '1'))
            conn.commit()
        finally:
            conn.close()
        self.win.destroy()


def maybe_run_setup(root, db_getter):
    """Show the wizard once on a fresh book. Safe to call every startup."""
    conn = db_getter()
    try:
        show = needs_setup(conn)
    finally:
        conn.close()
    if show:
        SetupWizard(root, db_getter)
