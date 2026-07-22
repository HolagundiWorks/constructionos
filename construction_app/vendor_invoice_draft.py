"""Vendor-invoice draft from pasted invoice text (E1 commercial capture floor).

No tkinter. Parses a free-text / OCR bag into header + line drafts. Confirm
writes ``vendor_invoices`` + items and derives totals via ``finance.invoice_totals``.
Nothing auto-posts to the journal.
"""

import re
from datetime import date

import capture
import finance

_DATE = re.compile(r'\b(20\d{2}-\d{2}-\d{2})\b')
_INV = re.compile(r'\b(?:invoice|inv|bill)[\s#:.-]*([A-Za-z0-9/-]+)', re.I)
_GST = re.compile(r'\b(?:gst|igst|cgst)[\s%@:]*(\d+(?:\.\d+)?)\s*%?', re.I)
_TDS = re.compile(r'\btds[\s%@:]*(\d+(?:\.\d+)?)\s*%?', re.I)
_LINE = re.compile(
    r'^(.+?)\s+(\d+(?:\.\d+)?)\s+([A-Za-z.]+)?\s*[@x×*]?\s*(\d+(?:\.\d+)?)\s*$')
_LINE2 = re.compile(
    r'^(.+?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$')  # desc qty rate


def _today():
    return date.today().isoformat()


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_invoice_text(text):
    """Return ``{header, lines}`` from a pasted vendor invoice."""
    raw = (text or '').strip()
    header = {
        'invoice_no': '',
        'invoice_date': _today(),
        'gst_pct': 18.0,
        'tds_pct': 0.0,
        'interstate': 0,
        'notes': '',
    }
    im = _INV.search(raw)
    if im:
        header['invoice_no'] = im.group(1)
    dm = _DATE.search(raw)
    if dm:
        header['invoice_date'] = dm.group(1)
    gm = _GST.search(raw)
    if gm:
        header['gst_pct'] = _f(gm.group(1), 18.0)
    tm = _TDS.search(raw)
    if tm:
        header['tds_pct'] = _f(tm.group(1), 0.0)
    if re.search(r'\b(inter[-\s]?state|igst)\b', raw, re.I):
        header['interstate'] = 1

    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(k in low for k in ('invoice', 'gst', 'tds', 'vendor', 'subtotal',
                                  'total', 'net payable', 'date:')):
            continue
        i = 0
        while i < len(s) and s[i].isdigit():
            i += 1
        if i and i < len(s) and s[i] in '.)-–—:':
            s = s[i + 1:].strip()
        m = _LINE.match(s)
        if m:
            desc, qty, unit, rate = m.group(1).strip(), m.group(2), (m.group(3) or 'Nos'), m.group(4)
            q, r = _f(qty), _f(rate)
            lines.append({
                'description': desc, 'unit': unit or 'Nos',
                'qty': q, 'rate': r, 'amount': round(q * r, 2),
            })
            continue
        m2 = _LINE2.match(s)
        if m2:
            desc, qty, rate = m2.group(1).strip(), m2.group(2), m2.group(3)
            q, r = _f(qty), _f(rate)
            lines.append({
                'description': desc, 'unit': 'Nos',
                'qty': q, 'rate': r, 'amount': round(q * r, 2),
            })
    return {'header': header, 'lines': lines}


def draft_from_text(text):
    parsed = parse_invoice_text(text)
    header = parsed['header']
    lines = parsed['lines']
    subtotal = round(sum(l['amount'] for l in lines), 2)
    totals = finance.invoice_totals(
        subtotal, header.get('gst_pct', 18), header.get('tds_pct', 0),
        bool(header.get('interstate')))
    header_conf = {
        'invoice_no': 0.85 if header.get('invoice_no') else 0.4,
        'invoice_date': 0.9 if header.get('invoice_date') else 0.5,
        'gst_pct': 0.7,
        'tds_pct': 0.6,
    }
    line_drafts = []
    for line in lines:
        conf = {
            'description': 0.8, 'unit': 0.7,
            'qty': 0.85, 'rate': 0.85, 'amount': 0.85,
        }
        draft = capture.build_draft(line, confidence=conf)
        line_drafts.append({
            'record': line,
            'draft': draft,
            'needs_review': capture.needs_review(draft),
        })
    return {
        'header': header,
        'header_confidence': header_conf,
        'lines': lines,
        'line_drafts': line_drafts,
        'subtotal': subtotal,
        'totals': totals,
        'needs_review': (not header.get('invoice_no')) or any(
            d['needs_review'] for d in line_drafts) or not lines,
    }
