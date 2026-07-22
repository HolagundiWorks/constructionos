"""BOQ line import from CSV / TSV / plain text (E1 tender-import floor).

No tkinter, no PDF. Parses a pasted rate schedule into draft BOQ lines with
per-field confidence. Amount is always ``qty * rate`` (never trusted from the
file alone when both qty and rate parse). Human confirm writes ``boq_items``.
"""

import csv
import io
import re

import capture

_NUM = re.compile(r'^-?\d+(?:[.,]\d+)?$')


def _to_float(value):
    if value is None:
        return None
    s = str(value).strip().replace(',', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _sniff_dialect(sample):
    """Prefer tab, then comma, then whitespace-ish CSV."""
    if '\t' in sample:
        return 'excel-tab'
    if sample.count(';') > sample.count(','):
        return 'excel'  # fall through — we handle ; manually
    return 'excel'


def parse_text(text, default_unit='Nos'):
    """Parse pasted BOQ text into draft line dicts.

    Accepted shapes (header row optional)::

        item_no, description, unit, qty, rate
        item_no\\tdescription\\tunit\\tqty\\trate
        item_no | description | qty | rate   (unit defaults)

    Returns ``{lines: [...], skipped: int}`` where each line has
    ``item_no, description, unit, qty, rate, amount, confidence``.
    """
    raw = (text or '').strip()
    if not raw:
        return {'lines': [], 'skipped': 0}
    # Normalise pipe/markdown tables to tabs.
    if '|' in raw and '\t' not in raw:
        cleaned = []
        for line in raw.splitlines():
            if re.match(r'^\s*\|?[\s\-:|]+\|?\s*$', line):
                continue  # markdown separator
            parts = [p.strip() for p in line.strip().strip('|').split('|')]
            cleaned.append('\t'.join(parts))
        raw = '\n'.join(cleaned)

    dialect_name = _sniff_dialect(raw.splitlines()[0] if raw else '')
    if ';' in raw.splitlines()[0] and ',' not in raw.splitlines()[0]:
        reader = csv.reader(io.StringIO(raw), delimiter=';')
    elif dialect_name == 'excel-tab':
        reader = csv.reader(io.StringIO(raw), delimiter='\t')
    else:
        reader = csv.reader(io.StringIO(raw))

    rows = [list(r) for r in reader if any(str(c).strip() for c in r)]
    if not rows:
        return {'lines': [], 'skipped': 0}

    header_map = _header_map(rows[0])
    start = 1 if header_map else 0
    lines = []
    skipped = 0
    for row in rows[start:]:
        parsed = _parse_row(row, header_map, default_unit)
        if parsed is None:
            skipped += 1
            continue
        lines.append(parsed)
    return {'lines': lines, 'skipped': skipped}


def _header_map(row):
    cells = [str(c).strip().lower() for c in row]
    aliases = {
        'item_no': ('item_no', 'item', 'item no', 'sno', 's.no', 'no', '#'),
        'description': ('description', 'desc', 'particulars', 'item description'),
        'unit': ('unit', 'uom'),
        'qty': ('qty', 'quantity', 'qty.', 'qnty'),
        'rate': ('rate', 'unit rate', 'price'),
        'amount': ('amount', 'amt', 'value'),
    }
    mapping = {}
    for field, names in aliases.items():
        for i, cell in enumerate(cells):
            if cell in names:
                mapping[field] = i
                break
    # Need at least description + (qty or rate) to count as a header.
    if 'description' in mapping and ('qty' in mapping or 'rate' in mapping):
        return mapping
    return None


def _cell(row, idx):
    if idx is None or idx >= len(row):
        return ''
    return str(row[idx]).strip()


def _parse_row(row, header_map, default_unit):
    row = list(row)
    if header_map:
        item_no = _cell(row, header_map.get('item_no'))
        desc = _cell(row, header_map.get('description'))
        unit = _cell(row, header_map.get('unit')) or default_unit
        qty = _to_float(_cell(row, header_map.get('qty')))
        rate = _to_float(_cell(row, header_map.get('rate')))
    else:
        # Positional: item_no, description, [unit], qty, rate
        if len(row) < 3:
            return None
        item_no = str(row[0]).strip()
        desc = str(row[1]).strip()
        rest = [str(c).strip() for c in row[2:]]
        unit = default_unit
        qty = rate = None
        # If first remaining looks non-numeric, treat as unit.
        if rest and not _NUM.match(rest[0].replace(',', '')):
            unit = rest[0] or default_unit
            rest = rest[1:]
        nums = [_to_float(x) for x in rest]
        nums = [n for n in nums if n is not None]
        if len(nums) >= 2:
            qty, rate = nums[0], nums[1]
        elif len(nums) == 1:
            qty = nums[0]
    if not desc:
        return None
    conf = {
        'item_no': 0.9 if item_no else 0.4,
        'description': 0.85,
        'unit': 0.7 if unit else 0.4,
        'qty': 0.9 if qty is not None else 0.3,
        'rate': 0.9 if rate is not None else 0.3,
    }
    qty = 0.0 if qty is None else qty
    rate = 0.0 if rate is None else rate
    amount = round(float(qty) * float(rate), 2)
    conf['amount'] = min(conf['qty'], conf['rate'])
    return {
        'item_no': item_no,
        'description': desc,
        'unit': unit or default_unit,
        'qty': qty,
        'rate': rate,
        'amount': amount,
        'confidence': conf,
    }


def to_capture_drafts(lines):
    """Wrap each parsed line as a ``capture`` draft."""
    out = []
    for line in lines or []:
        fields = {k: line[k] for k in
                  ('item_no', 'description', 'unit', 'qty', 'rate', 'amount')}
        draft = capture.build_draft(fields, confidence=line.get('confidence'))
        out.append({
            'draft': draft,
            'needs_review': capture.needs_review(draft),
            'record': capture.to_record(draft),
        })
    return out
