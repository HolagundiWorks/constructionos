"""AI Engine — a minimal **Start / Stop** control for the built-in assistant.

The app ships **one** hardcoded model (``ollama_client.DEFAULT_MODEL`` —
Qwen2.5-Coder 1.5B, tuned for the assistant's NL→SQL) that runs entirely on this
machine. There is deliberately **no downloader, model catalogue, or picker**:
the model is internal, so all the user needs is to turn the engine on to use the
Assistant and off to free the memory.

Under the hood the local runtime is Ollama, but it is never shown as such — this
tab just starts/stops the local server and, on first start, registers the
bundled model offline (``model_provision``). Network/process work runs on a
worker thread and marshals back with ``after`` so the window never freezes.
"""

import threading
import tkinter as tk
from tkinter import ttk

import ollama_api as api
import ollama_service as service
import ollama_client
import model_provision as provision
import theme
from ui_guard import can_write

MODEL = ollama_client.DEFAULT_MODEL      # the single, built-in model


class AiEngineTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._busy = False
        self._build_ui()
        self.refresh()

    def _host(self):
        conn = self.db_getter()
        try:
            import assistant
            return assistant.get_config(conn)[1]
        finally:
            conn.close()

    def _url(self):
        return api.base_url(self._host())

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='AI Engine', font=('TkDefaultFont', 14, 'bold')) \
            .pack(anchor='w', padx=14, pady=(14, 2))
        ttk.Label(
            self, wraplength=620, justify='left', foreground=pal['muted'],
            text='A built-in AI assistant runs entirely on this machine — no '
                 'internet, no accounts. Turn it on to use the Assistant, off '
                 'to free memory.') \
            .pack(anchor='w', padx=14, pady=(0, 12))

        card = ttk.LabelFrame(self, text='Engine')
        card.pack(fill='x', padx=14, pady=4)
        self.status_var = tk.StringVar(value='Checking…')
        ttk.Label(card, textvariable=self.status_var,
                  font=('TkDefaultFont', 11)).pack(anchor='w', padx=10,
                                                   pady=(8, 4))
        row = ttk.Frame(card); row.pack(fill='x', padx=10, pady=(0, 8))
        self.start_btn = ttk.Button(row, text='Start', style='Accent.TButton',
                                    command=self.start)
        self.start_btn.pack(side='left', padx=(0, 6))
        self.stop_btn = ttk.Button(row, text='Stop', command=self.stop)
        self.stop_btn.pack(side='left', padx=6)
        ttk.Button(row, text='Refresh', command=self.refresh).pack(
            side='left', padx=6)

        ttk.Label(card, text='Model:  {}  (built in)'.format(MODEL),
                  foreground=pal['helper']).pack(anchor='w', padx=10,
                                                 pady=(0, 8))
        self.detail_var = tk.StringVar()
        ttk.Label(self, textvariable=self.detail_var, wraplength=620,
                  justify='left', foreground=pal['muted']).pack(
            anchor='w', padx=14, pady=(2, 8))

    def _post(self, fn):
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

    # --------------------------------------------------------------- status
    def refresh(self):
        self.status_var.set('Checking…')

        def work():
            url = self._url()
            running = api.is_running(url)
            ver = api.version(url) if running else ''
            installed = service.installed()
            ready = provision.registered_now(url) if running else False
            self._post(lambda: self._render(running, ver, installed, ready))
        threading.Thread(target=work, daemon=True).start()

    def _render(self, running, ver, installed, ready):
        if self._busy:
            return
        if running and ready:
            self.status_var.set('● Running — the Assistant is ready.{}'.format(
                '   (v{})'.format(ver) if ver else ''))
            self.detail_var.set('')
        elif running and not ready:
            self.status_var.set('● Running — finishing model set-up…')
            self.detail_var.set('The built-in model is being registered; this '
                                'is a one-time step.')
        elif installed:
            self.status_var.set('○ Stopped — press Start to use the Assistant.')
            self.detail_var.set('')
        else:
            self.status_var.set('○ AI engine is not set up on this machine.')
            self.detail_var.set('The built-in AI runtime was not found. Reinstall '
                                'Construction OS with the AI option enabled to '
                                'use the Assistant offline.')
        self.start_btn.state(['!disabled'] if installed and not running
                             else ['disabled'])
        self.stop_btn.state(['!disabled'] if running else ['disabled'])

    # -------------------------------------------------------------- actions
    def start(self):
        if not can_write():
            return
        if not service.installed():
            self.refresh()
            return
        self._busy = True
        self.start_btn.state(['disabled'])
        self.stop_btn.state(['disabled'])
        self.status_var.set('Starting…')
        self.detail_var.set('')

        def work():
            service.start_server()
            provision._wait_available(self._url())
            # First start: register the bundled model offline (idempotent).
            if provision.bundled() and not provision.registered_now(self._url()):
                self._post(lambda: self.status_var.set(
                    'Setting up the model (one-time)…'))
                provision.provision(host=self._host())
            self._busy = False
            self._post(self.refresh)
        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        self._busy = True
        self.stop_btn.state(['disabled'])
        self.status_var.set('Stopping…')

        def work():
            service.stop_server()
            self._busy = False
            self._post(self.refresh)
        threading.Thread(target=work, daemon=True).start()


def build_ollama_tab(parent, db_getter):
    return AiEngineTab(parent, db_getter)
