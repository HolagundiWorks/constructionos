# ACO — UI Principles & Guidelines

**How the WinUI 3 client should look, feel, and behave** — grounded in
Microsoft’s Windows 11 / Fluent Design System, adapted for an Indian T2/T3
civil contractor who thinks in cash-in / cash-out, not ERP jargon.

_Document type: Design principles + implementation guidelines + Fluent inventory_
_Version: 1.1 · Last updated: 2026-07-24_
_Audience: local Windows / WinUI agents, humans shipping `winui/`, and anyone
reviewing UI PRs._
_Hard constraint:_ **stock Fluent / WinUI 3 controls only — no custom controls,
no hand-rolled chrome, no reinvented icons.** See
[`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md).

> **Inventory / audit:** §11 is the living map of which Fluent controls,
> patterns, icons, materials, and resources are wired today vs still needed for
> an enterprise-grade shell. Status of *product* WinUI work stays in
> [`ROADMAP.md`](ROADMAP.md) §2 — this file does not replace that board.

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
- **Iconography** — Segoe glyphs via `FontIcon` (shipped: MDL2; target: Fluent
  Icons — §11.4).
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

- **Segoe Fluent Icons** via `FontIcon` / `SymbolIcon` — prefer the Fluent font
  when set; **shipped ribbon uses Segoe MDL2** code points (`RibbonIcons.cs`).
  See §11.2 / §11.4. Never emoji or custom icon fonts.
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
- [ ] Icons: Segoe `FontIcon` (MDL2 today / Fluent when adopted); tooltip if icon-only.
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

---

## 11. Fluent inventory & enterprise-grade audit _(v1.1 · 2026-07-24)_

Verified against `winui/ConstructionOS.WinUI` (25 pages + shell). Goal: **Windows
11 enterprise ERP feel** — Familiar + Calm + Complete — without custom chrome.
Canonical galleries: [WinUI 3 Gallery](https://apps.microsoft.com/detail/9p3jfp6xqhqg),
[Fluent 2](https://fluent2.microsoft.design/),
[Windows design](https://learn.microsoft.com/en-us/windows/apps/design/).

### 11.1 Verdict

| Dimension | Grade | Notes |
|---|---|---|
| Stock controls only | ✅ Strong | No custom templates / owner-draw; ribbon is composed stock |
| Theme + accent | ✅ Strong | Light/Dark/System; Radiant Orange accent ramp; severity brushes untouched |
| Icons / pictograms | ⚠ Partial | Segoe **MDL2** glyphs via `FontIcon` (works); docs said Fluent Icons — align docs + optionally adopt Fluent font |
| Materials | ⚠ Deferred | Mica removed (SDK crash); Acrylic unused; card/layer theme brushes OK |
| Page recipes | ✅ Good | CommandBar registers, FieldForm dialogs, LiveCharts, InfoBar advisories |
| Enterprise depth | ⚠ Gaps | Dates as TextBox; uneven loading; no TeachingTip/Breadcrumb/InfoBadge/SettingsCard; civil spine pages thin |
| Accessibility | ⚠ Partial | PageTitleStyle + some AutomationProperties; not every icon-only control named |
| AI surfaces | ⚠ Thin | Capture/Assistant exist; Agents (Foundry Phase B) + draft-confirm takeoff UI not in WinUI |

**Bottom line:** the shell is already Fluent-*shaped* and shippable as a
nav-complete client. To read as **enterprise-grade**, close the §11.5 P0/P1
control gaps and the ROADMAP P0 workflow pages — not a redesign.

### 11.2 Mapped — Fluent / WinUI resources in use

#### Shell & navigation

| Resource | ACO use | File(s) |
|---|---|---|
| `Window` + `Frame` | Content host | `MainWindow.xaml` |
| `ToggleButton` strip | Section tabs (Excel-style ribbon) | `MainWindow` |
| `AppBarButton` + `FontIcon` | Ribbon command band + Masters CRUD | `MainWindow.xaml.cs`, `MastersPage` |
| `AutoSuggestBox` (`QueryIcon=Find`) | Global search → `/api/search` | `MainWindow` |
| `ScrollViewer` (H) | Narrow-window overflow for tabs/band | `MainWindow` |
| Theme card / layer brushes | Header + ribbon band surfaces | `CardBackground*`, `LayerFill*`, `CardStroke*` |

> **Intentional departure:** Microsoft recommends `NavigationView` for primary
> nav. ACO uses a stock-composed ribbon because `NavigationView` Top and
> `SelectorBar` native-crash on the pinned Windows App SDK 1.5 build
> (`WINUI3-MIGRATION.md` §9). Revisit when the SDK is bumped.

#### Forms, dialogs, status

| Resource | ACO use |
|---|---|
| `ContentDialog` (+ `XamlRoot`) | FieldForm add/edit; Masters delete confirm |
| `NumberBox` | FieldForm `kind=number`; Settings timeout |
| `ComboBox` | FK / enum fields; Capture; Settings |
| `TextBox` / `PasswordBox` | Text fields; Settings credentials |
| `ToggleSwitch` | Settings auto-start |
| `CheckBox` | Tools module toggles (code-behind) |
| `InfoBar` + severity | Advisories, notices, soft errors (Home, Money, Masters, …) |
| `ProgressRing` | Masters busy; `Ui.Loading()` |
| `ProgressBar` | Lookahead PPC |
| `CommandBar` + `AppBarButton` | Refresh / Add on ~15 register pages |

#### Data & visualization

| Resource | ACO use |
|---|---|
| `ListView` | Masters list; `Ui.Table` row host |
| LiveCharts2 `CartesianChart` | Charts, CashFlow, EVM (API `labels`/`values`) |
| KPI `Border` cards | Home / Review — `CardBackgroundFillColorDefaultBrush` |
| Header `Grid` + row grids | Register tables (CommunityToolkit `DataGrid` avoided — crash) |

#### Theme, brand, typography

| Resource | ACO use |
|---|---|
| `XamlControlsResources` | WinUI Fluent control styles |
| `SystemAccentColor` (+ Light/Dark 1–3) | Radiant Orange `#FF4F18` brand CTA (`App.xaml`; = `branding.py`) |
| `ElementTheme` | Light / Dark / System from Settings |
| Type ramp styles | `TitleTextBlockStyle`, `Subtitle*`, `Caption*`, `PageTitleStyle` (+ HeadingLevel) |
| Segoe UI Variable | Default (unchanged) |

#### Icons & pictograms

| Resource | ACO use |
|---|---|
| `FontIcon` + **Segoe MDL2 Assets** glyphs | Ribbon (`RibbonIcons.cs`), Masters CRUD, Info empty state |
| `Symbol` enum (`Add`, `Refresh`, `Find`) | Some `AppBarButton` / search |
| Brand mark assets | Outside WinUI tree (`construction_app/resources/`; MSIX visual assets) — **not** used as in-app nav pictograms |
| Emoji pictograms | **Retired** from WinUI nav (tkinter rail still may show them) |

`RibbonIcons` keyword map (19 glyphs + Document default): Home, Message,
ViewAll/Report, Repair, Contact, Shop, People, MapPin, Package, Flag,
Calculator, Important, FavoriteStar, Document, Accept, Calendar, Camera,
Download, Setting — see `winui/.../Helpers/RibbonIcons.cs`.

#### Packages (allowed stack)

| Package | Role |
|---|---|
| Microsoft.WindowsAppSDK 1.5 | Stock WinUI 3 |
| LiveChartsCore.SkiaSharpView.WinUI | Charts only |
| CommunityToolkit.Mvvm | Referenced — **patterns unused** (no `[ObservableProperty]` yet) |

### 11.3 Page → pattern map

| Page | Pattern (§4) | Fluent notes |
|---|---|---|
| Home | Dashboard | KPI cards + InfoBar advisories |
| Charts / CashFlow / Evm | Charts | LiveCharts + theme card brushes |
| Masters / Money / Parties / Risks / Opportunities / Lessons / Submittals / DataTable / Portfolio / Productivity / Gst | Register | CommandBar + list/table |
| Accounting | Report | ToggleButton view switcher |
| Lookahead / Review | Report | PPC bar / narrative + InfoBars |
| Settings / Tools | Settings form | Plain ScrollViewer — not SettingsCard |
| Capture / Import | Capture | Probe / paste — not full draft-confirm queue |
| Assistant | Form + InfoBar | Q&A; Agents Phase B not present |
| Process | Workflow list | No BreadcrumbBar / Stepper |
| Info | Empty placeholder | FontIcon + caption |

### 11.4 Not mapped yet (Fluent catalog → ACO need)

Prioritised for **enterprise grade**. “Avoid” = known crash or non-goal.

| Fluent / Toolkit resource | Enterprise need | Priority | Blocker |
|---|---|---|---|
| **`DatePicker` / `CalendarDatePicker`** | All `YYYY-MM-DD` fields (bills, muster, RA) | **P0** | FieldForm has no `date` kind — uses TextBox |
| **Unified loading** (`ProgressRing` + InfoBar) | Every register/report | **P0** | `PageLoad` is text-only; Masters alone uses ring |
| **`TeachingTip`** | First-run + AI draft tips | P1 | Not wired |
| **`BreadcrumbBar`** | Project → BOQ → MB → RA depth | P1 | Civil pages not built |
| **`InfoBadge`** | Open approvals / overdue baaki on ribbon | P1 | Not wired |
| **`SettingsCard` / `SettingsExpander`** (Toolkit) | Enterprise Settings/Tools density | P1 | Plain form today |
| **`Expander`** | Advisory groups; long forms | P1 | Flat stacks |
| **`MenuFlyout` / `CommandBarFlyout`** | Row actions (Edit / Delete / Open) | P1 | CRUD mostly CommandBar-global |
| **Segoe Fluent Icons font** | Doc §3.5 / Migration §6 intent | P1 | MDL2 works; switch font + refresh map |
| **`HyperlinkButton`** | “Open in Estimates” cross-links | P1 | Rare |
| **Mica** (`MicaBackdrop`) | Windows 11 signature shell | P2 | Removed — native crash; revisit on SDK bump |
| **Acrylic** on flyouts | Transient surfaces | P2 | No flyouts yet |
| **`ThemeShadow`** | Subtle card elevation | P2 | Optional; don’t over-elevate |
| **`ItemsRepeater` / `ItemsView`** | Virtualized KPI / large lists | P2 | Fine at current volume |
| **`TabView` / `Pivot`** | Multi-doc workspace | P2 | Optional |
| **`WebView2`** | HTML bill / CPWA print preview | P2 | Opens external/browser today |
| **`PersonPicture`** | User/session chip | P3 | Optional |
| **`NavigationView`** | Microsoft default shell | Avoid until SDK | Crash on Top mode |
| **CommunityToolkit `DataGrid`** | Dense grids | Avoid until SDK | Crash; ListView substitute OK |
| **`SelectorBar`** | Segmented views | Avoid until SDK | Crash |
| Custom icon fonts / emoji nav | — | **Non-goal** | Forbidden |

### 11.5 Suggested changes (do these)

#### A. Control / pattern (local WinUI)

1. **FieldForm `date` kind** → stock `DatePicker` (ISO date ↔ API text). Highest
   enterprise signal for money/civil forms.
2. **One loading recipe** — `PageLoad` shows `ProgressRing` + status; errors as
   `InfoBar` Severity=Error (not a fake table row). Align Masters / registers.
3. **Empty states** — every register: caption + one primary `AppBarButton`
   (“Add vendor”) — InfoPage pattern reused.
4. **SettingsCard** (CommunityToolkit.WinUI.Controls) for Settings/Tools groups
   (Connection, Appearance, Company, Modules).
5. **TeachingTip** on Assistant / Capture: “AI drafts only — you confirm.”
6. **InfoBadge** on Money / Approvals ribbon commands when API exposes counts.
7. **RibbonIcons** — document as MDL2 *or* set `FontFamily` to Segoe Fluent
   Icons and rematch glyphs; kill “Fluent Icons” claim until then.
8. **Adopt CommunityToolkit.Mvvm** on 2–3 pilot pages (Home, Money) to match
   coding standard; reduce code-behind growth.
9. **Mica revisit** after Windows App SDK upgrade; keep theme-brush fallback.
10. **Agents page (Foundry Phase B)** — persona picker + workflow runner using
    existing `/api/agents*` (InfoBar gated steps).

#### B. Product workflow (ROADMAP P0 — honesty)

Still missing or thin vs desktop ERP (API often ready): BOQ/MB/RA, subcontractors,
GRN three-way match UI, muster payout, AI Engine Start/Stop, takeoff canvas.
Fluent polish without these pages will not feel enterprise to the contractor.

#### C. Doc / process

- Keep this §11 updated when a control lands (same PR).
- PR checklist (§9) stays mandatory for `winui/` changes.
- Do **not** invent a second status board — pending work stays in `ROADMAP.md`.

### 11.6 Anti-patterns check (current tree)

| Check | Result |
|---|---|
| Custom `ControlTemplate` / owner-draw | ✅ None |
| `MessageDialog` / UWP XAML namespaces | ✅ None |
| `ContentDialog` without `XamlRoot` | ✅ Set in FieldForm + Masters |
| Hardcoded page colours | ✅ None (accent override in `App.xaml` only — intentional) |
| Emoji as nav icons | ✅ None in WinUI |
| Business maths in C# | ✅ Charts bind API series |
| Consolas on dump panes (Capture/Import/Assistant) | ⚠ Prefer `Cascadia Mono` / theme body for dumps — minor |
| Stale “theme forced Light” comment in `App.xaml` | ⚠ Fix comment (theme is runtime) |

### 11.7 Enterprise-grade target recipe (summary)

```
Shell:     stock ribbon (until NavigationView safe) + Mica when SDK allows
Nav icons: one Segoe font (Fluent preferred; MDL2 OK if documented)
Registers: CommandBar + ListView/table + FieldForm (NumberBox + DatePicker + ComboBox)
Status:    InfoBar severity map; ProgressRing loading; TeachingTip for AI
Settings:  SettingsCard groups; ToggleSwitch / NumberBox
Charts:    LiveCharts + theme brushes
Depth:     BreadcrumbBar on civil spine; InfoBadge on money queues
Trust:     AI = draft → ContentDialog confirm; Viewer = disabled writes
```

### 11.8 Relationship of this audit to other docs

| Doc | Role vs §11 |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) §2 | **What to build next** (P0–P4) |
| [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §5–6 | Architecture control/icon map (tkinter → WinUI) |
| [`RESEARCH.md`](RESEARCH.md) §4 | Condensed Fluent policy |
| This §11 | **What’s wired in the repo today** + gap list |
