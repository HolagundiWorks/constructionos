# Changelog — Construction OS

Notable changes, newest first. Dates are `YYYY-MM-DD`. This log records *what*
changed and *where* it lives; `docs/ROADMAP.md` tracks the phase status and
`AGENTS.md` §23 documents the architecture of the later modules.

---

## 2026-07-19 — Backlog completion (autopilot pass)

Completed the remaining planned (⏳) items across every roadmap phase. All new
business maths lives in pure, `python -c`-testable modules; all 31 tabs build
clean. Founding constraints unchanged (Python stdlib only, tkinter, single
SQLite file, no pip).

### Phase 2 — Get paid & submit (now ✅)
- **Print / Export on every document** — `report_open.save_and_open_html`
  helper; DocumentFrame "Print / Export" (quotations, POs) and a vendor-invoice
  export with GST/TDS breakup.
- **Configurable invoice number series** — `numbering.py` (Indian financial
  year, prefix + FY-reset formatting, next-serial by scanning numbers in use);
  tax-invoice auto-numbering honours it (e.g. `INV/2026-27/001`). Config in
  Tools → Invoice Number Series.
- **Rate Book / Specification library** — `rate_book` table + master under
  Billing (schedule of standard priced items with specs).
- **PWD deviation statement** — `civil.deviation` + a Deviation view in
  BOQ / RA Bills (tendered vs executed → excess/saving).

### Phase 3 — Labour (now ✅)
- **Optional PF / ESI / labour-cess** — `statutory.py` (EPF, ESI split, BOCW
  cess); optional `pf_no`/`esi_no` on the labour master; a standalone
  "Statutory" calculator under Muster & Wages. Nothing auto-deducts.

### Phase 4 — Trust & ease (now ✅)
- **First-run setup wizard** (`tab_wizard.py`) — firm details + first site +
  first client, shown once on a fresh book.
- **Guided low-typing entry** — `CrudFrame`/`Field` `default=TODAY` and
  `remember=True`: dates prefill today, Site (etc.) remembers the last choice
  per table+column. Applied across the ops tabs.
- **Vernacular UI** (`i18n.py`) — Hindi/Hinglish navigation labels with English
  fallback; language toggle in Tools.
- **App-wide error safety net** (`errors.py`) — a Tk `report_callback_exception`
  handler turns any uncaught callback error into a plain-language dialog (full
  traceback still logged). No stack trace ever reaches the user.

### Phase 5 — Compliance (now ✅)
- **RA / running bills in Output GST** — outward GST now spans tax invoices +
  RA + running bills (works-contract supply at a configurable Works GST %), with
  a Source column so RA-only billers are covered.
- **HSN-wise summary** — GSTR-1-style HSN/SAC taxable + CGST/SGST/IGST.

### Phase 6 — Insight (now ✅)
- **Receivable / payable ageing** (`ageing.py`) — FIFO-settle dated bills by
  receipts/payments, bucket the remainder 0-30/30-60/60-90/90+.
- **Contract / BOQ progress %** and **material budget vs actual** (value)
  (`analytics.py`).

### Phase 7 — Advanced (mostly ✅)
- **P&L + Balance Sheet** on the posted ledger (`reports.py`) in Accounting.
- **Payroll & subcontractor auto-posting** — `posting.payroll_lines`,
  `posting.sub_bill_lines`, and new `journal_post` loops (idempotent).
- **Subcontractor / work-order billing** — `subcontract.py`, tables
  `work_orders` (+items) and `sub_bills`, and `tab_subcontract.py` (work orders +
  sub running bills with retention & works-contract TDS).

### Assistant
- Schema docs + few-shot examples extended to the new modules (subcontractors,
  work orders, rate book, BOQ); results render a monospace **bar chart** for
  (label, number) answers (`assistant.text_bar_chart`).

### Schema additions
- Tables: `work_orders`, `work_order_items`, `sub_bills`, `rate_book`.
- Columns: `materials.rate`, `labor.pf_no`, `labor.esi_no` (idempotent
  migrations in `db._ADD_COLUMNS`).
- `app_settings` config keys: `works_gst_pct`, `invoice_prefix` /
  `invoice_width` / `invoice_fy_reset`, `language`, `setup_done`, and
  `last:<table>:<column>` remember-last values.

### New modules (all pure unless noted)
`report_open.py` (DB/tk helper), `numbering.py`, `ageing.py`, `analytics.py`,
`reports.py`, `subcontract.py`, `statutory.py`, `i18n.py`, `errors.py` (tk),
`tab_subcontract.py`, `tab_statutory.py`, `tab_wizard.py`.
