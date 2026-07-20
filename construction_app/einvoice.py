"""E-invoice (IRN) and e-way-bill field validation and readiness.

No tkinter, no database.

E-invoicing and e-way bills are GST mechanisms that, above a turnover
threshold or for goods moving beyond a value, are mandatory. Actually
*generating* them needs a live call to the government IRP / e-way-bill portal,
which an offline app cannot make. What it can do — and what this module is for
— is hold the fields the portal gives back (the IRN, the acknowledgement, the
e-way-bill number, the vehicle) against the invoice, check they are the right
shape before they are relied on, and print them where a compliant invoice
must show them.

Two things this module deliberately does **not** do:

* It does not decide whether e-invoicing or an e-way bill is *required*. That
  turns on the firm's annual turnover and on whether the supply is goods or a
  service — a works contract is a service (SAC), and much of what this
  audience invoices needs no e-way bill at all. Guessing wrong in either
  direction is worse than staying quiet: nagging a service-only firm trains
  them to ignore the app, and telling a goods supplier they are fine when they
  are not is a fine waiting to happen.
* It does not fabricate the QR code. A real e-invoice QR encodes the portal's
  digitally signed payload, which cannot be reproduced offline. The printed
  invoice shows the IRN and says the QR comes from the portal, rather than
  drawing a QR that would not verify.

So the checks here are about *shape*, and the readiness report is about *what
is present*, never *what is owed*.
"""

import re

# An IRN is the SHA-256 hash the IRP returns: 64 hexadecimal characters.
_IRN_RE = re.compile(r'^[0-9a-fA-F]{64}$')
# An e-way-bill number is 12 digits (often shown grouped; grouping is stripped).
_EWAY_RE = re.compile(r'^\d{12}$')
# A loose Indian registration-plate check: state, RTO, optional series, number.
# Deliberately lenient — BH-series, defence and older formats exist, so this
# warns on obvious nonsense rather than rejecting anything unusual.
_VEHICLE_RE = re.compile(r'^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}$')


def _clean(value):
    return str(value or '').strip()


def _digits(value):
    return re.sub(r'\D', '', str(value or ''))


def validate_irn(irn):
    """(ok, message). Blank is ok — the IRN simply is not recorded yet."""
    irn = _clean(irn)
    if not irn:
        return True, ''
    if _IRN_RE.match(irn):
        return True, ''
    return False, ('An IRN is the 64-character reference the e-invoice portal '
                   'returns. This does not look like one — check it was copied '
                   'in full.')


def validate_eway(number):
    """(ok, message). Grouping spaces/hyphens are ignored before checking."""
    raw = _clean(number)
    if not raw:
        return True, ''
    if _EWAY_RE.match(_digits(raw)):
        return True, ''
    return False, 'An e-way-bill number is 12 digits. This is not.'


def validate_vehicle(number):
    """(ok, message). Lenient — warns, does not reject."""
    raw = _clean(number).upper().replace(' ', '').replace('-', '')
    if not raw:
        return True, ''
    if _VEHICLE_RE.match(raw):
        return True, ''
    return False, ('This does not look like a vehicle number (e.g. KA25AB1234). '
                   'Recorded as entered.')


def normalise_eway(number):
    """E-way-bill number as bare digits, or the original if it is not 12 digits."""
    d = _digits(number)
    return d if _EWAY_RE.match(d) else _clean(number)


def _g(row, key, default=''):
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def has_einvoice(invoice):
    """True once an IRN is recorded against the invoice."""
    return bool(_clean(_g(invoice, 'irn')))


def has_eway(invoice):
    """True once an e-way-bill number is recorded."""
    return bool(_clean(_g(invoice, 'eway_bill_no')))


def validate(invoice):
    """Every format warning on one invoice's e-invoice / e-way fields.

    Returns a list of plain-language messages, empty when everything recorded
    is well-formed. A blank field never warns — absence is not an error here,
    because the module does not know the field is required.
    """
    warnings = []
    for check, field in ((validate_irn, 'irn'),
                         (validate_eway, 'eway_bill_no'),
                         (validate_vehicle, 'vehicle_no')):
        ok, msg = check(_g(invoice, field))
        if not ok:
            warnings.append(msg)
    return warnings


def summarise(invoice):
    """What e-invoice / e-way detail is present on one invoice, and is it
    well-formed. Reports presence and shape only — never whether it is owed."""
    invoice = invoice or {}
    warnings = validate(invoice)
    return {
        'has_einvoice': has_einvoice(invoice),
        'has_eway': has_eway(invoice),
        'irn': _clean(_g(invoice, 'irn')),
        'eway_bill_no': normalise_eway(_g(invoice, 'eway_bill_no')),
        'vehicle_no': _clean(_g(invoice, 'vehicle_no')).upper(),
        'transporter': _clean(_g(invoice, 'transporter')),
        'well_formed': not warnings,
        'warnings': warnings,
    }
