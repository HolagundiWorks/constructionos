"""GST/TDS export pack for CA handoff — pure, tkinter-free.

Builds CSV text (and a simple HTML summary) from the same figures
``gst.py`` already computes for the registers. Used by
``GET /api/gst/export``.
"""

import csv
import io

import gst


def _csv_section(title, cols, rows, totals=None):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['# ' + title])
    w.writerow(cols)
    for row in rows:
        w.writerow(list(row))
    if totals is not None:
        if isinstance(totals, dict):
            # Align numeric totals under the money columns when possible.
            tot_row = ['TOTAL'] + [''] * (len(cols) - 1)
            # Prefer known keys in order appearing in COLS.
            money_keys = ['taxable', 'cgst', 'sgst', 'igst', 'total', 'tax']
            # Heuristic: fill from the right for money columns.
            vals = []
            for k in ('taxable', 'cgst', 'sgst', 'igst', 'total'):
                if k in totals:
                    vals.append('{:,.2f}'.format(float(totals[k] or 0)))
            if 'tax' in totals and 'total' not in totals:
                vals.append('{:,.2f}'.format(float(totals['tax'] or 0)))
            # Place values at the end of the row.
            if vals and len(vals) < len(cols):
                tot_row = (['TOTAL'] + [''] * (len(cols) - 1 - len(vals))
                           + vals)
            w.writerow(tot_row)
        else:
            w.writerow(['TOTAL TDS', '{:,.2f}'.format(float(totals or 0))])
    w.writerow([])
    return buf.getvalue()


def pack(conn, month=''):
    """Return a CA-ready export pack for ``month`` (``YYYY-MM`` or blank=all).

    Keys::

        month, csv (combined text), sections (per-report csv),
        html (simple printable summary), counts.
    """
    month = (month or '').strip()
    out_rows, out_tot = gst.outward(conn, month)
    in_rows, in_tot = gst.inward(conn, month)
    hsn_rows, hsn_tot = gst.hsn_summary(conn, month)
    tds_rows, tds_tot = gst.tds_register(conn, month)

    sections = {
        'outward': _csv_section(
            'Outward GST', gst.COLS['outward'], out_rows, out_tot),
        'hsn': _csv_section(
            'HSN Summary', gst.COLS['hsn'], hsn_rows, hsn_tot),
        'inward': _csv_section(
            'Inward GST', gst.COLS['inward'], in_rows, in_tot),
        'tds': _csv_section(
            'TDS Register', gst.COLS['tds'], tds_rows, tds_tot),
    }
    combined = (
        '# ACO GST/TDS export pack\n'
        '# Month: {}\n\n'.format(month or 'ALL')
        + sections['outward']
        + sections['hsn']
        + sections['inward']
        + sections['tds']
    )

    def _fmt_tot(t):
        if isinstance(t, dict):
            return {k: round(float(v or 0), 2) for k, v in t.items()}
        return round(float(t or 0), 2)

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<title>GST/TDS export</title></head><body>'
        '<h1>GST / TDS export pack</h1>'
        '<p>Month: {}</p>'
        '<h2>Outward</h2><p>Taxable {:,.2f} · Tax total CGST {:,.2f} '
        '+ SGST {:,.2f} + IGST {:,.2f}</p>'
        '<h2>Inward</h2><p>Taxable {:,.2f}</p>'
        '<h2>TDS</h2><p>Total withheld {:,.2f}</p>'
        '<p>Use the CSV body from the API for import into the CA\'s tool.</p>'
        '</body></html>'
    ).format(
        month or 'ALL',
        out_tot.get('taxable', 0), out_tot.get('cgst', 0),
        out_tot.get('sgst', 0), out_tot.get('igst', 0),
        in_tot.get('taxable', 0),
        float(tds_tot or 0),
    )

    return {
        'month': month or None,
        'csv': combined,
        'sections': sections,
        'html': html,
        'totals': {
            'outward': _fmt_tot(out_tot),
            'inward': _fmt_tot(in_tot),
            'hsn': _fmt_tot(hsn_tot),
            'tds': _fmt_tot(tds_tot),
        },
        'counts': {
            'outward': len(out_rows),
            'hsn': len(hsn_rows),
            'inward': len(in_rows),
            'tds': len(tds_rows),
        },
    }
