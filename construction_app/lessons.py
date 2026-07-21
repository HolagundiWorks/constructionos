"""Lessons-learned taxonomy + roll-up (Part 2 — continuous improvement).

No tkinter, no database. A lessons-learned register is only worth keeping if it
**feeds forward** — a lesson nobody applies to the next job is a diary entry, not
an improvement. So this pure layer is deliberately built around that: it
classifies a lesson (what area, did it go well or badly, where did it come from)
and rolls a set of lessons up into the two things a review actually asks —
*what keeps going wrong* and *what should we carry into the next project*.

The persistence lives in ``lessons_store``; this is the vocabulary and the
summary, testable on plain dicts with ``python -c``.
"""

# --- outcome: did this go well, badly, or is it a neutral observation
POSITIVE, NEGATIVE, NEUTRAL = 'positive', 'negative', 'neutral'
OUTCOMES = (POSITIVE, NEGATIVE, NEUTRAL)

# --- where the lesson came from. A lesson can be born from a risk that
# materialised, an opportunity that was (or was not) realised, a plain site
# observation, or an AI-surfaced pattern.
RISK, OPPORTUNITY, OBSERVATION, AI = 'risk', 'opportunity', 'observation', 'ai'
SOURCES = (RISK, OPPORTUNITY, OBSERVATION, AI)

# --- lifecycle. 'Applied' is the one that matters: the lesson has been fed into
# future planning (a rate updated, a detection rule tuned, a checklist changed).
OPEN, REVIEWED, APPLIED = 'Open', 'Reviewed', 'Applied'
STATUSES = (OPEN, REVIEWED, APPLIED)

# Categories shared with the risk/opportunity registers, so a lesson born from a
# risk keeps its area.
CATEGORIES = ('schedule', 'cost', 'commercial', 'quality', 'safety',
              'procurement', 'external', 'site')


def normalize_outcome(value):
    """Coerce to a known outcome; anything unrecognised is a neutral
    observation rather than an error — a register import with an odd label must
    still load."""
    v = (value or '').strip().lower()
    return v if v in OUTCOMES else NEUTRAL


def normalize_source(value):
    v = (value or '').strip().lower()
    return v if v in SOURCES else OBSERVATION


def _get(row, key, default=None):
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def is_feed_forward(lesson):
    """True when a lesson carries a recommendation but has not yet been Applied.

    This is the register's live work list: captured insight that has not yet
    been turned into a change to the next project."""
    rec = str(_get(lesson, 'recommendation', '') or '').strip()
    status = str(_get(lesson, 'status', OPEN) or OPEN).strip()
    return bool(rec) and status != APPLIED


def summary(lessons):
    """Roll a set of lessons up for a review.

    Counts by category and by outcome, how many have been **applied** (the real
    measure that the register is improving anything), and the **feed-forward**
    list — recommendations not yet applied, the queue for the next project.
    """
    lessons = list(lessons or [])
    by_category = {}
    by_outcome = {POSITIVE: 0, NEGATIVE: 0, NEUTRAL: 0}
    applied = 0
    feed_forward = []
    for l in lessons:
        cat = str(_get(l, 'category', 'other') or 'other')
        by_category[cat] = by_category.get(cat, 0) + 1
        by_outcome[normalize_outcome(_get(l, 'outcome'))] += 1
        if str(_get(l, 'status', OPEN)).strip() == APPLIED:
            applied += 1
        if is_feed_forward(l):
            feed_forward.append(l)
    return {
        'count': len(lessons),
        'by_category': by_category,
        'by_outcome': by_outcome,
        'applied': applied,
        'feed_forward_count': len(feed_forward),
        'feed_forward': feed_forward,
    }
