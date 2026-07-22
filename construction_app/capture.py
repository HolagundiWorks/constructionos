"""Draft-and-confirm capture framework (E1.1) — the safety scaffold under AI
data entry.

No tkinter, no database, **no model**. The models that read a photo, a voice
note or a document (OCR / speech-to-text / a VLM — external sidecars, see
``docs/AI-MODELS-AND-DEPLOYMENT.md``) produce a bag of *extracted fields*. This
module is what stands between that bag and the books: it stages the extraction as
an **editable draft with a confidence per field**, flags the fields a human
should look at, folds in the human's corrections, and only then yields a plain
record to save. Nothing here is ever written on its own — a draft becomes a
record only after ``apply_overrides`` and an explicit ``to_record``.

This is the deterministic half of every capture feature, and the important half:
the part that guarantees AI *proposes* and a human *disposes*. It is fully
testable on synthetic extractions, independent of whichever model produced them.
"""

# Below this confidence, a field is surfaced for the human's eye rather than
# trusted. Tuned conservative: better to ask than to book a mis-read quantity.
REVIEW_THRESHOLD = 0.6

MANUAL, AI = 'manual', 'ai'


def field(name, value, confidence=1.0, source=AI):
    """One extracted field: its value, how sure the extractor is (0..1), and
    where it came from. A human-entered field is source='manual', confidence 1."""
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    return {'name': name, 'value': value, 'confidence': conf, 'source': source}


def build_draft(extracted, confidence=None, source=AI):
    """Stage an extraction as a draft.

    ``extracted`` is a ``{name: value}`` dict from a model; ``confidence`` an
    optional ``{name: 0..1}`` (missing names default to 1.0). Returns a draft
    ``{fields: [...], source}`` — order-stable so the review UI is stable."""
    confidence = confidence or {}
    fields = [field(name, value, confidence.get(name, 1.0), source)
              for name, value in (extracted or {}).items()]
    return {'fields': fields, 'source': source}


def _by_name(draft):
    return {f['name']: f for f in draft.get('fields', [])}


def low_confidence_fields(draft, threshold=REVIEW_THRESHOLD):
    """The fields below ``threshold`` — the review queue, worst-confidence
    first. These are what a human is asked to confirm before saving."""
    low = [f for f in draft.get('fields', []) if f['confidence'] < threshold]
    return sorted(low, key=lambda f: f['confidence'])


def needs_review(draft, threshold=REVIEW_THRESHOLD):
    """True if any field is below the confidence threshold."""
    return bool(low_confidence_fields(draft, threshold))


def apply_overrides(draft, overrides):
    """Fold a human's corrections into the draft.

    ``overrides`` is a ``{name: value}`` dict; each overridden field takes the
    new value at full confidence and source='manual' (the human has vouched for
    it). A name not already present is added as a manual field, so a human can
    supply something the model missed entirely. Returns a new draft; the input
    is not mutated."""
    overrides = overrides or {}
    existing = _by_name(draft)
    out = []
    for f in draft.get('fields', []):
        if f['name'] in overrides:
            out.append(field(f['name'], overrides[f['name']], 1.0, MANUAL))
        else:
            out.append(dict(f))
    for name, value in overrides.items():
        if name not in existing:
            out.append(field(name, value, 1.0, MANUAL))
    return {'fields': out, 'source': draft.get('source', AI)}


def to_record(draft):
    """The plain ``{name: value}`` record to save — the draft's values only.
    Call this at the point of a confirmed save, never before review."""
    return {f['name']: f['value'] for f in draft.get('fields', [])}


def origin_of(draft):
    """Audit-origin tag for a confirmed capture draft: ``'ai'`` if any field
    still carries an AI source, else ``'manual'``. A human override flips that
    field to manual; a fully overridden draft is therefore manual."""
    fields = draft.get('fields') or []
    if any(f.get('source') == AI for f in fields):
        return AI
    return MANUAL


def confidence_summary(draft):
    """A quick read on how much to trust a draft: lowest and average confidence,
    and how many fields need review — so a UI can say 'looks clean' or 'check
    these 3' before the human even scrolls."""
    fields = draft.get('fields', [])
    if not fields:
        return {'fields': 0, 'min': None, 'avg': None, 'to_review': 0}
    confs = [f['confidence'] for f in fields]
    return {
        'fields': len(fields),
        'min': round(min(confs), 3),
        'avg': round(sum(confs) / len(confs), 3),
        'to_review': len(low_confidence_fields(draft)),
    }
