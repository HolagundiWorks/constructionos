"""Tools — data safety for a single-PC contractor (Phase 4 start).

The whole business is one SQLite file. For a T2/T3 contractor with no IT and no
cloud, losing that file is losing the business memory (PRODUCT.md principle
"Trust & data safety"). This tab makes **one-click backup** and a **guarded
restore** possible without touching the filesystem by hand.

Backups are plain file copies with a date-stamped name, so they open in any
SQLite tool and can be dropped onto a USB stick or synced folder. Restore is
a copy-back after an explicit confirmation.

Connections in this app are short-lived (opened and closed per operation), so
replacing the file on disk is safe: the next operation simply opens the new
file. A restore still asks the user to restart the app so every open view
reloads from the restored data.
"""

import os
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import db
import modules
import assistant
import ollama_client
import branding


class ToolsTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Backup & Restore',
                  font=('TkDefaultFont', 14, 'bold')) \
            .pack(anchor='w', padx=12, pady=(12, 6))

        ttk.Label(self, text='Your entire business is stored in one file. Take a '
                             'backup often — to a USB drive or a synced folder.',
                  wraplength=560, justify='left') \
            .pack(anchor='w', padx=12, pady=(0, 10))

        info = ttk.LabelFrame(self, text='Data file'); info.pack(fill='x', padx=12, pady=6)
        self.path_var = tk.StringVar(value=db.DB_PATH)
        ttk.Label(info, textvariable=self.path_var, wraplength=560,
                  justify='left').pack(anchor='w', padx=10, pady=6)
        self.size_var = tk.StringVar()
        ttk.Label(info, textvariable=self.size_var).pack(anchor='w', padx=10, pady=(0, 6))

        actions = ttk.Frame(self); actions.pack(fill='x', padx=12, pady=10)
        ttk.Button(actions, text='Backup Now…', command=self.backup) \
            .pack(side='left', padx=(0, 6))
        ttk.Button(actions, text='Restore From Backup…', command=self.restore) \
            .pack(side='left', padx=6)
        ttk.Button(actions, text='Refresh', command=self.refresh) \
            .pack(side='left', padx=6)

        # --- Firm details (printed on tax invoices) ---
        firm = ttk.LabelFrame(self, text='Firm Details (shown on tax invoices)')
        firm.pack(fill='x', padx=12, pady=(6, 6))
        self.firm = {'company_name': tk.StringVar(), 'seller_gstin': tk.StringVar(),
                     'seller_address': tk.StringVar()}
        for idx, (key, label) in enumerate([
                ('company_name', 'Firm Name'), ('seller_gstin', 'GSTIN'),
                ('seller_address', 'Address')]):
            cell = ttk.Frame(firm); cell.grid(row=idx // 2, column=idx % 2, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=12).pack(side='left')
            ttk.Entry(cell, textvariable=self.firm[key], width=30).pack(side='left')
        ttk.Button(firm, text='Save Firm Details', command=self.save_firm) \
            .grid(row=2, column=0, padx=6, pady=6, sticky='w')

        # --- AI Assistant (local Ollama) ---
        ai = ttk.LabelFrame(self, text='AI Assistant (local Ollama)')
        ai.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(ai, text='Ask questions about your data in plain language. '
                          'Needs Ollama running locally (ollama.com) with a model '
                          'pulled, e.g.  ollama pull llama3.1', wraplength=560,
                  justify='left').pack(anchor='w', padx=8, pady=(6, 2))
        self.ai = {'assistant_model': tk.StringVar(), 'assistant_host': tk.StringVar()}
        row = ttk.Frame(ai); row.pack(fill='x', padx=8, pady=4)
        ttk.Label(row, text='Model', width=8).pack(side='left')
        ttk.Entry(row, textvariable=self.ai['assistant_model'], width=18).pack(side='left', padx=4)
        ttk.Label(row, text='Host', width=6).pack(side='left')
        ttk.Entry(row, textvariable=self.ai['assistant_host'], width=26).pack(side='left', padx=4)
        aibtns = ttk.Frame(ai); aibtns.pack(fill='x', padx=8, pady=4)
        ttk.Button(aibtns, text='Save', command=self.save_ai).pack(side='left')
        ttk.Button(aibtns, text='Test Connection', command=self.test_ai).pack(side='left', padx=6)
        ttk.Button(aibtns, text='Start Ollama', command=self.start_ollama).pack(side='left', padx=2)

        # --- Modules (switch tabs on/off) ---
        mod = ttk.LabelFrame(self, text='Modules (switch off what you don\'t use)')
        mod.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(mod, text='Unticked modules are hidden. Changes apply the next '
                            'time you open the app.', wraplength=560,
                  justify='left').pack(anchor='w', padx=8, pady=(6, 2))
        grid = ttk.Frame(mod); grid.pack(fill='x', padx=8, pady=4)
        self.module_vars = {}
        for row, (section, labels) in enumerate(modules.SECTIONS_CATALOG):
            ttk.Label(grid, text=section, width=12,
                      font=('TkDefaultFont', 9, 'bold')).grid(
                          row=row, column=0, sticky='nw', padx=(0, 6), pady=2)
            cell = ttk.Frame(grid); cell.grid(row=row, column=1, sticky='w')
            for col, label in enumerate(labels):
                var = tk.IntVar(value=1)
                self.module_vars[label] = var
                ttk.Checkbutton(cell, text=label, variable=var).grid(
                    row=col // 4, column=col % 4, sticky='w', padx=4, pady=1)
        btns = ttk.Frame(mod); btns.pack(fill='x', padx=8, pady=4)
        ttk.Button(btns, text='Save Modules', command=self.save_modules).pack(side='left')
        ttk.Button(btns, text='Enable All',
                   command=lambda: self._set_all_modules(1)).pack(side='left', padx=6)

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground='#2e7d32',
                  wraplength=560, justify='left') \
            .pack(anchor='w', padx=12, pady=(4, 2))
        ttk.Label(self, text='{} · {}'.format(branding.APP_NAME, branding.CREDIT),
                  foreground='#888').pack(anchor='w', padx=12, pady=(0, 12))
        self.refresh()

    def refresh(self):
        self.path_var.set(db.DB_PATH)
        if os.path.exists(db.DB_PATH):
            kb = os.path.getsize(db.DB_PATH) / 1024.0
            self.size_var.set('Current size: {:.1f} KB'.format(kb))
        else:
            self.size_var.set('Data file not created yet.')
        conn = self.db_getter()
        try:
            saved = {r['key']: r['value'] for r in conn.execute(
                "SELECT key, value FROM app_settings WHERE key IN "
                "('company_name', 'seller_gstin', 'seller_address')")}
        finally:
            conn.close()
        for key, var in self.firm.items():
            var.set(saved.get(key, ''))
        conn = self.db_getter()
        try:
            states = modules.enabled_map(conn)
        finally:
            conn.close()
        for label, var in self.module_vars.items():
            var.set(1 if states.get(label, True) else 0)
        conn = self.db_getter()
        try:
            model, host = assistant.get_config(conn)
        finally:
            conn.close()
        self.ai['assistant_model'].set(model)
        self.ai['assistant_host'].set(host)

    def save_ai(self):
        conn = self.db_getter()
        try:
            for key, var in self.ai.items():
                conn.execute(
                    'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                    (key, var.get().strip()))
            conn.commit()
        finally:
            conn.close()
        self.status_var.set('AI Assistant settings saved.')

    def start_ollama(self):
        host = self.ai['assistant_host'].get().strip() or ollama_client.DEFAULT_HOST
        if ollama_client.available(host):
            messagebox.showinfo('Already running', 'Ollama is already running.')
            return
        if not ollama_client.installed():
            messagebox.showwarning(
                'Ollama not installed',
                'Ollama was not found on this PC.\n\nInstall it from ollama.com, '
                'then use this button to start it. (Ollama is a separate free '
                'program — it cannot be bundled inside the app.)')
            return
        ollama_client.start_server()
        self.status_var.set('Starting Ollama… give it a few seconds, then '
                            'Test Connection.')

    def test_ai(self):
        host = self.ai['assistant_host'].get().strip() or ollama_client.DEFAULT_HOST
        if not ollama_client.available(host):
            messagebox.showwarning(
                'Not connected',
                'No Ollama server at {}.\n\nInstall from ollama.com, run '
                '"ollama serve", and pull a model, e.g. "ollama pull '
                'llama3.1".'.format(host))
            return
        models = ollama_client.list_models(host)
        messagebox.showinfo(
            'Connected',
            'Ollama is running at {}.\nInstalled models: {}'.format(
                host, ', '.join(models) or '(none — pull one first)'))

    def _set_all_modules(self, value):
        for var in self.module_vars.values():
            var.set(value)

    def save_modules(self):
        states = {label: bool(var.get()) for label, var in self.module_vars.items()}
        conn = self.db_getter()
        try:
            modules.set_states(conn, states)
        finally:
            conn.close()
        off = [l for l, on in states.items() if not on]
        self.status_var.set(
            'Modules saved. {} hidden. Restart the app to apply.'.format(
                len(off)) if off else 'Modules saved — all enabled.')
        messagebox.showinfo('Modules saved',
                            'Changes apply the next time you open the app.')

    def save_firm(self):
        conn = self.db_getter()
        try:
            for key, var in self.firm.items():
                conn.execute(
                    'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                    (key, var.get().strip()))
            conn.commit()
        finally:
            conn.close()
        self.status_var.set('Firm details saved — they will appear on tax invoices.')

    def backup(self):
        if not os.path.exists(db.DB_PATH):
            messagebox.showinfo('Nothing to back up',
                                'The data file does not exist yet.')
            return
        folder = filedialog.askdirectory(title='Choose a folder for the backup')
        if not folder:
            return
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(folder, 'contractor_os_backup_{}.db'.format(stamp))
        try:
            shutil.copy2(db.DB_PATH, dest)
        except OSError as exc:
            messagebox.showerror('Backup failed', str(exc))
            return
        self.status_var.set('Backup saved: {}'.format(dest))
        messagebox.showinfo('Backup complete', 'Saved backup to:\n{}'.format(dest))

    def restore(self):
        src = filedialog.askopenfilename(
            title='Choose a backup file to restore',
            filetypes=[('Construction OS backup', '*.db'), ('All files', '*.*')])
        if not src:
            return
        if os.path.abspath(src) == os.path.abspath(db.DB_PATH):
            messagebox.showinfo('Same file',
                                'That is already the current data file.')
            return
        if not messagebox.askyesno(
                'Confirm restore',
                'Restoring will REPLACE all current data with the backup:\n\n'
                '{}\n\nThis cannot be undone. A safety copy of the current data '
                'will be made first. Continue?'.format(src)):
            return
        # Safety copy of the current file before overwriting.
        try:
            if os.path.exists(db.DB_PATH):
                stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safety = '{}.before_restore_{}.db'.format(db.DB_PATH, stamp)
                shutil.copy2(db.DB_PATH, safety)
            shutil.copy2(src, db.DB_PATH)
        except OSError as exc:
            messagebox.showerror('Restore failed', str(exc))
            return
        self.refresh()
        self.status_var.set('Restored from: {}'.format(src))
        messagebox.showinfo(
            'Restore complete',
            'Data restored. Please close and reopen the app so every screen '
            'reloads from the restored data.')


def build_tools_tab(parent, db_getter):
    """Tools as an inner notebook: data/settings, security, and the audit log."""
    from tab_security import SecurityTab, AuditTab
    nb = ttk.Notebook(parent)
    nb.add(ToolsTab(nb, db_getter), text='Backup & Settings')
    nb.add(SecurityTab(nb, db_getter), text='Users & Security')
    nb.add(AuditTab(nb, db_getter), text='Audit Log')
    return nb
