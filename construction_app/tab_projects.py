"""Project management — the umbrella that ties a job together.

A **project** groups a client + site + budget + dates. **Milestones** track
progress and payment stages. The **Overview** is a computed dashboard: budget vs
cost-to-date (material issued + labour paid + equipment hire on the project's
site) vs billed (Approved/Paid bills + RA bills on that site's contracts), plus
milestone progress and open tasks.

Projects and Milestones are thin CrudFrames; Overview is bespoke and read-only.
Timeline tasks can be linked to a project (see tab_timeline) so the Gantt and
this dashboard can scope to one project.
"""

import tkinter as tk
from tkinter import ttk

import projman
from crud_frame import CrudFrame, Field
from tab_masters import client_options, site_options, project_options


def _build_projects(parent, db_getter):
    fields = [
        Field('name', 'Project Name'),
        Field('client_id', 'Client', kind='fk', options_func=client_options),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('start_date', 'Start Date'),
        Field('end_date', 'End Date'),
        Field('budget', 'Budget', kind='number', default='0'),
        Field('status', 'Status', kind='combo',
              options=['Active', 'On Hold', 'Completed', 'Cancelled'],
              default='Active'),
        # Delay terms, used by Timeline > Baseline vs Actual to estimate
        # liquidated-damages exposure. They vary by contract, so they are set
        # per project rather than assumed. Contract value is kept separate
        # from budget: budget is what you expect to spend, contract value is
        # what LDs are computed on.
        Field('contract_value', 'Contract Value (for LDs)', kind='number',
              default='0'),
        Field('ld_pct_per_week', 'LD % per week', kind='number', default='0.5'),
        Field('ld_cap_pct', 'LD cap %', kind='number', default='10'),
        Field('eot_granted_days', 'Extension granted (days)', kind='number',
              default='0'),
        Field('notes', 'Notes', width=200),
    ]
    return CrudFrame(parent, db_getter, 'projects', fields, 'Projects')


def _build_milestones(parent, db_getter):
    fields = [
        Field('project_id', 'Project', kind='fk', options_func=project_options),
        Field('name', 'Milestone'),
        Field('target_date', 'Target Date'),
        Field('actual_date', 'Actual Date'),
        Field('amount', 'Amount', kind='number', default='0'),
        Field('status', 'Status', kind='combo',
              options=['Pending', 'Done'], default='Pending'),
        Field('notes', 'Notes', width=180),
    ]
    return CrudFrame(parent, db_getter, 'milestones', fields, 'Milestones',
                     order_by='target_date, id')


