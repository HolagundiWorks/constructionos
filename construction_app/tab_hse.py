"""Health & safety register (Phase 8, Wave 4).

Four registers and a summary, kept deliberately light — at this scale safety
paperwork that takes long gets abandoned, and an abandoned register is worse
than none because it looks like a record.

* **Permits** — the jobs that actually kill people in this trade. The list
  marks each permit **valid / expired**, because an expired permit is not a
  lesser permit, it is no permit.
* **Incidents** — including near misses, which are the same event as an injury
  with the outcome changed by luck.
* **Toolbox talks** and **Inductions** — plain registers, useful mainly as
  evidence when a client or inspector asks.

The summary leads with expired permits and lost-time injuries, and reports the
**near-miss ratio**: a site reporting no near misses is almost never a safe
site, it is a site where nobody writes them down.
"""

import tkinter as tk
import theme
from datetime import date
from tkinter import ttk

import bill_export
import hse
import report_open
from crud_frame import CrudFrame, Field
from tab_masters import site_options


def build_permits(parent, db_getter):
    fields = [
        Field('permit_no', 'Permit No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('permit_type', 'Type', kind='combo', options=hse.PERMIT_TYPES,
              default=hse.PERMIT_TYPES[0]),
        Field('location', 'Location'),
        Field('description', 'Work'),
        Field('issued_to', 'Issued to'),
        Field('issued_by', 'Issued by'),
        Field('valid_from', 'Valid from', default='TODAY'),
        Field('valid_to', 'Valid to'),
        Field('precautions', 'Precautions'),
        Field('status', 'Status', kind='combo',
              options=[hse.OPEN, hse.CLOSED, hse.CANCELLED], default=hse.OPEN),
        Field('closed_date', 'Closed on'),
    ]
    return CrudFrame(parent, db_getter, 'work_permits', fields,
                     'Permits to work — an expired permit is no permit',
                     order_by='status, valid_to DESC, id DESC')


def build_incidents(parent, db_getter):
    fields = [
        Field('incident_no', 'Incident No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('incident_date', 'Date', default='TODAY'),
        Field('incident_time', 'Time'),
        Field('person', 'Person involved'),
        Field('severity', 'Severity', kind='combo', options=hse.SEVERITIES,
              default=hse.NEAR_MISS),
        Field('description', 'What happened'),
        Field('immediate_cause', 'Immediate cause'),
        Field('root_cause', 'Root cause'),
        Field('action_taken', 'Action taken'),
        Field('lost_days', 'Days lost', kind='number', default='0'),
        Field('reported_by', 'Reported by'),
    ]
    return CrudFrame(parent, db_getter, 'incidents', fields,
                     'Incidents and near misses — write down the near miss, '
                     'it is the cheapest safety measure there is',
                     order_by='incident_date DESC, id DESC')


def build_toolbox(parent, db_getter):
    fields = [
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('talk_date', 'Date', default='TODAY'),
        Field('topic', 'Topic'),
        Field('conducted_by', 'Conducted by'),
        Field('attendance', 'Attended', kind='number', default='0'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'toolbox_talks', fields,
                     'Toolbox talks', order_by='talk_date DESC, id DESC')


def build_inductions(parent, db_getter):
    fields = [
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('person', 'Person'),
        Field('induction_date', 'Inducted on', default='TODAY'),
        Field('conducted_by', 'By'),
        Field('valid_to', 'Valid to'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'safety_inductions', fields,
                     'Site inductions', order_by='induction_date DESC, id DESC')


class SafetySummary(ttk.Frame):
    COLUMNS = ('permit', 'type', 'site', 'valid_to', 'state')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.hours_var = tk.StringVar(value='0')
        self.headline_var = tk.StringVar()
        self.stats_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Safety position',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Kept short on purpose. Safety paperwork that '
                             'takes long gets abandoned, and an abandoned '
                             'register is worse than none — it looks like a '
                             'record.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=4)
        ttk.Label(top, text='Hours worked (for LTIFR)').pack(side='left')
        ttk.Entry(top, textvariable=self.hours_var, width=12).pack(side='left', padx=4)
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=6)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left')

        ttk.Label(self, textvariable=self.headline_var, foreground='#a4343a',
                  font=('TkDefaultFont', 11, 'bold'), wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(6, 2))
        ttk.Label(self, textvariable=self.stats_var, wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(0, 6))

        ttk.Label(self, text='Open permits',
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8)
        heads = {'permit': 'Permit', 'type': 'Type', 'site': 'Site',
                 'valid_to': 'Valid to', 'state': 'State'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=10)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=230 if c == 'state' else 130, anchor='w')
        self.tree.tag_configure('bad', background=theme.wash('bad'))
        self.tree.tag_configure('soon', background=theme.wash('warn'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            hours = float(str(self.hours_var.get()).strip() or 0)
        except ValueError:
            hours = 0.0
        conn = self.db_getter()
        try:
            permits = conn.execute(
                'SELECT p.*, s.name AS site FROM work_permits p '
                'LEFT JOIN sites s ON s.id = p.site_id').fetchall()
            incidents = conn.execute('SELECT * FROM incidents').fetchall()
        finally:
            conn.close()

        s = hse.summarise(incidents, permits, hours)
        expiring = dict((id(p), d) for p, d in hse.expiring_permits(permits, 2))

        self._rows = []
        for p in permits:
            if str(p['status'] or hse.OPEN) != hse.OPEN:
                continue
            valid, reason = hse.permit_valid(p)
            values = (p['permit_no'] or 'Permit {}'.format(p['id']),
                      p['permit_type'] or '-', p['site'] or '-',
                      p['valid_to'] or '-', reason)
            self._rows.append(values)
            tag = '' if valid else 'bad'
            if valid and id(p) in expiring:
                tag = 'soon'
            self.tree.insert('', 'end', values=values, tags=(tag,) if tag else ())

        alerts = []
        if s['expired_permits']:
            alerts.append('{} open permit(s) are outside their dates — that is '
                          'work proceeding with no valid permit'.format(
                              s['expired_permits']))
        if s['lost_time']:
            alerts.append('{} lost-time injury/injuries ({} days lost)'.format(
                s['lost_time'], s['lost_days']))
        self.headline_var.set('.  '.join(alerts) + '.' if alerts else
                              'No expired permits and no lost-time injuries.')

        parts = ['{} incident(s) recorded'.format(s['total'])]
        if s['near_miss_ratio'] is not None:
            parts.append('{:.0f}% of them near misses'.format(s['near_miss_ratio']))
        parts.append('{} valid permit(s) open'.format(s['open_permits']))
        parts.append('LTIFR {}'.format(
            '{:.2f}'.format(s['ltifr']) if s['ltifr'] is not None
            else 'n/a (needs 10,000+ hours to mean anything)'))
        self.stats_var.set('   ·   '.join(parts))

    def export(self):
        html = bill_export.build_statement_html(
            'Safety position', [self.headline_var.get(), self.stats_var.get()],
            ['Permit', 'Type', 'Site', 'Valid to', 'State'], self._rows,
            summary=self.stats_var.get())
        report_open.save_and_open_html(html, 'safety_position.html')


def build_hse_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(SafetySummary(nb, db_getter), text='Position')
    nb.add(build_permits(nb, db_getter), text='Permits')
    nb.add(build_incidents(nb, db_getter), text='Incidents')
    nb.add(build_toolbox(nb, db_getter), text='Toolbox Talks')
    nb.add(build_inductions(nb, db_getter), text='Inductions')
    return nb
