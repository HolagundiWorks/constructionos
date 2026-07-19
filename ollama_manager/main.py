"""Ollama Manager — a small desktop app to run Ollama and its models.

A separate program from Construction OS, sharing its constraints: Python
standard library only, tkinter, no pip, works offline apart from the model
downloads themselves.

    python ollama_manager/main.py

Three tabs:

* **Server** — whether Ollama is installed and running, its version, the
  address it is bound to, and Start / Stop / Install.
* **Models** — what is installed, how much disk it uses, install a new model
  with live progress, delete one, and choose which model is *current*.
* **Settings** — host, port, and pushing the chosen model into Construction OS.

Anything slow (pulling a model, installing Ollama, polling the server) runs on
a worker thread and reports back through a queue drained by the Tk main loop,
so the window never freezes and no Tk call is ever made off the main thread.
"""

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import api
import catalog
import config
import service

POLL_MS = 4000          # how often the status line refreshes itself


class ManagerApp(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.pack(fill='both', expand=True)

        self.cfg = config.load()
        self.events = queue.Queue()
        self._busy = False
        self._cancel_pull = False
        self._models = []

        self.host_var = tk.StringVar(value=self.cfg['host'])
        self.port_var = tk.StringVar(value=str(self.cfg['port']))
        self.model_var = tk.StringVar(value=self.cfg['model'])
        self.status_var = tk.StringVar(value='Checking…')
        self.detail_var = tk.StringVar(value='')
        self.progress_var = tk.StringVar(value='')
        self.disk_var = tk.StringVar(value='')

        self._build_ui()
        self.refresh_status()
        self.root.after(200, self._drain)
        self.root.after(POLL_MS, self._tick)

    # ------------------------------------------------------------------ url
    def url(self):
        return api.base_url(self.host_var.get(), self._port())

    def _port(self):
        try:
            return int(str(self.port_var.get()).strip() or api.DEFAULT_PORT)
        except ValueError:
            return api.DEFAULT_PORT

    # ------------------------------------------------------------------- UI
    def _build_ui(self):
        head = ttk.Frame(self); head.pack(fill='x', padx=12, pady=(12, 6))
        ttk.Label(head, text='Ollama Manager',
                  font=('TkDefaultFont', 15, 'bold')).pack(anchor='w')
        ttk.Label(head, text='Install and run local AI models on this PC. '
                             'Nothing leaves your machine except the model '
                             'downloads themselves.',
                  wraplength=640, justify='left',
                  foreground='#555').pack(anchor='w', pady=(2, 0))

        status = ttk.Frame(self); status.pack(fill='x', padx=12, pady=(4, 8))
        self.status_dot = tk.Canvas(status, width=14, height=14,
                                    highlightthickness=0)
        self.status_dot.pack(side='left', padx=(0, 8))
        self._dot('#999')
        ttk.Label(status, textvariable=self.status_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(side='left')
        ttk.Label(status, textvariable=self.detail_var,
                  foreground='#666').pack(side='left', padx=10)

        nb = ttk.Notebook(self); nb.pack(fill='both', expand=True, padx=12, pady=6)
        nb.add(self._server_tab(nb), text='  Server  ')
        nb.add(self._models_tab(nb), text='  Models  ')
        nb.add(self._settings_tab(nb), text='  Settings  ')

        bar = ttk.Frame(self); bar.pack(fill='x', padx=12, pady=(0, 10))
        self.progress = ttk.Progressbar(bar, mode='determinate', length=260)
        self.progress.pack(side='left')
        ttk.Label(bar, textvariable=self.progress_var,
                  foreground='#555').pack(side='left', padx=10)
        self.cancel_btn = ttk.Button(bar, text='Cancel', command=self.cancel_pull,
                                     state='disabled')
        self.cancel_btn.pack(side='right')

    def _dot(self, colour):
        self.status_dot.delete('all')
        self.status_dot.create_oval(2, 2, 12, 12, fill=colour, outline='')

    def _server_tab(self, parent):
        f = ttk.Frame(parent)
        box = ttk.LabelFrame(f, text='Ollama server')
        box.pack(fill='x', padx=8, pady=8)
        self.server_info = tk.StringVar(value='')
        ttk.Label(box, textvariable=self.server_info, justify='left',
                  wraplength=640).pack(anchor='w', padx=10, pady=8)

        btns = ttk.Frame(box); btns.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(btns, text='Start', command=self.start_server).pack(side='left')
        ttk.Button(btns, text='Stop', command=self.stop_server).pack(side='left', padx=6)
        ttk.Button(btns, text='Refresh', command=self.refresh_status).pack(side='left')

        inst = ttk.LabelFrame(f, text='Install Ollama')
        inst.pack(fill='x', padx=8, pady=8)
        ttk.Label(inst, text='Ollama is a separate program that runs the models. '
                             'It cannot be bundled inside this app — it is a '
                             'large native program with multi-gigabyte models.',
                  wraplength=640, justify='left').pack(anchor='w', padx=10, pady=(8, 4))
        self.install_hint = tk.StringVar(value='')
        ttk.Label(inst, textvariable=self.install_hint, foreground='#555',
                  wraplength=640, justify='left').pack(anchor='w', padx=10)
        ibtns = ttk.Frame(inst); ibtns.pack(fill='x', padx=10, pady=8)
        self.install_btn = ttk.Button(ibtns, text='Install Ollama',
                                      command=self.install_ollama)
        self.install_btn.pack(side='left')
        ttk.Button(ibtns, text='Open Download Page',
                   command=lambda: webbrowser.open(service.DOWNLOAD_PAGE)) \
            .pack(side='left', padx=6)
        return f

    def _models_tab(self, parent):
        f = ttk.Frame(parent)

        top = ttk.LabelFrame(f, text='Installed models')
        top.pack(fill='both', expand=True, padx=8, pady=(8, 4))
        cols = ('name', 'size', 'params', 'quant', 'modified')
        heads = {'name': 'Model', 'size': 'Size', 'params': 'Parameters',
                 'quant': 'Quantisation', 'modified': 'Installed'}
        self.tree = ttk.Treeview(top, columns=cols, show='headings', height=9)
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=210 if c == 'name' else 110, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=8)
        ttk.Label(top, textvariable=self.disk_var,
                  foreground='#555').pack(anchor='w', padx=10, pady=(0, 6))

        mb = ttk.Frame(top); mb.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(mb, text='Use Selected As Current',
                   command=self.set_current).pack(side='left')
        ttk.Button(mb, text='Model Info', command=self.model_info).pack(side='left', padx=6)
        ttk.Button(mb, text='Uninstall', command=self.delete_model).pack(side='left')
        ttk.Button(mb, text='Refresh', command=self.refresh_models).pack(side='left', padx=6)

        add = ttk.LabelFrame(f, text='Install a model')
        add.pack(fill='x', padx=8, pady=(4, 8))
        row = ttk.Frame(add); row.pack(fill='x', padx=8, pady=8)
        ttk.Label(row, text='Model').pack(side='left')
        self.pull_var = tk.StringVar()
        self.pull_combo = ttk.Combobox(row, textvariable=self.pull_var, width=52,
                                       values=catalog.choices())
        self.pull_combo.pack(side='left', padx=6)
        ttk.Button(row, text='Install', command=self.pull_model).pack(side='left')
        ttk.Label(add, text='Pick from the list or type any Ollama tag '
                            '(e.g. "llama3.1:70b"). Downloads are large — the '
                            'size shown is what will be fetched.',
                  wraplength=640, justify='left', foreground='#555') \
            .pack(anchor='w', padx=10, pady=(0, 8))
        return f

    def _settings_tab(self, parent):
        f = ttk.Frame(parent)
        box = ttk.LabelFrame(f, text='Connection')
        box.pack(fill='x', padx=8, pady=8)
        row = ttk.Frame(box); row.pack(fill='x', padx=10, pady=8)
        ttk.Label(row, text='Host', width=6).pack(side='left')
        ttk.Entry(row, textvariable=self.host_var, width=20).pack(side='left', padx=(0, 12))
        ttk.Label(row, text='Port', width=5).pack(side='left')
        ttk.Entry(row, textvariable=self.port_var, width=8).pack(side='left')
        ttk.Button(row, text='Test', command=self.refresh_status).pack(side='left', padx=10)
        ttk.Label(box, text='The default is 127.0.0.1:11434. Change the port '
                            'only if something else already uses it — Start '
                            'will bind the server to whatever you set here.',
                  wraplength=640, justify='left', foreground='#555') \
            .pack(anchor='w', padx=10, pady=(0, 8))

        cur = ttk.LabelFrame(f, text='Current model')
        cur.pack(fill='x', padx=8, pady=8)
        row2 = ttk.Frame(cur); row2.pack(fill='x', padx=10, pady=8)
        ttk.Label(row2, text='Model', width=6).pack(side='left')
        ttk.Entry(row2, textvariable=self.model_var, width=34).pack(side='left')
        ttk.Button(row2, text='Save', command=self.save_settings).pack(side='left', padx=10)

        link = ttk.LabelFrame(f, text='Construction OS')
        link.pack(fill='x', padx=8, pady=8)
        self.link_hint = tk.StringVar(value='')
        ttk.Label(link, textvariable=self.link_hint, wraplength=640,
                  justify='left').pack(anchor='w', padx=10, pady=(8, 4))
        ttk.Button(link, text='Use This Model In Construction OS',
                   command=self.push_to_cos).pack(anchor='w', padx=10, pady=(0, 10))
        return f

    # -------------------------------------------------------------- threading
    def _run(self, fn, *args, **kwargs):
        """Run a slow call off the main thread; it reports via self.events."""
        if self._busy:
            messagebox.showinfo('Please wait', 'Another task is still running.')
            return False
        self._busy = True
        threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()
        return True

    def _post(self, kind, **payload):
        """Called from worker threads — never touches Tk directly."""
        payload['kind'] = kind
        self.events.put(payload)

    def _drain(self):
        try:
            while True:
                ev = self.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        self.root.after(200, self._drain)

    def _handle(self, ev):
        kind = ev.get('kind')
        if kind == 'status':
            self._apply_status(ev)
        elif kind == 'models':
            self._apply_models(ev.get('models') or [], ev.get('error'))
        elif kind == 'progress':
            total, done = ev.get('total') or 0, ev.get('completed') or 0
            if total:
                self.progress['mode'] = 'determinate'
                self.progress['maximum'] = total
                self.progress['value'] = done
                self.progress_var.set('{}  {} / {}'.format(
                    ev.get('status', ''), api.human_size(done), api.human_size(total)))
            else:
                self.progress_var.set(ev.get('status', ''))
        elif kind == 'done':
            self._busy = False
            self._cancel_pull = False
            self.cancel_btn['state'] = 'disabled'
            self.progress['value'] = 0
            self.progress_var.set(ev.get('message', ''))
            if ev.get('error'):
                messagebox.showerror(ev.get('title', 'Failed'), ev['error'])
            elif ev.get('info'):
                messagebox.showinfo(ev.get('title', 'Done'), ev['info'])
            self.refresh_status()
            self.refresh_models()

    def _tick(self):
        if not self._busy:
            self.refresh_status()
        self.root.after(POLL_MS, self._tick)

    # ---------------------------------------------------------------- status
    def refresh_status(self):
        url, port = self.url(), self._port()
        host = self.host_var.get()
        threading.Thread(target=self._status_worker, args=(url, host, port),
                         daemon=True).start()

    def _status_worker(self, url, host, port):
        info = {
            'installed': service.installed(),
            'binary': service.binary_path() or '',
            'cli': service.cli_version(),
            'port_open': service.port_in_use(host, port),
            'running': api.is_running(url),
            'url': url,
            'pm': service.package_manager(),
            'loaded': [],
            'version': '',
            'disk': service.models_dir_size(),
        }
        if info['running']:
            try:
                info['version'] = api.version(url)
                info['loaded'] = api.running_models(url)
            except api.OllamaError:
                pass
        self._post('status', **info)

    def _apply_status(self, s):
        # Reachable over HTTP but no local binary: Ollama is running somewhere
        # this app cannot control — inside WSL or Docker, or on another PC.
        # Everything that goes through the API (models, downloads) still works;
        # only Start/Stop/Install do not, so say that plainly rather than
        # claiming it is "not installed" while it is visibly answering.
        elsewhere = s['running'] and not s['installed']
        if s['running']:
            self._dot('#2e7d46')
            self.status_var.set('Running (elsewhere)' if elsewhere else 'Running')
            loaded = ', '.join(s['loaded']) or 'none loaded'
            self.detail_var.set('{}  ·  v{}  ·  in memory: {}'.format(
                s['url'], s['version'] or '?', loaded))
        elif s['port_open']:
            self._dot('#b26a00')
            self.status_var.set('Port busy — not answering')
            self.detail_var.set(
                'Something is listening on {} but it is not the Ollama API.'
                .format(s['url']))
        elif not s['installed']:
            self._dot('#a4343a')
            self.status_var.set('Not installed')
            self.detail_var.set('Install Ollama to get started.')
        else:
            self._dot('#a4343a')
            self.status_var.set('Stopped')
            self.detail_var.set('Ollama is installed but not running.')

        if elsewhere:
            installed_line = ('no local install — reachable over the network '
                              '(WSL, Docker, or another PC)')
            program_line = ('not on this PC\'s PATH, so Start / Stop / Install '
                            'are unavailable here')
            version_line = 'v{} (reported by the server)'.format(s['version'] or '?')
        else:
            installed_line = 'yes' if s['installed'] else 'no'
            program_line = s['binary'] or '(not found on PATH)'
            version_line = s['cli'] or '(unknown)'
        self.server_info.set(
            'Installed:  {}\nProgram:    {}\nVersion:    {}\nAddress:    {}\n'
            'Models on disk: {}'.format(
                installed_line, program_line, version_line, s['url'],
                api.human_size(s['disk']) if s['disk'] is not None
                else '(unknown — models live where the server runs)'))
        self.disk_var.set(
            'Models folder: {}   ({})'.format(
                service.models_dir(),
                api.human_size(s['disk']) if s['disk'] is not None else 'unknown'))

        if elsewhere:
            self.install_hint.set(
                'Ollama is already answering at {} — installing a second copy '
                'on Windows would only compete for the same port. Manage '
                'models from the Models tab; they are handled by whichever '
                'server is answering.'.format(s['url']))
            self.install_btn['state'] = 'disabled'
        elif s['installed']:
            self.install_hint.set('Ollama is already installed on this PC.')
            self.install_btn['state'] = 'disabled'
        elif s['pm']:
            self.install_hint.set(
                'Can install automatically using {}. You will be shown the '
                'exact command first.'.format(s['pm']))
            self.install_btn['state'] = 'normal'
        else:
            self.install_hint.set(
                'No supported package manager found here. Use "Open Download '
                'Page" and run the official installer.')
            self.install_btn['state'] = 'disabled'

        db = config.construction_os_db()
        self.link_hint.set(
            'Construction OS found at:\n{}\n\nIts AI Assistant will be set to '
            'use the current model.'.format(db) if db else
            'Construction OS was not found next to this app, so there is '
            'nothing to update.')

    # ---------------------------------------------------------------- server
    def start_server(self):
        if api.is_running(self.url()):
            messagebox.showinfo('Already running',
                                'Ollama is already answering at {}.'.format(self.url()))
            return
        ok, msg = service.start_server(self.host_var.get(), self._port())
        self.progress_var.set(msg)
        if not ok:
            messagebox.showerror('Could not start', msg)
            return
        self.root.after(1500, self.refresh_status)
        self.root.after(4000, self.refresh_models)

    def stop_server(self):
        if api.is_running(self.url()) and not service.installed():
            messagebox.showinfo(
                'Cannot stop from here',
                'Ollama is answering at {}, but it is not installed on this '
                'PC — it is most likely running inside WSL, Docker, or on '
                'another machine.\n\nStop it where it runs (for example '
                '"pkill ollama" inside WSL). This app can still manage its '
                'models.'.format(self.url()))
            return
        if not messagebox.askyesno(
                'Stop Ollama',
                'Stop the local Ollama server?\n\nAnything using it — including '
                'the Construction OS assistant — will stop working until you '
                'start it again. Models stay installed.'):
            return
        ok, msg = service.stop_server()
        self.progress_var.set(msg)
        if not ok:
            messagebox.showinfo('Stop', msg)
        self.root.after(1200, self.refresh_status)

    def install_ollama(self):
        cmd = service.install_command()
        if not cmd:
            messagebox.showinfo(
                'Install manually',
                'No supported package manager was found. Use "Open Download '
                'Page" and run the official installer.')
            return
        if not messagebox.askyesno(
                'Install Ollama',
                'Run this command to install Ollama?\n\n{}\n\nIt downloads and '
                'installs the official package, which can take a few minutes.'
                .format(' '.join(cmd))):
            return
        self.progress_var.set('Installing Ollama…')
        self.progress['mode'] = 'indeterminate'
        self.progress.start(12)
        self._run(self._install_worker)

    def _install_worker(self):
        ok, msg = service.install()
        self._post('done', title='Install Ollama',
                   info=msg if ok else None, error=None if ok else msg,
                   message='' if ok else 'Install failed.')

    # ---------------------------------------------------------------- models
    def refresh_models(self):
        url = self.url()
        threading.Thread(target=self._models_worker, args=(url,),
                         daemon=True).start()

    def _models_worker(self, url):
        try:
            self._post('models', models=api.list_models(url))
        except api.OllamaError as exc:
            self._post('models', models=[], error=str(exc))

    def _apply_models(self, models, error=None):
        self._models = models
        for item in self.tree.get_children():
            self.tree.delete(item)
        current = (self.model_var.get() or '').strip()
        for m in models:
            mark = '● ' if m['name'] == current else '   '
            self.tree.insert('', 'end', iid=m['name'], values=(
                mark + m['name'], api.human_size(m['size']),
                m['parameters'] or '-', m['quantization'] or '-',
                m['modified'] or '-'))
        if not models and not error:
            self.tree.insert('', 'end', values=(
                '   (no models installed — install one below)', '', '', '', ''))

    def _selected_model(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a model first.')
            return None
        return sel[0]

    def set_current(self):
        name = self._selected_model()
        if not name:
            return
        self.model_var.set(name)
        self.cfg['model'] = name
        config.save(self.cfg)
        self._apply_models(self._models)
        self.progress_var.set('Current model: {}'.format(name))

    def model_info(self):
        name = self._selected_model()
        if not name:
            return
        try:
            data = api.show_model(self.url(), name)
        except api.OllamaError as exc:
            messagebox.showerror('Model info', str(exc))
            return
        details = data.get('details') or {}
        lines = [
            'Model:        {}'.format(name),
            'Family:       {}'.format(details.get('family', '-')),
            'Parameters:   {}'.format(details.get('parameter_size', '-')),
            'Quantisation: {}'.format(details.get('quantization_level', '-')),
            'Format:       {}'.format(details.get('format', '-')),
        ]
        params = (data.get('parameters') or '').strip()
        if params:
            lines += ['', 'Parameters set by the model:', params[:600]]
        messagebox.showinfo('Model info', '\n'.join(lines))

    def delete_model(self):
        name = self._selected_model()
        if not name:
            return
        if not messagebox.askyesno(
                'Uninstall model',
                'Delete "{}" from this PC?\n\nIt frees the disk space and can '
                'be installed again later by downloading it.'.format(name)):
            return
        self.progress_var.set('Removing {}…'.format(name))
        self._run(self._delete_worker, name)

    def _delete_worker(self, name):
        try:
            api.delete_model(self.url(), name)
        except api.OllamaError as exc:
            self._post('done', title='Uninstall failed', error=str(exc))
            return
        if (self.model_var.get() or '') == name:
            self.model_var.set('')
            self.cfg['model'] = ''
            config.save(self.cfg)
        self._post('done', message='Removed {}.'.format(name))

    def pull_model(self):
        tag = catalog.tag_from_choice(self.pull_var.get())
        if not tag:
            messagebox.showinfo('Which model?',
                                'Pick a model from the list or type a tag.')
            return
        if not api.is_running(self.url()):
            messagebox.showinfo(
                'Ollama is not running',
                'Start the Ollama server first — downloads go through it.')
            return
        if not messagebox.askyesno(
                'Install model',
                'Download "{}"?\n\nModels are large; on a slow connection this '
                'can take a long while. You can cancel partway.'.format(tag)):
            return
        self._cancel_pull = False
        self.cancel_btn['state'] = 'normal'
        self.progress['mode'] = 'determinate'
        self.progress['value'] = 0
        self.progress_var.set('Starting download…')
        self._run(self._pull_worker, tag)

    def _pull_worker(self, tag):
        try:
            api.pull_model(
                self.url(), tag,
                on_progress=lambda s, c, t: self._post(
                    'progress', status=s, completed=c, total=t),
                should_stop=lambda: self._cancel_pull)
        except api.OllamaError as exc:
            msg = str(exc)
            if 'cancelled' in msg.lower():
                self._post('done', message='Download cancelled.')
            else:
                self._post('done', title='Install failed', error=msg)
            return
        if not (self.model_var.get() or '').strip():
            self.model_var.set(tag)          # first model becomes the current one
            self.cfg['model'] = tag
            config.save(self.cfg)
        self._post('done', title='Installed',
                   info='"{}" is ready to use.'.format(tag),
                   message='Installed {}.'.format(tag))

    def cancel_pull(self):
        self._cancel_pull = True
        self.progress_var.set('Cancelling…')

    # -------------------------------------------------------------- settings
    def save_settings(self):
        self.cfg['host'] = self.host_var.get().strip() or api.DEFAULT_HOST
        self.cfg['port'] = self._port()
        self.cfg['model'] = self.model_var.get().strip()
        config.save(self.cfg)
        self.progress_var.set('Settings saved.')
        self.refresh_status()
        self.refresh_models()

    def push_to_cos(self):
        model = (self.model_var.get() or '').strip()
        if not model:
            messagebox.showinfo('No model',
                                'Choose a current model first (Models tab).')
            return
        self.save_settings()
        ok, msg = config.push_to_construction_os(model, self.url())
        if ok:
            messagebox.showinfo('Construction OS updated', msg)
        else:
            messagebox.showwarning('Not updated', msg)


def main():
    root = tk.Tk()
    root.title('Ollama Manager')
    root.geometry('760x620')
    try:
        root.call('tk', 'scaling', 1.2)
    except tk.TclError:
        pass
    app = ManagerApp(root)
    app.refresh_models()
    root.mainloop()


if __name__ == '__main__':
    main()
