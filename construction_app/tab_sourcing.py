"""Quotes, vendor rating, RFIs and drawing revisions (Phase 8, Wave 4).

* **Quotes** — record what each vendor offered against a requisition, then
  compare. The comparison reports the saving against the highest quote, which
  is what justifies bothering, and recommends a quote **with its reasoning**
  rather than silently picking the lowest number.
* **Vendor rating** — approved-vendor flag plus quality / delivery / price out
  of 5, ranked. Unrated vendors sort last rather than being assumed poor.
* **RFIs** — questions that stop work, with the date they were asked. An
  unanswered RFI is a delay with somebody else's name on it, which matters
  when the delay is eventually priced.
* **Drawings** — revision register. The whole discipline is that the latest
  revision is the one on site; building to a superseded drawing is rework
  nobody planned for, so the list flags exactly that.
"""

import tkinter as tk
import theme
from datetime import date
from tkinter import ttk, messagebox

import bill_export
import report_open
import sourcing
import submittals
from crud_frame import CrudFrame, Field, TODAY
from tab_masters import site_options, vendor_options
from tab_boq_ra import contract_options
from ui_guard import can_write


def _requisition_options(conn):
    return [(r['id'], '{}  {}'.format(r['req_no'] or 'REQ {}'.format(r['id']),
                                      r['req_date'] or ''))
            for r in conn.execute(
                'SELECT id, req_no, req_date FROM material_requisitions '
                'ORDER BY id DESC')]


