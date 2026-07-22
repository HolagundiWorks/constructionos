"""Free-text → structured field bags (WhatsApp / site notes floor).

No tkinter, no model. Deterministic keyword/regex extraction into draft
records for daily progress, work-done, NCR and snags. Stages via ``capture``;
nothing is written without an explicit confirm.
"""

import re
from datetime import date

import capture

_DATE = re.compile(r'\b(20\d{2}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b')
_QTY = re.compile(
    r'\b(\d+(?:\.\d+)?)\s*(cum|cu\.?m|sqm|sq\.?m|rmt|rm|nos|no|kg|mt|bags?)\b',
    re.I)
_LABOUR = re.compile(r'\b(\d+)\s*(?:labou?r(?:ers)?|workers?|men)\b', re.I)
_PLANT = re.compile(r'\b(\d+)\s*(?:plant|machines?|equipment)\b', re.I)
_WEATHER = re.compile(r'\b(clear|sunny|rain(?:y)?|cloudy|hot|humid|storm)\b', re.I)
_NCR = re.compile(r'\b(ncr|non[-\s]?conformance|defect|failed?\s+inspection)\b', re.I)
_SNAG = re.compile(r'\b(snag|punch\s*list|defect\s*liability|handover\s+issue)\b', re.I)
_SEVERITY = re.compile(r'\b(critical|major|minor|blocker)\b', re.I)


def _today():
    return date.today().isoformat()


def _norm_date(raw):
    s = (raw or '').strip()
    if not s:
        return _today()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](20\d{2})$', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Prefer DMY (Indian).
        if mo <= 12 and d <= 31:
            return '{:04d}-{:02d}-{:02d}'.format(y, mo, d)
    return _today()


def unit_norm(u):
    u = (u or '').lower().replace('.', '')
    mapping = {
        'cum': 'cum', 'cu m': 'cum',
        'sqm': 'sqm', 'sq m': 'sqm',
        'rmt': 'rm', 'rm': 'rm',
        'nos': 'Nos', 'no': 'Nos',
        'kg': 'kg', 'mt': 'MT',
        'bag': 'bags', 'bags': 'bags',
    }
    return mapping.get(u, u or 'Nos')


TARGETS = ('work_done', 'daily_progress', 'ncr', 'snag', 'measurement')

_MB_DIMS = re.compile(
    r'(?:nos|no\.?s?)\s*[=:]?\s*(\d+(?:\.\d+)?)\s*'
    r'(?:[x×*]\s*)?(?:l(?:en(?:gth)?)?)\s*[=:]?\s*(\d+(?:\.\d+)?)\s*'
    r'(?:[x×*]\s*)?(?:b(?:readth)?|w(?:idth)?)\s*[=:]?\s*(\d+(?:\.\d+)?)?\s*'
    r'(?:[x×*]\s*)?(?:d(?:epth)?|h(?:eight)?)\s*[=:]?\s*(\d+(?:\.\d+)?)?',
    re.I)
_MB_SIMPLE = re.compile(
    r'\b(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)'
    r'(?:\s*[x×]\s*(\d+(?:\.\d+)?))?'
    r'(?:\s*[x×]\s*(\d+(?:\.\d+)?))?\b')


def detect_target(text):
    """Best guess target table for free text."""
    t = text or ''
    if _NCR.search(t):
        return 'ncr'
    if _SNAG.search(t):
        return 'snag'
    if re.search(r'\b(mb|measurement|nos\s*[x×]|length|breadth|depth)\b', t, re.I):
        return 'measurement'
    if _QTY.search(t) and not _LABOUR.search(t):
        return 'work_done'
    if _LABOUR.search(t) or _WEATHER.search(t) or re.search(r'\bdpr\b', t, re.I):
        return 'daily_progress'
    if _QTY.search(t):
        return 'work_done'
    return 'daily_progress'


def extract_measurement(text):
    """Measurement-book style dims → nos/length/breadth/depth (+ description)."""
    import civil
    t = (text or '').strip()
    conf = {}
    nos = length = breadth = depth = None
    m = _MB_DIMS.search(t)
    if m:
        nos = float(m.group(1))
        length = float(m.group(2))
        breadth = float(m.group(3)) if m.group(3) else None
        depth = float(m.group(4)) if m.group(4) else None
    else:
        m2 = _MB_SIMPLE.search(t)
        if m2:
            # Ambiguous: treat as Nos x L [x B [x D]]
            nos = float(m2.group(1))
            length = float(m2.group(2))
            breadth = float(m2.group(3)) if m2.group(3) else None
            depth = float(m2.group(4)) if m2.group(4) else None
    conf['nos'] = 0.85 if nos is not None else 0.3
    conf['length'] = 0.85 if length is not None else 0.3
    conf['breadth'] = 0.7 if breadth is not None else 0.4
    conf['depth'] = 0.7 if depth is not None else 0.4
    qty = civil.measurement_quantity(nos, length, breadth, depth)
    conf['quantity'] = min(conf['nos'], conf['length'])
    desc = re.sub(r'\s+', ' ', t).strip()[:200]
    conf['description'] = 0.65
    dm = _DATE.search(t)
    mb_date = _norm_date(dm.group(1) if dm else '')
    conf['mb_date'] = 0.85 if dm else 0.5
    fields = {
        'description': desc,
        'nos': nos if nos is not None else 1.0,
        'length': length if length is not None else '',
        'breadth': breadth if breadth is not None else '',
        'depth': depth if depth is not None else '',
        'quantity': qty,
        'mb_date': mb_date,
    }
    return fields, conf


