"""Approvals — one desk for everything waiting on a signature (Wave 3).

Rather than scattering an Approve button through every document tab, this is a
single queue: everything currently sitting in a draft or submitted state, newest
first, with its value. That suits how a small firm actually works — the owner
sits down once and clears the pile — and it makes "what is waiting on me?"
answerable, which is the question that never gets asked when approvals live on
eight different screens.

Approving does two things: it advances the document's own status, and it writes
an approval row recording **who** and **when**, plus an audit-log entry. That
pairing is the point — the status alone was never evidence.

Rejecting records the decision and leaves the document where it is, because a
rejected bill is not deleted, it is sent back.
"""

import tkinter as tk
import theme
from datetime import datetime
from tkinter import ttk, messagebox

import approval
import auth
import bill_export
import report_open
import session
from ui_guard import can_write

# doc_type -> SQL selecting (id, number, party, date, amount) of pending docs.
_PENDING_SQL = {
    'Estimate': (
        "SELECT e.id, COALESCE(e.est_number, 'EST ' || e.id) AS number, "
        "COALESCE(s.name,'-') AS party, e.estimate_date AS dt, "
        "e.total_estimate AS amount FROM estimates e "
        "LEFT JOIN sites s ON s.id = e.site_id WHERE e.status IN ('Draft')"),
    'PurchaseOrder': (
        "SELECT p.id, COALESCE(p.po_no, 'PO ' || p.id) AS number, "
        "COALESCE(v.name,'-') AS party, p.po_date AS dt, "
        "p.total_amount AS amount FROM purchase_orders p "
        "LEFT JOIN vendors v ON v.id = p.vendor_id WHERE p.status IN ('Draft')"),
    'Bill': (
        "SELECT b.id, COALESCE(b.bill_no, 'Bill ' || b.id) AS number, "
        "COALESCE(cl.name,'-') AS party, b.bill_date AS dt, "
        "b.net_payable AS amount FROM bills b "
        "LEFT JOIN contracts c ON c.id = b.contract_id "
        "LEFT JOIN clients cl ON cl.id = c.client_id "
        "WHERE b.status IN ('Draft','Submitted')"),
    'RABill': (
        "SELECT r.id, COALESCE(r.bill_no, 'RA ' || r.id) AS number, "
        "COALESCE(cl.name,'-') AS party, r.bill_date AS dt, "
        "r.net_payable AS amount FROM ra_bills r "
        "LEFT JOIN contracts c ON c.id = r.contract_id "
        "LEFT JOIN clients cl ON cl.id = c.client_id "
        "WHERE r.status IN ('Draft','Submitted')"),
    'SubBill': (
        "SELECT sb.id, COALESCE(sb.bill_no, 'Sub ' || sb.id) AS number, "
        "COALESCE(v.name,'-') AS party, sb.bill_date AS dt, "
        "sb.net_payable AS amount FROM sub_bills sb "
        "LEFT JOIN work_orders wo ON wo.id = sb.work_order_id "
        "LEFT JOIN vendors v ON v.id = wo.vendor_id WHERE sb.status IN ('Draft')"),
    'Variation': (
        "SELECT v.id, COALESCE(v.var_no, 'VO ' || v.id) AS number, "
        "COALESCE(c.contract_no,'-') AS party, v.var_date AS dt, "
        "v.amount AS amount FROM variations v "
        "LEFT JOIN contracts c ON c.id = v.contract_id WHERE v.status IN ('Raised')"),
}


def pending_documents(conn):
    """Everything currently waiting on a decision, newest first."""
    out = []
    for doc_type, sql in _PENDING_SQL.items():
        label = approval.APPROVABLE[doc_type][5]
        try:
            rows = conn.execute(sql).fetchall()
        except Exception:                                    # noqa: BLE001
            continue          # older file without that table — skip it
        for r in rows:
            out.append({
                'doc_type': doc_type, 'doc_id': r['id'], 'label': label,
                'number': r['number'], 'party': r['party'] or '-',
                'date': r['dt'] or '', 'amount': r['amount'] or 0,
            })
    return sorted(out, key=lambda d: str(d['date'] or ''), reverse=True)


def record(conn, doc_type, doc_id, action, note=''):
    """Record a decision and move the document's own status with it.

    The approval row is the evidence (who, when); the status change is what the
    rest of the app already reads. Writing both keeps them in step — a document
    marked Approved with no approval row would be exactly the gap this closes.
    """
    who = session.username() or 'local'
    when = datetime.now().isoformat(timespec='seconds')
    conn.execute(
        'INSERT INTO approvals (doc_type, doc_id, action, approved_by, '
        'approved_at, note) VALUES (?, ?, ?, ?, ?, ?)',
        (doc_type, doc_id, action, who, when, note))
    if action == approval.APPROVED:
        table, _num, status_col, _pending, new_status, _label = \
            approval.APPROVABLE[doc_type]
        conn.execute('UPDATE {} SET {} = ? WHERE id = ?'.format(table, status_col),
                     (new_status, doc_id))
    auth.audit(conn, who, action, doc_type, doc_id, note or None)
    conn.commit()
    return when


