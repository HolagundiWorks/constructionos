"""Variations / change orders — the revenue-protection register (Phase 8).

Two views:

* **Variations** — the register itself. A ``CrudFrame`` per the usual pattern,
  with ``amount`` derived from qty x rate on save (never hand-entered), and a
  ``var_no`` filled in automatically per contract when left blank.
* **Position** — the point of the whole feature: per contract, how much is
  still awaiting approval, and above all **how much is approved but not yet
  billed**. That last figure is work the client has already agreed to pay for
  that nobody has asked for — the leak this register exists to close.

All arithmetic lives in ``variation.py`` so it can be tested without a display.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import theme

import bill_export
import event_hooks
import followups
import report_open
import variation
from crud_frame import CrudFrame, Field
from tab_boq_ra import contract_options
from ui_guard import can_write


def _compute_amount(conn, row_id, values):
    """Derive amount = qty x rate, and auto-number within the contract.

    Best-effort like the other on_save hooks (hire total, cube strength): it
    never raises, because a failed auto-fill must not block the user's save.
    """
    try:
        amount = variation.variation_amount(values.get('qty', 0),
                                            values.get('rate', 0))
        conn.execute('UPDATE variations SET amount = ? WHERE id = ?',
                     (amount, row_id))
        if not (values.get('var_no') or '').strip():
            contract_id = values.get('contract_id')
            existing = [r['var_no'] for r in conn.execute(
                'SELECT var_no FROM variations WHERE contract_id = ? AND id != ?',
                (contract_id, row_id))]
            conn.execute('UPDATE variations SET var_no = ? WHERE id = ?',
                         (variation.next_var_no(existing), row_id))
        conn.commit()
    except Exception:                                        # noqa: BLE001
        pass


def _on_variation_save(conn, row_id, values):
    """Amount auto-fill + gated follow-ups when a variation is Approved."""
    _compute_amount(conn, row_id, values)
    if (values.get('status') or '') != variation.APPROVED:
        return
    try:
        result = event_hooks.react(followups.VARIATION_APPROVED, {
            'variation_id': row_id,
            'contract_id': values.get('contract_id'),
        })
        steps = result.get('followups') or []
        if not steps:
            return
        lines = []
        for f in steps:
            tag = '  [needs your approval]' if f.get('gated') else ''
            lines.append('• {} — {}{}'.format(
                f.get('action', ''), f.get('where', ''), tag))
        messagebox.showinfo(
            'Suggested next steps',
            'Variation approved. Draft follow-ups '
            '(nothing was auto-posted):\n\n' + '\n'.join(lines))
    except Exception:                                        # noqa: BLE001
        pass


def build_register(parent, db_getter):
    fields = [
        Field('contract_id', 'Contract', kind='fk', options_func=contract_options),
        Field('var_no', 'Variation No'),
        Field('var_date', 'Date', default='TODAY'),
        Field('description', 'Description of extra work'),
        Field('reason', 'Reason', kind='combo',
              options=['Client instruction', 'Site condition', 'Design change',
                       'Quantity variation', 'Other'],
              default='Client instruction'),
        Field('reference', 'Letter / Email Ref'),
        Field('unit', 'Unit'),
        Field('qty', 'Qty', kind='number', default='0'),
        Field('rate', 'Rate', kind='number', default='0'),
        Field('status', 'Status', kind='combo', options=variation.STATUSES,
              default=variation.RAISED),
        Field('approved_by', 'Approved By'),
        Field('approved_date', 'Approved On'),
        Field('billed_in', 'Billed In (bill no)'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'variations', fields,
                     'Variations / Change Orders', on_save=_on_variation_save)


class VariationPosition(ttk.Frame):
    """Per-contract variation position, headlining approved-but-unbilled."""

    COLUMNS = ('contract', 'raised', 'approved', 'billed', 'original',
               'revised', 'pct')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.headline_var = tk.StringVar(value='')
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Variation Position',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Extra work that is approved but not yet billed is '
                             'money the client has already agreed to pay and '
                             'nobody has asked for. Bill it.',
                  wraplength=680, justify='left', foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        self.headline = ttk.Label(self, textvariable=self.headline_var,
                                  font=('TkDefaultFont', 12, 'bold'))
        self.headline.pack(anchor='w', padx=8, pady=(0, 6))

        heads = {'contract': 'Contract', 'raised': 'Awaiting approval',
                 'approved': 'Approved, NOT billed', 'billed': 'Billed',
                 'original': 'Original value', 'revised': 'Revised value',
                 'pct': 'Variation %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=12)
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=170 if col == 'contract' else 120,
                             anchor='w' if col == 'contract' else 'e')
        self.tree.tag_configure('chase', background=theme.wash('warn'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(btns, text='Export', command=self.export).pack(side='left', padx=6)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        conn = self.db_getter()
        try:
            contracts = conn.execute(
                'SELECT id, contract_no, contract_value FROM contracts '
                'ORDER BY id DESC').fetchall()
            per_contract = {}
            for r in conn.execute('SELECT * FROM variations'):
                per_contract.setdefault(r['contract_id'], []).append(r)
        finally:
            conn.close()

        total_unbilled = 0.0
        for c in contracts:
            rows = per_contract.get(c['id'], [])
            if not rows:
                continue
            s = variation.summarise(rows)
            impact = variation.contract_impact(c['contract_value'], rows)
            total_unbilled += s['approved_unbilled']
            name = c['contract_no'] or 'Contract {}'.format(c['id'])
            values = (
                name,
                '{:,.2f}'.format(s['pending_approval']),
                '{:,.2f}'.format(s['approved_unbilled']),
                '{:,.2f}'.format(s['billed']),
                '{:,.2f}'.format(impact['original_value']),
                '{:,.2f}'.format(impact['revised_value']),
                '-' if impact['variation_pct'] is None
                else '{:.1f}%'.format(impact['variation_pct']),
            )
            self._rows.append(values)
            self.tree.insert('', 'end', values=values,
                             tags=('chase',) if s['approved_unbilled'] else ())

        if not self._rows:
            self.headline_var.set('No variations recorded yet.')
        elif total_unbilled:
            self.headline_var.set(
                'Approved but NOT yet billed:  {:,.2f}   '
                '— bill this before the final account.'.format(total_unbilled))
        else:
            self.headline_var.set(
                'Nothing approved is waiting to be billed. Good.')

    def export(self):
        headers = ['Contract', 'Awaiting approval', 'Approved not billed',
                   'Billed', 'Original value', 'Revised value', 'Variation %']
        html = bill_export.build_statement_html(
            'Variation Position', [self.headline_var.get()],
            headers, self._rows, summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'variation_position.html')


def build_variations_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(build_register(nb, db_getter), text='Variations')
    nb.add(VariationPosition(nb, db_getter), text='Position')
    return nb
