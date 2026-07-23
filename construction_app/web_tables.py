"""Curated labels + columns for read-only register tables (CT-6).

``webapi._list_ops_table`` returns raw ``SELECT *`` today; WinUI renders that as
cryptic keys and FK ids. This module is the single place that names each table
and picks an ordered, human column list, and resolves common ``*_id`` FKs to
display names on each row.

No tkinter. Soft-fail: an unknown table yields ``label=table`` and columns
inferred from the first row (or empty) — never raises into the transport.
"""

# FK column → (lookup table, label column, output key on the row)
_FK = {
    'site_id': ('sites', 'name', 'site'),
    'labor_id': ('labor', 'name', 'labor'),
    'vendor_id': ('vendors', 'name', 'vendor'),
    'client_id': ('clients', 'name', 'client'),
    'project_id': ('projects', 'name', 'project'),
    'contract_id': ('contracts', 'contract_no', 'contract'),
    'material_id': ('materials', 'name', 'material'),
    'equipment_id': ('equipment', 'name', 'equipment'),
    'warehouse_id': ('warehouses', 'name', 'warehouse'),
}


def _c(key, label, align='left'):
    return {'key': key, 'label': label, 'align': align}


# Per-table curated specs. Keys prefer resolved FK names over raw ids.
SPECS = {
    'attendance': {
        'label': 'Attendance',
        'columns': [
            _c('att_date', 'Date'), _c('labor', 'Labour'),
            _c('status', 'Status'), _c('hours', 'Hours', 'right'),
            _c('remarks', 'Remarks'),
        ],
    },
    'payroll': {
        'label': 'Payroll',
        'columns': [
            _c('labor', 'Labour'), _c('month', 'Month', 'right'),
            _c('year', 'Year', 'right'), _c('days_present', 'Days', 'right'),
            _c('gross_amount', 'Gross', 'right'),
            _c('deduction', 'Deduction', 'right'),
            _c('net_amount', 'Net', 'right'), _c('status', 'Status'),
        ],
    },
    'equipment_hire': {
        'label': 'Equipment hire',
        'columns': [
            _c('equipment_name', 'Equipment'), _c('vendor', 'Vendor'),
            _c('site', 'Site'), _c('hire_type', 'Type'),
            _c('rate', 'Rate', 'right'), _c('hire_start', 'Start'),
            _c('hire_end', 'End'), _c('total_amount', 'Total', 'right'),
        ],
    },
    'plant_logs': {
        'label': 'Plant log',
        'columns': [
            _c('log_date', 'Date'), _c('equipment', 'Equipment'),
            _c('site', 'Site'), _c('hours_run', 'Hours', 'right'),
            _c('diesel_ltr', 'Diesel (L)', 'right'),
            _c('operator', 'Operator'), _c('remarks', 'Remarks'),
        ],
    },
    'consumption_norms': {
        'label': 'Consumption norms',
        'columns': [
            _c('activity', 'Activity'), _c('unit', 'Unit'),
            _c('material', 'Material'),
            _c('qty_per_unit', 'Qty / unit', 'right'),
            _c('remarks', 'Remarks'),
        ],
    },
    'daily_progress': {
        'label': 'Daily progress',
        'columns': [
            _c('report_date', 'Date'), _c('site', 'Site'),
            _c('weather', 'Weather'),
            _c('labour_count', 'Labour', 'right'),
            _c('plant_count', 'Plant', 'right'),
            _c('work_summary', 'Work summary'),
        ],
    },
    'ncrs': {
        'label': 'NCRs',
        'columns': [
            _c('ncr_no', 'NCR no'), _c('raised_date', 'Raised'),
            _c('site', 'Site'), _c('severity', 'Severity'),
            _c('description', 'Description'), _c('status', 'Status'),
            _c('closed_date', 'Closed'),
        ],
    },
    'incidents': {
        'label': 'Incidents',
        'columns': [
            _c('incident_no', 'No'), _c('incident_date', 'Date'),
            _c('site', 'Site'), _c('person', 'Person'),
            _c('severity', 'Severity'), _c('description', 'Description'),
            _c('lost_days', 'Lost days', 'right'),
        ],
    },
    'snags': {
        'label': 'Snags',
        'columns': [
            _c('snag_no', 'Snag no'), _c('raised_date', 'Raised'),
            _c('site', 'Site'), _c('contract', 'Contract'),
            _c('location', 'Location'), _c('description', 'Description'),
            _c('severity', 'Severity'), _c('status', 'Status'),
        ],
    },
    'rate_analysis': {
        'label': 'Rate analysis',
        'columns': [
            _c('code', 'Code'), _c('description', 'Description'),
            _c('unit', 'Unit'), _c('rate_per_unit', 'Rate / unit', 'right'),
            _c('notes', 'Notes'),
        ],
    },
    'takeoffs': {
        'label': 'Takeoffs',
        'columns': [
            _c('name', 'Name'), _c('project', 'Project'),
            _c('site', 'Site'), _c('source', 'Source'),
            _c('page', 'Page', 'right'), _c('unit', 'Unit'),
            _c('created_at', 'Created'),
        ],
    },
    'bid_assessments': {
        'label': 'Bid assessments',
        'columns': [
            _c('tender_ref', 'Tender'), _c('title', 'Title'),
            _c('client', 'Client'), _c('tender_value', 'Value', 'right'),
            _c('score', 'Score', 'right'), _c('verdict', 'Verdict'),
            _c('decision', 'Decision'), _c('outcome', 'Outcome'),
        ],
    },
    'quotations': {
        'label': 'Quotations',
        'columns': [
            _c('id', 'Id', 'right'), _c('client', 'Client'),
            _c('quote_date', 'Date'), _c('valid_until', 'Valid until'),
            _c('status', 'Status'),
            _c('total_amount', 'Total', 'right'),
        ],
    },
    'estimates': {
        'label': 'Estimates',
        'columns': [
            _c('est_number', 'Number'), _c('title', 'Title'),
            _c('site', 'Site'), _c('estimate_date', 'Date'),
            _c('status', 'Status'),
            _c('total_estimate', 'Total', 'right'),
        ],
    },
    'variations': {
        'label': 'Variations',
        'columns': [
            _c('var_no', 'Var no'), _c('var_date', 'Date'),
            _c('contract', 'Contract'), _c('description', 'Description'),
            _c('qty', 'Qty', 'right'), _c('rate', 'Rate', 'right'),
            _c('amount', 'Amount', 'right'), _c('status', 'Status'),
        ],
    },
    'material_requisitions': {
        'label': 'Material requisitions',
        'columns': [
            _c('req_no', 'Req no'), _c('req_date', 'Date'),
            _c('site', 'Site'), _c('status', 'Status'),
            _c('remarks', 'Remarks'),
        ],
    },
    'approvals': {
        'label': 'Approvals',
        'columns': [
            _c('doc_type', 'Document'), _c('doc_id', 'Doc id', 'right'),
            _c('action', 'Action'), _c('approved_by', 'By'),
            _c('approved_at', 'When'), _c('note', 'Note'),
        ],
    },
    'retention_releases': {
        'label': 'Retention releases',
        'columns': [
            _c('doc_type', 'Document'), _c('doc_id', 'Doc id', 'right'),
            _c('release_date', 'Date'), _c('amount', 'Amount', 'right'),
            _c('reference', 'Reference'), _c('remarks', 'Remarks'),
        ],
    },
    'journal_entries': {
        'label': 'Journal entries',
        'columns': [
            _c('entry_date', 'Date'), _c('narration', 'Narration'),
            _c('reference', 'Reference'),
            _c('total_debit', 'Debit', 'right'),
            _c('total_credit', 'Credit', 'right'),
            _c('source', 'Source'), _c('source_id', 'Source id', 'right'),
        ],
    },
    'timeline_tasks': {
        'label': 'Programme tasks',
        'columns': [
            _c('task_name', 'Task'), _c('project', 'Project'),
            _c('site', 'Site'), _c('start_date', 'Start'),
            _c('end_date', 'End'),
            _c('duration_days', 'Days', 'right'),
            _c('status', 'Status'),
        ],
    },
    'material_ledger': {
        'label': 'Material ledger',
        'columns': [
            _c('txn_date', 'Date'), _c('site', 'Site'),
            _c('material', 'Material'), _c('txn_type', 'Type'),
            _c('qty', 'Qty', 'right'), _c('rate', 'Rate', 'right'),
            _c('vendor', 'Vendor'), _c('remarks', 'Remarks'),
        ],
    },
    'purchase_orders': {
        'label': 'Purchase orders',
        'columns': [
            _c('po_no', 'PO no'), _c('po_date', 'Date'),
            _c('vendor', 'Vendor'), _c('site', 'Site'),
            _c('status', 'Status'),
            _c('total_amount', 'Total', 'right'),
        ],
    },
    'goods_receipts': {
        'label': 'Goods receipts',
        'columns': [
            _c('grn_no', 'GRN no'), _c('grn_date', 'Date'),
            _c('vendor', 'Vendor'), _c('site', 'Site'),
            _c('purchase_order_id', 'PO id', 'right'),
            _c('status', 'Status'), _c('remarks', 'Remarks'),
        ],
    },
}


