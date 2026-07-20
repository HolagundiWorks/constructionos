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
from tkinter import ttk, messagebox

import projman
import projectcost
import bill_export
import report_open
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


def _sole_on_site(conn, pid):
    """True when this project is the only one on its site — the condition
    under which untagged rows may be attributed by site."""
    row = conn.execute('SELECT site_id FROM projects WHERE id = ?',
                       (pid,)).fetchone()
    site_id = row['site_id'] if row else None
    return conn.execute(
        'SELECT COUNT(*) FROM projects WHERE site_id = ? AND site_id IS NOT NULL',
        (site_id,)).fetchone()[0] <= 1


def _gather_project_rows(conn, pid, site_id):
    """Candidate cost/revenue rows: everything tagged to this project or
    sitting on its site, so the rollup can decide which actually count.

    Cost categories mirror the Overview tab (material issued, labour paid,
    equipment hire); revenue is Approved/Paid bills and RA bills, with the
    project and site inherited from the contract.
    """
    rows = []
    for r in conn.execute(
            "SELECT qty*rate AS amount, project_id, site_id FROM "
            "material_ledger WHERE txn_type='OUT' AND "
            "(project_id=? OR site_id=?)", (pid, site_id)):
        rows.append({'category': projectcost.MATERIAL, 'amount': r['amount'],
                     'project_id': r['project_id'], 'site_id': r['site_id']})
    for r in conn.execute(
            "SELECT amount, project_id, site_id FROM payments WHERE "
            "direction='Payment' AND party_type='Labour' AND "
            "(project_id=? OR site_id=?)", (pid, site_id)):
        rows.append({'category': projectcost.LABOUR, 'amount': r['amount'],
                     'project_id': r['project_id'], 'site_id': r['site_id']})
    for r in conn.execute(
            "SELECT total_amount AS amount, project_id, site_id FROM "
            "equipment_hire WHERE (project_id=? OR site_id=?)", (pid, site_id)):
        rows.append({'category': projectcost.HIRE, 'amount': r['amount'],
                     'project_id': r['project_id'], 'site_id': r['site_id']})
    for table in ('bills', 'ra_bills'):
        for r in conn.execute(
                "SELECT b.net_payable AS amount, c.project_id AS project_id, "
                "c.site_id AS site_id FROM {} b JOIN contracts c "
                "ON c.id = b.contract_id WHERE b.status IN ('Approved','Paid') "
                "AND (c.project_id=? OR c.site_id=?)".format(table),
                (pid, site_id)):
            rows.append({'category': projectcost.REVENUE, 'amount': r['amount'],
                         'project_id': r['project_id'], 'site_id': r['site_id']})
    return rows


def project_cost_rollup(conn, pid):
    """The full cost/revenue rollup for one project. Shared by the Project Cost
    view and the KPI dashboard so both compute it the same way."""
    p = conn.execute('SELECT site_id, budget FROM projects WHERE id = ?',
                    (pid,)).fetchone()
    if p is None:
        return projectcost.rollup([], pid, None, True, 0)
    rows = _gather_project_rows(conn, pid, p['site_id'])
    return projectcost.rollup(rows, pid, p['site_id'],
                             _sole_on_site(conn, pid), p['budget'])