def build_quotes(parent, db_getter):
    fields = [
        Field('requisition_id', 'Against requisition', kind='fk',
              options_func=_requisition_options),
        Field('vendor_id', 'Vendor', kind='fk', options_func=vendor_options),
        Field('quote_no', 'Quote No'),
        Field('quote_date', 'Date', default='TODAY'),
        Field('description', 'For'),
        Field('amount', 'Amount (pre-tax)', kind='number', default='0'),
        Field('delivery_date', 'Can deliver by'),
        Field('validity', 'Valid until'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'quotes', fields,
                     'Quotes — one quotation is not a price, it is an opening '
                     'position', order_by='requisition_id DESC, amount')


def build_rfis(parent, db_getter):
    fields = [
        Field('rfi_no', 'RFI No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('contract_id', 'Contract', kind='fk', options_func=contract_options),
        Field('raised_date', 'Raised', default='TODAY'),
        Field('raised_by', 'Raised by'),
        Field('subject', 'Subject'),
        Field('question', 'Question'),
        Field('required_by', 'Answer needed by'),
        Field('status', 'Status', kind='combo',
              options=['Open', 'Answered', 'Closed'], default='Open'),
        Field('answer', 'Answer'),
        Field('answered_date', 'Answered on'),
        Field('answered_by', 'Answered by'),
        Field('impact', 'Cost / time impact'),
    ]
    return CrudFrame(parent, db_getter, 'rfis', fields,
                     'Requests for information — an unanswered RFI is a delay '
                     'with someone else\'s name on it',
                     order_by='status, required_by, id DESC')


def build_drawings(parent, db_getter):
    fields = [
        Field('drawing_no', 'Drawing No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('title', 'Title'),
        Field('revision', 'Revision'),
        Field('revision_date', 'Revision date'),
        Field('received_date', 'Received', default='TODAY'),
        Field('issued_to_site', 'On site (1/0)', kind='number', default='0'),
        Field('superseded', 'Superseded (1/0)', kind='number', default='0'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'drawings', fields,
                     'Drawing revisions — the latest revision is the one that '
                     'should be on site', order_by='drawing_no, revision DESC')


class QuoteCompare(ttk.Frame):
    COLUMNS = ('vendor', 'quote', 'amount', 'delivery', 'vs_cheapest')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self._map = {}
        self.req_var = tk.StringVar()
        self.needed_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        self.rec_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Compare quotes',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='The three-quote rule is not bureaucracy — it is '
                             'the difference between a price and an opening '
                             'position.',
                  wraplength=700, justify='left', foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=4)
        ttk.Label(top, text='Requisition').pack(side='left')
        self.req_combo = ttk.Combobox(top, textvariable=self.req_var, width=26,
                                      state='readonly')
        self.req_combo.pack(side='left', padx=4)
        self.req_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_quotes())
        ttk.Label(top, text='Needed by').pack(side='left', padx=(10, 2))
        ttk.Entry(top, textvariable=self.needed_var, width=12).pack(side='left')
        ttk.Button(top, text='Compare', command=self.refresh_quotes).pack(side='left', padx=6)
        ttk.Button(top, text='Mark Selected As Chosen',
                   command=self.choose).pack(side='left')

        heads = {'vendor': 'Vendor', 'quote': 'Quote', 'amount': 'Amount',
                 'delivery': 'Can deliver', 'vs_cheapest': 'vs cheapest'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=8)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=170 if c == 'vendor' else 120,
                             anchor='e' if c in ('amount', 'vs_cheapest') else 'w')
        self.tree.tag_configure('best', background=theme.wash('good'))
        self.tree.pack(fill='x', padx=8, pady=4)

        ttk.Label(self, textvariable=self.rec_var, foreground=theme.palette()['info'],
                  font=('TkDefaultFont', 11, 'bold'), wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(6, 2))
        ttk.Label(self, textvariable=self.summary_var, wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(0, 6))
        ttk.Button(self, text='Print / Export', command=self.export) \
            .pack(anchor='w', padx=8, pady=(0, 8))

    def refresh(self):
        conn = self.db_getter()
        try:
            opts = _requisition_options(conn)
        finally:
            conn.close()
        self._map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.req_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
        self.refresh_quotes()

    def refresh_quotes(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        raw = self.req_var.get().strip()
        req_id = self._map.get(raw) if raw else None
        if req_id is None:
            self.summary_var.set('Pick a requisition to compare its quotes.')
            self.rec_var.set('')
            return
        conn = self.db_getter()
        try:
            quotes = conn.execute(
                'SELECT q.*, v.name AS vendor FROM quotes q '
                'LEFT JOIN vendors v ON v.id = q.vendor_id '
                'WHERE q.requisition_id = ?', (req_id,)).fetchall()
        finally:
            conn.close()

        result = sourcing.compare_quotes(quotes)
        needed = self.needed_var.get().strip() or None
        best, note = sourcing.recommendation(quotes, needed)
        cheapest = result['cheapest']
        low = float(cheapest['amount'] or 0) if cheapest is not None else 0

        for q in result['ranked']:
            diff = float(q['amount'] or 0) - low
            values = (q['vendor'] or '-', q['quote_no'] or '-',
                      '{:,.2f}'.format(float(q['amount'] or 0)),
                      q['delivery_date'] or '-',
                      '—' if diff == 0 else '+{:,.2f}'.format(diff))
            self._rows.append(values)
            self.tree.insert('', 'end', iid=str(q['id']), values=values,
                             tags=('best',) if best is not None and q['id'] == best['id'] else ())

        if result['priced']:
            self.summary_var.set(
                '{} quote(s), {} priced   ·   saving against the highest: '
                '{:,.2f}{}'.format(
                    result['count'], result['priced'], result['saving_vs_highest'],
                    '   ·   spread {:.0f}%'.format(result['spread_pct'])
                    if result['spread_pct'] is not None else ''))
        else:
            self.summary_var.set('No priced quotes against this requisition yet.')
        self.rec_var.set('Recommended: {}  —  {}'.format(
            best['vendor'] or 'vendor', note) if best is not None else note)

    def choose(self):
        if not can_write():
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a quote first.')
            return
        raw = self.req_var.get().strip()
        req_id = self._map.get(raw) if raw else None
        conn = self.db_getter()
        try:
            conn.execute('UPDATE quotes SET selected = 0 WHERE requisition_id = ?',
                         (req_id,))
            conn.execute('UPDATE quotes SET selected = 1 WHERE id = ?',
                         (int(sel[0]),))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo('Recorded',
                            'Marked as the chosen quote. Raise the purchase '
                            'order against this vendor.')
        self.refresh_quotes()

    def export(self):
        html = bill_export.build_statement_html(
            'Quote comparison', [self.rec_var.get(), self.summary_var.get()],
            ['Vendor', 'Quote', 'Amount', 'Can deliver', 'vs cheapest'],
            self._rows, summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'quote_comparison.html')


class VendorRating(ttk.Frame):
    COLUMNS = ('vendor', 'approved', 'quality', 'delivery', 'price', 'score')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Vendor rating',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Three factors out of 5. Unrated vendors sort '
                             'last rather than being assumed poor — an unrated '
                             'factor is unknown, not bad. Edit the scores on '
                             'the Vendors master.',
                  wraplength=700, justify='left', foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        heads = {'vendor': 'Vendor', 'approved': 'Approved', 'quality': 'Quality',
                 'delivery': 'Delivery', 'price': 'Price', 'score': 'Score'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=200 if c == 'vendor' else 100,
                             anchor='w' if c == 'vendor' else 'e')
        self.tree.tag_configure('approved', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        ttk.Button(self, text='Refresh', command=self.refresh) \
            .pack(anchor='w', padx=8, pady=(0, 8))

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            vendors = conn.execute(
                'SELECT id, name, approved, quality, delivery, price '
                'FROM vendors').fetchall()
        finally:
            conn.close()
        self._rows = []
        for v, score in sourcing.rank_vendors([dict(r) for r in vendors]):
            values = (v['name'], 'Yes' if v.get('approved') else '-',
                      v.get('quality') or '-', v.get('delivery') or '-',
                      v.get('price') or '-',
                      '-' if score is None else '{:.1f}'.format(score))
            self._rows.append(values)
            self.tree.insert('', 'end', values=values,
                             tags=('approved',) if v.get('approved') else ())


def build_submittals(parent, db_getter):
    """Register of proposed materials / makes / shop drawings awaiting approval.

    Kept separate from RFIs and drawing revisions on purpose (see the module
    docstring): a submittal asks *"is the make I propose acceptable?"*, which is
    a different question from an RFI and a different thing from a drawing copy.
    A resubmittal is entered as a new row; set its "Supersedes ID" to the prior
    submittal's id so the history is traceable.
    """
    fields = [
        Field('submittal_no', 'Submittal No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('contract_id', 'Contract', kind='fk', options_func=contract_options),
        Field('title', 'Title / make'),
        Field('submittal_type', 'Type', kind='combo',
              options=['Material', 'Make', 'Shop Drawing', 'Sample'],
              default='Material'),
        Field('spec_ref', 'Spec / BOQ ref'),
        Field('submitted_date', 'Submitted', default=TODAY),
        Field('submitted_by', 'Submitted by'),
        Field('required_by', 'Approval needed by'),
        Field('status', 'Status', kind='combo', options=list(submittals.STATUSES),
              default='Submitted'),
        Field('reviewer', 'Reviewer'),
        Field('reviewed_date', 'Reviewed on'),
        Field('review_remarks', 'Reviewer remarks'),
        Field('supersedes_id', 'Supersedes ID', kind='number', default=''),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'submittals', fields,
                     'Submittals — material / make approvals',
                     order_by="status, required_by, id DESC")


def build_sourcing_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(QuoteCompare(nb, db_getter), text='Compare Quotes')
    nb.add(build_quotes(nb, db_getter), text='Quotes')
    nb.add(VendorRating(nb, db_getter), text='Vendor Rating')
    nb.add(build_rfis(nb, db_getter), text='RFIs')
    nb.add(build_drawings(nb, db_getter), text='Drawings')
    nb.add(build_submittals(nb, db_getter), text='Submittals')
    return nb
