"""Users & Security and Audit Log tabs (under Tools).

Security is opt-in: with it off, the app opens straight in (single-user) and
this panel lets anyone bootstrap the first users; once login is enabled, user
management is Admin-only. Enabling login requires at least one active Admin so
nobody can lock themselves out.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import auth
import session


class SecurityTab(ttk.Frame):
    COLUMNS = ('username', 'role', 'active', 'locked', 'created')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Users & Security',
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=10, pady=(10, 4))

        enable_row = ttk.Frame(self); enable_row.pack(fill='x', padx=10, pady=4)
        self.enable_var = tk.IntVar(value=0)
        ttk.Checkbutton(enable_row, text='Require sign-in (enable login & user accounts)',
                        variable=self.enable_var, command=self._toggle_security).pack(side='left')
        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground='#555',
                  wraplength=620, justify='left').pack(anchor='w', padx=10)

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings', height=7)
        heads = {'username': 'Username', 'role': 'Role', 'active': 'Active',
                 'locked': 'Locked', 'created': 'Created'}
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=140 if col in ('username', 'created') else 90, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=4)

        add = ttk.LabelFrame(self, text='Add user'); add.pack(fill='x', padx=10, pady=4)
        self.u_var = tk.StringVar(); self.p_var = tk.StringVar()
        self.r_var = tk.StringVar(value='Operator')
        ttk.Label(add, text='Username').pack(side='left', padx=(6, 2))
        ttk.Entry(add, textvariable=self.u_var, width=16).pack(side='left', padx=2)
        ttk.Label(add, text='Password').pack(side='left', padx=(6, 2))
        ttk.Entry(add, textvariable=self.p_var, width=16, show='*').pack(side='left', padx=2)
        ttk.Label(add, text='Role').pack(side='left', padx=(6, 2))
        ttk.Combobox(add, textvariable=self.r_var, width=10, state='readonly',
                     values=list(session.ROLES)).pack(side='left', padx=2)
        ttk.Button(add, text='Add', command=self.add_user).pack(side='left', padx=6)

        act = ttk.Frame(self); act.pack(fill='x', padx=10, pady=(0, 8))
        ttk.Button(act, text='Reset Password', command=self.reset_password).pack(side='left', padx=3)
        ttk.Button(act, text='Set Role', command=self.set_role).pack(side='left', padx=3)
        ttk.Button(act, text='Activate/Deactivate', command=self.toggle_active).pack(side='left', padx=3)
        ttk.Button(act, text='Unlock', command=self.unlock).pack(side='left', padx=3)
        ttk.Button(act, text='Refresh', command=self.refresh).pack(side='left', padx=3)

        self.refresh()

    # -------------------------------------------------------------- helpers
    def _actor(self):
        return session.username() or 'setup'

    def _management_allowed(self):
        """Anyone may manage while security is off (bootstrap); once on, Admin only."""
        conn = self.db_getter()
        try:
            secured = auth.security_enabled(conn)
        finally:
            conn.close()
        return (not secured) or session.is_admin()

    def _guard(self):
        if not self._management_allowed():
            messagebox.showerror('Admin only',
                                 'Only an Admin can manage users once login is enabled.')
            return False
        return True

    def _selected(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0], 'values')[0] if sel else None

    # ---------------------------------------------------------------- data
    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            secured = auth.security_enabled(conn)
            self.enable_var.set(1 if secured else 0)
            for u in auth.list_users(conn):
                self.tree.insert('', 'end', values=(
                    u['username'], u['role'], 'Yes' if u['is_active'] else 'No',
                    'Yes' if u['locked'] else 'No', u['created_at'] or ''))
            n = auth.user_count(conn)
        finally:
            conn.close()
        who = ' Signed in as {} ({}).'.format(session.username(), session.role()) \
            if session.is_authenticated() else ''
        self.status_var.set(
            ('Login is ON — sign-in required at startup.' if secured else
             'Login is OFF — the app opens without a password.') +
            ' {} user(s).'.format(n) + who +
            ('' if self._management_allowed() else '  (Admin only — read-only here.)'))

    # --------------------------------------------------------------- actions
    def _toggle_security(self):
        # Reflect the desired state, but validate before persisting.
        want_on = bool(self.enable_var.get())
        conn = self.db_getter()
        try:
            if want_on and auth.admin_count(conn) == 0:
                messagebox.showerror(
                    'Add an Admin first',
                    'Create at least one Admin user before enabling login, '
                    'otherwise no one could manage the system.')
                self.enable_var.set(0)
                return
            if not want_on and auth.security_enabled(conn) and not session.is_admin() \
                    and session.is_authenticated():
                messagebox.showerror('Admin only', 'Only an Admin can disable login.')
                self.enable_var.set(1)
                return
            auth.set_security_enabled(conn, want_on, actor=self._actor())
        finally:
            conn.close()
        messagebox.showinfo(
            'Saved',
            'Login is now {}. It takes effect the next time you open the app.'.format(
                'required' if want_on else 'off'))
        self.refresh()

    def add_user(self):
        if not self._guard():
            return
        conn = self.db_getter()
        try:
            ok, msg = auth.create_user(conn, self.u_var.get(), self.p_var.get(),
                                       self.r_var.get(), actor=self._actor())
        finally:
            conn.close()
        (messagebox.showinfo if ok else messagebox.showerror)(
            'Add user' if ok else 'Could not add user', msg)
        if ok:
            self.u_var.set(''); self.p_var.set('')
            self.refresh()

    def reset_password(self):
        if not self._guard():
            return
        username = self._selected()
        if not username:
            messagebox.showinfo('No selection', 'Select a user.')
            return
        from tkinter import simpledialog
        newpw = simpledialog.askstring('Reset password',
                                       'New password for {}:'.format(username), show='*')
        if not newpw:
            return
        conn = self.db_getter()
        try:
            ok, msg = auth.change_password(conn, username, newpw, actor=self._actor())
        finally:
            conn.close()
        (messagebox.showinfo if ok else messagebox.showerror)('Reset password', msg)

    def set_role(self):
        if not self._guard():
            return
        username = self._selected()
        if not username:
            messagebox.showinfo('No selection', 'Select a user.')
            return
        role = self.r_var.get()
        conn = self.db_getter()
        try:
            ok, msg = auth.set_role(conn, username, role, actor=self._actor())
        finally:
            conn.close()
        (messagebox.showinfo if ok else messagebox.showerror)('Set role', msg)
        self.refresh()

    def toggle_active(self):
        if not self._guard():
            return
        username = self._selected()
        if not username:
            messagebox.showinfo('No selection', 'Select a user.')
            return
        conn = self.db_getter()
        try:
            u = auth.get_user(conn, username)
            ok, msg = auth.set_active(conn, username, not u['is_active'],
                                      actor=self._actor())
        finally:
            conn.close()
        (messagebox.showinfo if ok else messagebox.showerror)('Update', msg)
        self.refresh()

    def unlock(self):
        if not self._guard():
            return
        username = self._selected()
        if not username:
            messagebox.showinfo('No selection', 'Select a user.')
            return
        conn = self.db_getter()
        try:
            auth.unlock(conn, username, actor=self._actor())
        finally:
            conn.close()
        self.refresh()


class AuditTab(ttk.Frame):
    COLUMNS = ('ts', 'username', 'action', 'entity', 'entity_id', 'detail')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        top = ttk.Frame(self); top.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(top, text='Audit Log', font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right')

        heads = {'ts': 'Time', 'username': 'User', 'action': 'Action',
                 'entity': 'Entity', 'entity_id': 'Ref', 'detail': 'Detail'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=150 if col == 'ts' else 110, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            for r in auth.recent_audit(conn, 300):
                self.tree.insert('', 'end', values=(
                    r['ts'], r['username'], r['action'], r['entity'] or '',
                    r['entity_id'] or '', r['detail'] or ''))
        finally:
            conn.close()