def extract_work_done(text):
    """Qty + unit + activity from a short site note."""
    t = (text or '').strip()
    conf = {}
    m = _QTY.search(t)
    qty = float(m.group(1)) if m else None
    unit = unit_norm(m.group(2)) if m else 'Nos'
    conf['qty'] = 0.85 if m else 0.3
    conf['unit'] = 0.8 if m else 0.4
    # Activity: text before the qty, or whole line stripped of qty clause.
    activity = t
    if m:
        activity = (t[:m.start()] + t[m.end():]).strip(' -–—,;:')
    activity = re.sub(r'\s+', ' ', activity).strip() or 'Work done'
    conf['activity'] = 0.7 if activity != 'Work done' else 0.4
    dm = _DATE.search(t)
    entry_date = _norm_date(dm.group(1) if dm else '')
    conf['entry_date'] = 0.9 if dm else 0.5
    fields = {
        'activity': activity,
        'qty': qty if qty is not None else 0.0,
        'unit': unit,
        'entry_date': entry_date,
        'remarks': t[:200],
    }
    return fields, conf


def extract_daily_progress(text):
    t = (text or '').strip()
    conf = {}
    dm = _DATE.search(t)
    report_date = _norm_date(dm.group(1) if dm else '')
    conf['report_date'] = 0.9 if dm else 0.5
    lm = _LABOUR.search(t)
    labour = float(lm.group(1)) if lm else 0.0
    conf['labour_count'] = 0.85 if lm else 0.3
    pm = _PLANT.search(t)
    plant = float(pm.group(1)) if pm else 0.0
    conf['plant_count'] = 0.8 if pm else 0.3
    wm = _WEATHER.search(t)
    weather = wm.group(1).capitalize() if wm else ''
    conf['weather'] = 0.8 if wm else 0.4
    fields = {
        'report_date': report_date,
        'weather': weather,
        'labour_count': labour,
        'plant_count': plant,
        'work_summary': t[:500],
        'remarks': '',
    }
    conf['work_summary'] = 0.75
    return fields, conf


def extract_ncr(text):
    t = (text or '').strip()
    conf = {}
    sm = _SEVERITY.search(t)
    severity = sm.group(1).capitalize() if sm else 'Major'
    if severity.lower() == 'blocker':
        severity = 'Critical'
    conf['severity'] = 0.8 if sm else 0.5
    dm = _DATE.search(t)
    raised = _norm_date(dm.group(1) if dm else '')
    conf['raised_date'] = 0.85 if dm else 0.5
    fields = {
        'description': t[:500],
        'severity': severity,
        'raised_date': raised,
        'status': 'Open',
        'remarks': '',
    }
    conf['description'] = 0.75
    conf['status'] = 1.0
    return fields, conf


def extract_snag(text):
    t = (text or '').strip()
    conf = {}
    sm = _SEVERITY.search(t)
    severity = sm.group(1).capitalize() if sm else 'Minor'
    if severity.lower() == 'critical':
        severity = 'Major'
    conf['severity'] = 0.75 if sm else 0.5
    # Location hint: "at lobby" / "in flat 302"
    loc_m = re.search(r'\b(?:at|in)\s+([A-Za-z0-9][\w\s\-/]{1,40})', t, re.I)
    location = loc_m.group(1).strip() if loc_m else ''
    conf['location'] = 0.7 if location else 0.3
    fields = {
        'description': t[:500],
        'location': location,
        'severity': severity,
        'status': 'Open',
        'raised_date': _today(),
    }
    conf['description'] = 0.75
    conf['status'] = 1.0
    conf['raised_date'] = 0.5
    return fields, conf


_EXTRACTORS = {
    'work_done': extract_work_done,
    'daily_progress': extract_daily_progress,
    'ncr': extract_ncr,
    'snag': extract_snag,
    'measurement': extract_measurement,
}


def extract(text, target=None):
    """Return ``{target, draft, needs_review, fields, confidence}``."""
    tgt = (target or detect_target(text) or 'daily_progress').strip()
    if tgt not in _EXTRACTORS:
        tgt = 'daily_progress'
    fields, conf = _EXTRACTORS[tgt](text)
    draft = capture.build_draft(fields, confidence=conf, source=capture.AI)
    return {
        'target': tgt,
        'fields': fields,
        'confidence': conf,
        'draft': draft,
        'needs_review': capture.needs_review(draft),
        'summary': capture.confidence_summary(draft),
    }
