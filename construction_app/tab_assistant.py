"""Assistant tab — ask questions about your data in plain language.

Free-text questions go through the RAG text-to-SQL pipeline in ``assistant.py``
(local Ollama model); quick-answer buttons run deterministic queries that work
even when Ollama isn't running. The LLM call runs in a background thread so the
window never freezes; results are marshalled back with ``after``.

The assistant is strictly **read-only** (see ``assistant.safe_execute``).
"""

import threading
import tkinter as tk
from tkinter import ttk

import assistant
import ollama_client


class AssistantTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._busy = False
        # Recent turns, so a follow-up question can refer back to the last one.
        self.history = []

        head = ttk.Frame(self); head.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(head, text='Ask about your data',
                  font=('TkDefaultFont', 13, 'bold')).pack(side='left')
        self.status_var = tk.StringVar()
        ttk.Label(head, textvariable=self.status_var, foreground='#666').pack(side='right')

        # Quick, LLM-free answers.
        quick = ttk.LabelFrame(self, text='Quick answers (no AI needed)')
        quick.pack(fill='x', padx=10, pady=4)
        self.quick_row = ttk.Frame(quick); self.quick_row.pack(fill='x', padx=6, pady=6)
        ttk.Button(quick, text='Refresh', command=self.load_quick).pack(anchor='e', padx=6, pady=(0, 6))

        # Free-text question.
        ask = ttk.Frame(self); ask.pack(fill='x', padx=10, pady=(8, 4))
        ttk.Label(ask, text='Question').pack(side='left')
        self.q_var = tk.StringVar()
        entry = ttk.Entry(ask, textvariable=self.q_var)
        entry.pack(side='left', fill='x', expand=True, padx=6)
        entry.bind('<Return>', lambda e: self.ask())
        self.ask_btn = ttk.Button(ask, text='Ask', command=self.ask)
        self.ask_btn.pack(side='left')
        # Follow-ups build on the last couple of questions; New topic forgets
        # them so an unrelated question is not muddled by stale context.
        ttk.Button(ask, text='New topic',
                   command=self.new_topic).pack(side='left', padx=(4, 0))

        ttk.Label(self, text='e.g. "how much does Sharma owe me?", "cash received '
                             'this month", "which vendors do I owe?"',
                  foreground='#888', font=('TkDefaultFont', 8)).pack(anchor='w', padx=12)

        # Answer + result table.
        self.answer_var = tk.StringVar()
        ttk.Label(self, textvariable=self.answer_var, wraplength=760,
                  justify='left', font=('TkDefaultFont', 11)).pack(anchor='w', padx=12, pady=6)

        self.tree = ttk.Treeview(self, show='headings', height=9)
        self.tree.pack(fill='both', expand=True, padx=10, pady=4)

        # A simple monospace bar chart, shown only for (label, number) results.
        self.chart_var = tk.StringVar()
        ttk.Label(self, textvariable=self.chart_var, justify='left',
                  font=('Courier', 9)).pack(anchor='w', padx=12, pady=(0, 4))

        self.sql_var = tk.StringVar()
        ttk.Label(self, textvariable=self.sql_var, foreground='#888',
                  wraplength=780, justify='left',
                  font=('TkDefaultFont', 8)).pack(anchor='w', padx=12, pady=(0, 8))

        self.refresh_status()
        self.load_quick()

    # ---------------------------------------------------------------- config
    def _config(self):
        conn = self.db_getter()
        try:
            return assistant.get_config(conn)
        finally:
            conn.close()

    def refresh_status(self):
        model, host = self._config()
        if ollama_client.available(host):
            self.status_var.set('AI: connected ({} @ {})'.format(model, host))
        else:
            self.status_var.set('AI: offline — quick answers still work. '
                                'Start Ollama & set the model in Tools.')

    # ------------------------------------------------------------ quick answers
    def load_quick(self):
        for w in self.quick_row.winfo_children():
            w.destroy()
        conn = self.db_getter()
        try:
            data = assistant.quick_answers(conn)
        finally:
            conn.close()
        for label, value in data.items():
            b = ttk.Button(self.quick_row, text='{}: ₹ {:,.0f}'.format(label, value),
                           command=lambda l=label, v=value: self._show_quick(l, v))
            b.pack(side='left', padx=4)

    def _show_quick(self, label, value):
        self.answer_var.set('{}:  ₹ {:,.2f}'.format(label, value))
        self._set_table([], [])
        self.sql_var.set('')

    # ------------------------------------------------------------------- ask
    def ask(self):
        if self._busy:
            return
        question = self.q_var.get().strip()
        if not question:
            return
        self._busy = True
        self.ask_btn.configure(state='disabled')
        self.answer_var.set('Thinking…')
        self._set_table([], [])
        self.sql_var.set('')
        model, host = self._config()
        # Snapshot the history for this turn (the worker runs off-thread).
        history = list(self.history)
        self._pending_q = question
        threading.Thread(target=self._worker, args=(question, model, host, history),
                         daemon=True).start()

    def new_topic(self):
        """Forget the conversation so the next question starts fresh."""
        self.history = []
        self.q_var.set('')
        self.answer_var.set('New topic — ask anything.')

    def _worker(self, question, model, host, history):
        result = assistant.answer(question, model=model, host=host,
                                  history=history)
        # Marshal back onto the UI thread.
        self.after(0, lambda: self._render(result))

    def _render(self, result):
        self._busy = False
        self.ask_btn.configure(state='normal')
        columns, rows = result.get('columns', []), result.get('rows', [])
        if 'error' in result:
            self.answer_var.set('⚠ ' + result['error'])
            self._set_table(columns, rows)
            self._set_chart(columns, rows)
            self.sql_var.set(result.get('sql', ''))
            return
        self.answer_var.set(result.get('summary') or 'Done.')
        self._set_table(columns, rows)
        self._set_chart(columns, rows)
        self.sql_var.set('SQL: ' + result.get('sql', ''))
        # Remember this turn so the next question can follow on. Only the
        # question and a short summary are kept — enough to resolve a
        # reference, not the whole result set. Capped so context stays small.
        self.history.append({'question': getattr(self, '_pending_q', ''),
                             'summary': result.get('summary', '')})
        self.history = self.history[-4:]

    def _set_chart(self, columns, rows):
        self.chart_var.set(assistant.text_bar_chart(columns, rows))

    def _set_table(self, columns, rows):
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=list(columns))
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=max(90, min(240, 700 // max(1, len(columns)))),
                             anchor='w')
        for r in rows:
            self.tree.insert('', 'end', values=list(r))


def build_assistant_tab(parent, db_getter):
    return AssistantTab(parent, db_getter)