class ProjectOverview(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._map = {}
        self.project_var = tk.StringVar()

        top = ttk.Frame(self); top.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(top, text='Project', font=('TkDefaultFont', 11, 'bold')).pack(side='left')
        self.combo = ttk.Combobox(top, textvariable=self.project_var, width=28,
                                  state='readonly')
        self.combo.pack(side='left', padx=6)
        self.combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Reload', command=self.reload).pack(side='left')

        self.tiles = ttk.Frame(self); self.tiles.pack(fill='x', padx=8, pady=8)
        self._vars = {}
        specs = [('Budget', 'budget', '#5d4037'), ('Cost to Date', 'cost', '#c62828'),
                 ('Billed', 'billed', '#1565c0'), ('Margin so far', 'margin', '#2e7d32'),
                 ('Budget Used', 'used', '#6a1b9a'), ('Progress', 'progress', '#00695c')]
        for idx, (title, key, accent) in enumerate(specs):
            r, c = divmod(idx, 3)
            card = ttk.LabelFrame(self.tiles, text=title)
            card.grid(row=r, column=c, padx=8, pady=6, sticky='nsew')
            self.tiles.columnconfigure(c, weight=1)
            var = tk.StringVar(value='—'); self._vars[key] = var
            ttk.Label(card, textvariable=var, foreground=accent,
                      font=('TkDefaultFont', 16, 'bold')).pack(padx=14, pady=12, anchor='w')

        self.detail_var = tk.StringVar()
        ttk.Label(self, textvariable=self.detail_var, justify='left',
                  wraplength=760).pack(anchor='w', padx=12, pady=6)
        self.reload()

    def reload(self):
        conn = self.db_getter()
        try:
            opts = project_options(conn)
        finally:
            conn.close()
        self._map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.combo['values'] = list(self._map.keys())
        self.refresh()

    def _pid(self):
        raw = self.project_var.get().strip()
        return self._map.get(raw, raw.split(' - ')[0]) if raw else None

    def refresh(self):
        pid = self._pid()
        for v in self._vars.values():
            v.set('—')
        self.detail_var.set('')
        if pid is None:
            return
        conn = self.db_getter()
        try:
            p = conn.execute('SELECT * FROM projects WHERE id = ?', (pid,)).fetchone()
            if p is None:
                return
            site_id = p['site_id']

            def scalar(sql, params):
                return conn.execute(sql, params).fetchone()[0] or 0

            material = labour = hire = billed = 0
            if site_id is not None:
                material = scalar("SELECT COALESCE(SUM(qty*rate),0) FROM material_ledger "
                                  "WHERE txn_type='OUT' AND site_id=?", (site_id,))
                labour = scalar("SELECT COALESCE(SUM(amount),0) FROM payments "
                                "WHERE direction='Payment' AND party_type='Labour' AND site_id=?", (site_id,))
                hire = scalar("SELECT COALESCE(SUM(total_amount),0) FROM equipment_hire WHERE site_id=?", (site_id,))
                billed = scalar("SELECT COALESCE(SUM(net_payable),0) FROM bills "
                                "WHERE status IN ('Approved','Paid') AND contract_id IN "
                                "(SELECT id FROM contracts WHERE site_id=?)", (site_id,))
                billed += scalar("SELECT COALESCE(SUM(net_payable),0) FROM ra_bills "
                                 "WHERE status IN ('Approved','Paid') AND contract_id IN "
                                 "(SELECT id FROM contracts WHERE site_id=?)", (site_id,))
            milestones = conn.execute(
                'SELECT amount, status FROM milestones WHERE project_id=?', (pid,)).fetchall()
            open_tasks = scalar(
                "SELECT COUNT(*) FROM timeline_tasks WHERE (project_id=? OR "
                "(project_id IS NULL AND site_id=?)) AND status != 'Completed'",
                (pid, site_id))
            ms_total = len(milestones)
            ms_done = sum(1 for m in milestones if (m['status'] or '').lower() == 'done')
        finally:
            conn.close()

        cost = material + labour + hire
        bs = projman.budget_status(p['budget'], cost)
        progress = projman.milestone_progress(milestones)
        margin = round(billed - cost, 2)

        def rupee(x):
            return '₹ {:,.0f}'.format(round(float(x or 0)))
        self._vars['budget'].set(rupee(bs['budget']))
        self._vars['cost'].set(rupee(bs['cost']))
        self._vars['billed'].set(rupee(billed))
        self._vars['margin'].set(rupee(margin))
        self._vars['used'].set('—' if bs['used_pct'] is None else '{:.0f}%'.format(bs['used_pct']))
        self._vars['progress'].set('{:.0f}%'.format(progress))

        parts = [
            'Client site cost breakup: material {}, labour {}, hire {}.'.format(
                rupee(material), rupee(labour), rupee(hire)),
            'Milestones: {} of {} done.'.format(ms_done, ms_total),
            'Open tasks: {}.'.format(open_tasks),
        ]
        if bs['over_budget']:
            parts.append('⚠ Cost has exceeded the budget.')
        self.detail_var.set('  '.join(parts))


def build_projects_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_projects(nb, db_getter), text='Projects')
    nb.add(_build_milestones(nb, db_getter), text='Milestones')
    nb.add(ProjectOverview(nb, db_getter), text='Overview')
    return nb
