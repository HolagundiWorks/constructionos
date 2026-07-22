"""Process view + command search (E7.4) — guided "what's next" over workflows.

Pure sequencing lives in ``workflow.py`` / ``workflow_state.py``; this tab only
renders progress, the next incomplete step per flow, and a command-palette
search over the live catalog. An optional ``on_goto(section, tab)`` deep-links
into the rail.
"""

import tkinter as tk
from tkinter import ttk

import menu
import theme
import workflow
import workflow_state


_FLOW_TITLES = {
    'bid_to_contract': 'Bid → Contract',
    'contract_to_cash': 'Contract → Cash',
    'procure_to_pay': 'Procure → Pay',
    'plan_to_execute': 'Plan → Execute',
}


class ProcessTab(ttk.Frame):
    def __init__(self, parent, db_getter, on_goto=None):
        super().__init__(parent)
        self.db_getter = db_getter
        self.on_goto = on_goto
        self._hits = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text="What's next",
                  font=('TkDefaultFont', 14, 'bold')).pack(
            anchor='w', padx=12, pady=(12, 2))
        ttk.Label(
            self,
            text='Operational flows across the menu — not a re-org, just the '
                 'sequence. Search jumps to any tab.',
            foreground=pal['muted'], wraplength=760, justify='left'
        ).pack(anchor='w', padx=12, pady=(0, 8))

        # --- command search
        search = ttk.LabelFrame(self, text='Go to…')
        search.pack(fill='x', padx=12, pady=4)
        row = ttk.Frame(search); row.pack(fill='x', padx=8, pady=6)
        ttk.Label(row, text='Search').pack(side='left')
        self.q_var = tk.StringVar()
        ent = ttk.Entry(row, textvariable=self.q_var, width=40)
        ent.pack(side='left', padx=6)
        ent.bind('<KeyRelease>', lambda _e: self._filter())
        ent.bind('<Return>', lambda _e: self._open_selected())
        ttk.Button(row, text='Open', command=self._open_selected).pack(
            side='left', padx=4)

        self.hit_list = tk.Listbox(search, height=6, activestyle='dotbox')
        self.hit_list.pack(fill='x', padx=8, pady=(0, 8))
        self.hit_list.bind('<Double-Button-1>', lambda _e: self._open_selected())

        # --- workflows
        self.flows = ttk.Frame(self)
        self.flows.pack(fill='both', expand=True, padx=12, pady=4)
        ttk.Button(self, text='Refresh', command=self.refresh).pack(
            anchor='w', padx=12, pady=(0, 10))

    def refresh(self):
        conn = self.db_getter()
        try:
            report = workflow_state.progress_report(conn)
        finally:
            conn.close()
        for child in self.flows.winfo_children():
            child.destroy()
        for name in workflow.WORKFLOWS:
            p = report.get(name) or workflow.progress(workflow.WORKFLOWS[name], {})
            box = ttk.LabelFrame(self.flows, text=_FLOW_TITLES.get(name, name))
            box.pack(fill='x', pady=4)
            nxt = p.get('next')
            if p.get('complete'):
                line = 'Complete — {}/{} steps ({:.0f}%).'.format(
                    p['done'], p['total'], p['pct'] or 0)
            elif nxt:
                line = '{done}/{total} · next: {label}  →  {sec} › {tab}'.format(
                    done=p['done'], total=p['total'],
                    label=nxt['label'], sec=nxt['section'], tab=nxt['tab'])
            else:
                line = 'No steps.'
            ttk.Label(box, text=line, wraplength=720, justify='left').pack(
                anchor='w', padx=8, pady=6)
            if nxt and self.on_goto:
                ttk.Button(
                    box, text='Open next step',
                    command=lambda s=nxt['section'], t=nxt['tab']: self.on_goto(s, t)
                ).pack(anchor='w', padx=8, pady=(0, 8))
        self._filter()

    def _filter(self):
        import record_search
        q = self.q_var.get()
        tab_hits = menu.search_tabs(q)
        conn = self.db_getter()
        try:
            rec_hits = record_search.search_records(conn, q, limit=20)
        finally:
            conn.close()
        self._hits = (
            [{'kind': 'tab', **h} for h in tab_hits]
            + rec_hits
        )
        self.hit_list.delete(0, 'end')
        for h in self._hits[:50]:
            text = h.get('display') or h.get('label') or ''
            if h.get('kind') == 'tab':
                text = h.get('label') or text
            self.hit_list.insert('end', text)

    def _open_selected(self):
        if not self.on_goto or not self._hits:
            return
        idxs = self.hit_list.curselection()
        i = idxs[0] if idxs else 0
        if i >= len(self._hits):
            return
        h = self._hits[i]
        self.on_goto(h.get('section'), h.get('tab'))


def build_process_tab(parent, db_getter, on_goto=None):
    return ProcessTab(parent, db_getter, on_goto=on_goto)
