"""Measurement Book (Form 23 / CMB) and RA abstract (PWD Form 26) — DB bridge.

``bill_export.py`` renders these statutory documents but is pure (no database);
this assembles the exact rows they need from the live database, so the desktop
tab and the browser serve **one identical document** — the measurement book a
contractor prints from their laptop and the one a client opens over the LAN can
never disagree, because both come through here.

DB-only, no tkinter. The measurement book is keyed by *contract* (all of a
contract's measurements, grouped into Form-23 pages); the RA abstract is keyed
by a single *RA bill* (its measured items versus the tender).
"""

import bill_export
import mb


def company_name(conn):
    """Firm name from app_settings (Tools › Firm Details), for the letterhead —
    read the same way the desktop reads it, so both print the same name."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
    return (row['value'] if row and row['value'] else '') or 'Construction OS'


def contract_context(conn, contract_id):
    """Contract row plus its client and site (any may be None)."""
    contract = conn.execute('SELECT * FROM contracts WHERE id = ?',
                            (contract_id,)).fetchone()
    client = site = None
    if contract is not None:
        if contract['client_id'] is not None:
            client = conn.execute('SELECT * FROM clients WHERE id = ?',
                                  (contract['client_id'],)).fetchone()
        if contract['site_id'] is not None:
            site = conn.execute('SELECT * FROM sites WHERE id = ?',
                                (contract['site_id'],)).fetchone()
    return contract, client, site


def measurement_rows(conn, contract_id):
    """The contract's measurements joined to their BOQ item (for item_no/unit),
    in entry order — the rows ``bill_export.build_mb_html`` groups into pages."""
    return conn.execute(
        "SELECT m.*, b.item_no, b.unit FROM measurements m "
        "LEFT JOIN boq_items b ON b.id = m.boq_item_id "
        "WHERE m.contract_id = ? ORDER BY m.id", (contract_id,)).fetchall()


def has_measurements(conn, contract_id):
    """True when the contract has at least one measurement to print."""
    row = conn.execute(
        'SELECT 1 FROM measurements WHERE contract_id = ? LIMIT 1',
        (contract_id,)).fetchone()
    return row is not None


def measurement_book_html(conn, contract_id, company=None):
    """The full Measurement Book (Form 23 / CMB) HTML for a contract.

    Groups the contract's measurements into pages, appends the measured-vs-
    tendered abstract, and surfaces ``mb.integrity_issues`` as a record-check
    panel — the same document the desktop 'Export Measurement Book' produces.
    """
    contract, client, site = contract_context(conn, contract_id)
    rows = measurement_rows(conn, contract_id)
    boq = conn.execute(
        'SELECT id, item_no, description, unit, qty FROM boq_items '
        'WHERE contract_id = ? ORDER BY id', (contract_id,)).fetchall()
    return bill_export.build_mb_html(
        contract, client, site, rows, boq_items=boq,
        company_name=company or company_name(conn),
        issues=mb.integrity_issues(rows))


def ra_bill_context(conn, ra_bill_id):
    """RA bill row plus its contract, client and site (any may be None)."""
    bill = conn.execute('SELECT * FROM ra_bills WHERE id = ?',
                        (ra_bill_id,)).fetchone()
    if bill is None:
        return None, None, None, None
    contract, client, site = (None, None, None)
    if bill['contract_id'] is not None:
        contract, client, site = contract_context(conn, bill['contract_id'])
    return bill, contract, client, site


def ra_abstract_html(conn, ra_bill_id, company=None):
    """The PWD-style RA abstract (Form 26 layout) HTML for one RA bill, or
    ``None`` when the bill does not exist."""
    bill, contract, client, site = ra_bill_context(conn, ra_bill_id)
    if bill is None:
        return None
    items = conn.execute(
        "SELECT b.item_no, b.description, b.unit, b.qty AS boq_qty, "
        "b.rate AS boq_rate, ri.upto_qty, ri.previous_qty, ri.current_qty, "
        "ri.rate, ri.current_amount FROM ra_bill_items ri "
        "LEFT JOIN boq_items b ON b.id = ri.boq_item_id "
        "WHERE ri.ra_bill_id = ? ORDER BY ri.id", (ra_bill_id,)).fetchall()
    return bill_export.build_ra_pwd_html(
        bill, contract, client, site, items,
        company_name=company or company_name(conn))
