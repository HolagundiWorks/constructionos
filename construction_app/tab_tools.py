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

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground='#2e7d32',
                  wraplength=560, justify='left') \
            .pack(anchor='w', padx=12, pady=(4, 12))
        self.refresh()

    def refresh(self):
        self.path_var.set(db.DB_PATH)
        if os.path.exists(db.DB_PATH):
            kb = os.path.getsize(db.DB_PATH) / 1024.0
            self.size_var.set('Current size: {:.1f} KB'.format(kb))
        else:
            self.size_var.set('Data file not created yet.')

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
            filetypes=[('Contractor-OS backup', '*.db'), ('All files', '*.*')])
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
    return ToolsTab(parent, db_getter)
