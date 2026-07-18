"""Startup login dialog (shown only when security is enabled).

A modal window over the (hidden) main window. On a correct login it records the
session via ``session.login`` and sets ``self.ok = True``; closing or cancelling
leaves ``ok`` False so the caller can exit.
"""

import tkinter as tk
from tkinter import ttk

import auth
import session


class LoginDialog:
    def __init__(self, root, db_getter):
        self.db_getter = db_getter
        self.ok = False

        self.win = tk.Toplevel(root)
        self.win.title('Contractor-OS — Sign in')
        self.win.resizable(False, False)
        self.win.transient(root)
        self.win.grab_set()

        frm = ttk.Frame(self.win, padding=20)
        frm.pack(fill='both', expand=True)
        ttk.Label(frm, text='Sign in', font=('TkDefaultFont', 14, 'bold')) \
            .grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky='w')

        ttk.Label(frm, text='Username').grid(row=1, column=0, sticky='w', pady=4)
        self.user_var = tk.StringVar()
        user_entry = ttk.Entry(frm, textvariable=self.user_var, width=24)
        user_entry.grid(row=1, column=1, pady=4)
        ttk.Label(frm, text='Password').grid(row=2, column=0, sticky='w', pady=4)
        self.pw_var = tk.StringVar()
        pw_entry = ttk.Entry(frm, textvariable=self.pw_var, width=24, show='*')
        pw_entry.grid(row=2, column=1, pady=4)

        self.msg_var = tk.StringVar()
        ttk.Label(frm, textvariable=self.msg_var, foreground='#c62828',
                  wraplength=240).grid(row=3, column=0, columnspan=2, sticky='w')

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(btns, text='Sign in', command=self._attempt).pack(side='left', padx=4)
        ttk.Button(btns, text='Cancel', command=self._cancel).pack(side='left')

        self.win.bind('<Return>', lambda e: self._attempt())
        self.win.protocol('WM_DELETE_WINDOW', self._cancel)
        user_entry.focus_set()
        root.wait_window(self.win)

    def _attempt(self):
        conn = self.db_getter()
        try:
            ok, msg, user = auth.authenticate(
                conn, self.user_var.get().strip(), self.pw_var.get())
        finally:
            conn.close()
        if ok:
            session.login(user['username'], user['role'])
            self.ok = True
            self.win.destroy()
        else:
            self.msg_var.set(msg)
            self.pw_var.set('')

    def _cancel(self):
        self.ok = False
        self.win.destroy()
