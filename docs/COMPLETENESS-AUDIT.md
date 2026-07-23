# Documentation vs shipped code — completeness audit

**Date:** 2026-07-23  
**Baseline:** `main` @ `22e4006` (API **u0.11**, **728** tests / 5 skipped)  
**Scope:** Claims in `ROADMAP.md`, `CLOUD-TASKS.md`, `WINUI3-MIGRATION.md`,
`PRODUCT.md`, `AGENTS.md`, `CLAUDE.md` vs what the tree actually contains.  
**Companion reports:** [`RESEARCH-COMPETITIVE-CASE-STUDY.md`](RESEARCH-COMPETITIVE-CASE-STUDY.md),
[`RESEARCH-OPTIMISATION-AND-PRECISION.md`](RESEARCH-OPTIMISATION-AND-PRECISION.md).

---

## 1. Executive scorecard

| Claim domain | Doc status | Code reality | Grade |
|---|---|---|---|
| Desktop ERP (tkinter) feature surface | ✅ Shipped | Present end-to-end; headless-tested maths | **A** |
| Cloud JSON API + CT-1…CT-10 | ✅ Shipped u0.11 | Present + `TestWebApi` | **A** |
| Multi-company + select-then-login | ✅ Shipped | Present (registry, web, API) | **A** |
| WinUI U0–U6 “built + runs” | ✅ | Client code + packaging scripts present; not re-verified on this Linux host | **A−** (trust local Windows evidence) |
| WinUI U5/U7 “every tab live / no placeholders / parity” | ✅ / 🚧 | **Nav-wired yes; feature-depth no** — several tabs open thin/wrong pages | **C+** (overclaim) |
| PRODUCT “no roles / not ERP” | Non-goals | Opt-in roles **exist**; product *is* a focused ERP | **B−** (stale framing) |
| AGENTS headline counts | ~150 modules / 82 tables / 628 tests | **180** modules / **85** tables / **728** tests | **C** (stale numbers) |
| AI “built-in model / Foundry verified” | ✅ | Code paths exist; weights/sidecars soft-stub | **B** (runtime-dependent) |
| L8 OCR/STT/VLM | ⏳ | Stub server + empty folders only | **Accurate** |

**Verdict:** Documentation is **excellent on the Python/desktop/API spine** and
**over-optimistic on WinUI functional parity**. “Every menu tab is a live page”
is true as *navigation*, false as *desktop-equivalent workflow*.

---

## 2. Verified inventory (evidence)

| Metric | Value | How measured |
|---|---|---|
| `construction_app/*.py` | **180** | filesystem |
| AST tkinter-free | **117** | import graph |
| `tab_*.py` | **55** | filesystem |
| `SECTIONS_CATALOG` labels | **52** | `modules.ALL_MODULES` |
| `CREATE TABLE` | **85** | `db.py` |
| Indexes | **61** | `db.py` |
| API | **u0.11** | `webapi` health/contract |
| Masters / money docs / register tables | 12 / 5 / 21 | `webapi` whitelists |
| WinUI Views | **22** `.xaml` pages | filesystem |
| Unittest | **728** OK, **5** skipped | `unittest discover` this host |

Cloud environment limits: **no display, no .NET run** — WinUI packaging and
tkinter smoke are **not** re-executed here; status for those relies on docs +
source inspection.

---

## 3. Claim-by-claim matrix

### 3.1 `docs/ROADMAP.md` — Shipped section

| Claim | Evidence | Status |
|---|---|---|
| Masters, payments, ageing, cash-flow, estimates, RA/GST | Pure modules + tabs + tests | ✅ Accurate |
| Muster, procurement, 3-way match, variations, retention | Present | ✅ Accurate |
| ITP/NCR, PPC, HSE, plant, KPIs | Present | ✅ Accurate |
| CPWA Form 21/23/26 | `muster`/`mb_report`/`bill_export` | ✅ Accurate |
| Double-entry auto-post, P&L, BS, GST/TDS | `journal_post`, `reports`, `gst` | ✅ Accurate |
| CPM, Gantt, EVM, risk/opp, weekly review | Domain + desktop (+ API/WinUI partial) | ✅ Desktop; ⚠ WinUI depth varies |
| Assistant + Foundry Local | `assistant`, `foundry_*` | ✅ Code; ⚠ needs local runtime |
| Multi-firm / company-select login | `company.py`, login, API | ✅ Accurate |
| Browser/LAN write for money docs | `webapp`/`web_docs` | ✅ Accurate |

### 3.2 Roadmap local track (U0–U7)

| Phase | Doc | Audit notes |
|---|---|---|
| U0 | ✅ u0.11 | Matches; CT-6…10 consumed |
| U1–U4 | ✅ | Shell/masters/money/charts code present |
| U5 | “every catalog tab wired… no placeholders” | **Overclaim** — see §4 |
| U6 | Dev-signed MSIX | Scripts present; release cert still open (doc admits) |
| U7 | “parity pass ✅” | **Nav parity ≠ feature parity** |

