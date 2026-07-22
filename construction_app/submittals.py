"""Pure submittal lifecycle helpers (document control).

No tkinter, no database. A **submittal** is the pre-execution approval of a
proposed material / make / shop drawing — distinct from an RFI (a question about
the documents) and a drawing revision (which copy is current). These helpers
classify a submittal's status and decide whether one is overdue, so the register
tab and the dashboard read the same rules. Exercised with ``python -c``.
"""

import ageing

# The lifecycle. "Approved as noted" proceeds like Approved but flags conditions;
# "Revise & resubmit" is answered but not cleared — a new (superseding) row
# follows. Only "Submitted" is still awaiting the reviewer.
STATUSES = ('Submitted', 'Approved', 'Approved as noted', 'Revise & resubmit',
            'Rejected')
OPEN_STATUSES = ('Submitted',)
APPROVED_STATUSES = ('Approved', 'Approved as noted')


def is_open(status):
    """True while the submittal is still awaiting the reviewer's decision."""
    return status in OPEN_STATUSES


def is_approved(status):
    """True when the proposed item may be ordered/installed (incl. as-noted)."""
    return status in APPROVED_STATUSES


def is_overdue(required_by, status, as_on=None):
    """True when an open submittal has passed its required-by date.

    A decided submittal (approved/rejected/resubmit) is never overdue — the ball
    is no longer in the reviewer's court. A blank required-by is not overdue
    (no deadline was set).
    """
    if not is_open(status) or not required_by:
        return False
    return ageing.days_between(required_by, as_on) > 0
