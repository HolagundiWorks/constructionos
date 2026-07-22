"""Bid / no-bid scorecard.

Six judgement factors scored 1-5 against anchored descriptions, plus evidence
pulled from the firm's own ledger — whether this client has actually paid, how
much of our money is already with them, and how full the order book is.

The vetoes are the point. A weighted average lets five comfortable scores
drown out one fatal factor, so conditions that should end the conversation sit
outside the score and override it.
"""

import branding
import json
import theme
import tkinter as tk
from tkinter import ttk, messagebox

from ui_guard import can_write

import allocation
import bidding
import bill_export
import report_open


def _company_name(conn):
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
    return (row['value'] if row and row['value'] else '') or branding.APP_NAME


def _capacity(conn):
    """Annual turnover the firm reckons it can deliver (Tools > Firm Details)."""
    row = conn.execute("SELECT value FROM app_settings "
                       "WHERE key = 'annual_capacity'").fetchone()
    try:
        return float(row['value']) if row and row['value'] else 0.0
    except (TypeError, ValueError):
        return 0.0


def client_position(conn, client_id):
    """What this client owes us, aged — from bills, invoices and receipts."""
    if not client_id:
        return {}
    docs = []
    for sql, dtype in (
            ("SELECT id, bill_date AS d, net_payable AS amt FROM bills "
             "WHERE contract_id IN (SELECT id FROM contracts WHERE client_id = ?) "
             "AND status IN ('Approved','Paid')", 'Bill'),
            ("SELECT id, bill_date AS d, net_payable AS amt FROM ra_bills "
             "WHERE contract_id IN (SELECT id FROM contracts WHERE client_id = ?) "
             "AND status IN ('Approved','Paid')", 'RABill'),
            ("SELECT id, invoice_date AS d, total_amount AS amt "
             "FROM tax_invoices WHERE client_id = ?", 'TaxInvoice')):
        try:
            for r in conn.execute(sql, (client_id,)):
                docs.append({'doc_type': dtype, 'doc_id': r['id'],
                             'date': r['d'], 'amount': r['amt'] or 0})
        except Exception:
            continue          # a table this build does not have — skip it
    allocs = [dict(r) for r in conn.execute(
        'SELECT doc_type, doc_id, amount FROM payment_allocations')]
    receipts = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM payments "
        "WHERE direction = 'Receipt' AND party_type = 'Client' AND party_id = ?",
        (client_id,)).fetchone()['t']
    allocated = sum(a['amount'] or 0 for a in allocs)
    return allocation.party_position(docs, allocs,
                                     max(receipts - allocated, 0))


def retention_with_client(conn, client_id):
    """Retention withheld by this client across their bills."""
    if not client_id:
        return 0.0
    total = 0.0
    for sql in ("SELECT COALESCE(SUM(retention_amt), 0) AS t FROM ra_bills "
                "WHERE contract_id IN (SELECT id FROM contracts "
                "WHERE client_id = ?)",
                "SELECT COALESCE(SUM(retention_amt), 0) AS t FROM bills "
                "WHERE contract_id IN (SELECT id FROM contracts "
                "WHERE client_id = ?)"):
        try:
            total += conn.execute(sql, (client_id,)).fetchone()['t'] or 0
        except Exception:
            continue
    return round(total, 2)


