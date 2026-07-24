"""Writable master-data specs for the browser app — **tkinter-free**, so the
headless web server can build forms without importing the desktop tabs (which
pull in Tk).

These mirror the desktop CRUD (``tab_masters.py`` / ``tab_vendor.py``)
field-for-field, so the browser and the desktop offer the same fields, labels,
combos and defaults. To stop the two drifting silently, ``tests/test_web.py``
checks that every field here is a real column of its table.

A field is a plain dict:

    key       column name
    label     form label
    kind      'text' | 'number' | 'dim' | 'combo' | 'fk' | 'textarea'
              ('dim' = a measurement dimension: blank stays NULL, not 0)
    options   for 'combo': the allowed values
    fk_sql    for 'fk': a query returning (id, label) rows for the dropdown
    default   starting value for a new record
    required  reject a blank on submit

A table may also carry a **deriver** (see ``_DERIVERS``) that fills computed
columns on save — e.g. a measurement's ``quantity = Nos×L×B×D`` — so the browser
and the desktop store the same derived figures.
"""


from datetime import date

import civil       # pure — measurement quantity (Nos x L x B x D)
import compliance  # pure — the statutory obligation list


def _is_date_key(key):
    """A field whose value is an ISO calendar date, so clients can offer a real
    date picker instead of free text."""
    return key == 'date' or key.endswith('_date')


def _f(key, label, kind='text', options=None, fk_sql=None, default='',
       required=False):
    if kind == 'text' and _is_date_key(key):
        kind = 'date'
    return {'key': key, 'label': label, 'kind': kind, 'options': options or [],
            'fk_sql': fk_sql, 'default': default, 'required': required}


_SITES = 'SELECT id, name FROM sites ORDER BY name'
_CLIENTS = 'SELECT id, name FROM clients ORDER BY name'
_PROJECTS = 'SELECT id, name FROM projects ORDER BY name'
_CONTRACTS = 'SELECT id, contract_no FROM contracts ORDER BY id DESC'
_BOQ_ITEMS = ("SELECT id, COALESCE(item_no, '') || ' — ' || "
              "COALESCE(substr(description, 1, 50), '') FROM boq_items "
              "ORDER BY id DESC")
_OBLIGATIONS = [o['name'] for o in compliance.OBLIGATIONS]
_OBLIGATION_KEY = {o['name']: o['key'] for o in compliance.OBLIGATIONS}

