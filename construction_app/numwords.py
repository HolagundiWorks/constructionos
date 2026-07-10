"""Indian-numbering amount-in-words (pure, testable).

Rupees invoices in India are printed "in words" using the lakh/crore system
(e.g. Rupees Two Lakh Forty Two Thousand Only). No tkinter, no database.
"""

_ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight',
         'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
         'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
_TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy',
         'Eighty', 'Ninety']


def _below_hundred(n):
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return (_TENS[tens] + (' ' + _ONES[ones] if ones else '')).strip()


def _in_words(n):
    """Whole number to Indian-system words (handles crores and beyond)."""
    if n == 0:
        return ''
    parts = []
    crore, n = divmod(n, 10000000)
    lakh, n = divmod(n, 100000)
    thousand, n = divmod(n, 1000)
    hundred, n = divmod(n, 100)
    if crore:
        parts.append(_in_words(crore) + ' Crore')   # recursion for >99 crore
    if lakh:
        parts.append(_below_hundred(lakh) + ' Lakh')
    if thousand:
        parts.append(_below_hundred(thousand) + ' Thousand')
    if hundred:
        parts.append(_ONES[hundred] + ' Hundred')
    if n:
        parts.append(_below_hundred(n))
    return ' '.join(p for p in parts if p).strip()


def rupees_in_words(amount):
    """Format a rupee amount as words, e.g. 'Rupees One Lakh ... and Fifty Paise Only'."""
    try:
        amount = round(float(amount or 0), 2)
    except (TypeError, ValueError):
        amount = 0.0
    negative = amount < 0
    amount = abs(amount)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    if paise == 100:  # rounding carried up
        rupees += 1
        paise = 0

    rupee_words = _in_words(rupees) or 'Zero'
    text = 'Rupees ' + rupee_words
    if paise:
        text += ' and ' + _in_words(paise) + ' Paise'
    text += ' Only'
    if negative:
        text = 'Minus ' + text
    return text
