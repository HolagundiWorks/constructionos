"""Plant: service schedule, fuel analysis, and service history.

The daily log stays where the site team already works — Site Reports > Plant
Log. This tab is what the log is *for*: which machines are due for service,
and which days burned more diesel than that machine normally does.

The fuel view names days and machines, never conclusions. Unusual consumption
has innocent explanations — a machine idling on standby, a tank filled the
evening before — and arithmetic alone is not grounds to accuse anyone. It is
grounds to ask.
"""

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk, messagebox

from ui_guard import can_write

import bill_export
import plant
import report_open
from crud_frame import CrudFrame, Field, TODAY
from tab_masters import equipment_options, vendor_options


def _company_name(conn):
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
    return (row['value'] if row and row['value'] else '') or 'Construction OS'


def plant_logs(conn, since=None):
    """Daily logs, newest last, with the machine name resolved where linked."""
    sql = ("SELECT p.id, p.log_date, p.site_id, p.equipment_id, "
           "COALESCE(e.name, p.equipment) AS equipment, p.hours_run, "
           "p.diesel_ltr, p.downtime_hrs, p.operator, p.remarks "
           "FROM plant_logs p LEFT JOIN equipment e ON e.id = p.equipment_id")
    args = []
    if since:
        sql += ' WHERE p.log_date >= ?'
        args.append(since)
    return [dict(r) for r in conn.execute(sql + ' ORDER BY p.log_date, p.id',
                                          args)]


def fleet_status(conn, as_on=None):
    """Service status for every machine in the master."""
    machines = [dict(r) for r in conn.execute('SELECT * FROM equipment '
                                              'ORDER BY name')]
    logs = plant_logs(conn)
    by_machine = plant.group_by_machine(logs)
    out = []
    for m in machines:
        rows = by_machine.get(('id', m['id']), [])
        if not rows:
            # fall back to name matching for logs written before the link
            rows = by_machine.get(('name', str(m['name'] or '').strip().lower()), [])
        status = plant.service_status(m, rows, as_on=as_on)
        status.update(plant.summarise_machine(rows))
        out.append(status)
    return out


def open_plant_alerts(conn, as_on=None, days=90):
    """Fleet counts for the KPI dashboard."""
    logs = plant_logs(conn, since=(
        (date.today() - timedelta(days=days)).isoformat()))
    return plant.fleet_summary(fleet_status(conn, as_on),
                              plant.fuel_outliers(logs), logs)