class ProjectCost(ttk.Frame):
    """Cost, revenue and margin for one project, honouring explicit project
    tags where they exist and falling back to the site otherwise.

    The Overview tab attributes everything by site, which cannot tell two
    projects on one plot apart. This one uses ``projectcost``: a tagged row
    always counts, an untagged row counts by site only when the project is the
    sole one there, and untagged cost on a shared site is reported unattributed
    rather than guessed.
    """

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._map = {}
        self._rollup = {}
        self.project_var = tk.StringVar()
        self.headline_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.warn_var = tk.StringVar()
        self._build_ui()
        self.reload()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(top, text='Project', font=('TkDefaultFont', 11, 'bold')).pack(side='left')
        self.combo = ttk.Combobox(top, textvariable=self.project_var, width=28,
                                  state='readonly')
        self.combo.pack(side='left', padx=6)
        self.combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Reload', command=self.reload).pack(side='left')
        ttk.Button(top, text='Print / Export',
                   command=self.export).pack(side='left', padx=6)

        self.tiles = ttk.Frame(self); self.tiles.pack(fill='x', padx=8, pady=8)
        self._vars = {}
        specs = [('Revenue', 'revenue', '#1565c0'),
                 ('Cost', 'cost', '#c62828'),
                 ('Margin', 'margin', '#2e7d32'),
                 ('Margin %', 'margin_pct', '#00695c'),
                 ('Budget Used', 'used', '#6a1b9a')]
        for idx, (title, key, accent) in enumerate(specs):
            r, c = divmod(idx, 3)
            card = ttk.LabelFrame(self.tiles, text=title)
            card.grid(row=r, column=c, padx=8, pady=6, sticky='nsew')
            self.tiles.columnconfigure(c, weight=1)
            var = tk.StringVar(value='—'); self._vars[key] = var
            ttk.Label(card, textvariable=var, foreground=accent,
                      font=('TkDefaultFont', 16, 'bold')).pack(padx=14, pady=12, anchor='w')

        ttk.Label(self, textvariable=self.headline_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=12)
        ttk.Label(self, textvariable=self.detail_var, justify='left',
                  wraplength=820).pack(anchor='w', padx=12, pady=4)
        ttk.Label(self, textvariable=self.warn_var, foreground='#8a5a00',
                  wraplength=820, justify='left').pack(anchor='w', padx=12)
        ttk.Label(self, text=(
            'Tag a cost to a project on its entry form (material issue, payment, '
            'hire) or tag a contract to a project so its bills roll up here. '
            'Cost categories mirror the Overview tab (material, labour, hire); '
            'purchase orders and vendor invoices are not counted as realised '
            'cost.'), foreground='#666', wraplength=820, justify='left') \
            .pack(anchor='w', padx=12, pady=(6, 8))

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
        for v in self._vars.values():
            v.set('—')
        self.headline_var.set(''); self.detail_var.set(''); self.warn_var.set('')
        pid = self._pid()
        if pid is None:
            return
        conn = self.db_getter()
        try:
            roll = project_cost_rollup(conn, pid)
            sole = _sole_on_site(conn, pid)
        finally:
            conn.close()
        self._rollup = roll

        def rupee(x):
            return '₹ {:,.0f}'.format(round(float(x or 0)))
        self._vars['revenue'].set(rupee(roll['revenue']))
        self._vars['cost'].set(rupee(roll['total_cost']))
        self._vars['margin'].set(rupee(roll['margin']))
        self._vars['margin_pct'].set('—' if roll['margin_pct'] is None
                                     else '{:.0f}%'.format(roll['margin_pct']))
        self._vars['used'].set('—' if roll['budget_used_pct'] is None
                               else '{:.0f}%'.format(roll['budget_used_pct']))

        self.headline_var.set(
            'Attribution: {}'.format(
                'this project is the only one on its site, so untagged costs '
                'roll up by site.' if sole else
                'this site hosts more than one project, so only tagged costs '
                'count — tag the rest to attribute them.'))
        cats = roll['by_category']
        self.detail_var.set(
            'Cost breakup: material {}, labour {}, hire {}.'.format(
                rupee(cats['material']), rupee(cats['labour']),
                rupee(cats['hire'])))
        bits = []
        if roll['over_budget']:
            bits.append('Cost has exceeded the budget.')
        if roll['unattributed_cost']:
            bits.append('{} of untagged cost on this shared site is not '
                        'attributed to any project — tag it to count it.'.format(
                            rupee(roll['unattributed_cost'])))
        self.warn_var.set('  '.join(bits))

    def export(self):
        if not self._rollup:
            messagebox.showinfo('Nothing to export', 'Select a project first.')
            return
        roll = self._rollup
        cats = roll['by_category']
        rows = [('Revenue billed', '{:,.2f}'.format(roll['revenue'])),
                ('Material', '{:,.2f}'.format(cats['material'])),
                ('Labour', '{:,.2f}'.format(cats['labour'])),
                ('Hire', '{:,.2f}'.format(cats['hire'])),
                ('Total cost', '{:,.2f}'.format(roll['total_cost'])),
                ('Margin', '{:,.2f}'.format(roll['margin']))]
        summary = 'Margin {:,.2f}'.format(roll['margin'])
        if roll['unattributed_cost']:
            summary += '   ({:,.2f} untagged cost not attributed)'.format(
                roll['unattributed_cost'])
        html = bill_export.build_statement_html(
            'Project cost sheet — {}'.format(self.project_var.get()),
            [self.headline_var.get()], ['Line', 'Amount'], rows,
            summary=summary)
        report_open.save_and_open_html(html, 'project_cost.html')


def build_projects_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_projects(nb, db_getter), text='Projects')
    nb.add(_build_milestones(nb, db_getter), text='Milestones')
    nb.add(ProjectOverview(nb, db_getter), text='Overview')
    nb.add(ProjectCost(nb, db_getter), text='Project Cost')
    return nb