### 3.3 `docs/CLOUD-TASKS.md`

| Task | Doc | Code |
|---|---|---|
| CT-1…CT-10 | All ✅ | Confirmed on main (`gst`, measurements, charts, `web_tables`, pnl/bs, cols, lookahead, company audit) |
| CT-9 “Why” text | Still says WinUI shows a placeholder | **Stale prose** — `LookaheadPage` exists |

### 3.4 `docs/PRODUCT.md` drift

| Statement | Reality |
|---|---|
| “No role-based access control” as non-goal | Opt-in Admin/Operator/Viewer **ships** |
| “Not a cloud SaaS” | Still true (localhost/offline) |
| Audience T2/T3 cash-first contractor | Still the right north star |
| Double-entry “not primary” | Accurate UX priority; ledger still present as advanced |

### 3.5 `AGENTS.md` / `CLAUDE.md` counts

| Doc claim (approx) | Measured |
|---|---|
| ~150 modules | **180** |
| 82 tables | **85** |
| 628 tests | **728** |
| 91 tkinter-free | **117** AST-pure (includes web) |

---

## 4. WinUI: “live page” vs “powerful & precise”

Roadmap language after `22e4006` correctly says every tab resolves to an
API-backed page and that crude text dumps were replaced. **That is true.**

What remains **imprecise** (wrong or shallow relative to desktop):

| Menu / always-on | WinUI destination | Desktop equivalent | Gap type |
|---|---|---|---|
| Assistant | `CapturePage` | RAG text-to-SQL | **Miswire** |
| AI Engine | `CapturePage` | Foundry Start/Stop | **Miswire** |
| BOQ / RA Bills | `ImportPage` | MB + RA generate + forms | **Miswire** |
| Subcontractors | Masters `thekedars` | Work orders + sub bills | **Miswire** |
| Cash Flow | `MoneyPage` (payments via `Has("Cash")`) | Cash-flow forecast | **Miswire** |
| Cash & Parties | `MoneyPage` | Party statements / baaki | **Shallow** |
| Key Numbers + Insight | Same `ChartsPage` | Two analytics surfaces | **Collapsed** |
| Timeline | `DataTablePage` tasks | Gantt + CPM | **Shallow** |
| ~21 ops/billing tabs | Read-only `DataTablePage` | Full workflows | **Shallow** |
| Goods Receipt / Sourcing | Often `ImportPage` *or* table | Full GRN/PO chain | **Partial** |
| Tools | Firm + modules | Backup, sample, refdata, security, language | **Partial** (doc admits) |

Source: `NavRoute.cs` + `MainWindow` master/table/money maps.

**Precision rule for docs going forward:** reserve “parity” for *workflow parity*;
use “nav-complete” for ribbon wiring.

---

## 5. Fake data / stubs (honest inventory)

| Kind | Location | Fake business numbers? |
|---|---|---|
| Sample company | `sampledata.py` | No — labelled separate book |
| CPWD refdata | `refdata.py` | No — opt-in starter rates |
| Sidecar stub | `sidecars/stub_server.py` | No — empty extract + `stub:true` |
| OCR/STT/VLM folders | README only | N/A until weights |
| Foundry empty when down | `foundry_*` | No — soft fail |
| Undefined SPI/etc. | domain returns `None` | **Anti-fake** (correct) |

No product modules invent KPI zeros to look healthy.

---

## 6. Documentation debt (fix list)

1. ~~Soften U5/U7 “parity / no placeholders”~~ — done in this pack (`ROADMAP.md`).  
2. ~~Refresh AGENTS headline counts~~ — refreshed to **180 / 117 / 85 / 728**.  
3. ~~Fix CLOUD-TASKS CT-9 “placeholder” why-clause~~ — done.  
4. ~~Align PRODUCT non-goals with shipped optional security~~ — done.  
5. ~~Mark WINUI3-MIGRATION U0 as u0.11~~ — done.  
6. SOP-manual / older gap reports: re-check `[gap]` tags against shipped features.

---

## 7. What is *actually* complete enough to bet on

**Bet the business on today (desktop + API + LAN):**

- Civil billing spine (BOQ → MB → RA → Form 23/26)  
- Cash-first money + GST/TDS + posting  
- Multi-company books  
- Offline single-file ops  
- Headless-tested domain maths  

**Do not yet claim “Windows client replaces desktop” for:**

- Measurement-driven RA generation  
- Assistant chat  
- Subcontractor billing  
- Full muster/GRN/Gantt workflows  
- Production-signed MSIX on clean machines  

---

## 8. How this audit was run

```bash
git fetch --all --prune && git pull origin main
python -m unittest discover -s tests          # 728 OK, 5 skipped
# counts via AST + db.py regex (see §2)
# WinUI routes: NavRoute.cs + MainWindow.xaml.cs
```

*Re-run after material merges; bump the baseline SHA in the header.*