# table -> {label, fields}. Order and wording follow the desktop tabs.
MASTERS = {
    'sites': {'label': 'Site', 'fields': [
        _f('name', 'Name', required=True),
        _f('location', 'Location'),
        _f('site_type', 'Type', 'combo', options=['Site', 'Warehouse'],
           default='Site'),
        _f('status', 'Status', 'combo', options=['Active', 'Closed'],
           default='Active'),
    ]},
    'clients': {'label': 'Client', 'fields': [
        _f('name', 'Name', required=True),
        _f('contact_person', 'Contact'),
        _f('phone', 'Phone'),
        _f('email', 'Email'),
        _f('address', 'Address', 'textarea'),
    ]},
    'vendors': {'label': 'Vendor', 'fields': [
        _f('name', 'Name', required=True),
        _f('contact_person', 'Contact'),
        _f('phone', 'Phone'),
        _f('email', 'Email'),
        _f('gst_no', 'GST No'),
        _f('address', 'Address', 'textarea'),
    ]},
    'materials': {'label': 'Material', 'fields': [
        _f('name', 'Name', required=True),
        _f('unit', 'Unit'),
        _f('category', 'Category'),
        _f('hsn_code', 'HSN Code'),
        _f('rate', 'Std Rate', 'number', default='0'),
    ]},
    'labor': {'label': 'Labour', 'fields': [
        _f('name', 'Name', required=True),
        _f('father_name', "Father's Name"),
        _f('site_id', 'Site', 'fk', fk_sql=_SITES),
        _f('skill', 'Skill'),
        _f('daily_wage', 'Daily Wage', 'number', default='0'),
        _f('phone', 'Phone'),
        _f('status', 'Status', 'combo', options=['Active', 'Inactive'],
           default='Active'),
        _f('pf_no', 'PF No (optional)'),
        _f('esi_no', 'ESI No (optional)'),
    ]},
    'equipment': {'label': 'Equipment', 'fields': [
        _f('name', 'Name', required=True),
        _f('category', 'Category'),
        _f('current_site_id', 'Current Site', 'fk', fk_sql=_SITES),
        _f('status', 'Status', 'combo',
           options=['Available', 'In Use', 'Maintenance'], default='Available'),
        _f('make_model', 'Make / Model'),
        _f('service_interval_hours', 'Service every (hours)', 'number',
           default='0'),
        _f('service_interval_days', 'Service every (days)', 'number',
           default='0'),
        _f('last_service_date', 'Last Serviced On'),
    ]},
    'projects': {'label': 'Project', 'fields': [
        _f('name', 'Project name', required=True),
        _f('client_id', 'Client', 'fk', fk_sql=_CLIENTS),
        _f('site_id', 'Site', 'fk', fk_sql=_SITES),
        _f('start_date', 'Start date'),
        _f('end_date', 'End date'),
        _f('budget', 'Budget', 'number', default='0'),
        _f('status', 'Status', 'combo',
           options=['Active', 'On Hold', 'Completed', 'Cancelled'],
           default='Active'),
        _f('contract_value', 'Contract value (for LDs)', 'number', default='0'),
        _f('ld_pct_per_week', 'LD % per week', 'number', default='0.5'),
        _f('ld_cap_pct', 'LD cap %', 'number', default='10'),
        _f('eot_granted_days', 'Extension granted (days)', 'number',
           default='0'),
        _f('notes', 'Notes', 'textarea'),
    ]},
    'milestones': {'label': 'Milestone', 'fields': [
        _f('project_id', 'Project', 'fk', fk_sql=_PROJECTS),
        _f('name', 'Milestone', required=True),
        _f('target_date', 'Target date'),
        _f('actual_date', 'Actual date'),
        _f('amount', 'Amount', 'number', default='0'),
        _f('status', 'Status', 'combo', options=['Pending', 'Done'],
           default='Pending'),
        _f('notes', 'Notes', 'textarea'),
    ]},
    'rate_book': {'label': 'Rate Item', 'fields': [
        _f('code', 'Code'),
        _f('category', 'Category'),
        _f('description', 'Description', 'textarea', required=True),
        _f('unit', 'Unit'),
        _f('rate', 'Rate', 'number', default='0'),
        _f('specification', 'Specification', 'textarea'),
    ]},
    'contracts': {'label': 'Contract', 'fields': [
        _f('contract_no', 'Contract no', required=True),
        _f('client_id', 'Client', 'fk', fk_sql=_CLIENTS),
        _f('site_id', 'Site', 'fk', fk_sql=_SITES),
        _f('contract_value', 'Contract value', 'number', default='0'),
        _f('retention_pct', 'Retention %', 'number', default='5'),
        _f('start_date', 'Start date'),
        _f('end_date', 'End date'),
        _f('status', 'Status', 'combo',
           options=['Active', 'Completed', 'Cancelled'], default='Active'),
    ]},
    'thekedars': {'label': 'Thekedar', 'fields': [
        _f('name', 'Name', required=True),
        _f('phone', 'Phone'),
        _f('site_id', 'Site', 'fk', fk_sql=_SITES),
        _f('skill_type', 'Skill / trade'),
        _f('status', 'Status', 'combo', options=['Active', 'Inactive'],
           default='Active'),
    ]},
    'snags': {'label': 'Snag', 'fields': [
        _f('site_id', 'Site', 'fk', fk_sql=_SITES),
        _f('contract_id', 'Contract', 'fk', fk_sql=_CONTRACTS),
        _f('snag_no', 'Snag no'),
        _f('raised_date', 'Raised', default='@today'),
        _f('location', 'Location / element'),
        _f('description', 'Defect', 'textarea', required=True),
        _f('trade', 'Trade'),
        _f('severity', 'Severity', 'combo',
           options=['Minor', 'Major', 'Blocker'], default='Minor'),
        _f('assigned_to', 'Assigned to'),
        _f('target_date', 'Fix by'),
        _f('status', 'Status', 'combo',
           options=['Open', 'Fixed', 'Verified'], default='Open'),
        _f('fixed_date', 'Fixed on'),
        _f('verified_date', 'Verified on'),
        _f('verified_by', 'Verified by'),
        _f('remarks', 'Remarks', 'textarea'),
    ]},
    'ncrs': {'label': 'NCR', 'fields': [
        _f('ncr_no', 'NCR no'),
        _f('site_id', 'Site', 'fk', fk_sql=_SITES),
        _f('raised_date', 'Raised', default='@today'),
        _f('raised_by', 'Raised by'),
        _f('description', 'Non-conformance', 'textarea', required=True),
        _f('severity', 'Severity', 'combo',
           options=['Minor', 'Major', 'Critical'], default='Minor'),
        _f('root_cause', 'Root cause', 'textarea'),
        _f('corrective_action', 'Corrective action', 'textarea'),
        _f('preventive_action', 'Preventive action', 'textarea'),
        _f('status', 'Status', 'combo', options=['Open', 'Closed'],
           default='Open'),
        _f('closed_date', 'Closed on'),
        _f('closed_by', 'Closed by'),
    ]},
    # Per-item measurement-book entry (closes the last browser/desktop gap).
    # quantity is derived (Nos×L×B×D) on save — see _derive_measurement — so a
    # blank dimension stays "not applicable" (factor 1), never a zeroing 0.
    'measurements': {'label': 'Measurement', 'fields': [
        _f('contract_id', 'Contract', 'fk', fk_sql=_CONTRACTS, required=True),
        _f('boq_item_id', 'BOQ item', 'fk', fk_sql=_BOQ_ITEMS),
        _f('mb_date', 'Date', default='@today'),
        _f('mb_ref', 'MB page / ref'),
        _f('description', 'Location / particulars', 'textarea'),
        _f('nos', 'Nos', 'dim'),
        _f('length', 'Length', 'dim'),
        _f('breadth', 'Breadth', 'dim'),
        _f('depth', 'Depth / height', 'dim'),
        _f('remarks', 'Remarks', 'textarea'),
    ]},
    # Statutory compliance filings (GST/TDS/PF/ESI/cess/IT). obligation is
    # picked by friendly name and stored as the OBLIGATIONS key — see
    # _derive_compliance — so it lines up with the desktop calendar.
    'compliance_filings': {'label': 'Compliance filing', 'fields': [
        _f('obligation', 'Obligation', 'combo', options=_OBLIGATIONS,
           required=True),
        _f('period', 'Period (e.g. 2026-04)', required=True),
        _f('due_date', 'Due date'),
        _f('filed_date', 'Filed on'),
        _f('ref_no', 'ARN / challan / ack no'),
        _f('amount', 'Amount', 'number'),
        _f('notes', 'Notes', 'textarea'),
    ]},
}


