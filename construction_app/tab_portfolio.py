"""Portfolio shell — federated roll-up over firm/year SQLite files (E2).

Read-only. Uses ``portfolio_store`` so each file stays authoritative; this tab
only pools and points at which file needs attention. Paths are entered as a
comma-separated list (same contract as ``GET /api/portfolio?paths=``).
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog

import db
import portfolio_store
import theme


class PortfolioTab(ttk.Frame):
    COLS = ('file', 'projects', 'risks', 'exposure', 'opps', 'upside',
            'lessons_ff')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.paths_var = tk.StringVar()
        self.headline_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='Portfolio',
                  font=('TkDefaultFont', 14, 'bold')).pack(
            anchor='w', padx=12, pady=(12, 2))
        ttk.Label(
            self,
            text='Roll up projects, risks, opportunities and lessons across '
                 'firm/year files. Read-only — each file stays the source of truth.',
            foreground=pal['muted'], wraplength=760, justify='left'
        ).pack(anchor='w', padx=12, pady=(0, 6))

        bar = ttk.Frame(self); bar.pack(fill='x', padx=12, pady=4)
        ttk.Label(bar, text='Extra files').pack(side='left')
        ttk.Entry(bar, textvariable=self.paths_var, width=50).pack(
            side='left', padx=6)
        ttk.Button(bar, text='Add…', command=self._pick).pack(side='left')
        ttk.Button(bar, text='Refresh', command=self.refresh).pack(
            side='left', padx=6)

        ttk.Label(self, textvariable=self.headline_var,
                  font=('TkDefaultFont', 11, 'bold'), wraplength=760,
                  justify='left').pack(anchor='w', padx=12, pady=4)

        lf = ttk.Frame(self); lf.pack(fill='both', expand=True, padx=12, pady=4)
        self.tree = ttk.Treeview(lf, columns=self.COLS, show='headings',
                                 height=10)
        heads = {
            'file': 'File', 'projects': 'Projects', 'risks': 'Risks',
            'exposure': 'Risk exposure ₹', 'opps': 'Opportunities',
            'upside': 'Upside ₹', 'lessons_ff': 'Lessons to apply',
        }
        for c in self.COLS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=110 if c != 'file' else 220, anchor='w')
        self.tree.pack(fill='both', expand=True)

    def _pick(self):
        path = filedialog.askopenfilename(
            title='Add firm/year SQLite file',
            filetypes=[('SQLite', '*.db *.sqlite'), ('All', '*.*')])
        if not path:
            return
        cur = self.paths_var.get().strip()
        self.paths_var.set((cur + ',' + path) if cur else path)

    def _path_list(self):
        extra = [p.strip() for p in self.paths_var.get().split(',') if p.strip()]
        current = getattr(db, 'DB_PATH', None)
        paths = []
        if current and os.path.exists(current):
            paths.append(('Current book', current))
        for p in extra:
            if os.path.exists(p):
                paths.append((os.path.basename(p), p))
        return paths

    def refresh(self):
        paths = self._path_list()
        if not paths:
            # Fall back to the live connection for current-file only.
            conn = self.db_getter()
            try:
                roll = {
                    'totals': portfolio_store.file_rollup(conn, 'Current book'),
                    'per_file': [portfolio_store.file_rollup(conn, 'Current book')],
                    'unreadable': [],
                }
                # Normalise to roll_up shape
                fr = roll['per_file'][0]
                roll = {
                    'totals': {
                        'projects': fr['projects'],
                        'risk_count': fr['risks'].get('count', 0),
                        'risk_needs_action': fr['risks'].get('needs_action', 0),
                        'risk_exposure': fr['risks'].get(
                            'total_expected_exposure', 0),
                        'opportunity_count': fr['opportunities'].get('count', 0),
                        'opportunity_pursue_now': fr['opportunities'].get(
                            'pursue_now', 0),
                        'opportunity_value': fr['opportunities'].get(
                            'total_expected_value', 0),
                        'lessons_to_apply': fr['lessons'].get(
                            'feed_forward_count', 0),
                    },
                    'per_file': [fr],
                    'unreadable': [],
                }
            finally:
                conn.close()
        else:
            roll = portfolio_store.roll_up(paths)

        self.tree.delete(*self.tree.get_children())
        for fr in roll.get('per_file') or []:
            risks = fr.get('risks') or {}
            opps = fr.get('opportunities') or {}
            less = fr.get('lessons') or {}
            self.tree.insert('', 'end', values=(
                fr.get('name') or '—',
                fr.get('projects', 0),
                risks.get('count', 0),
                '{:,.0f}'.format(risks.get('total_expected_exposure', 0) or 0),
                opps.get('count', 0),
                '{:,.0f}'.format(opps.get('total_expected_value', 0) or 0),
                less.get('feed_forward_count', 0),
            ))
        t = roll.get('totals') or {}
        unread = roll.get('unreadable') or []
        self.headline_var.set(
            '{p} projects · {rn} risks needing action (₹{re:,.0f}) · '
            '{on} opportunities to pursue (₹{ou:,.0f}) · {lf} lessons to apply'
            '{u}'.format(
                p=t.get('projects', 0),
                rn=t.get('risk_needs_action', 0),
                re=t.get('risk_exposure', 0) or 0,
                on=t.get('opportunity_pursue_now', t.get('opp_pursue_now', 0)),
                ou=t.get('opportunity_value', t.get('opp_upside', 0)) or 0,
                lf=t.get('lessons_to_apply', t.get('lessons_feed_forward', 0)),
                u=(' · unreadable: ' + ', '.join(unread)) if unread else ''))


def build_portfolio_tab(parent, db_getter):
    return PortfolioTab(parent, db_getter)
