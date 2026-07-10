"""Equipment Hire: a CrudFrame with a best-effort hire-cost auto-calc.

``_compute_hire_total`` runs as the ``on_save`` hook. If both dates parse as
YYYY-MM-DD it computes an inclusive day count and derives ``total_amount`` from
the rate and hire type. If the dates are missing/unparseable it leaves whatever
the user typed untouched — manual override always wins. It never raises (auto
fill, not a validated rule).
"""

from datetime import datetime

from crud_frame import CrudFrame, Field
from tab_masters import vendor_options, site_options


def _compute_hire_total(conn, row_id, values):
    """Best-effort auto-fill of total_amount from date range + rate + type.

    Mirrors the pattern of _compute_duration in tab_timeline: fetch/compute,
    UPDATE the derived column, commit, and never raise.
    """
    try:
        start = values.get('hire_start', '')
        end = values.get('hire_end', '')
        d0 = datetime.strptime(start, '%Y-%m-%d')
        d1 = datetime.strptime(end, '%Y-%m-%d')
        days = (d1 - d0).days + 1  # inclusive
        if days <= 0:
            return
        rate = float(values.get('rate', 0) or 0)
        hire_type = values.get('hire_type', '')
        if hire_type == 'Daily':
            total = days * rate
        elif hire_type == 'Monthly':
            total = (days / 30.0) * rate   # simple 30-day approximation
        elif hire_type == 'Hourly':
            total = days * 8 * rate        # assume 8-hour standard day
        else:
            total = rate
        conn.execute('UPDATE equipment_hire SET total_amount = ? WHERE id = ?',
                     (total, row_id))
        conn.commit()
    except Exception:
        # Missing/unparseable dates -> leave the manually entered value alone.
        pass


def build_equipment_hire_tab(parent, db_getter):
    fields = [
        Field('equipment_name', 'Equipment'),
        Field('vendor_id', 'Vendor', kind='fk', options_func=vendor_options),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('hire_type', 'Hire Type', kind='combo',
              options=['Daily', 'Monthly', 'Hourly'], default='Daily'),
        Field('rate', 'Rate', kind='number', default='0'),
        Field('hire_start', 'Start (YYYY-MM-DD)'),
        Field('hire_end', 'End (YYYY-MM-DD)'),
        Field('total_amount', 'Total (auto)', kind='number', default='0'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'equipment_hire', fields,
                     'Equipment Hire', order_by='id DESC',
                     on_save=_compute_hire_total)