def spec(table):
    """Return ``{label, columns}`` for ``table``, or a soft fallback."""
    s = SPECS.get(table)
    if s:
        return {'label': s['label'], 'columns': list(s['columns'])}
    return {'label': table.replace('_', ' ').title(), 'columns': None}


def _load_map(conn, table, label_col, ids):
    if not ids:
        return {}
    clean = []
    for i in ids:
        try:
            clean.append(int(i))
        except (TypeError, ValueError):
            continue
    if not clean:
        return {}
    # Trusted table/column names from _FK only.
    placeholders = ','.join('?' * len(clean))
    try:
        rows = conn.execute(
            'SELECT id, {} AS label FROM {} WHERE id IN ({})'.format(
                label_col, table, placeholders),
            clean).fetchall()
    except Exception:  # noqa: BLE001 — missing table/column → empty map
        return {}
    out = {}
    for r in rows:
        try:
            out[int(r['id'])] = r['label']
        except (KeyError, TypeError, ValueError):
            pass
    return out


def resolve_fks(conn, items):
    """Copy items and attach resolved FK display names (``site``, ``vendor``, …).

    Original ``*_id`` values are kept. Soft-fails per FK — never raises.
    """
    if not items:
        return []
    # Collect ids per FK key present on any row.
    needed = {}
    for row in items:
        for fk in _FK:
            if fk in row and row[fk] not in (None, ''):
                needed.setdefault(fk, set()).add(row[fk])
    maps = {}
    for fk, ids in needed.items():
        table, label_col, _out = _FK[fk]
        maps[fk] = _load_map(conn, table, label_col, ids)

    out = []
    for row in items:
        d = dict(row)
        for fk, (_t, _l, out_key) in _FK.items():
            if fk not in d:
                continue
            raw = d.get(fk)
            try:
                key = int(raw) if raw is not None and raw != '' else None
            except (TypeError, ValueError):
                key = None
            d[out_key] = maps.get(fk, {}).get(key) if key is not None else None
        out.append(d)
    return out


def columns_from_items(items):
    """Fallback column list when no curated spec exists."""
    if not items:
        return []
    keys = list(items[0].keys())
    # Prefer putting id first if present.
    if 'id' in keys:
        keys = ['id'] + [k for k in keys if k != 'id']
    return [_c(k, k.replace('_', ' ').title(),
               'right' if k.endswith(('_id', '_amt', 'amount', 'qty', 'rate',
                                       'total', 'hours', 'days'))
               or k in ('debit', 'credit', 'month', 'year') else 'left')
            for k in keys]


def enrich(conn, table, items):
    """Return ``(label, columns, enriched_items)`` for a list response."""
    s = spec(table)
    enriched = resolve_fks(conn, items)
    cols = s['columns']
    if cols is None:
        cols = columns_from_items(enriched)
    return s['label'], cols, enriched