class FleetView(ttk.Frame):
    COLUMNS = ('name', 'status', 'hours_since', 'hours_left', 'days_left',
               'last_service_date', 'litres_per_hour', 'availability')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.headline_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(top, text='Print / Export',
                   command=self.export).pack(side='left', padx=6)
        ttk.Label(self, textvariable=self.headline_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10)

        headings = {'name': 'Machine', 'status': 'Service',
                    'hours_since': 'Hrs Since Service', 'hours_left': 'Hrs Left',
                    'days_left': 'Days Left', 'last_service_date': 'Last Serviced',
                    'litres_per_hour': 'L / hr', 'availability': 'Availability %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=160 if col == 'name' else 110, anchor='w')
        self.tree.tag_configure('overdue', background='#ffe3e3')
        self.tree.tag_configure('due', background='#fff4e5')
        self.tree.tag_configure('none', background='#f4f4f4')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Label(self, text=(
            'Service falls due on hours run or elapsed days, whichever comes '
            'first — a machine idle through the monsoon still needs its oil '
            'changed. Set both intervals on the machine in Masters > '
            'Equipment; a machine with no interval reads "not scheduled" '
            'rather than OK, because the app cannot know it is fine.'),
            foreground='#666', wraplength=900, justify='left') \
            .pack(anchor='w', padx=10, pady=(0, 8))

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            self._rows = fleet_status(conn)
        finally:
            conn.close()
        for r in self._rows:
            tag = ('overdue' if r['status'] == plant.OVERDUE else
                   'due' if r['status'] == plant.DUE else
                   'none' if r['status'] == plant.UNKNOWN else '')
            self.tree.insert('', 'end', tags=(tag,), values=(
                r['name'], r['status'], '{:g}'.format(r['hours_since_service']),
                '{:g}'.format(r['hours_left']) if r['hours_left'] is not None else '—',
                r['days_left'] if r['days_left'] is not None else '—',
                r['last_service_date'] or '—',
                '{:.2f}'.format(r['litres_per_hour'])
                if r['litres_per_hour'] is not None else '—',
                '{:.1f}'.format(r['availability'])
                if r['availability'] is not None else '—'))
        s = plant.fleet_summary(self._rows)
        if not self._rows:
            self.headline_var.set('No machines in the equipment master yet.')
        elif s['overdue'] or s['due']:
            self.headline_var.set(
                '{} machine(s) OVERDUE for service, {} due soon.   {} of {} '
                'have no schedule set.'.format(
                    s['overdue'], s['due'], s['unscheduled'], s['machines']))
        else:
            self.headline_var.set(
                'No service overdue across {} machine(s).{}'.format(
                    s['machines'],
                    '   {} have no schedule set.'.format(s['unscheduled'])
                    if s['unscheduled'] else ''))

    def export(self):
        if not self._rows:
            messagebox.showinfo('Nothing to export', 'No machines recorded.')
            return
        rows = [(r['name'], r['status'], '{:g}'.format(r['hours_since_service']),
                 '{:g}'.format(r['hours_left']) if r['hours_left'] is not None else '-',
                 r['days_left'] if r['days_left'] is not None else '-',
                 r['last_service_date'] or '-',
                 '{:.2f}'.format(r['litres_per_hour'])
                 if r['litres_per_hour'] is not None else '-')
                for r in self._rows]
        html = bill_export.build_statement_html(
            'Plant service status', [self.headline_var.get()],
            ['Machine', 'Service', 'Hrs Since', 'Hrs Left', 'Days Left',
             'Last Serviced', 'L / hr'],
            rows, summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'plant_service_status.html')


class FuelView(ttk.Frame):
    COLUMNS = ('log_date', 'equipment', 'operator', 'hours_run', 'diesel_ltr',
               'litres_per_hour', 'baseline', 'excess_pct')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.days_var = tk.StringVar(value='90')
        self.tol_var = tk.StringVar(value='{:g}'.format(
            plant.DEFAULT_TOLERANCE_PCT))
        self.headline_var = tk.StringVar()
        self.nowork_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Last').pack(side='left')
        ttk.Entry(top, textvariable=self.days_var, width=5).pack(side='left', padx=3)
        ttk.Label(top, text='days   Flag above baseline by').pack(side='left')
        ttk.Entry(top, textvariable=self.tol_var, width=5).pack(side='left', padx=3)
        ttk.Label(top, text='%').pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=8)
        ttk.Button(top, text='Print / Export',
                   command=self.export).pack(side='left')

        ttk.Label(self, textvariable=self.headline_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10)
        ttk.Label(self, textvariable=self.nowork_var,
                  foreground='#8a5a00').pack(anchor='w', padx=10)

        headings = {'log_date': 'Date', 'equipment': 'Machine',
                    'operator': 'Operator', 'hours_run': 'Hours',
                    'diesel_ltr': 'Diesel (L)', 'litres_per_hour': 'L / hr',
                    'baseline': 'Its Usual L / hr', 'excess_pct': 'Above Usual'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=140 if col == 'equipment' else 105,
                             anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Label(self, text=(
            'Each machine is judged against its own usual burn rate, not a '
            'fleet average or a spec sheet, and only once it has {} logged '
            'days to have a norm. A high day is a question, not a finding — '
            'a machine can idle on standby and a tank can be filled the '
            'evening before.'.format(plant.MIN_SAMPLE)),
            foreground='#666', wraplength=900, justify='left') \
            .pack(anchor='w', padx=10, pady=(0, 8))

    def _int(self, var, default):
        try:
            return int(float(var.get().strip()))
        except ValueError:
            return default

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        days = self._int(self.days_var, 90)
        try:
            tol = float(self.tol_var.get().strip())
        except ValueError:
            tol = plant.DEFAULT_TOLERANCE_PCT
        since = (date.today() - timedelta(days=days)).isoformat()
        conn = self.db_getter()
        try:
            logs = plant_logs(conn, since=since)
        finally:
            conn.close()

        self._rows = plant.fuel_outliers(logs, tolerance_pct=tol)
        for r in self._rows:
            self.tree.insert('', 'end', values=(
                r['log_date'], r['equipment'], r['operator'] or '—',
                '{:g}'.format(r['hours_run']), '{:g}'.format(r['diesel_ltr']),
                '{:.2f}'.format(r['litres_per_hour']),
                '{:.2f}'.format(r['baseline']),
                '+{:.0f}%'.format(r['excess_pct'])))

        if not logs:
            self.headline_var.set('No plant logs in the last {} days.'.format(days))
        elif self._rows:
            self.headline_var.set(
                '{} day(s) above the usual burn rate, {:,.0f} litres more than '
                'those machines normally use for that work.'.format(
                    len(self._rows), plant.excess_litres(self._rows)))
        else:
            self.headline_var.set(
                'Nothing unusual across {} log(s) in the last {} days.'.format(
                    len(logs), days))

        nowork = plant.fuel_without_work(logs)
        self.nowork_var.set(
            '{} day(s) issued diesel against a machine that logged no hours — '
            'worth checking those first.'.format(len(nowork))
            if nowork else '')

    def export(self):
        if not self._rows:
            messagebox.showinfo('Nothing to export',
                                'No unusual consumption to report.')
            return
        rows = [(r['log_date'], r['equipment'], r['operator'] or '-',
                 '{:g}'.format(r['hours_run']), '{:g}'.format(r['diesel_ltr']),
                 '{:.2f}'.format(r['litres_per_hour']),
                 '{:.2f}'.format(r['baseline']),
                 '+{:.0f}%'.format(r['excess_pct'])) for r in self._rows]
        html = bill_export.build_statement_html(
            'Fuel consumption — days above the usual rate',
            [self.headline_var.get(), self.nowork_var.get() or '',
             'Each machine is compared with its own median burn rate. These '
             'are questions to ask, not findings.'],
            ['Date', 'Machine', 'Operator', 'Hours', 'Diesel (L)', 'L / hr',
             'Its Usual L / hr', 'Above Usual'],
            rows, summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'fuel_analysis.html')


def _build_services(parent, db_getter):
    """Service history. Recording one here does not move the machine's
    last-serviced date — that stays a deliberate edit on the master, so a
    quote or an inspection logged as a 'service' cannot silently reset the
    schedule."""
    fields = [
        Field('service_date', 'Date', default=TODAY),
        Field('equipment_id', 'Machine', kind='fk',
              options_func=equipment_options, remember=True),
        Field('service_type', 'Type', kind='combo',
              options=['Routine', 'Repair', 'Breakdown'], default='Routine'),
        Field('hours_at_service', 'Hour Meter', kind='number', default='0'),
        Field('cost', 'Cost', kind='number', default='0'),
        Field('vendor_id', 'Vendor / Garage', kind='fk',
              options_func=vendor_options),
        Field('notes', 'Notes', width=200),
    ]
    return CrudFrame(parent, db_getter, 'plant_services', fields,
                     'Service History', order_by='service_date DESC, id DESC')


def build_plant_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(FleetView(nb, db_getter), text='Fleet & Service')
    nb.add(FuelView(nb, db_getter), text='Fuel')
    nb.add(_build_services(nb, db_getter), text='Service History')
    return nb
