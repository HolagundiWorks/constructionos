"""GRN draft from challan text / OCR field bags (E1 photo→GRN floor).

No tkinter. Parses a delivery-challan paste (or sidecar-extracted fields) into
a GRN header + line drafts matched against the materials master. Nothing is
posted to stock — a human confirm path must create the Draft GRN.
"""

import re
from datetime import date

import capture
import material_match

_QTY = re.compile(
    r'^(.+?)\s+[x×*@]?\s*(\d+(?:\.\d+)?)\s*([A-Za-z.]+)?\s*$')
_CHALLAN = re.compile(r'\b(?:challan|dc|dn)[\s#:.-]*([A-Za-z0-9/-]+)', re.I)
_VEHICLE = re.compile(r'\b(?:vehicle|truck|lorry|veh)[\s#:.-]*([A-Z0-9-]+)', re.I)
_DATE = re.compile(r'\b(20\d{2}-\d{2}-\d{2})\b')


def _today():
    return date.today().isoformat()


def parse_challan_text(text):
    """Split challan paste into header hints + raw line descriptions.

    Returns ``{challan_no, vehicle_no, grn_date, lines:[{description, qty, unit}]}``.
    """
    raw = (text or '').strip()
    header = {
        'challan_no': '',
        'vehicle_no': '',
        'grn_date': _today(),
        'remarks': '',
    }
    cm = _CHALLAN.search(raw)
    if cm:
        header['challan_no'] = cm.group(1)
    vm = _VEHICLE.search(raw)
    if vm:
        header['vehicle_no'] = vm.group(1).upper()
    dm = _DATE.search(raw)
    if dm:
        header['grn_date'] = dm.group(1)

    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        # Skip header-ish lines
        low = s.lower()
        if any(k in low for k in ('challan', 'vehicle', 'truck', 'lorry',
                                  'vendor', 'supplier', 'date:', 'dc no')):
            continue
        # Strip leading serial
        i = 0
        while i < len(s) and s[i].isdigit():
            i += 1
        if i and i < len(s) and s[i] in '.)-–—:':
            s = s[i + 1:].strip()
        m = _QTY.match(s)
        if m:
            desc, qty_s, unit = m.group(1).strip(), m.group(2), (m.group(3) or '').strip()
            try:
                qty = float(qty_s)
            except ValueError:
                qty = 0.0
            lines.append({'description': desc, 'qty': qty, 'unit': unit})
        elif s:
            lines.append({'description': s, 'qty': 0.0, 'unit': ''})
    return {'header': header, 'lines': lines}


def draft_from_text(text, material_rows, threshold=0.55):
    """Build a GRN draft: header + matched lines with confidence."""
    parsed = parse_challan_text(text)
    return draft_from_parsed(parsed, material_rows, threshold=threshold)


def draft_from_parsed(parsed, material_rows, threshold=0.55):
    header = dict((parsed or {}).get('header') or {})
    rows = []
    matched = unmatched = 0
    for line in (parsed or {}).get('lines') or []:
        desc = line.get('description') or ''
        m = material_match.match_one(desc, material_rows, threshold=threshold)
        conf = m['confidence']
        unit = line.get('unit') or m.get('unit') or ''
        try:
            qty = float(line.get('qty') or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if m['material_id'] is None:
            unmatched += 1
        else:
            matched += 1
        rows.append({
            'query': desc,
            'material_id': m['material_id'],
            'matched_name': m['matched_name'],
            'description': m['matched_name'] or desc,
            'unit': unit,
            'qty_received': qty,
            'qty_rejected': 0.0,
            'qty_accepted': qty,
            'confidence': conf,
            'needs_review': m['material_id'] is None or conf < capture.REVIEW_THRESHOLD,
            'candidates': m['candidates'],
        })
    header_conf = {
        'challan_no': 0.85 if header.get('challan_no') else 0.3,
        'vehicle_no': 0.8 if header.get('vehicle_no') else 0.3,
        'grn_date': 0.9 if header.get('grn_date') else 0.5,
    }
    return {
        'header': header,
        'header_confidence': header_conf,
        'lines': rows,
        'matched': matched,
        'unmatched': unmatched,
        'needs_review': unmatched > 0 or any(r['needs_review'] for r in rows),
    }


def header_capture_draft(header, confidence=None):
    fields = {
        'challan_no': header.get('challan_no') or '',
        'vehicle_no': header.get('vehicle_no') or '',
        'grn_date': header.get('grn_date') or _today(),
        'remarks': header.get('remarks') or '',
    }
    return capture.build_draft(fields, confidence=confidence or {})
