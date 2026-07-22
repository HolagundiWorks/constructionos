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
import theme
import shutil
import sqlite3
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import assets
import db
import modules
import branding
import firm as firm_module
import company
import i18n
import numbering
import refdata
import sampledata
from ui_guard import can_write
from widgets import Switch, ScrollFrame


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

        # --- Web / LAN access (open in a browser, no client install) ---
        # Placed near the top so the LAN server is easy to find.
        self._web = None
        self._build_web_panel()

        # --- One-click backup to a remembered folder (e.g. a synced drive) ---
        # "Cloud backup" for an offline app: point this at the local folder of
        # Google Drive / OneDrive / Dropbox and the sync client does the rest.
        # No network code, no credentials, no pip dependency.
        sync = ttk.LabelFrame(self, text='Backup to a synced folder (cloud)')
        sync.pack(fill='x', padx=12, pady=(0, 6))
        ttk.Label(sync, text='Choose the local folder of your cloud drive '
                             '(Google Drive, OneDrive, Dropbox…). Backups '
                             'copied there are uploaded by that app.',
                  wraplength=560, justify='left').pack(anchor='w', padx=8, pady=(6, 2))
        row = ttk.Frame(sync); row.pack(fill='x', padx=8, pady=4)
        self.sync_folder_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.sync_folder_var, width=48).pack(side='left', padx=(0, 6))
        ttk.Button(row, text='Choose…', command=self.choose_sync_folder).pack(side='left', padx=2)
        ttk.Button(row, text='Backup Now', command=self.backup_to_sync).pack(side='left', padx=2)

        # --- Company files (multi-firm / multi-year) ---
        self._build_company_panel()

        # --- Firm details (letterhead + payment details on every document) ---
        firm_box = ttk.LabelFrame(
            self, text='Firm Details (letterhead on quotations, contracts, '
                       'invoices and reports)')
        firm_box.pack(fill='x', padx=12, pady=(6, 6))
        # Panel fields come from firm.FIELDS so the settings screen and the
        # letterhead reader can never list different things; works_gst_pct is
        # appended because it is a tax setting, not a letterhead detail.
        panel = list(firm_module.FIELDS) + [('works_gst_pct', 'Works GST %')]
        self.firm = {key: tk.StringVar() for key, _ in panel}
        for idx, (key, label) in enumerate(panel):
            cell = ttk.Frame(firm_box)
            cell.grid(row=idx // 2, column=idx % 2, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=16).pack(side='left')
            ttk.Entry(cell, textvariable=self.firm[key], width=30).pack(side='left')
        firm = firm_box
        ttk.Label(firm, text='Works GST % is the GST rate applied to RA / running '
                             'bills in the Output GST view (typical works contract '
                             'rate is 18%).', wraplength=540, foreground=theme.palette()['muted'],
                  justify='left').grid(row=2, column=0, columnspan=2, padx=6, sticky='w')
        ttk.Button(firm, text='Save Firm Details', command=self.save_firm) \
            .grid(row=3, column=0, padx=6, pady=6, sticky='w')
        logo_row = ttk.Frame(firm)
        logo_row.grid(row=3, column=1, padx=6, pady=6, sticky='w')
        ttk.Button(logo_row, text='Upload Firm Logo…',
                   command=self.upload_firm_logo).pack(side='left')
        ttk.Button(logo_row, text='Remove',
                   command=self.remove_firm_logo).pack(side='left', padx=(6, 0))
        self.logo_status = tk.StringVar()
        ttk.Label(firm, textvariable=self.logo_status, foreground=theme.palette()['muted'],
                  wraplength=540, justify='left') \
            .grid(row=4, column=0, columnspan=2, padx=6, pady=(0, 4), sticky='w')

        # --- Invoice number series ---
        series = ttk.LabelFrame(self, text='Invoice Number Series')
        series.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(series, text='Blank invoice numbers auto-fill from this series. '
                              'With FY reset on, numbering restarts each April, e.g. '
                              'INV/2026-27/001.', wraplength=540, foreground=theme.palette()['muted'],
                  justify='left').grid(row=0, column=0, columnspan=4, padx=6,
                                       pady=(6, 2), sticky='w')
        self.series = {'invoice_prefix': tk.StringVar(),
                       'invoice_width': tk.StringVar()}
        self.fy_reset_var = tk.IntVar(value=1)
        ttk.Label(series, text='Prefix', width=8).grid(row=1, column=0, padx=6, pady=4, sticky='w')
        ttk.Entry(series, textvariable=self.series['invoice_prefix'], width=12) \
            .grid(row=1, column=1, padx=(0, 10), pady=4, sticky='w')
        ttk.Label(series, text='Serial digits', width=12).grid(row=1, column=2, padx=6, pady=4, sticky='w')
        ttk.Entry(series, textvariable=self.series['invoice_width'], width=6) \
            .grid(row=1, column=3, padx=(0, 10), pady=4, sticky='w')
        ttk.Checkbutton(series, text='Reset each financial year',
                        variable=self.fy_reset_var).grid(row=2, column=0, columnspan=2,
                                                         padx=6, pady=2, sticky='w')
        ttk.Button(series, text='Save Series', command=self.save_series) \
            .grid(row=2, column=3, padx=6, pady=4, sticky='w')

        # The AI is a built-in, hardcoded model — turn it on/off from the
        # Assistant › AI Engine screen (its own rail row); nothing to configure
        # here.

        # --- Language ---
        lang = ttk.LabelFrame(self, text='Language / भाषा')
        lang.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(lang, text='Menu and tab names can be shown in Hindi or '
                            'Hinglish. Applies the next time you open the app.',
                  wraplength=540, foreground=theme.palette()['muted'], justify='left') \
            .pack(anchor='w', padx=8, pady=(6, 2))
        self.lang_var = tk.StringVar()
        self._lang_names = {name: code for code, name in i18n.LANGUAGES}
        row = ttk.Frame(lang); row.pack(fill='x', padx=8, pady=4)
        ttk.Combobox(row, textvariable=self.lang_var, width=16, state='readonly',
                     values=[name for _c, name in i18n.LANGUAGES]).pack(side='left')
        ttk.Button(row, text='Save Language', command=self.save_language) \
            .pack(side='left', padx=6)

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
                          row=row, column=0, sticky='nw', padx=(0, 10), pady=7)
            cell = ttk.Frame(grid); cell.grid(row=row, column=1, sticky='w')
            for col, label in enumerate(labels):
                var = tk.IntVar(value=1)
                self.module_vars[label] = var
                # a pill switch + label, on the fog ground the LabelFrame sits on
                item = ttk.Frame(cell); item.grid(
                    row=col // 3, column=col % 3, sticky='w', padx=(0, 18), pady=4)
                Switch(item, variable=var, surface='canvas').pack(side='left')
                ttk.Label(item, text=label).pack(side='left', padx=(7, 0))
        btns = ttk.Frame(mod); btns.pack(fill='x', padx=8, pady=4)
        ttk.Button(btns, text='Save Modules', command=self.save_modules).pack(side='left')
        ttk.Button(btns, text='Enable All',
                   command=lambda: self._set_all_modules(1)).pack(side='left', padx=6)

        # --- Reference library (CPWD items, material rates, consumption norms) ---
        ref = ttk.LabelFrame(
            self, text='Reference library (CPWD items, material rates, '
                       'consumption norms)')
        ref.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(ref, text='Load a starter library into THIS company file: '
                            'standard civil items (rate book), current material '
                            'rates, and the material split — how much cement, '
                            'sand, steel etc. each unit of concrete, masonry, '
                            'plastering and other civil work consumes. Rates are '
                            'indicative (mid-2026) — edit to your locality. '
                            'Nothing already present is changed.',
                  wraplength=560, justify='left').pack(anchor='w', padx=8,
                                                       pady=(6, 2))
        rbtn = ttk.Frame(ref); rbtn.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(rbtn, text='Load CPWD Reference Data',
                   command=self.load_reference_data).pack(side='left')

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground=theme.palette()['success'],
                  wraplength=560, justify='left') \
            .pack(anchor='w', padx=12, pady=(4, 2))
        ttk.Label(self, text='{} · {}'.format(branding.APP_NAME, branding.CREDIT),
                  foreground=theme.palette()['helper']).pack(anchor='w', padx=12, pady=(0, 12))
        self.refresh()

    def refresh(self):
        self.path_var.set(db.DB_PATH)
        self._refresh_logo_status()
        self.refresh_companies()
        if os.path.exists(db.DB_PATH):
            kb = os.path.getsize(db.DB_PATH) / 1024.0
            self.size_var.set('Current size: {:.1f} KB'.format(kb))
        else:
            self.size_var.set('Data file not created yet.')
        conn = self.db_getter()
        try:
            keys = list(self.firm) + ['backup_folder']
            saved = {r['key']: r['value'] for r in conn.execute(
                "SELECT key, value FROM app_settings WHERE key IN ({})".format(
                    ', '.join('?' * len(keys))), keys)}
        finally:
            conn.close()
        for key, var in self.firm.items():
            var.set(saved.get(key, '18' if key == 'works_gst_pct' else ''))
        self.sync_folder_var.set(saved.get('backup_folder', ''))
        conn = self.db_getter()
        try:
            sset = {r['key']: r['value'] for r in conn.execute(
                "SELECT key, value FROM app_settings WHERE key IN "
                "('invoice_prefix', 'invoice_width', 'invoice_fy_reset', 'language')")}
        finally:
            conn.close()
        self.series['invoice_prefix'].set(sset.get('invoice_prefix', 'INV'))
        self.series['invoice_width'].set(sset.get('invoice_width', '3'))
        self.fy_reset_var.set(0 if sset.get('invoice_fy_reset', '1') == '0' else 1)
        code = sset.get('language', 'en')
        names = {c: n for c, n in i18n.LANGUAGES}
        self.lang_var.set(names.get(code, 'English'))
        conn = self.db_getter()
        try:
            states = modules.enabled_map(conn)
        finally:
            conn.close()
        for label, var in self.module_vars.items():
            var.set(1 if states.get(label, True) else 0)

    def _set_all_modules(self, value):
        for var in self.module_vars.values():
            var.set(value)

    def save_modules(self):
        if not can_write():
            return
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
        if not can_write():
            return
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
        self.status_var.set('Firm details saved — they appear as the letterhead '
                            'on quotations, contracts, invoices and reports.')

    # ---------------------------------------------------------- firm logo
    def _refresh_logo_status(self):
        if assets.firm_logo_path():
            self.logo_status.set('Firm logo: set — shown on every printed '
                                 'document. Use Remove to go back to the default.')
        else:
            self.logo_status.set('Firm logo: not set — documents use the default '
                                 'logo. Upload a PNG, JPG or GIF.')

    def upload_firm_logo(self):
        if not can_write():
            return
        path = filedialog.askopenfilename(
            title='Choose your firm logo',
            filetypes=[('Image files', '*.png *.jpg *.jpeg *.gif'),
                       ('All files', '*.*')])
        if not path:
            return
        ok, msg = assets.set_firm_logo(path)
        if not ok:
            messagebox.showerror('Logo not saved', msg)
            return
        self._refresh_logo_status()
        self.status_var.set('Firm logo saved — it now appears as the letterhead '
                            'on printed documents.')

    def remove_firm_logo(self):
        if not can_write():
            return
        if not assets.firm_logo_path():
            return
        if not messagebox.askyesno(
                'Remove logo', 'Remove your firm logo? Printed documents will '
                'use the default logo.'):
            return
        assets.clear_firm_logo()
        self._refresh_logo_status()
        self.status_var.set('Firm logo removed.')

    def save_language(self):
        if not can_write():
            return
        code = self._lang_names.get(self.lang_var.get(), 'en')
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                ('language', code))
            conn.commit()
        finally:
            conn.close()
        self.status_var.set('Language saved — reopen the app to apply.')

    def save_series(self):
        if not can_write():
            return
        values = {
            'invoice_prefix': self.series['invoice_prefix'].get().strip() or 'INV',
            'invoice_width': self.series['invoice_width'].get().strip() or '3',
            'invoice_fy_reset': '1' if self.fy_reset_var.get() else '0',
        }
        conn = self.db_getter()
        try:
            for key, val in values.items():
                conn.execute(
                    'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                    (key, val))
            conn.commit()
        finally:
            conn.close()
        self.status_var.set('Invoice number series saved.')

    # ------------------------------------------------- company files (Phase 7)
    def _build_company_panel(self):
        """Multi-firm / multi-year: switch between company files, or start a
        new one carrying this year's masters forward."""
        box = ttk.LabelFrame(self, text='Company Files (separate firms / financial years)')
        box.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(box, text='Each firm — and each financial year, if you prefer '
                            'a clean start — is its own data file. Switching '
                            'reopens the app on that file; nothing is deleted.',
                  wraplength=560, justify='left').pack(anchor='w', padx=8, pady=(6, 2))

        self.company_tree = ttk.Treeview(
            box, columns=('name', 'path'), show='headings', height=4)
        self.company_tree.heading('name', text='Company / Year')
        self.company_tree.heading('path', text='File')
        self.company_tree.column('name', width=180, anchor='w')
        self.company_tree.column('path', width=360, anchor='w')
        self.company_tree.pack(fill='x', padx=8, pady=4)

        btns = ttk.Frame(box); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Switch To Selected', command=self.switch_company).pack(side='left', padx=(0, 4))
        ttk.Button(btns, text='New Firm…', command=self.new_firm).pack(side='left', padx=2)
        ttk.Button(btns, text='New Financial Year…', command=self.new_year).pack(side='left', padx=2)
        ttk.Button(btns, text='Add Existing…', command=self.add_existing_company).pack(side='left', padx=2)
        ttk.Button(btns, text='Remove From List', command=self.forget_company).pack(side='left', padx=2)
        ttk.Button(btns, text='Load Sample Data…',
                   command=self.load_sample_data).pack(side='left', padx=2)

    def refresh_companies(self):
        for item in self.company_tree.get_children():
            self.company_tree.delete(item)
        data = company.load()
        # Always show the file currently open, even before it is registered.
        if company.find(data, db.DB_PATH) is None:
            company.add(data, os.path.basename(db.DB_PATH), db.DB_PATH)
            company.set_active(data, db.DB_PATH)
            company.save(data)
        for f in data.get('files', []):
            active = company._same(f['path'], db.DB_PATH)
            name = ('● ' if active else '   ') + (f['name'] or '')
            missing = '' if os.path.exists(f['path']) else '   (file not found)'
            self.company_tree.insert('', 'end', values=(name, f['path'] + missing))

    def _selected_company_path(self):
        sel = self.company_tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a company file first.')
            return None
        raw = self.company_tree.item(sel[0], 'values')[1]
        return raw.replace('   (file not found)', '')

    def _switch_to(self, path, created=False):
        """Point the app at another company file and ask for a restart.

        Connections are short-lived, so the next operation opens the new file —
        but views already on screen still hold the old data, so a restart is
        the honest way to apply it (same as Restore).
        """
        data = company.load()
        company.set_active(data, path)
        company.save(data)
        db.DB_PATH = path
        self.refresh()
        self.status_var.set('Now using: {}'.format(path))
        messagebox.showinfo(
            'Company file created' if created else 'Switched',
            '{}\n\nPlease close and reopen the app so every screen loads this '
            'file.'.format(path))

    def switch_company(self):
        path = self._selected_company_path()
        if path is None:
            return
        if not os.path.exists(path):
            messagebox.showerror(
                'File not found',
                'That data file is missing:\n\n{}\n\nIt may be on a drive that '
                'is not connected. Use "Remove From List" if it is gone for '
                'good — the file itself is never deleted by this app.'.format(path))
            return
        if company._same(path, db.DB_PATH):
            messagebox.showinfo('Already open', 'That is the file you are using.')
            return
        self._switch_to(path)

    def _create_company(self, name, carry_from=None):
        """Create a new company file, optionally carrying masters forward."""
        folder = os.path.dirname(os.path.abspath(db.DB_PATH))
        path = company.suggest_path(folder, name)
        prev = db.DB_PATH
        try:
            db.DB_PATH = path
            db.init_db()
            if carry_from and os.path.exists(carry_from):
                src = sqlite3.connect(carry_from)
                src.row_factory = sqlite3.Row
                dst = db.get_conn()
                try:
                    copied = company.carry_forward(src, dst)
                finally:
                    src.close(); dst.close()
                total = sum(copied.values())
                self.status_var.set(
                    'Carried forward {} master records into {}.'.format(total, name))
        except Exception as exc:                      # noqa: BLE001 - user-facing
            db.DB_PATH = prev
            messagebox.showerror(
                'Could not create the file',
                'The new company file could not be created:\n\n{}'.format(exc))
            return None
        data = company.load()
        company.add(data, name, path, make_active=True)
        company.save(data)
        return path

    def new_firm(self):
        name = simpledialog.askstring(
            'New firm', 'Name of the new firm:', parent=self)
        if not name or not name.strip():
            return
        path = self._create_company(name.strip())
        if path:
            self.refresh_companies()
            self._switch_to(path, created=True)

    def new_year(self):
        """Start a fresh file for the next financial year, carrying masters."""
        current = ''
        conn = self.db_getter()
        try:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
            current = (row['value'] if row else '') or 'Company'
        finally:
            conn.close()
        try:
            fy = numbering.financial_year(date.today().isoformat())
        except Exception:                              # noqa: BLE001
            fy = ''
        suggested = '{} {}'.format(current, company.next_year_label(fy) or fy).strip()
        name = simpledialog.askstring(
            'New financial year',
            'Name for the new year\'s file:\n\n(Masters — sites, clients, '
            'vendors, materials, labour, chart of accounts, rate book and firm '
            'settings — are copied. Bills, payments and the ledger start '
            'empty.)',
            initialvalue=suggested, parent=self)
        if not name or not name.strip():
            return
        path = self._create_company(name.strip(), carry_from=db.DB_PATH)
        if path:
            self.refresh_companies()
            self._switch_to(path, created=True)

    def add_existing_company(self):
        path = filedialog.askopenfilename(
            title='Choose an existing company file',
            filetypes=[('Construction OS data', '*.db'), ('All files', '*.*')])
        if not path:
            return
        name = simpledialog.askstring(
            'Name', 'Name for this company file:',
            initialvalue=os.path.splitext(os.path.basename(path))[0], parent=self)
        data = company.load()
        company.add(data, (name or '').strip() or os.path.basename(path), path)
        company.save(data)
        self.refresh_companies()
        self.status_var.set('Added {} to the list.'.format(path))

    def load_reference_data(self):
        """Add the CPWD reference library (materials, consumption norms, rate
        book, worked analyses) to the CURRENT company file. Idempotent — the
        seeder skips anything already present, so it is safe to run again."""
        if not can_write():
            return
        if not messagebox.askyesno(
                'Load reference data',
                'Add a starter reference library to THIS company file:\n\n'
                '•  standard civil items (Rate Book)\n'
                '•  current material rates (Materials)\n'
                '•  consumption norms — the material split for concrete, '
                'masonry, plastering and other civil work\n'
                '•  a few worked rate analyses\n\n'
                'Rates are indicative (mid-2026) — edit them to your area. '
                'Anything already present is left unchanged. Continue?'):
            return
        conn = self.db_getter()
        try:
            n = refdata.load(conn)
        except Exception as exc:                          # noqa: BLE001
            messagebox.showerror(
                'Could not load reference data',
                'The reference library could not be loaded:\n\n{}'.format(exc))
            return
        finally:
            conn.close()
        self.status_var.set(
            'Reference library: +{} materials, +{} norms, +{} rate-book items, '
            '+{} analyses.'.format(n['materials'], n['norms'], n['rate_book'],
                                   n['analyses']))
        total = sum(n.values())
        if total:
            messagebox.showinfo(
                'Reference data loaded',
                'Added {} materials, {} consumption norms, {} rate-book items '
                'and {} rate analyses.\n\nSee Masters › Materials and Rate Book, '
                'Operations › Consumption, and Billing › Rate Analysis.'.format(
                    n['materials'], n['norms'], n['rate_book'], n['analyses']))
        else:
            messagebox.showinfo(
                'Already loaded',
                'The reference library was already present — nothing to add.')

    def load_sample_data(self):
        """Create a separate 'Sample Data' company file, fill it with a
        realistic demo book, and switch to it. The user's own files are never
        touched — the sample lives in its own file they can remove or delete."""
        if not can_write():
            return
        if not messagebox.askyesno(
                'Load sample data',
                'This creates a separate "Sample Data" company file and fills it '
                'with a realistic demo project — aged bills, retention, an '
                'over-invoiced PO, overdue filings and more — so you can see '
                'every screen working.\n\nYour own data files are not touched. '
                'Continue?'):
            return
        path = self._create_company('Sample Data')
        if not path:
            return
        # _create_company has already pointed db.DB_PATH at the new empty file.
        conn = db.get_conn()
        try:
            seeded = sampledata.seed(conn)
        except Exception as exc:                          # noqa: BLE001
            conn.close()
            messagebox.showerror(
                'Could not load sample data',
                'The sample book could not be filled:\n\n{}'.format(exc))
            return
        finally:
            try:
                conn.close()
            except Exception:                             # noqa: BLE001
                pass
        self.refresh_companies()
        if seeded:
            self._switch_to(path, created=True)
        else:
            messagebox.showinfo(
                'Nothing to do',
                'That file already had data, so it was left as it is.')

    def forget_company(self):
        path = self._selected_company_path()
        if path is None:
            return
        if company._same(path, db.DB_PATH):
            messagebox.showinfo(
                'In use', 'You cannot remove the file you are working in. '
                'Switch to another one first.')
            return
        if not messagebox.askyesno(
                'Remove from list',
                'Remove this file from the list?\n\n{}\n\nThe file itself is '
                'NOT deleted — it stays on disk and can be added back with '
                '"Add Existing".'.format(path)):
            return
        data = company.load()
        company.remove(data, path)
        company.save(data)
        self.refresh_companies()

    # -------------------------------------------------- synced-folder backup
    def choose_sync_folder(self):
        if not can_write():
            return
        folder = filedialog.askdirectory(
            title='Choose your cloud drive folder (Google Drive, OneDrive…)')
        if not folder:
            return
        self.sync_folder_var.set(folder)
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                ('backup_folder', folder))
            conn.commit()
        finally:
            conn.close()
        self.status_var.set('Backup folder saved: {}'.format(folder))

    def backup_to_sync(self):
        folder = self.sync_folder_var.get().strip()
        if not folder:
            messagebox.showinfo('No folder', 'Choose your cloud drive folder first.')
            return
        if not os.path.isdir(folder):
            messagebox.showerror(
                'Folder not found',
                'That folder does not exist:\n\n{}\n\nIf your cloud drive is '
                'not signed in, its folder may be missing.'.format(folder))
            return
        if not os.path.exists(db.DB_PATH):
            messagebox.showinfo('Nothing to back up', 'The data file does not exist yet.')
            return
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base = os.path.splitext(os.path.basename(db.DB_PATH))[0]
        dest = os.path.join(folder, '{}_backup_{}.db'.format(base, stamp))
        try:
            shutil.copy2(db.DB_PATH, dest)
        except OSError as exc:
            messagebox.showerror('Backup failed', str(exc))
            return
        self.status_var.set('Backed up to {}'.format(dest))
        messagebox.showinfo(
            'Backup complete',
            'Saved to your synced folder:\n\n{}\n\nYour cloud app will upload '
            'it shortly.'.format(dest))

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


    # ---------------------------------------------------------- Web / LAN
    def _build_web_panel(self):
        web = ttk.LabelFrame(
            self, text='Web / LAN access (open in a browser, no install)')
        web.pack(fill='x', padx=12, pady=(6, 6))
        ttk.Label(
            web, text='Run a local web server so anyone on your office network '
                      'can open Construction OS in a browser at '
                      'http://<this-PC>:<port> — no app to install. Login is '
                      'required (the first visit creates the admin). It serves '
                      'THIS company file. Keep it on a trusted LAN: the login '
                      'travels unencrypted over plain HTTP.',
            wraplength=560, justify='left').pack(anchor='w', padx=8, pady=(6, 2))
        row = ttk.Frame(web); row.pack(fill='x', padx=8, pady=4)
        ttk.Label(row, text='Port').pack(side='left')
        self.web_port_var = tk.StringVar(value='8080')
        ttk.Entry(row, textvariable=self.web_port_var, width=8).pack(
            side='left', padx=(4, 10))
        self.web_start_btn = ttk.Button(row, text='Start server',
                                        command=self.start_web)
        self.web_start_btn.pack(side='left', padx=2)
        self.web_stop_btn = ttk.Button(row, text='Stop', command=self.stop_web,
                                       state='disabled')
        self.web_stop_btn.pack(side='left', padx=2)
        self.web_status_var = tk.StringVar(value='Stopped.')
        ttk.Label(web, textvariable=self.web_status_var, foreground=theme.palette()['success']) \
            .pack(anchor='w', padx=8, pady=(2, 0))
        self.web_urls_var = tk.StringVar()
        ttk.Label(web, textvariable=self.web_urls_var, wraplength=560,
                  justify='left', foreground=theme.palette()['muted']).pack(
            anchor='w', padx=8, pady=(0, 8))

    def start_web(self):
        if self._web is not None and self._web.running:
            return
        try:
            port = int((self.web_port_var.get() or '8080').strip())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror('Web server', 'Port must be 1–65535.')
            return
        import webserver
        import netinfo
        self._web = webserver.WebServer(host='0.0.0.0', port=port)
        try:
            self._web.start()
        except OSError as exc:
            self._web = None
            messagebox.showerror(
                'Web server',
                'Could not start on port {}: {}\n\nThe port may be in use — '
                'try another (e.g. 8090).'.format(port, exc))
            return
        self.web_status_var.set('● Running on port {}'.format(self._web.port))
        self.web_urls_var.set(
            'Open on other devices on this network:\n  '
            + '\n  '.join(netinfo.urls(self._web.port)))
        self.web_start_btn.state(['disabled'])
        self.web_stop_btn.state(['!disabled'])

    def stop_web(self):
        if self._web is not None:
            self._web.stop()
            self._web = None
        self.web_status_var.set('Stopped.')
        self.web_urls_var.set('')
        self.web_start_btn.state(['!disabled'])
        self.web_stop_btn.state(['disabled'])


def build_tools_tab(parent, db_getter):
    """Tools as an inner notebook: data/settings, security, and the audit log.

    Backup & Settings has many stacked panels (including Web / LAN access), so
    it lives inside a ScrollFrame — otherwise the lower panels fall below the
    window with no way to reach them."""
    from tab_security import SecurityTab, AuditTab
    nb = ttk.Notebook(parent)
    scroll = ScrollFrame(nb)
    ToolsTab(scroll.body, db_getter).pack(fill='x', anchor='n')
    nb.add(scroll, text='Backup & Settings')
    nb.add(SecurityTab(nb, db_getter), text='Users & Security')
    nb.add(AuditTab(nb, db_getter), text='Audit Log')
    return nb
