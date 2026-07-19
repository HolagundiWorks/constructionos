"""Weekly look-ahead with PPC, and cost-value reconciliation (Wave 3).

**Look-ahead** — what the site promises to finish this week, scored at the end
of it. The score (Percent Plan Complete) says the plan was unreliable; the
**reasons for misses** say why, and that is the half that changes anything.

**CVR** — cost incurred against value earned per cost head, per site. Profit
at the end of a job is a post-mortem; this is the same arithmetic early enough
to act on.

Cost heads are drawn from what the app already records — material issued,
labour paid, equipment hire, subcontract — against value earned from approved
bills, so nothing has to be re-entered to see the picture.
"""

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk, messagebox

import bill_export
import planning
import report_open
from crud_frame import CrudFrame, Field
from tab_masters import site_options
from ui_guard import can_write


def _monday(d=None):
    d = d or date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def build_commitments(parent, db_getter):
    fields = [
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('week_start', 'Week (Monday)', default=_monday()),
        Field('task', 'Task promised'),
        Field('responsible', 'Who'),
        Field('planned_qty', 'Qty', kind='number', default='0'),
        Field('unit', 'Unit'),
        Field('status', 'Status', kind='combo',
              options=[planning.NOT_DONE, planning.DONE],
              default=planning.NOT_DONE),
        Field('reason', 'If missed, why', kind='combo', options=planning.REASONS),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'commitments', fields,
                     'Weekly commitments — promise it, then score it',
                     order_by='week_start DESC, id DESC')


class PPCView(ttk.Frame):
    COLUMNS = ('week', 'promised', 'done', 'ppc')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.site_var = tk.StringVar()
        self._site_map = {}
        self.summary_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Plan reliability (PPC)',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Percent Plan Complete is finished ÷ promised, '
                             'counted strictly: a part-finished task is a miss. '
                             'Typical sites start near 50%. The reasons below '
                             'are what you actually fix.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=4)
        ttk.Label(top, text='Site').pack(side='left')
        self.site_combo = ttk.Combobox(top, textvariable=self.site_var, width=22,
                                       state='readonly')
        self.site_combo.pack(side='left', padx=4)
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=6)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left')

        heads = {'week': 'Week from', 'promised': 'Promised', 'done': 'Done',
                 'ppc': 'PPC %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=8)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=140, anchor='w' if c == 'week' else 'e')
        self.tree.tag_configure('poor', background='#ffe3e3')
        self.tree.tag_configure('good', background='#e4f1e8')
        self.tree.pack(fill='x', padx=8, pady=4)

        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=6)
        ttk.Label(self, text='Why work was missed',
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8)
        self.reason_tree = ttk.Treeview(self, columns=('reason', 'count'),
                                        show='headings', height=7)
        self.reason_tree.heading('reason', text='Reason')
        self.reason_tree.heading('count', text='Times')
        self.reason_tree.column('reason', width=340, anchor='w')
        self.reason_tree.column('count', width=80, anchor='e')
        self.reason_tree.pack(fill='both', expand=True, padx=8, pady=4)

    def refresh(self):
        conn = self.db_getter()
        try:
            opts = site_options(conn)
            self._site_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.site_combo['values'] = [''] + ['{} - {}'.format(i, n)
                                                for i, n in opts]
            raw = self.site_var.get().strip()
            site_id = self._site_map.get(raw) if raw else None
            sql = 'SELECT * FROM commitments'
            args = []
            if site_id:
                sql += ' WHERE site_id = ?'
                args.append(site_id)
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()

        weeks = {}
        for r in rows:
            weeks.setdefault(r['week_start'] or '(no week)', []).append(r)
        trend = planning.ppc_trend(weeks)

        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        for label, score in reversed(trend['weeks']):
            items = weeks[label]
            done = sum(1 for i in items if (i['status'] or '') == planning.DONE)
            values = (label, str(len(items)), str(done),
                      '-' if score is None else '{:.0f}%'.format(score))
            self._rows.append(values)
            tag = ('good' if score is not None and score >= 80 else
                   'poor' if score is not None and score < 60 else '')
            self.tree.insert('', 'end', values=values, tags=(tag,) if tag else ())

        avg = trend['average']
        self.summary_var.set(
            'Average PPC {:.0f}%   ·   {} week(s) planned   ·   {}'.format(
                avg, len(trend['weeks']),
                'good reliability' if avg >= 80 else
                'unreliable — fix the top reason below') if avg is not None
            else 'No commitments recorded yet.')

        for item in self.reason_tree.get_children():
            self.reason_tree.delete(item)
        for reason, count in planning.reasons_for_misses(rows):
            self.reason_tree.insert('', 'end', values=(reason, count))

    def export(self):
        html = bill_export.build_statement_html(
            'Plan reliability (PPC)', [self.summary_var.get()],
            ['Week from', 'Promised', 'Done', 'PPC %'], self._rows,
            summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'ppc.html')