def _derive_measurement(values):
    """quantity = Nos × L × B × D (blanks → factor 1, via civil.dim_factor)."""
    values['quantity'] = civil.measurement_quantity(
        values.get('nos'), values.get('length'),
        values.get('breadth'), values.get('depth'))
    return values


def _derive_compliance(values):
    """Store the obligation as its stable key, not the display name."""
    name = values.get('obligation')
    if name in _OBLIGATION_KEY:
        values['obligation'] = _OBLIGATION_KEY[name]
    return values


_DERIVERS = {
    'measurements': _derive_measurement,
    'compliance_filings': _derive_compliance,
}


def derive(table, values):
    """Fill/normalise computed columns before an insert or update. A no-op for
    tables without a deriver, so callers can apply it unconditionally."""
    fn = _DERIVERS.get(table)
    return fn(dict(values)) if fn else values


def resolve_default(default):
    """A form-field's starting value, resolving the ``@today`` sentinel to the
    current date (parallels ``web_docs.resolve_default``)."""
    return date.today().isoformat() if default == '@today' else default


def is_master(table):
    return table in MASTERS


def fields(table):
    return MASTERS[table]['fields']


def label(table):
    return MASTERS[table]['label']


def fk_options(conn, sql):
    """[(id, label), ...] for an fk dropdown."""
    return [(r[0], r[1]) for r in conn.execute(sql)]


def enrich_fields(conn, fields):
    """Copy field specs and resolve ``fk_sql`` into JSON-friendly ``options``.

    WinUI / JSON clients need ``[{id, label}, …]`` — they must not run SQL.
    The HTML layer still uses ``fk_sql`` via ``fk_options``; both stay present.
    Missing tables or bad SQL yield an empty options list (soft-fail).
    """
    out = []
    for field in fields or []:
        f = dict(field)
        if f.get('kind') == 'fk' and f.get('fk_sql'):
            try:
                pairs = fk_options(conn, f['fk_sql'])
            except Exception:  # noqa: BLE001 — soft-fail for older DBs
                pairs = []
            f['options'] = [{'id': i, 'label': lab} for i, lab in pairs]
        out.append(f)
    return out


def coerce(field, raw):
    """Validate + convert one submitted value.

    Returns ``(ok, value, error)`` — mirroring the desktop CrudFrame's
    ``_collect_values`` (number -> float, fk -> id or None, combo -> a value
    from the list), so the browser and the desktop accept exactly the same
    input."""
    raw = (raw or '').strip()
    kind = field['kind']
    if field.get('required') and raw == '':
        return False, None, '{} is required.'.format(field['label'])
    if kind == 'number':
        if raw == '':
            return True, 0.0, None
        try:
            return True, float(raw), None
        except ValueError:
            return False, None, '{} must be a number.'.format(field['label'])
    if kind == 'dim':
        # A measurement-book dimension: blank means "not applicable" and
        # contributes a factor of 1 (civil.dim_factor), so it must stay NULL —
        # not become 0, which would zero the whole quantity.
        if raw == '':
            return True, None, None
        try:
            return True, float(raw), None
        except ValueError:
            return False, None, '{} must be a number.'.format(field['label'])
    if kind == 'fk':
        if raw == '':
            return True, None, None
        try:
            return True, int(raw), None
        except ValueError:
            return False, None, 'Invalid selection for {}.'.format(field['label'])
    if kind == 'combo':
        if raw != '' and raw not in field['options']:
            return False, None, 'Invalid value for {}.'.format(field['label'])
        return True, raw, None
    return True, raw, None
