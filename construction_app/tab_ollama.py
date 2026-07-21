"""Ollama — the AI engine manager, folded into the main app.

What used to be a separate "Ollama Manager" program now lives here as a tab
beside the Assistant: check whether the local Ollama server is running and start
it; install Ollama through the system package manager; see the models on disk,
pull a new one from a short catalogue with live progress, delete one; and pick
which model the Assistant uses. One app, not two.

All the work — the HTTP API and the OS process control — is the same stdlib code
the standalone tool used (``ollama_api`` / ``ollama_service`` / ``ollama_catalog``),
so nothing new is downloaded and the app stays pure standard library. Network and
process calls run on worker threads and marshal back with ``after`` so the window
never freezes.
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

import assistant
import ollama_api as api
import ollama_service as service
import ollama_catalog as catalog
import theme
from ui_guard import can_write


class OllamaManagerTab(ttk.Frame):
    COLUMNS = ('name', 'parameters', 'size', 'modified')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._cancel = False
        self._pulling = False
        self._build_ui()
        self.refresh_status()
        self.refresh_models()

    # ---------------------------------------------------------------- config
    def _host(self):
        conn = self.db_getter()
        try:
            _model, host = assistant.get_config(conn)
        finally:
            conn.close()
        return host or 'http://localhost:11434'

    def _url(self):
        return api.base_url(self._host())

    def _active_model(self):
        conn = self.db_getter()
        try:
            return assistant.get_config(conn)[0]
        finally:
            conn.close()

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='AI engine (Ollama)',
                  font=('TkDefaultFont', 13, 'bold')) \
            .pack(anchor='w', padx=10, pady=(10, 2))

        # --- server status
        srv = ttk.LabelFrame(self, text='Local server')
        srv.pack(fill='x', padx=10, pady=6)
        self.status_var = tk.StringVar(value='Checking…')
        ttk.Label(srv, textvariable=self.status_var).pack(
            anchor='w', padx=8, pady=(6, 4))
        row = ttk.Frame(srv); row.pack(fill='x', padx=8, pady=(0, 8))
        self.start_btn = ttk.Button(row, text='Start Ollama',
                                    command=self.start_server)
        self.start_btn.pack(side='left', padx=(0, 4))
        self.stop_btn = ttk.Button(row, text='Stop', command=self.stop_server)
        self.stop_btn.pack(side='left', padx=4)
        ttk.Button(row, text='Refresh', command=self.refresh_all).pack(
            side='left', padx=4)
        self.install_btn = ttk.Button(row, text='Install Ollama',
                                      command=self.install_ollama)
        self.install_btn.pack(side='left', padx=(12, 4))
        ttk.Button(row, text='Download page',
                   command=lambda: webbrowser.open(service.DOWNLOAD_PAGE)) \
            .pack(side='left', padx=4)

        # --- installed models
        inst = ttk.LabelFrame(self, text='Installed models')
        inst.pack(fill='both', expand=True, padx=10, pady=6)
        self.tree = ttk.Treeview(inst, columns=self.COLUMNS, show='headings',
                                 height=7)
        heads = {'name': 'Model', 'parameters': 'Params', 'size': 'Size',
                 'modified': 'Modified'}
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=90 if c != 'name' else 240, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=(6, 4))
        mrow = ttk.Frame(inst); mrow.pack(fill='x', padx=8, pady=(0, 6))
        ttk.Button(mrow, text='Use for Assistant', style='Accent.TButton',
                   command=self.use_for_assistant).pack(side='left')
        ttk.Button(mrow, text='Delete', command=self.delete_selected).pack(
            side='left', padx=6)
        self.disk_var = tk.StringVar()
        ttk.Label(mrow, textvariable=self.disk_var,
                  foreground=pal['muted']).pack(side='right')

        # --- pull a model
        pull = ttk.LabelFrame(self, text='Get a model')
        pull.pack(fill='x', padx=10, pady=6)
        ttk.Label(pull, text='Pick a model (or type any Ollama tag), then '
                             'Download. Models are gigabytes — it runs in the '
                             'background.', wraplength=620, justify='left',
                  foreground=pal['muted']).pack(anchor='w', padx=8, pady=(6, 2))
        prow = ttk.Frame(pull); prow.pack(fill='x', padx=8, pady=2)
        self.model_var = tk.StringVar(value=catalog.SUGGESTED)
        self.model_combo = ttk.Combobox(prow, textvariable=self.model_var,
                                        width=52, values=catalog.choices())
        self.model_combo.pack(side='left', padx=(0, 6))
        self.pull_btn = ttk.Button(prow, text='Download',
                                   command=self.start_pull)
        self.pull_btn.pack(side='left')
        self.cancel_btn = ttk.Button(prow, text='Cancel', state='disabled',
                                     command=self.cancel_pull)
        self.cancel_btn.pack(side='left', padx=4)
        self.progress = ttk.Progressbar(pull, mode='determinate', maximum=100)
        self.progress.pack(fill='x', padx=8, pady=(6, 2))
        self.pull_status = tk.StringVar()
        ttk.Label(pull, textvariable=self.pull_status,
                  foreground=pal['muted']).pack(anchor='w', padx=8, pady=(0, 6))

    def _post(self, fn):
        """Marshal a worker-thread callback onto the UI thread, dropping it if
        the tab has since been destroyed (a build/test may tear down first)."""
        def safe():
            try:
                if self.winfo_exists():
                    fn()
            except tk.TclError:
                pass
        try:
            self.after(0, safe)
        except (tk.TclError, RuntimeError):
            pass

    # ----------------------------------------------------------- status/list
    def refresh_all(self):
        self.refresh_status()
        self.refresh_models()

    def refresh_status(self):
        self.status_var.set('Checking…')

        def work():
            url = self._url()
            running = api.is_running(url)
            ver = api.version(url) if running else ''
            inst = service.installed()
            self._post(lambda: self._set_status(running, ver, inst))
        threading.Thread(target=work, daemon=True).start()

    def _set_status(self, running, ver, inst):
        if running:
            self.status_var.set('● Running{}   ·   {}'.format(
                ' (v{})'.format(ver) if ver else '', self._url()))
        elif inst:
            self.status_var.set('○ Installed but not running — press Start.')
        else:
            self.status_var.set('○ Ollama not found. Install it, or open the '
                                'download page.')
        self.start_btn.state(['!disabled'] if inst and not running
                             else ['disabled'])
        self.stop_btn.state(['!disabled'] if running else ['disabled'])
        self.install_btn.state(['!disabled'] if not inst else ['disabled'])

    def refresh_models(self):
        def work():
            try:
                models = api.list_models(self._url())
            except api.OllamaError:
                models = []
            size = service.models_dir_size()
            self._post(lambda: self._fill_models(models, size))
        threading.Thread(target=work, daemon=True).start()

    def _fill_models(self, models, size):
        self.tree.delete(*self.tree.get_children())
        active = (self._active_model() or '').strip()
        for m in models:
            name = m['name']
            mark = '● ' if name == active or name.split(':')[0] == active else ''
            self.tree.insert('', 'end', iid=name, values=(
                mark + name, m['parameters'], api.human_size(m['size']),
                m['modified']))
        self.disk_var.set('Models on disk: {}'.format(
            api.human_size(size)) if size else '')

    # --------------------------------------------------------------- actions
    def start_server(self):
        host = self._host()
        # host may be a full url; service wants host/port split — let it default.
        ok, msg = service.start_server()
        self.status_var.set(msg)
        self.after(1500, self.refresh_all)

    def stop_server(self):
        ok, msg = service.stop_server()
        self.status_var.set(msg)
        self.after(800, self.refresh_all)

    def install_ollama(self):
        cmd = service.install_command()
        if not cmd:
            if messagebox.askyesno(
                    'Install Ollama',
                    'No supported package manager was found. Open the official '
                    'download page to install Ollama?'):
                webbrowser.open(service.DOWNLOAD_PAGE)
            return
        if not messagebox.askyesno(
                'Install Ollama',
                'Run this to install Ollama?\n\n  {}\n\nIt may take a few '
                'minutes.'.format(' '.join(cmd))):
            return
        self.install_btn.state(['disabled'])
        self.status_var.set('Installing Ollama…')

        def work():
            ok, msg = service.install()
            self._post(lambda: (self.status_var.set(msg),
                                   self.refresh_all()))
        threading.Thread(target=work, daemon=True).start()

    def _selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def use_for_assistant(self):
        if not can_write():
            return
        name = self._selected()
        if not name:
            messagebox.showinfo('Pick a model', 'Select a model first.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES "
                "('assistant_model', ?) ON CONFLICT(key) DO UPDATE SET "
                "value = excluded.value", (name,))
            conn.commit()
        finally:
            conn.close()
        self.refresh_models()
        messagebox.showinfo('Assistant model set',
                            'The Assistant will now use "{}".'.format(name))

    def delete_selected(self):
        name = self._selected()
        if not name:
            return
        if not messagebox.askyesno(
                'Delete model',
                'Delete "{}" and free its disk space? This cannot be '
                'undone.'.format(name)):
            return

        def work():
            try:
                api.delete_model(self._url(), name)
                err = None
            except api.OllamaError as exc:
                err = str(exc)
            self._post(lambda: self._after_delete(err))
        threading.Thread(target=work, daemon=True).start()

    def _after_delete(self, err):
        if err:
            messagebox.showerror('Could not delete', err)
        self.refresh_models()

    # ------------------------------------------------------------------ pull
    def start_pull(self):
        if self._pulling:
            return
        tag = catalog.tag_from_choice(self.model_var.get())
        if not tag:
            return
        if not api.is_running(self._url()):
            messagebox.showinfo(
                'Server not running',
                'Start the Ollama server first (Start Ollama above).')
            return
        self._pulling = True
        self._cancel = False
        self.pull_btn.state(['disabled'])
        self.cancel_btn.state(['!disabled'])
        self.progress.configure(value=0)
        self.pull_status.set('Starting download of {}…'.format(tag))

        def work():
            try:
                api.pull_model(self._url(), tag, on_progress=self._progress,
                               should_stop=lambda: self._cancel)
                err = None
            except api.OllamaError as exc:
                err = str(exc)
            self._post(lambda: self._after_pull(tag, err))
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, status, completed, total):
        def update():
            if total:
                self.progress.configure(value=completed / total * 100.0)
                self.pull_status.set('{} — {} / {}'.format(
                    status, api.human_size(completed), api.human_size(total)))
            else:
                self.pull_status.set(status)
        self._post(update)

    def cancel_pull(self):
        self._cancel = True
        self.pull_status.set('Cancelling…')

    def _after_pull(self, tag, err):
        self._pulling = False
        self.pull_btn.state(['!disabled'])
        self.cancel_btn.state(['disabled'])
        if err:
            self.pull_status.set('')
            if 'cancel' not in err.lower():
                messagebox.showerror('Download failed', err)
        else:
            self.progress.configure(value=100)
            self.pull_status.set('Downloaded {}.'.format(tag))
            self.refresh_models()


def build_ollama_tab(parent, db_getter):
    return OllamaManagerTab(parent, db_getter)
