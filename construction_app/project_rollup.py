"""Per-project cost/revenue rollup — the DB bridge over ``projectcost``.

No tkinter. The pure attribution maths live in ``projectcost``; this module is
the thin, conn-taking layer that gathers candidate rows from the ledger and
returns one rollup dict. Shared by EVM (``evm.py``), the dashboard, the KPI
tab, and the Project Cost view so every surface computes cost the same way —
and so a headless caller never has to import a GUI module.
"""

import projectcost


def sole_on_site(conn, pid):
    """True when this project is the only one on its site — the condition
    under which untagged rows may be attributed by site."""
    row = conn.execute('SELECT site_id FROM projects WHERE id = ?',
                       (pid,)).fetchone()
    site_id = row['site_id'] if row else None
    return conn.execute(
        'SELECT COUNT(*) FROM projects WHERE site_id = ? AND site_id IS NOT NULL',
        (site_id,)).fetchone()[0] <= 1


def gather_project_rows(conn, pid, site_id):
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
    """The full cost/revenue rollup for one project.

    Shared by EVM, Project Cost, KPI and the dashboard so every surface uses
    the same numbers.
    """
    p = conn.execute('SELECT site_id, budget FROM projects WHERE id = ?',
                     (pid,)).fetchone()
    if p is None:
        return projectcost.rollup([], pid, None, True, 0)
    rows = gather_project_rows(conn, pid, p['site_id'])
    return projectcost.rollup(rows, pid, p['site_id'],
                              sole_on_site(conn, pid), p['budget'])
