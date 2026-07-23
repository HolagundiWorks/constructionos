"""Startup company picker + login dialog.

Flow: **select company → sign in** (or Continue when that book has security
off). Creating / importing a company is available from this screen so a fresh
install never has to dig into Tools first.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import theme
import auth
import session
import assets
import branding
import company
import db


class LoginDialog:
    """Modal boot dialog: company first, then credentials for that book."""

    def __init__(self, root, db_getter):
        self.db_getter = db_getter
        self.ok = False
        self._paths = []          # parallel to combobox labels
        self._require_auth = True
        self._first_run = False

        self.win = tk.Toplevel(root)
        self.win.title('{} — Sign in'.format(branding.APP_NAME))
        self.win.resizable(False, False)
        self.win.transient(root)
        self.win.grab_set()

        frm = ttk.Frame(self.win, padding=20)
        frm.pack(fill='both', expand=True)
        try:
            self._logo = tk.PhotoImage(file=assets.LOGO_SQUARE)
            ttk.Label(frm, image=self._logo).grid(row=0, column=0, columnspan=3,
                                                  pady=(0, 8))
        except Exception:
            pass
        ttk.Label(frm, text='Sign in', font=('TkDefaultFont', 14, 'bold')) \
            .grid(row=1, column=0, columnspan=3, pady=(0, 4), sticky='w')
        ttk.Label(frm, text='Select a company, then sign in.',
                  foreground=theme.palette()['helper']) \
            .grid(row=2, column=0, columnspan=3, pady=(0, 10), sticky='w')

        ttk.Label(frm, text='Company').grid(row=3, column=0, sticky='w', pady=4)
        self.company_var = tk.StringVar()
        self.company_combo = ttk.Combobox(
            frm, textvariable=self.company_var, width=28, state='readonly')
        self.company_combo.grid(row=3, column=1, pady=4, sticky='we')
        self.company_combo.bind('<<ComboboxSelected>>', lambda e: self._on_company())
        co_btns = ttk.Frame(frm)
        co_btns.grid(row=3, column=2, sticky='w', padx=(6, 0))
        ttk.Button(co_btns, text='New…', width=7,
                   command=self._new_company).pack(side='left', padx=(0, 2))
        ttk.Button(co_btns, text='Import…', width=8,
                   command=self._import_company).pack(side='left')

        ttk.Label(frm, text='Username').grid(row=4, column=0, sticky='w', pady=4)
        self.user_var = tk.StringVar()
        self.user_entry = ttk.Entry(frm, textvariable=self.user_var, width=30)
        self.user_entry.grid(row=4, column=1, columnspan=2, pady=4, sticky='we')
        ttk.Label(frm, text='Password').grid(row=5, column=0, sticky='w', pady=4)
        self.pw_var = tk.StringVar()
        self.pw_entry = ttk.Entry(frm, textvariable=self.pw_var, width=30, show='*')
        self.pw_entry.grid(row=5, column=1, columnspan=2, pady=4, sticky='we')

        self.hint_var = tk.StringVar()
        ttk.Label(frm, textvariable=self.hint_var,
                  foreground=theme.palette()['helper'], wraplength=320) \
            .grid(row=6, column=0, columnspan=3, sticky='w', pady=(2, 0))

        self.msg_var = tk.StringVar()
        ttk.Label(frm, textvariable=self.msg_var, foreground=theme.palette()['error'],
                  wraplength=320).grid(row=7, column=0, columnspan=3, sticky='w')

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=3, pady=(10, 0), sticky='e')
        self.go_btn = ttk.Button(btns, text='Sign in', command=self._attempt)
        self.go_btn.pack(side='left', padx=4)
        ttk.Button(btns, text='Cancel', command=self._cancel).pack(side='left')

        ttk.Label(frm, text='{} · {}'.format(branding.APP_NAME, branding.CREDIT),
                  foreground=theme.palette()['helper'], font=('TkDefaultFont', 8)) \
            .grid(row=9, column=0, columnspan=3, pady=(12, 0))

        self.win.bind('<Return>', lambda e: self._attempt())
        self.win.protocol('WM_DELETE_WINDOW', self._cancel)
        self._reload_companies(prefer=db.DB_PATH)
        self.user_entry.focus_set()
        root.wait_window(self.win)

    # -------------------------------------------------------------- companies
    def _reload_companies(self, prefer=None):
        entries = [e for e in company.list_entries() if e['exists']]
        if not entries and os.path.exists(db.DB_PATH):
            company.select_company(db.DB_PATH)
            entries = [e for e in company.list_entries() if e['exists']]
        self._paths = [e['path'] for e in entries]
        labels = [e['name'] for e in entries]
        self.company_combo['values'] = labels
        idx = 0
        if prefer:
            for i, p in enumerate(self._paths):
                if company._same(p, prefer):
                    idx = i
                    break
        elif entries:
            for i, e in enumerate(entries):
                if e['active']:
                    idx = i
                    break
        if labels:
            self.company_combo.current(idx)
        self._on_company()

    def _selected_path(self):
        try:
            i = self.company_combo.current()
        except tk.TclError:
            return None
        if i is None or i < 0 or i >= len(self._paths):
            return None
        return self._paths[i]

    def _on_company(self):
        path = self._selected_path()
        self.msg_var.set('')
        if not path:
            self.hint_var.set('Create or import a company to continue.')
            self._require_auth = True
            self.go_btn.configure(text='Sign in')
            return
        company.select_company(path)
        conn = self.db_getter()
        try:
            need = auth.security_enabled(conn) and auth.user_count(conn) > 0
            first = auth.user_count(conn) == 0
        finally:
            conn.close()
        self._require_auth = need
        if first:
            self.hint_var.set(
                'This company has no users yet — enter a username and password '
                'to create the first Admin, or leave blank and Continue if you '
                'want to stay open (Tools can turn security on later).')
            self.go_btn.configure(text='Continue')
            self._require_auth = False
            self._first_run = True
        elif need:
            self.hint_var.set('Sign in to open this company.')
            self.go_btn.configure(text='Sign in')
            self._first_run = False
        else:
            self.hint_var.set(
                'Security is off for this company — Continue opens it without a '
                'password.')
            self.go_btn.configure(text='Continue')
            self._first_run = False

    def _new_company(self):
        name = simpledialog.askstring(
            'New company', 'Name of the new company / firm:', parent=self.win)
        if not name or not name.strip():
            return
        ok, msg, path = company.create_company(name.strip(), make_active=True)
        if not ok:
            messagebox.showerror('Could not create', msg, parent=self.win)
            return
        self._reload_companies(prefer=path)

    def _import_company(self):
        src = filedialog.askopenfilename(
            parent=self.win,
            title='Import a company file',
            filetypes=[(branding.APP_NAME + ' data', '*.db'),
                       ('All files', '*.*')])
        if not src:
            return
        name = simpledialog.askstring(
            'Name', 'Name for this company:',
            initialvalue=os.path.splitext(os.path.basename(src))[0],
            parent=self.win)
        ok, msg, path = company.import_company(
            src, name=(name or '').strip() or None, make_active=True)
        if not ok:
            messagebox.showerror('Import failed', msg, parent=self.win)
            return
        self._reload_companies(prefer=path)

    # ----------------------------------------------------------------- submit
    def _attempt(self):
        path = self._selected_path()
        if not path:
            self.msg_var.set('Select or create a company first.')
            return
        company.select_company(path)
        username = self.user_var.get().strip()
        password = self.pw_var.get()
        conn = self.db_getter()
        try:
            n_users = auth.user_count(conn)
            secured = auth.security_enabled(conn) and n_users > 0
            if secured:
                ok, msg, user = auth.authenticate(conn, username, password)
                if not ok:
                    self.msg_var.set(msg)
                    self.pw_var.set('')
                    return
                session.login(user['username'], user['role'])
            elif n_users == 0 and username and password:
                # Optional: create first admin from the boot screen.
                ok, msg = auth.create_user(
                    conn, username, password, role='Admin', actor='boot-setup')
                if not ok:
                    self.msg_var.set(msg)
                    return
                # Turning security on is still opt-in via Tools; just land as Admin.
                session.login(username, 'Admin')
            else:
                # Open book with no session (security off) — full access defaults.
                session.logout()
        finally:
            conn.close()
        self.ok = True
        self.win.destroy()

    def _cancel(self):
        self.ok = False
        self.win.destroy()
