"""Cross-project pattern learning floor (local-first, opt-in).

No tkinter, no ML model. Aggregates lessons (and optional risk categories)
into **draft** lessons a human reviews — ``source='ai'``. Never auto-applies
rates or closes a lesson. Persistence is via ``lessons_store.add``.
"""

import lessons_register as lessons


def _get(row, key, default=None):
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def from_lessons(lesson_rows, min_count=2):
    """Repeat negative categories → feed-forward lesson drafts.

    When the same category appears as ``outcome=negative`` at least
    ``min_count`` times (and still has open recommendations), emit one draft
    lesson per category summarising the pattern.
    """
    counts = {}
    samples = {}
    for row in lesson_rows or []:
        if lessons.normalize_outcome(_get(row, 'outcome')) != lessons.NEGATIVE:
            continue
        cat = (_get(row, 'category') or 'site').strip().lower() or 'site'
        counts[cat] = counts.get(cat, 0) + 1
        samples.setdefault(cat, [])
        title = (_get(row, 'title') or '').strip()
        rec = (_get(row, 'recommendation') or '').strip()
        if title and len(samples[cat]) < 3:
            samples[cat].append({'title': title, 'recommendation': rec})

    drafts = []
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n < int(min_count):
            continue
        tips = samples.get(cat) or []
        tip_bits = []
        for t in tips:
            if t['recommendation']:
                tip_bits.append(t['recommendation'])
            elif t['title']:
                tip_bits.append(t['title'])
        recommendation = (
            'Review prior {} failures before the next estimate; '
            'carry forward: {}.'.format(
                cat, '; '.join(tip_bits) if tip_bits else 'see related lessons')
        )
        drafts.append({
            'category': cat,
            'title': 'Recurring {} issue ({} past lessons)'.format(cat, n),
            'description': 'Pattern across {} negative lesson(s) in {}.'.format(
                n, cat),
            'outcome': lessons.NEGATIVE,
            'recommendation': recommendation,
            'source': lessons.AI,
            'status': lessons.OPEN,
            'basis': '{} negative lessons in category {}'.format(n, cat),
            'impact_value': 0,
        })
    return drafts


def from_risk_categories(risk_rows, min_count=2):
    """Open high-band risks clustered by category → lesson draft suggestions."""
    counts = {}
    for row in risk_rows or []:
        status = (_get(row, 'status') or 'Open').strip()
        if status.lower() in ('closed', 'dismissed', 'accepted'):
            continue
        band = (_get(row, 'band') or '').strip().lower()
        score = _get(row, 'score')
        # Prefer explicit band; else treat score >= 12 as high-ish.
        high = band in ('high', 'critical') or (
            score is not None and float(score) >= 12)
        if not high:
            continue
        cat = (_get(row, 'category') or 'site').strip().lower() or 'site'
        counts[cat] = counts.get(cat, 0) + 1
    drafts = []
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n < int(min_count):
            continue
        drafts.append({
            'category': cat,
            'title': 'Open high {} risks clustering ({})'.format(cat, n),
            'description': 'Portfolio/file has {} open high-band {} risks.'.format(
                n, cat),
            'outcome': lessons.NEUTRAL,
            'recommendation': (
                'Add a {} checklist item on the next similar job and review '
                'mitigations before mobilisation.'.format(cat)),
            'source': lessons.AI,
            'status': lessons.OPEN,
            'basis': '{} open high risks in {}'.format(n, cat),
            'impact_value': 0,
        })
    return drafts


def collect(lesson_rows=None, risk_rows=None, min_count=2):
    """Union of lesson + risk pattern drafts (deduped by title)."""
    drafts = []
    drafts.extend(from_lessons(lesson_rows, min_count=min_count))
    drafts.extend(from_risk_categories(risk_rows, min_count=min_count))
    seen = set()
    out = []
    for d in drafts:
        key = d.get('title')
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out
