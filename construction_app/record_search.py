"""Record-level search (N4) — find projects, parties, docs by free text.

No tkinter. Returns hits shaped for the Process palette and ``GET /api/search``:
``{kind, table, id, label, section, tab, href}``. ``href`` aligns with the
browser ``/t/{table}/{id}`` routes where those exist.
"""

# Tables searched, in priority order. Each entry: (table, id_col, label_sql,
# section, tab, extra WHERE fragment using alias ``t``).
_SOURCES = (
    ('projects', 'id', "COALESCE(t.name, 'Project ' || t.id)",
     'Project Management', 'Projects', ''),
    ('clients', 'id', "COALESCE(t.name, 'Client ' || t.id)",
     'Masters', 'Clients', ''),
    ('vendors', 'id', "COALESCE(t.name, 'Vendor ' || t.id)",
     'Masters', 'Vendors', ''),
    ('sites', 'id', "COALESCE(t.name, 'Site ' || t.id)",
     'Masters', 'Sites', ''),
    ('contracts', 'id',
     "COALESCE(t.contract_no, 'Contract ' || t.id)",
     'Billing', 'Contracts', ''),
    ('purchase_orders', 'id',
     "COALESCE(t.po_no, 'PO ' || t.id)",
     'Purchases', 'Purchase Orders', ''),
    ('goods_receipts', 'id',
     "COALESCE(t.grn_no, 'GRN ' || t.id)",
     'Purchases', 'Goods Receipt', ''),
    ('risks', 'id', "COALESCE(t.title, 'Risk ' || t.id)",
     'Controls', 'Risk Register', ''),
    ('opportunities', 'id', "COALESCE(t.title, 'Opportunity ' || t.id)",
     'Controls', 'Opportunity Register', ''),
    ('lessons_learned', 'id', "COALESCE(t.title, 'Lesson ' || t.id)",
     'Controls', 'Lessons Learned', ''),
    ('submittals', 'id',
     "COALESCE(t.title, t.submittal_no, 'Submittal ' || t.id)",
     'Controls', 'Submittals', ''),
)


def search_records(conn, query, limit=40):
    """Case-insensitive substring search across key registers.

    Empty query → []. Limit is a hard cap across all tables combined.
    """
    q = (query or '').strip()
    if not q:
        return []
    like = '%' + q + '%'
    hits = []
    remaining = max(1, int(limit or 40))
    for table, id_col, label_sql, section, tab, extra in _SOURCES:
        if remaining <= 0:
            break
        where_extra = (' AND ' + extra) if extra else ''
        sql = (
            'SELECT t.{id} AS id, ({label}) AS label FROM "{table}" t '
            'WHERE CAST(({label}) AS TEXT) LIKE ? COLLATE NOCASE'
            '{extra} ORDER BY t.{id} DESC LIMIT ?'
        ).format(id=id_col, label=label_sql, table=table, extra=where_extra)
        try:
            rows = conn.execute(sql, (like, remaining)).fetchall()
        except Exception:  # noqa: BLE001 — older DB missing a table
            continue
        for r in rows:
            rid = r['id']
            label = r['label'] or '{} {}'.format(table, rid)
            hits.append({
                'kind': 'record',
                'table': table,
                'id': rid,
                'label': label,
                'section': section,
                'tab': tab,
                # Browser deep-link + WinUI NavigationView tag (section/tab).
                'href': '/t/{}/{}'.format(table, rid),
                'nav': '{}/{}'.format(section, tab),
                'tag': '{}/{}'.format(section, tab),
                'display': '{} › {} — {}'.format(section, tab, label),
            })
            remaining -= 1
            if remaining <= 0:
                break
    return hits