class CVRView(ttk.Frame):
    COLUMNS = ('head', 'cost', 'value', 'margin', 'pct')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.site_var = tk.StringVar()
        self._site_map = {}
        self.summary_var = tk.StringVar()
        self.warn_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Cost–value reconciliation',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Cost incurred against value earned, by head. '
                             'Profit at the end of a job is a post-mortem — '
                             'this is the same arithmetic early enough to do '
                             'something about it.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=4)
        ttk.Label(top, text='Site').pack(side='left')
        self.site_combo = ttk.Combobox(top, textvariable=self.site_var, width=22,
                                       state='readonly')
        self.site_combo.pack(side='left', padx=4)
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=6)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left')

        heads = {'head': 'Cost head', 'cost': 'Cost incurred',
                 'value': 'Value earned', 'margin': 'Margin', 'pct': 'Margin %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=8)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=160 if c == 'head' else 130,
                             anchor='w' if c == 'head' else 'e')
        self.tree.tag_configure('loss', background='#ffe3e3')
        self.tree.pack(fill='x', padx=8, pady=4)
        ttk.Label(self, textvariable=self.warn_var, foreground='#a4343a',
                  font=('TkDefaultFont', 11, 'bold'), wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(4, 0))
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=6)

    def refresh(self):
        conn = self.db_getter()
        try:
            opts = site_options(conn)
            self._site_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.site_combo['values'] = [''] + ['{} - {}'.format(i, n)
                                                for i, n in opts]
            raw = self.site_var.get().strip()
            sid = self._site_map.get(raw) if raw else None

            def one(sql, args=()):
                return conn.execute(sql, args).fetchone()[0] or 0

            where = ' AND site_id = ?' if sid else ''
            args = (sid,) if sid else ()
            material = one("SELECT SUM(qty * rate) FROM material_ledger "
                           "WHERE txn_type = 'OUT'" + where, args)
            labour = one("SELECT SUM(amount) FROM payments WHERE direction = "
                         "'Payment' AND party_type = 'Labour'" + where, args)
            hire = one('SELECT SUM(total_amount) FROM equipment_hire WHERE 1=1'
                       + where, args)
            subwhere = ''
            subargs = ()
            if sid:
                subwhere = ' AND wo.site_id = ?'
                subargs = (sid,)
            sub = one("SELECT SUM(sb.this_bill_value) FROM sub_bills sb "
                      "LEFT JOIN work_orders wo ON wo.id = sb.work_order_id "
                      "WHERE sb.status IN ('Approved','Paid')" + subwhere, subargs)
            # Value earned: approved client billing on this site's contracts.
            cwhere = ' AND c.site_id = ?' if sid else ''
            value = one(
                "SELECT COALESCE((SELECT SUM(b.work_done_value - b.previous_billed) "
                "FROM bills b JOIN contracts c ON c.id = b.contract_id "
                "WHERE b.status IN ('Approved','Paid')" + cwhere + '), 0) + '
                "COALESCE((SELECT SUM(r.this_bill_value) FROM ra_bills r "
                "JOIN contracts c ON c.id = r.contract_id "
                "WHERE r.status IN ('Approved','Paid')" + cwhere + '), 0)',
                args + args if sid else ())
        finally:
            conn.close()

        total_cost = material + labour + hire + sub
        # Value is earned as a whole, not per head; apportioning it by each
        # head's share of cost is the standard CVR simplification, and stating
        # that is better than implying the split is measured.
        heads = {}
        for name, cost in (('Material', material), ('Labour', labour),
                           ('Plant & hire', hire), ('Subcontract', sub)):
            share = (cost / total_cost * value) if total_cost else 0
            heads[name] = (cost, share)
        result = planning.cvr(heads)

        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        for r in result['rows']:
            values = (r['head'], '{:,.2f}'.format(r['cost']),
                      '{:,.2f}'.format(r['value']), '{:,.2f}'.format(r['margin']),
                      '-' if r['margin_pct'] is None else '{:.1f}%'.format(r['margin_pct']))
            self._rows.append(values)
            self.tree.insert('', 'end', values=values,
                             tags=('loss',) if r['margin'] < 0 else ())
        self.summary_var.set(
            'Cost {:,.2f}   ·   value {:,.2f}   ·   margin {:,.2f}{}'.format(
                result['cost'], result['value'], result['margin'],
                '  ({:.1f}%)'.format(result['margin_pct'])
                if result['margin_pct'] is not None else ''))
        self.warn_var.set(
            'Losing money on: {}. Value is apportioned across heads by their '
            'share of cost.'.format(', '.join(result['losing']))
            if result['losing'] else
            'Value is apportioned across heads by their share of cost.')

    def export(self):
        html = bill_export.build_statement_html(
            'Cost–value reconciliation',
            [self.summary_var.get(), self.warn_var.get()],
            ['Cost head', 'Cost incurred', 'Value earned', 'Margin', 'Margin %'],
            self._rows, summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'cvr.html')


def build_planning_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(build_commitments(nb, db_getter), text='Weekly Look-ahead')
    nb.add(PPCView(nb, db_getter), text='Plan Reliability (PPC)')
    nb.add(CVRView(nb, db_getter), text='Cost vs Value')
    return nb
