"""The contractor's own firm details, for document letterheads.

Reads the firm's identity out of ``app_settings`` — name, GSTIN, address,
contact, and bank details for payment — and hands back a plain dict the pure
``bill_export`` builders can render. Kept apart from ``branding.py`` (which
holds the *software's* name and credit, a constant) because this is the
*user's* firm and lives in their data file.

Every document a contractor sends out should carry the same letterhead, and
anything asking for money should carry the bank details to pay into. Before
this, only the GST tax invoice did; everything else showed a bare name.
"""

# app_settings keys -> the dict keys the letterhead helpers expect.
_MAP = {
    'company_name': 'name',
    'seller_gstin': 'gstin',
    'seller_address': 'address',
    'firm_phone': 'phone',
    'firm_email': 'email',
    'firm_bank_name': 'bank_name',
    'firm_bank_account': 'bank_account',
    'firm_bank_ifsc': 'bank_ifsc',
    'firm_doc_footer': 'footer',
}

# The keys the firm-details settings panel offers, in display order, with the
# label shown beside each. Shared with tab_tools so the panel and the reader
# cannot drift apart.
FIELDS = [
    ('company_name', 'Firm Name'),
    ('seller_gstin', 'GSTIN'),
    ('seller_address', 'Address'),
    ('firm_phone', 'Phone'),
    ('firm_email', 'Email'),
    ('firm_bank_name', 'Bank & Branch'),
    ('firm_bank_account', 'Account No.'),
    ('firm_bank_ifsc', 'IFSC'),
    ('firm_doc_footer', 'Document footer / terms'),
]


def details(conn):
    """Firm details as ``{name, gstin, address, phone, email, bank_*, footer}``.

    Absent keys come back as empty strings, so a builder can test truthiness to
    decide whether to render a line rather than printing a blank label.
    """
    saved = {r['key']: (r['value'] or '') for r in conn.execute(
        "SELECT key, value FROM app_settings WHERE key IN ({})".format(
            ', '.join('?' * len(_MAP))), list(_MAP))}
    out = {v: saved.get(k, '').strip() for k, v in _MAP.items()}
    out['name'] = out['name'] or 'Construction OS'
    return out


def has_bank(firm):
    """True when enough bank detail is present to be worth printing."""
    firm = firm or {}
    return bool(firm.get('bank_account') and firm.get('bank_ifsc'))