class ApprovalsTab(ttk.Frame):
    COLUMNS = ('type', 'number', 'party', 'date', 'amount')
    HIST = ('when', 'type', 'doc', 'action', 'by')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._pending = []
        self._rows = []
        self.summary_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Waiting for approval',
                  font=('TkDefaultFont', 13, 'bold')) \
            .pack(anchor='w', padx=8, pady=(10, 2))
        ttk.Label(self, text='Everything sitting in draft, in one queue. '
                             'Approving records who signed and when — a status '
                             'anyone can change is not evidence.',
                  wraplength=720, justify='left', foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=(0, 4))

        heads = {'type': 'Document', 'number': 'No.', 'party': 'Party / site',
                 'date': 'Date', 'amount': 'Value'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=10)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=150 if c in ('type', 'party') else 120,
                             anchor='e' if c == 'amount' else 'w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 6))
        ttk.Button(btns, text='Approve', command=lambda: self.decide(approval.APPROVED)).pack(side='left')
        ttk.Button(btns, text='Reject', command=lambda: self.decide(approval.REJECTED)).pack(side='left', padx=6)
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(btns, text='Print / Export', command=self.export).pack(side='left', padx=6)

        ttk.Label(self, text='Recent decisions',
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=(6, 2))
        heads2 = {'when': 'When', 'type': 'Document', 'doc': 'ID',
                  'action': 'Decision', 'by': 'By'}
        self.hist = ttk.Treeview(self, columns=self.HIST, show='headings', height=6)
        for c in self.HIST:
            self.hist.heading(c, text=heads2[c])
            self.hist.column(c, width=150 if c == 'when' else 110, anchor='w')
        self.hist.tag_configure('rej', foreground=theme.palette()['error'])
        self.hist.pack(fill='both', expand=True, padx=8, pady=(0, 10))

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.hist.get_children():
            self.hist.delete(item)
        conn = self.db_getter()
        try:
            self._pending = pending_documents(conn)
            history = conn.execute(
                'SELECT * FROM approvals ORDER BY id DESC LIMIT 50').fetchall()
        finally:
            conn.close()

        self._rows = []
        for d in self._pending:
            values = (d['label'], d['number'], d['party'], d['date'] or '-',
                      '{:,.2f}'.format(float(d['amount'] or 0)))
            self._rows.append(values)
            self.tree.insert('', 'end',
                             iid='{}:{}'.format(d['doc_type'], d['doc_id']),
                             values=values)

        s = approval.summarise(self._pending)
        if s['count']:
            parts = ', '.join('{} {}'.format(v['count'], k.lower())
                              for k, v in sorted(s['by_type'].items()))
            self.summary_var.set(
                '{} document(s) worth {:,.2f} waiting — {}.  Largest single '
                'item {:,.2f}.'.format(s['count'], s['amount'], parts, s['largest']))
        else:
            self.summary_var.set('Nothing is waiting for approval.')

        for h in history:
            self.hist.insert('', 'end', values=(
                h['approved_at'] or '-', h['doc_type'], h['doc_id'],
                h['action'], h['approved_by'] or '-'),
                tags=('rej',) if h['action'] == approval.REJECTED else ())

    def decide(self, action):
        if not can_write():
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a document first.')
            return
        doc_type, doc_id = sel[0].split(':')
        doc = next((d for d in self._pending
                    if d['doc_type'] == doc_type and str(d['doc_id']) == doc_id), None)
        if doc is None:
            return
        verb = 'Approve' if action == approval.APPROVED else 'Reject'
        if not messagebox.askyesno(
                verb, '{} {} {} for {:,.2f}?\n\nThis records your name and the '
                'time against it.'.format(verb, doc['label'].lower(),
                                          doc['number'], float(doc['amount'] or 0))):
            return
        conn = self.db_getter()
        try:
            record(conn, doc_type, int(doc_id), action)
        finally:
            conn.close()
        self.refresh()

    def export(self):
        html = bill_export.build_statement_html(
            'Waiting for approval', [self.summary_var.get()],
            ['Document', 'No.', 'Party / site', 'Date', 'Value'], self._rows,
            summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'approvals_pending.html')


def build_approvals_tab(parent, db_getter):
    return ApprovalsTab(parent, db_getter)
