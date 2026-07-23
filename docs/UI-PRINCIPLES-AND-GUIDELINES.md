# ACO — UI Principles & Guidelines

**How the WinUI 3 client should look, feel, and behave** — grounded in
Microsoft’s Windows 11 / Fluent Design System, adapted for an Indian T2/T3
civil contractor who thinks in cash-in / cash-out, not ERP jargon.

_Document type: Design principles + implementation guidelines_
_Version: 1.0 · Last updated: 2026-07-22_
_Audience: local Windows / WinUI agents, humans shipping `winui/`, and anyone
reviewing UI PRs._
_Hard constraint:_ **stock Fluent / WinUI 3 controls only — no custom controls,
no hand-rolled chrome, no reinvented icons.** See
[`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md).

### Canonical Microsoft sources (follow these)

| Topic | Microsoft Learn |
|---|---|
| Design principles | [Windows 11 design principles](https://learn.microsoft.com/en-us/windows/apps/design/design-principles) |
| Guidelines overview | [Design guidelines](https://learn.microsoft.com/en-us/windows/apps/design/guidelines-overview) |
| Navigation | [Navigation basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics) |
| Commanding | [Commanding basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics) |
| Color | [Color in Windows](https://learn.microsoft.com/en-us/windows/apps/design/style/color) |
| Typography | [Typography in Windows](https://learn.microsoft.com/en-us/windows/apps/design/style/typography) |
| Materials | [Materials (Mica, Acrylic, Smoke)](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/materials) |
| Writing | [Writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style) |
| Gallery | [WinUI 3 Gallery](https://apps.microsoft.com/detail/9p3jfp6xqhqg) (interactive reference) |

When this document and Microsoft’s guidance disagree on a Fluent mechanic,
**Microsoft wins**. When they disagree on *product voice* (cash-first, Hindi/
Hinglish, plain-language money), **ACO wins** — see
[`PRODUCT.md`](PRODUCT.md).

**Research (market / CPWD / Fluent — single doc):**
[`RESEARCH.md`](RESEARCH.md) — grounded in
the same Learn hub ([Design Windows apps](https://learn.microsoft.com/en-us/windows/apps/design/)).
**Shipped from it:** Light / Dark / follow-Windows appearance (Settings), the
Assistant/Cash-Flow/Parties routes, and one loading/empty/error recipe.

---

## 0. Why this document exists

The WinUI replatform is a **presentation layer** over a tested Python domain
core (`docs/WINUI3-MIGRATION.md`). That only stays honest if every screen:

1. Uses **stock** WinUI / Fluent patterns users already know from Windows 11.
2. Speaks the contractor’s language (cash, baaki, bills) — not CA jargon.
3. Never invents UI chrome that breaks the “no custom items” rule.

This file is the **single checklist** for those three. New pages, XAML, and UI
PRs should be reviewable against it.

---

## 1. Windows 11 principles → ACO

Microsoft’s five principles (from [design principles](https://learn.microsoft.com/en-us/windows/apps/design/design-principles))
are the north star. Below: what each means *here*.

### 1.1 Effortless — “easy to do what I want, with focus and precision”

| Do | Don’t |
|---|---|
| Default dates to today; remember last site / vendor / party (`remember` / API defaults). | Force empty forms when a sensible default exists. |
| Put the next action where the eye already is (primary button on the form, not buried in a menu). | Scatter Save / Post / Approve across three unrelated surfaces. |
| Prefer pickers (`ComboBox`, FK options from API, `AutoSuggestBox`) over free typing. | Require typing IDs or codes the user doesn’t know. |
| One primary job per page (list *or* enter *or* review). | Dashboard soup on every screen. |
| Keep money maths on the server; show derived totals as read-only. | Recompute GST/TDS/SPI in C#. |

**Product translation:** minimal typing is a founding rule (`PRODUCT.md` §4).
Every extra field is a tax on the munshi.

### 1.2 Calm — “softer and decluttered; fades into the background”

| Do | Don’t |
|---|---|
| Use system theme brushes and Mica so the shell feels like Windows, not a loud brand skin. | Purple gradients, glow, multi-layer shadows, emoji decoration. |
| Emphasize with **one** accent / severity at a time (`InfoBar`, accent on the active nav item). | Red + orange + yellow chips competing for attention. |
| Prefer whitespace and the Fluent type ramp over boxes-inside-boxes. | Nested cards for static text that isn’t interactive. |
| Soften “bad news” with severity-mapped `InfoBar`s, not alarming full-page errors. | Stack traces, red full-bleed panels, jargon errors. |

**Signature experiences Microsoft names — use them as intended:**

- **Color** — calming foundation; highlight only when needed.
- **Elevation / layering** — hierarchy via surface, not heavy borders.
- **Iconography** — Segoe Fluent Icons only.
- **Materials** — Mica on the window; Acrylic on flyouts/menus; Smoke under dialogs.
- **Geometry** — stock corner radii / control templates; don’t restyle.
- **Typography** — Segoe UI Variable + Windows type ramp.
- **Motion** — reactive, short, context-appropriate (see §8).

### 1.3 Personal — “adapts to how I use my device”

| Do | Don’t |
|---|---|
| Honour Windows light/dark and (where we opt in) accent. Persist app theme in settings / `app_settings`. | Hard-code hex colours that ignore `ElementTheme`. |
| Persona-aware menu from `GET /api/menu?persona=` (Owner vs munshi-style density later). | One fixed mega-menu with every tab equally loud. |
| Support keyboard + mouse first; touch-friendly hit targets (≥40×40 epx) where relevant. | Tiny icon-only buttons with no tooltip. |
| Local language / Hinglish labels when i18n is on; keep English strings sentence-case and plain. | All-caps labels; unexplained English accounting terms. |

### 1.4 Familiar — “new look, no learning curve”

| Do | Don’t |
|---|---|
| Use `CommandBar`, `ContentDialog`, `InfoBar`, `ListView`, `NumberBox`, `DatePicker`, `AutoSuggestBox`, `ToggleButton`, `AppBarButton` the way WinUI Gallery shows. | Ship a **custom-templated** control, owner-drawn chrome, or a third-party UI kit that replaces Fluent. |
| Match Windows placement conventions (search in the shell chrome, Settings reachable as a tab, back only when hierarchy needs it). | Put Settings as a random page with no standard entry. |
| Mirror patterns users know from File Explorer / Settings / Edge (list→details, horizontal scroll for overflow). | Novel gestures as the only way to reach core money actions. |

**Current shell (stock primitives):** an **Excel-style ribbon** the owner asked
for — a horizontal `ToggleButton` **section tab strip**, and picking a section
fills a **command band** of that section's tabs as icon-over-label `AppBarButton`s
(Segoe Fluent glyphs), with `AutoSuggestBox` search in the header and Settings as
a leaf tab. It is **composed from stock controls, not a custom control** (no
custom template, no owner-draw). This is an owner-directed departure from the
default "use `NavigationView`" recommendation — additionally forced because
`NavigationView` Top mode and `SelectorBar` both native-crash on the current
Windows App SDK build (see [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §9,
fix 7). See `winui/.../MainWindow.xaml`.

### 1.5 Complete + Coherent — “visually seamless across the app”

| Do | Don’t |
|---|---|
| Share spacing, type styles, and command placement across Masters / Money / Billing. | Each page invents its own button row layout. |
| Same empty / loading / error patterns (`PageLoad`, `InfoBar`, skeleton or progress ring). | Spinner on one page, blank white on another, MessageBox on a third. |
| Same icon set (Segoe Fluent Icons) and same severity mapping for advisories. | Mix emoji + Fluent icons + PNG glyphs. |
| Treat browser/LAN and WinUI as **different shells, same domain language** (same field labels where possible). | WinUI renames “Net payable” while the print still says something else. |

---

## 2. Product principles that override generic Fluent taste

Fluent tells us *how* to be Windows. ACO tells us *what* to prioritize
([`PRODUCT.md`](PRODUCT.md)):

1. **Cash-first, not ledger-first.** Home / Money lead with cash, baaki, billed vs
   collected. Double-entry Accounting is advanced / for the CA.
2. **Print-first.** Every important commercial document must remain printable
   (HTML export path today; WinUI opens/prints via the same exports).
3. **Plain language.** Prefer “Who owes me?” over “Accounts receivable”;
   “Baaki” / “Outstanding” over AR jargon in localized builds.
4. **Trust & soft failure.** No stack traces in the UI. AI proposes; humans approve
   anything that moves money or a date. Writes are role-guarded.
5. **Offline / localhost.** The WinUI client talks to a local Python API; design
   for “backend starting / offline” states without panic chrome.

If a Fluent-looking screen violates cash-first or plain language, **redesign the
content hierarchy**, not the control set.

---

## 3. Foundations checklist (Microsoft guidelines map)

Use this as a PR review list. Each foundation maps to Microsoft’s
[guidelines overview](https://learn.microsoft.com/en-us/windows/apps/design/guidelines-overview).

### 3.1 Color

- Theme via **WinUI theme resources** (`TextFillColor*`, `CardBackgroundFill*`,
  `AccentFillColor*`) — never raw brand hex in page XAML unless documented in
  one theme dictionary.
- **Light and dark** both required; smoke-test KPI cards and charts in both.
- Accent **sparingly** (selected nav, primary button, focus). Status uses
  `InfoBar` severity, not rainbow text.
- Do not encode meaning with red/green alone (colorblindness); pair with icon /
  text (“Overdue”, “On track”).
- Charts: bind series from API `labels`/`values`; use theme-aware LiveCharts
  brushes — no maths and no fixed neon palettes in C#.

### 3.2 Typography

- Default: **Segoe UI Variable** (WinUI default). Do not ship Inter / Roboto /
  random web fonts.
- Follow the [Windows type ramp](https://learn.microsoft.com/en-us/windows/apps/design/style/typography):
  body ~14/20 Regular; titles Semibold; avoid Bold/Italic as the main emphasis.
- **Sentence case** for all UI strings (titles, buttons, nav).
- Minimums: ~12 px Regular / ~14 px Semibold — don’t shrink money figures below
  legibility to fit a card.
- Truncate with ellipsis on single-line labels; wrap body copy.
- Hindi / regional: use platform fonts for those scripts; don’t force Segoe on
  Devanagari if the OS maps better.

### 3.3 Layout & geometry

- Content `Frame` margin stays modest (shell already uses ~12); prefer consistent
  page padding (e.g. 16–24 epx) over one-off margins.
- Align to a simple vertical rhythm; use `StackPanel` / `Grid` with shared
  `Spacing` rather than magic numbers per control.
- Prefer **list/details** for registers (sites, vendors, measurements): list left
  or top, form/detail adjacent — high switch frequency.
- Avoid deep nesting (>2 levels) without `BreadcrumbBar`.
- Cards only when they wrap an **interaction** or a KPI that is itself a unit of
  attention (Home KPI band). Don’t card every paragraph.

### 3.4 Elevation & materials

| Surface | Material / pattern |
|---|---|
| Main window backdrop | **Mica** (or system backdrop) — shows focus vs inactive |
| Flyouts, menus, overflow | **Acrylic** |
| Modal dialogs | **Smoke** under `ContentDialog` |
| KPI / chart surfaces | Theme card brush (`CardBackgroundFillColorDefaultBrush`) — stock |

Do not fake glass with custom blurs or PNG overlays.

### 3.5 Iconography

- **Segoe Fluent Icons** via `FontIcon` / `SymbolIcon` only
  (`WINUI3-MIGRATION.md` §6).
- One metaphor per concept (Home, Money, Settings) — don’t change glyph meaning
  across pages.
- Icon + text in nav when space allows; icon-only needs `ToolTipService`.

### 3.6 Motion

- Use stock control motion (ribbon `ToggleButton`/`AppBarButton`, InfoBar
  open/close, ContentDialog).
- Page transitions: prefer subtle / default `Frame` navigation — no parade of
  custom storyboards.
- Motion must **feedback** (saved, deleted, error) or **orient** (where did I go),
  never decorate.

### 3.7 Navigation

Principles from Microsoft: **consistency, simplicity, clarity**.

**Structure for ACO:**

- **Flat / lateral** at section level (Home, Masters, Money, Billing, …) —
  peers, any order → the ribbon **tab strip** (`ToggleButton`s).
- **One level down** inside a section — the section's tabs show as icon commands
  in the ribbon **band** (not a dropdown), so a section's destinations are one
  click away. Deeper hierarchy (e.g. Project → BOQ → Measurements) uses in-page
  list/details + breadcrumb if depth > 2.
- Keep peer groups reasonable; overflow is OK — the tab strip and band each
  scroll horizontally on a narrow window.
- Avoid pogo-sticking: related money actions reachable without climbing to root
  and back (CommandBar on the page, or search).
- **Back:** none at the shell today (flat sections + one band level). If a
  drill-down page is pushed on the `Frame` stack, show back and follow
  Microsoft's back-history table (transient UI / item enumeration → dismiss,
  don't invent history).

**Search:** `AutoSuggestBox` in the ribbon header; results from
`GET /api/search` with `section`/`tab` for routing — no custom command palette chrome.

### 3.8 Commanding

- Primary recurring actions on the **page canvas** or page **`CommandBar`**
  (Save, Add, Refresh, Export/Print).
- Destructive / rare actions in overflow or confirm dialog.
- Prefer direct manipulation where safe (select row → edit fields); don’t rely
  only on “up/down” buttons.
- **Confirm** only for irreversible or money-moving actions (delete master still
  referenced, approve bill, post payments). Don’t confirm every Save.
- Provide undo *or* confirm — not neither for destructive ops.
- Viewer role: disable/hide write commands; explain with a calm `InfoBar` /
  dialog (“Read-only”) — never a crash.

### 3.9 Usability & accessibility

- Keyboard: Tab order matches reading order; Enter activates primary button in
  dialogs; Esc dismisses light-dismiss UI.
- Focus visible (stock focus visuals — don’t remove).
- Contrast: text/icons vs background meets theme contrast; don’t place gray-on-gray
  money figures.
- Screen readers: meaningful `AutomationProperties.Name` on icon-only controls.
- Hit targets large enough for touch where we claim touch support.
- Loading: show progress; never leave a silent blank stage.
- Offline / API down: plain-language `InfoBar` + retry — same tone as desktop
  `errors.py` (no stack trace).

### 3.10 Writing (voice & tone)

Microsoft: **warm and relaxed**, **ready to lend a hand**, **crisp and clear**.

ACO additions:

| Pattern | Example |
|---|---|
| Address the user as “you”; the app as “we” | “We couldn’t save this payment.” |
| Lead with what matters | “Client still owes ₹1,20,000” not “AR balance non-zero” |
| Active voice on buttons | “Save payment”, “Generate RA bill”, “Print muster” |
| Sentence case | “Purchase orders” not “Purchase Orders” in running UI (nav may title-case section names consistently) |
| Errors: cause + next step | “Backend isn’t running. Start ACO API or retry.” |
| No blame | Not “You entered an invalid GSTIN.” → “That GSTIN doesn’t look right. Check the 15 characters and try again.” |
| Define abbreviations once | “TDS (tax deducted at source)” on first use in a view |
| Money language | Prefer “Net payable”, “Baaki”, “Received” over ledger jargon |

Dialog title ↔ button text must **call and respond** (“Delete this vendor?” →
Delete / Cancel).

### 3.11 Widgets / glanceables

- Optional later: Windows widgets are out of MVP. Home KPI band is the
  in-app glanceable surface — keep it to a **small set** of money facts +
  advisories, not a second ERP.

---

## 4. Page patterns (stock recipes)

Use these recipes; don’t invent new shells.

| Job | Stock pattern | Notes |
|---|---|---|
| App shell | Ribbon (`ToggleButton` tab strip + `AppBarButton` band) + `Frame` | Owner-directed Excel-style ribbon, composed from stock controls; `NavigationView` Top / `SelectorBar` avoided (native-crash on this SDK — WINUI3-MIGRATION §9 fix 7) |
| Section landing / register | `ListView` + form / detail pane | FK fields from API `options` |
| Document entry | Form + line `ListView` + totals | Totals read-only from API/domain |
| Dashboard | KPI band + `InfoBar` list | Data from `/api/kpi`, `/api/dashboard` |
| Charts | LiveCharts2 in a page | Series from `/api/cashflow|ageing|evm` `labels`/`values` |
| Settings | Settings page (leaf tab) + `ScrollViewer` form | Theme, persona, API URL |
| Search navigate | `AutoSuggestBox` | `/api/search` |
| Blocking question | `ContentDialog` | Smoke backdrop |
| Soft status | `InfoBar` | Severity by advisory level |
| Progress | `ProgressRing` / `ProgressBar` | During API calls |
| Empty state | Short sentence + one action | “No vendors yet. Add a vendor.” |

**Forbidden without explicit owner approval:** custom title bars that fight the
system caption buttons, **owner-drawn or custom-templated** controls, third-party
UI kits that replace Fluent controls, emoji as primary navigation icons. (The
shipped ribbon is *not* owner-draw — it composes stock `ToggleButton` /
`AppBarButton` — and is the owner-approved shell; see §1.4.)

---

## 5. Information architecture & density

- **Owner persona:** fewer top-level items, money and Home first.
- **Munshi / operator:** denser grids OK, but still Fluent spacing — density ≠
  clutter.
- Don’t put schedules, addresses, promo chips, and KPI soup in the first viewport
  of a **task** page. Home may show KPIs; a Payment page shows the payment job.
- Related records: in-page links or search — avoid forcing a full nav round-trip
  for “open this contract’s BOQ”.

---

## 6. AI & automation in the UI

Aligned with product trust rules:

- AI surfaces are **draft → confirm**. Use `InfoBar` / review lists, never silent
  writes.
- Label AI-origin clearly (“Suggested”, “Draft from scan”) using stock text /
  icons — not a fake “AI glow”.
- Confidence: prefer honest Low/High copy over fake precision meters.
- Fail soft: if the engine is off, show deterministic quick answers / empty
  draft state, rest of app unaffected.

---

## 7. Theming & branding

- App name **ACO** (with the full name *Accelerated Construction Operations* as a
  quiet secondary caption) appears in the shell header / window title at a clear
  but not overpowering weight (`SubtitleTextBlockStyle` + `CaptionTextBlockStyle`
  as shipped). Brand strings come from `construction_app/branding.py`.
- The logo mark is the existing geometry filled **Radiant Orange** (`#FF4F18`);
  use accent **sparingly** in-shell (per §3.1) — the mark and letterhead carry
  the brand, not coloured chrome.
- Prefer system chrome + Fluent materials over heavy brand illustration in the
  ERP shell (this is a work tool, not a marketing landing page).
- Printed documents may carry letterhead (`assets` / export HTML); the WinUI
  shell stays native Windows.

---

## 8. Do / Don’t quick card (pin this)

**Do**

- Stock WinUI 3 + Community Toolkit + LiveCharts2 only.
- Theme resources, Mica, Segoe Fluent Icons, type ramp.
- Cash-first copy; sentence case; calm errors with a next step.
- API-driven numbers; CSRF + role gates on writes.
- Light **and** dark smoke for every new page.

**Don’t**

- Custom controls, custom icon fonts, emoji nav, glow, purple AI skins.
- Business maths in C#.
- Stack traces or blame-the-user errors.
- Confirm spam on harmless saves; silent deletes on money docs.
- One-off colours and fonts that ignore `ElementTheme`.

---

## 9. Review checklist for UI PRs

Copy into PR descriptions when touching `winui/`:

- [ ] Control is stock Fluent / Toolkit / LiveCharts (name it).
- [ ] No new raw colours; theme brushes only.
- [ ] Works in light and dark.
- [ ] Primary action obvious; destructive action confirmed or undoable.
- [ ] Empty / loading / error / offline states handled.
- [ ] Strings: sentence case, plain language, no unexplained jargon.
- [ ] Icons: Segoe Fluent Icons; tooltip if icon-only.
- [ ] Numbers from API; no duplicated domain maths.
- [ ] Viewer/read-only respected if write affordances exist.
- [ ] Matches a §4 page pattern (or documents why not).

---

## 10. Relationship to other docs

| Doc | Role |
|---|---|
| This file | **How UI should feel and which Fluent rules we enforce** |
| [`../.github/instructions/winui3.instructions.md`](../.github/instructions/winui3.instructions.md) | **WinUI 3 / Windows App SDK coding standard** — the hard API/threading/windowing/theming rules (auto-applied to `*.xaml`/`*.cs`/`*.csproj` by VS Code / Copilot) |
| [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) | Architecture, component mapping, phases U0–U7 |
| [`PRODUCT.md`](PRODUCT.md) | Audience, jobs-to-be-done, product non-negotiables |
| [`API.md`](API.md) | JSON contract the client binds to |
| [`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) | Overall system + menu/workflow |

**Ownership:** local Windows agent implements and smoke-tests WinUI against this
guide; cloud/headless agent keeps the API and docs coherent but does not claim
WinUI screenshots from Linux.
