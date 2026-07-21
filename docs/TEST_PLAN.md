# Construction OS — Test Plan

Stdlib only, no pip. Two layers: an automated suite that runs anywhere, and a
short manual pass for the things a machine cannot judge (does the screen read
right, does the interaction feel right).

## How to run

```
# from the repo root, with the project's Python 3.8+ interpreter
python -m unittest discover -s tests
```

- `tests/test_core.py` — pure business maths and the posting engine. Headless,
  no tkinter. This is where money is proven: tax, civil quantities, wages,
  ageing, allocation, retention, programme/LD, the advisory engine, the CPWD
  reference data, and the double-entry rules. Fast (~2s).
- `tests/test_smoke_tabs.py` — builds **every** tab against the sample book
  (`sampledata`) under light **and** dark. Needs a display; auto-skips on a
  headless box. ~11s. This is the net that catches "only breaks with real
  data" bugs (e.g. a tab using a module it forgot to import — which is exactly
  how the KPI-tab crash slipped through until a project existed).

Both must be green before a push.

## What the automated suite covers

| Area | Tests | Guards against |
|---|---|---|
| Tax / GST / TDS | `TestFinance`, `TestStatutory` | wrong split, wrong rounding |
| Civil quantities | `TestCivil`, `TestMeasurementBook` | mis-measured BOQ/MB |
| Wages / muster | `TestWages`, `TestMusterRoll` | wrong pay, strict date/time |
| Ageing / allocation | `TestAgeing`, `TestAllocation` | mis-aged receivables |
| Retention / DLP | `TestRetention` | releasing early / late |
| Programme / LD | `TestProgrammeBaseline` | wrong LD exposure |
| Project cost | `TestProjectCost` | double-counting shared-site cost |
| Advisory engine | `TestAdvisory` | wrong severity/confidence/ranking |
| Reference data | `TestReferenceData` | orphaned norms, bad coefficients, non-idempotent load |
| Import hygiene | `TestTabModuleImports` | a module using an un-imported dependency |
| Posting engine | `TestJournalPostingEndToEnd` | unbalanced journals |
| Tab build (data) | `test_smoke_tabs` | data-dependent build crashes, both themes |

## Manual QA — run after UI changes

Load the sample book first: **Tools › Reference library / Company Files › Load
Sample Data**, restart, then walk the list. Toggle **dark mode** (rail foot) and
repeat the visual checks.

### Project Management (new section)
- [ ] Rail shows **Project Management** (🏗) separate from **Operations** (🛠).
- [ ] It holds Projects, Timeline, Look-ahead; Operations no longer does.
- [ ] Toggling the whole section off in Tools › Modules hides it after restart.

### Per-project Overview drill-down
- [ ] Project Management › Projects › **Overview**: pick a project.
- [ ] Eight tiles populate (Budget, Cost, Billed, Margin, Budget Used,
      Milestone Progress, Programme, Retention).
- [ ] Programme tile shows slip days + LD exposure for a delayed project (NH-48
      in the sample), "On time"/"no baseline" otherwise.
- [ ] **Attention** list shows red/amber/grey flags (unbilled variations, open
      blockers, RFIs, NCRs, over-budget); green line when clean.

### Rate Book picker
- [ ] Billing › Estimates → **From Rate Book…** opens a searchable list; picking
      fills code/description/unit/rate; the fields stay editable.
- [ ] Same on Billing › BOQ / RA Bills → BOQ item entry.
- [ ] On a book with no rate book loaded, the button explains where to load it.

### Reference library
- [ ] Tools › **Load CPWD Reference Data** adds materials/norms/rate-book/
      analyses; running it twice adds nothing (idempotent).
- [ ] Masters › Materials shows current rates; Operations… → Consumption shows
      the norms; Billing › Rate Analysis shows the worked examples.

### Dark mode
- [ ] Every register's status rows (KPI board, Plant, Compliance, Quality,
      Timeline, Retention, Cash Flow…) use dark-appropriate row washes — no
      light bands on the dark tree.
- [ ] KPI headline/subtitle and project tiles are legible in both themes.

Known limitation (documented, not a bug): a tab already open when you flip the
theme keeps its Treeview row colours until reopened — Tk cannot restyle tag
colours live.

## Regression strategy

- Every new pure module gets unit tests in `test_core.py` next to its peers.
- Every new tab (or a tab that gains data-dependent code) is covered by
  `test_smoke_tabs` building it on the sample book — the cheapest guard against
  the crash-with-data class.
- `TestTabModuleImports` statically blocks the "forgot to import" class across
  the whole codebase.