def committed_workload(conn):
    """Value of work already on the books (active projects and contracts)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(contract_value), 0) AS t FROM contracts "
        "WHERE status = 'Active'").fetchone()
    return round(row['t'] or 0, 2)


class BidScorecard(ttk.Frame):
    COLUMNS = ('id', 'tender_ref', 'title', 'tender_value', 'score',
               'verdict', 'decision', 'outcome')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._cmap = {}
        self._assessment = {}
        self.h = {k: tk.StringVar() for k in
                  ('tender_ref', 'title', 'tender_value', 'submission_date',
                   'notes')}
        self.client_var = tk.StringVar()
        self.decision_var = tk.StringVar(value='Not decided')
        self.outcome_var = tk.StringVar(value='Pending')
        self.factor_vars = {f['key']: tk.StringVar() for f in bidding.FACTORS}
        self.verdict_var = tk.StringVar()
        self.evidence_var = tk.StringVar()
        self.veto_var = tk.StringVar()
        self.warn_var = tk.StringVar()
        self._build_ui()
        self.reload()

    def _build_ui(self):
        hdr = ttk.LabelFrame(self, text='Tender')
        hdr.pack(fill='x', padx=8, pady=(8, 4))
        entries = [('tender_ref', 'Tender Ref', 14), ('title', 'Work', 34),
                   ('tender_value', 'Tender Value', 14),
                   ('submission_date', 'Submit By', 14)]
        for idx, (key, label, w) in enumerate(entries):
            cell = ttk.Frame(hdr)
            cell.grid(row=idx // 2, column=idx % 2, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=13).pack(side='left')
            ttk.Entry(cell, textvariable=self.h[key], width=w).pack(side='left')
        cell = ttk.Frame(hdr); cell.grid(row=2, column=0, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text='Client', width=13).pack(side='left')
        self.client_combo = ttk.Combobox(cell, textvariable=self.client_var,
                                         width=24, state='readonly')
        self.client_combo.pack(side='left')
        self.client_combo.bind('<<ComboboxSelected>>', lambda e: self.recalc())
        cell = ttk.Frame(hdr); cell.grid(row=2, column=1, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text='Notes', width=13).pack(side='left')
        ttk.Entry(cell, textvariable=self.h['notes'], width=44).pack(side='left')

        scores = ttk.LabelFrame(self, text='Judgement — 1 is the worst case, '
                                           '5 the best')
        scores.pack(fill='x', padx=8, pady=4)
        for idx, f in enumerate(bidding.FACTORS):
            ttk.Label(scores, text='{} ({}%)'.format(f['name'], f['weight']),
                      width=32).grid(row=idx, column=0, padx=6, pady=2, sticky='w')
            combo = ttk.Combobox(scores, textvariable=self.factor_vars[f['key']],
                                 width=4, state='readonly',
                                 values=['', '1', '2', '3', '4', '5'])
            combo.grid(row=idx, column=1, padx=4, pady=2)
            combo.bind('<<ComboboxSelected>>', lambda e: self.recalc())
            ttk.Label(scores, text='1 = {}   |   5 = {}'.format(
                f['low'], f['high']), foreground=theme.palette()['muted']).grid(
                row=idx, column=2, padx=8, pady=2, sticky='w')

        out = ttk.Frame(self); out.pack(fill='x', padx=8, pady=4)
        ttk.Label(out, textvariable=self.verdict_var,
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        ttk.Label(out, textvariable=self.evidence_var, foreground=theme.palette()['muted'],
                  wraplength=980, justify='left').pack(anchor='w')
        ttk.Label(out, textvariable=self.veto_var, foreground=theme.palette()['error'],
                  wraplength=980, justify='left').pack(anchor='w', pady=(4, 0))
        ttk.Label(out, textvariable=self.warn_var, foreground=theme.palette()['warning'],
                  wraplength=980, justify='left').pack(anchor='w')

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=4)
        ttk.Button(btns, text='New', command=self.new).pack(side='left', padx=3)
        ttk.Button(btns, text='Save', command=self.save).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Label(btns, text='   We decided').pack(side='left')
        ttk.Combobox(btns, textvariable=self.decision_var, width=12,
                     state='readonly',
                     values=['Not decided', 'Bid', 'No bid']).pack(side='left', padx=4)
        ttk.Label(btns, text='Outcome').pack(side='left')
        ttk.Combobox(btns, textvariable=self.outcome_var, width=11,
                     state='readonly',
                     values=['Pending', 'Won', 'Lost', 'Withdrawn']).pack(
            side='left', padx=4)
        ttk.Button(btns, text='Print / Export',
                   command=self.export).pack(side='right', padx=3)

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=7)
        headings = {'id': 'ID', 'tender_ref': 'Ref', 'title': 'Work',
                    'tender_value': 'Value', 'score': 'Score',
                    'verdict': 'Advice', 'decision': 'We Decided',
                    'outcome': 'Outcome'}
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=50 if col == 'id' else
                             (220 if col == 'title' else 120), anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        ttk.Label(self, text=(
            'The verdict is advice, not a decision — you know things the '
            'ledger does not. The red lines are the ones worth arguing with: '
            'they cite evidence rather than a number. Recording what you '
            'actually decided and how it turned out is what lets the scoring '
            'be checked against reality later.'),
            foreground=theme.palette()['muted'], wraplength=980, justify='left') \
            .pack(anchor='w', padx=10, pady=(0, 8))

    # ------------------------------------------------------------ loading
    def reload(self):
        conn = self.db_getter()
        try:
            opts = [(r['id'], r['name']) for r in conn.execute(
                'SELECT id, name FROM clients ORDER BY name')]
        finally:
            conn.close()
        self._cmap = {'{} - {}'.format(i, n): i for i, n in opts}
        self.client_combo['values'] = [''] + list(self._cmap)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            rows = conn.execute(
                'SELECT id, tender_ref, title, tender_value, score, verdict, '
                'decision, outcome FROM bid_assessments ORDER BY id DESC'
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            self.tree.insert('', 'end', iid=str(r['id']), values=(
                r['id'], r['tender_ref'] or '', r['title'] or '',
                '{:,.2f}'.format(r['tender_value'] or 0),
                '{:g}'.format(r['score']) if r['score'] is not None else '—',
                r['verdict'] or '—', r['decision'] or '', r['outcome'] or ''))
        self.recalc()

    def _client_id(self):
        return self._cmap.get(self.client_var.get().strip())

    def _judgements(self):
        return {k: v.get() for k, v in self.factor_vars.items() if v.get()}

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM bid_assessments WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        for key in ('tender_ref', 'title', 'notes'):
            self.h[key].set(r[key] or '')
        self.h['tender_value'].set('{:g}'.format(r['tender_value'] or 0))
        self.h['submission_date'].set(r['submission_date'] or '')
        self.decision_var.set(r['decision'] or 'Not decided')
        self.outcome_var.set(r['outcome'] or 'Pending')
        self.client_var.set('')
        for disp, cid in self._cmap.items():
            if cid == r['client_id']:
                self.client_var.set(disp); break
        try:
            saved = json.loads(r['scores'] or '{}')
        except ValueError:
            saved = {}
        for key, var in self.factor_vars.items():
            var.set(str(saved.get(key, '')))
        self.recalc()

    # -------------------------------------------------------- computation
    def _evidence(self, conn):
        cid = self._client_id()
        try:
            value = float(self.h['tender_value'].get().strip() or 0)
        except ValueError:
            value = 0.0
        client = bidding.client_evidence(
            client_position(conn, cid), retention_with_client(conn, cid), value)
        work = bidding.workload_evidence(committed_workload(conn),
                                         _capacity(conn), value)
        return client, work

    def recalc(self):
        conn = self.db_getter()
        try:
            client, work = self._evidence(conn)
        finally:
            conn.close()
        result = bidding.assess(self._judgements(), client, work)
        self._assessment = result

        total = result['score']
        self.verdict_var.set('{}    (score {}{})'.format(
            result['verdict'],
            '{:g}'.format(total) if total is not None else 'not yet scored',
            ', {} of {} factors scored'.format(result['scored'],
                                               result['factors'])
            if total is not None and result['scored'] < result['factors'] else ''))

        bits = []
        if client['has_history']:
            bits.append('This client owes {:,.2f}{}'.format(
                client['outstanding'],
                ', {:,.2f} of it more than 60 days old'.format(
                    client['aged_overdue']) if client['aged_overdue'] else
                ' and nothing is overdue'))
        if client['retention_held']:
            bits.append('{:,.2f} of our retention sits with them'.format(
                client['retention_held']))
        if work['utilisation_pct'] is not None:
            bits.append('order book at {:g}% of capacity'.format(
                work['utilisation_pct']))
        elif work['committed']:
            bits.append('{:,.2f} of work already committed (set an annual '
                        'capacity in Tools to see utilisation)'.format(
                            work['committed']))
        self.evidence_var.set('Evidence: ' + '.  '.join(bits) + '.'
                              if bits else '')
        self.veto_var.set('\n'.join('STOP — ' + v for v in result['vetoes']))
        self.warn_var.set('\n'.join(result['warnings']))

    # ------------------------------------------------------------ writes
    def new(self):
        self.selected_id = None
        for var in self.h.values():
            var.set('')
        self.client_var.set('')
        self.decision_var.set('Not decided')
        self.outcome_var.set('Pending')
        for var in self.factor_vars.values():
            var.set('')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.recalc()

    def _values(self):
        try:
            value = float(self.h['tender_value'].get().strip() or 0)
        except ValueError:
            value = 0.0
        result = self._assessment or {}
        return (self.h['tender_ref'].get().strip(),
                self.h['title'].get().strip(), self._client_id(), value,
                self.h['submission_date'].get().strip(),
                json.dumps(self._judgements()), result.get('score'),
                result.get('verdict', ''), self.decision_var.get(),
                self.outcome_var.get(), self.h['notes'].get().strip())

    def save(self):
        if not can_write():
            return
        if not self.h['title'].get().strip():
            messagebox.showinfo('Missing', 'Enter what the work is.')
            return
        self.recalc()
        vals = self._values()
        conn = self.db_getter()
        try:
            if self.selected_id is None:
                cur = conn.execute(
                    'INSERT INTO bid_assessments (tender_ref, title, client_id, '
                    'tender_value, submission_date, scores, score, verdict, '
                    'decision, outcome, notes) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', vals)
                self.selected_id = cur.lastrowid
            else:
                conn.execute(
                    'UPDATE bid_assessments SET tender_ref = ?, title = ?, '
                    'client_id = ?, tender_value = ?, submission_date = ?, '
                    'scores = ?, score = ?, verdict = ?, decision = ?, '
                    'outcome = ?, notes = ? WHERE id = ?',
                    vals + (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.refresh()
        if self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))

    def delete(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an assessment.')
            return
        if not messagebox.askyesno('Delete', 'Delete this assessment?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM bid_assessments WHERE id = ?',
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.new()
        self.refresh()

    def export(self):
        result = self._assessment or {}
        if not result:
            messagebox.showinfo('Nothing to export', 'Score a tender first.')
            return
        rows = []
        judgements = self._judgements()
        for f in bidding.FACTORS:
            raw = judgements.get(f['key'])
            rows.append((f['name'], '{}%'.format(f['weight']),
                         raw or '—',
                         f['high'] if str(raw) in ('4', '5') else
                         f['low'] if str(raw) in ('1', '2') else ''))
        total = result['score']
        lines = ['Tender: {}'.format(self.h['tender_ref'].get() or '-'),
                 'Client: {}'.format(self.client_var.get() or '-'),
                 'Value: {}'.format(self.h['tender_value'].get() or '-'),
                 self.evidence_var.get()]
        for v in result['vetoes']:
            lines.append('STOP — ' + v)
        for w in result['warnings']:
            lines.append(w)
        conn = self.db_getter()
        try:
            company = _company_name(conn)
        finally:
            conn.close()
        html = bill_export.build_statement_html(
            'Bid / no-bid assessment — {}'.format(self.h['title'].get() or ''),
            lines, ['Factor', 'Weight', 'Score', 'What that means'], rows,
            summary='{}   (score {})'.format(
                result['verdict'],
                '{:g}'.format(total) if total is not None else 'not scored'),
            company_name=company)
        report_open.save_and_open_html(html, 'bid_assessment.html')


def build_bidding_tab(parent, db_getter):
    return BidScorecard(parent, db_getter)
