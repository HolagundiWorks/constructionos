# ACO — UI Principles & Guidelines

**How the WinUI 3 client should look, feel, and behave** — grounded in
**[Fluent 2](https://fluent2.microsoft.design/)** (design language) and Windows /
WinUI 3 stock controls, adapted for an Indian T2/T3 civil contractor who thinks
in cash-in / cash-out, not ERP jargon.

_Document type: Design principles + Fluent 2 foundations + implementation
guidelines + inventory_
_Version: 2.0 · Last updated: 2026-07-24 · Design system: **Fluent 2**_
_Audience: local Windows / WinUI agents, humans shipping `winui/`, and anyone
reviewing UI PRs._
_Hard constraint:_ **stock Fluent / WinUI 3 controls only — no custom controls,
no hand-rolled chrome, no reinvented icons.** See
[`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md).

> **Inventory / audit:** §11 maps which Fluent controls, patterns, icons,
> materials, and resources are wired today vs still needed. Status of *product*
> WinUI work stays in [`ROADMAP.md`](ROADMAP.md) §2 — this file does not replace
> that board.

### Canonical sources (follow these)

| Layer | Source |
|---|---|
| **Fluent 2 hub** | [fluent2.microsoft.design](https://fluent2.microsoft.design/) |
| Design principles | [Fluent 2 design principles](https://fluent2.microsoft.design/design-principles) |
| Color | [Fluent 2 color](https://fluent2.microsoft.design/color) · [tokens](https://fluent2.microsoft.design/color-tokens) |
| Elevation | [Fluent 2 elevation](https://fluent2.microsoft.design/elevation) |
| Iconography | [Fluent 2 iconography](https://fluent2.microsoft.design/iconography) |
| Layout | [Fluent 2 layout](https://fluent2.microsoft.design/layout) |
| Material | [Fluent 2 material](https://fluent2.microsoft.design/material) |
| Motion | [Fluent 2 motion](https://fluent2.microsoft.design/motion) |
| Shapes | [Fluent 2 shapes](https://fluent2.microsoft.design/shapes) |
| Typography | [Fluent 2 typography](https://fluent2.microsoft.design/typography) |
| WinUI platform | [Windows apps design](https://learn.microsoft.com/en-us/windows/apps/design/) · [WinUI 3 Gallery](https://apps.microsoft.com/detail/9p3jfp6xqhqg) |

**Conflict rule:** Fluent 2 design language + WinUI stock controls win on
visual/interaction mechanics. When they disagree with *product voice*
(cash-first, Hindi/Hinglish, plain-language money), **ACO wins** — see
[`PRODUCT.md`](PRODUCT.md). Windows Learn docs are the platform how-to; Fluent 2
is the design-language *why*.

**Research (market / CPWD / Fluent — single doc):** [`RESEARCH.md`](RESEARCH.md).

---

## 0. Why this document exists

The WinUI replatform is a **presentation layer** over a tested Python domain
core (`docs/WINUI3-MIGRATION.md`). That only stays honest if every screen:

1. Speaks **Fluent 2** — natural on Windows, built for focus, inclusive,
   unmistakably Microsoft (via WinUI), with ACO brand accent used sparingly.
2. Speaks the contractor’s language (cash, baaki, bills) — not CA jargon.
3. Never invents UI chrome that breaks the “no custom items” rule.

This file is the **single checklist** for those three. New pages, XAML, and UI
PRs should be reviewable against it.

---

## 1. Fluent 2 design principles → ACO

Source: [Fluent 2 design principles](https://fluent2.microsoft.design/design-principles).
These four principles are the north star for ACO’s WinUI shell.

### 1.1 Natural on every platform

> Experiences should adapt to the device and build off the familiar — designing
> for what people already understand.

| Do (ACO) | Don’t |
|---|---|
| Reuse **stock WinUI 3 / Fluent** controls ~80%+ of the time; spend energy on cash-first content, not chrome. | Invent custom templates, owner-draw ribbons, or third-party UI kits that replace Fluent. |
| Honour Windows light/dark/system theme; `DatePicker` / `NumberBox` / `ContentDialog` the way WinUI Gallery shows. | Free-type dates; MessageDialog; UWP-era APIs. |
| Ribbon composed from stock `ToggleButton` + `AppBarButton` (owner-approved) when `NavigationView` Top is unsafe on this SDK. | Fake Excel chrome with custom drawing. |

**Emotional goal:** reliability and trust — the munshi should feel “this is a
normal Windows app,” not a foreign skin.

### 1.2 Built for focus

> Stay in the flow. Inspire action, simply and seamlessly. Less visual clutter.

| Do (ACO) | Don’t |
|---|---|
| One primary job per page (list *or* enter *or* review). Default dates; remember last site/vendor. | Dashboard soup on every screen; empty forms when a default exists. |
| Primary action where the eye already is; derived money totals read-only from API. | Scatter Save / Post / Approve; recompute GST/TDS/SPI in C#. |
| Emphasize with **one** accent or severity at a time (`InfoBar`, selected nav). | Red + orange + yellow chips competing; purple AI glow. |

**Product translation:** minimal typing is a founding rule (`PRODUCT.md` §4).
Every extra field is a tax on the munshi.

### 1.3 One for all, all for one

> Include a range of perspectives and abilities — when you’re included, you
> belong.

| Do (ACO) | Don’t |
|---|---|
| Keyboard Tab order = reading order; visible focus; `AutomationProperties.Name` on icon-only controls. | Icon-only with no name/tooltip; remove focus visuals. |
| Contrast via theme brushes; never encode status with colour alone (pair with icon/text). | Gray-on-gray money; red/green-only meaning. |
| Hindi / Hinglish when i18n is on; respect reduced-motion preferences for animation. | All-caps labels; unexplained English accounting terms; flashy motion. |
| Viewer role: disable writes + calm `InfoBar` (“Read-only”). | Crash or stack traces for permission failures. |

### 1.4 Unmistakably Microsoft (with ACO brand)

> Feel like one Microsoft — signature experiences (color, icons, materials)
> create familiarity. A little personality goes a long way.

| Do (ACO) | Don’t |
|---|---|
| WinUI signature materials (Mica / Acrylic / Smoke when safe), Segoe typography, Fluent system icons. | Brand orange on large surfaces; custom icon fonts; emoji nav. |
| ACO **Radiant Orange** (`#FF4F18`) only as **brand accent** — CTAs, selection, logo mark (`App.xaml` `SystemAccentColor` ramp). | Orange as severity (use system Critical/Caution/Success). |
| Quiet “ACO” wordmark in shell; letterhead on prints — not marketing chrome in the ERP. | Overpowering hero branding that fights Windows chrome. |

**Bridge to Windows 11 Learn principles** (Effortless / Calm / Personal /
Familiar / Complete): they remain useful platform language and map cleanly onto
Fluent 2’s four — Calm≈Focus, Familiar≈Natural, Personal≈One for all,
Complete≈Unmistakably Microsoft. Prefer citing **Fluent 2** in new UI PRs.

---

## 2. Product principles that override generic Fluent taste

Fluent 2 tells us *how* to be Microsoft-shaped. ACO tells us *what* to prioritize
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

## 3. Fluent 2 foundations (design language → WinUI)

Each subsection follows Fluent 2. Use as a PR review list. WinUI theme resources
are our token surface (Fluent alias tokens → `{ThemeResource …}`).

### 3.1 Color

Source: [Fluent 2 color](https://fluent2.microsoft.design/color).

Fluent defines three palettes — apply them deliberately:

| Palette | Role in ACO |
|---|---|
| **Neutral** | Surfaces, text, layout chrome — `TextFillColor*`, `CardBackgroundFill*`, `LayerFill*`, strokes. Lighter neutrals on focus surfaces. |
| **Shared / semantic** | Status only — `InfoBar` Critical / Caution / Success / Attention. Never decorate with semantic colour. |
| **Brand** | ACO Radiant Orange as accent — primary buttons, selected ribbon tab, focus accents. **Not** large backgrounds. |

**Rules**

- Page XAML: **theme resources only** — no raw hex (brand ramp lives once in
  `App.xaml`).
- Interaction: rely on stock control states (Windows may lighten on interact —
  platform distinction in Fluent 2). Don’t hand-author hover colours.
- Accessibility: contrast ≥ 4.5:1 body text; don’t use colour as the only signal;
  let people keep system personalization (theme + high contrast).
- Charts: API `labels`/`values` + theme-aware LiveCharts brushes — no neon
  fixed palettes, no maths in C#.

### 3.2 Elevation

Source: [Fluent 2 elevation](https://fluent2.microsoft.design/elevation).

Elevation = perceived z-distance via shadow/light (and on Windows, **strokes**
often outline instead of key shadows).

| Level (Fluent ramp) | ACO use | WinUI approach |
|---|---|---|
| Rest / flat | Page canvas, lists | Layer / card theme brushes; `CardStrokeColorDefaultBrush` |
| Low (`shadow2`–`8`) | KPI cards, raised command band | Card brush + 1px stroke; optional `ThemeShadow` 4–8 |
| Mid (`shadow8`–`16`) | CommandBar flyouts, tooltips | Stock flyout chrome |
| High (`shadow28`–`64`) | `ContentDialog`, panels | Stock dialog + **Smoke**; don’t fake 64px shadows in XAML |

**Don’t:** multi-layer decorative shadows, glow, or brand-coloured drop shadows.
On brand-tinted surfaces prefer stock controls over inventing luminosity-adjusted
shadows.

### 3.3 Iconography

Source: [Fluent 2 iconography](https://fluent2.microsoft.design/iconography).

| Collection | ACO |
|---|---|
| **System icons** | Nav, CommandBar, status — `FontIcon` / `SymbolIcon`. Regular for wayfinding; Filled for selected/compact. |
| **Product launch icons** | Do **not** use Office/Teams product glyphs inside ACO chrome. |
| **File type icons** | Optional later for attachments — not nav. |

**Rules**

- Name icons for the **object** (Shield, Home), not the feature slogan.
- One metaphor per concept across the app; icon + label on the ribbon; icon-only
  needs tooltip + `AutomationProperties.Name`.
- Colour on system icons: at most one solid colour; prefer theme foreground.
- **Shipped:** Segoe **MDL2** code points in `RibbonIcons.cs` (WinUI default).
  **Target:** Segoe **Fluent Icons** font when set explicitly (§11).
- Never emoji as primary nav; never custom icon fonts.

### 3.4 Layout

Source: [Fluent 2 layout](https://fluent2.microsoft.design/layout).

**Spacing ramp (4px base)** — use these epx values (Fluent `size*` → WinUI
margin/padding/Spacing):

| Token-ish | epx | Typical ACO use |
|---|---:|---|
| size40 / 80 | 4 / 8 | Control internals, tight stacks |
| size120 / 160 | 12 / 16 | Ribbon padding, page content padding |
| size200 / 240 | 20 / 24 | Section gutters, large groups |
| size400 | 40 | Min touch / hit target where touch matters |

Also allow 2 / 6 / 10 when aligning Fluent icons to the 4px grid.

**Hierarchy:** more empty space around a block = more importance. Dense munshi
grids are OK; density ≠ clutter — use proximity to group related fields.

**Grid:** prefer `Grid` over deep `StackPanel` chains; list/details for
registers; avoid >2 nav levels without `BreadcrumbBar`.

**Responsive (Fluent breakpoints → WinUI):**

| Class | Range | ACO |
|---|---|---|
| large | ~640–1023 | Ribbon scrolls H; single-column forms |
| x-large+ | ≥1024 | List/details side-by-side where useful |

Techniques: reposition / resize / reflow / show-hide — not a second layout fork
unless AdaptiveTriggers need it (640 / 1008 as in coding standard).

**Cards:** only for interaction units or KPI glanceables — not every paragraph.

### 3.5 Material

Source: [Fluent 2 material](https://fluent2.microsoft.design/material).

| Material | When | ACO status |
|---|---|---|
| **Solid** | Default opaque surfaces (mode-aware) | ✅ Theme card/layer fills |
| **Mica** | App window base; tints with wallpaper when focused | ⚠ Deferred (SDK crash) — revisit; keep solid layer fallback |
| **Acrylic** | Transient light-dismiss (menus, flyouts) | ⏳ When flyouts ship |
| **Smoke** | Dim behind modals (always translucent black) | ✅ Stock under `ContentDialog` |

Do not fake glass with custom blurs or PNG overlays.

### 3.6 Motion

Source: [Fluent 2 motion](https://fluent2.microsoft.design/motion).

Principles: **Functional · Natural · Consistent · Appealing** — in that order.
ACO prioritises Functional + Consistent; keep Appealing subtle.

| Pattern | ACO use |
|---|---|
| Enter / exit | `InfoBar`, `ContentDialog`, TeachingTip (when added) |
| Elevation | Button / card press via stock control motion |
| Top-level | `Frame` page changes — **quick fade**, not sliding parade |
| Container transform | Responsive reflow only as needed |

**Rules**

- Prefer built-in theme transitions
  (`EntranceThemeTransition`, `ContentThemeTransition`, …) over custom
  storyboards.
- Short durations; ease-out for exits; avoid linear except rotation.
- Honour “no motion” / reduced-motion settings; no flashing; don’t animate
  off-focus chrome.
- Motion must **feedback** (saved, error) or **orient** (where did I go) —
  never decorate.

### 3.7 Shapes

Source: [Fluent 2 shapes](https://fluent2.microsoft.design/shapes).

Forms: **rectangle** (buttons, cards, fields), **circle** (avatars — rare),
**pill** (tags / ToggleSwitch channel — stock), **beak** (callouts / TeachingTip).

| Token | Radius | WinUI |
|---|---:|---|
| Small | 2 | Tiny badges |
| Medium | 4 | Controls — `ControlCornerRadius` |
| Large | 8 | Cards / overlays — `OverlayCornerRadius` |
| X-Large | 12 | Sheets / large popovers |
| None | 0 | Full-bleed bars at screen edge |

**Stroke:** Thin 1px borders via `CardStrokeColorDefaultBrush` /
`ControlStrokeColorDefaultBrush`. Don’t invent thick decorative frames.
Skip rounding where it creates awkward gaps (split controls, screen edge).

### 3.8 Typography

Source: [Fluent 2 typography](https://fluent2.microsoft.design/typography)
(Windows ramp).

- Font: **Segoe UI Variable** (WinUI default). Do not ship Inter / Roboto /
  random web fonts. Hindi/Devanagari: allow platform script fonts.
- Use built-in styles only — map to Fluent Windows ramp:

| Fluent Windows role | WinUI style |
|---|---|
| Caption | `CaptionTextBlockStyle` |
| Body / Body Strong | `BodyTextBlockStyle` / `BodyStrongTextBlockStyle` |
| Subtitle | `SubtitleTextBlockStyle` |
| Title | `TitleTextBlockStyle` (+ `PageTitleStyle` HeadingLevel 1) |
| Large Title / Display | `TitleLargeTextBlockStyle` / `DisplayTextBlockStyle` (sparingly) |

- **Sentence case** always. No all-caps for emphasis.
- LTR: left-align long copy; center only short callouts.
- Money figures: don’t shrink below body legibility to fit a card.
- Contrast: body ≥ 4.5:1; large text ≥ 3:1.

### 3.9 Navigation & commanding (platform patterns)

Still follow Windows [navigation](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics)
and [commanding](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics)
basics — they implement Fluent 2 “Natural” + “Focus” on desktop.

**ACO structure**

- Flat sections → ribbon tab strip; one level down → ribbon command band.
- Deeper civil paths → in-page list/details + `BreadcrumbBar` when depth > 2.
- Search: `AutoSuggestBox` → `/api/search`.
- Primary actions on page `CommandBar`; destructive → confirm; Viewer → disabled
  writes + calm explanation.

### 3.10 Usability & accessibility

Aligns with Fluent 2 **One for all, all for one**:

- Keyboard + visible focus; screen-reader names; ≥40×40 epx hit targets where
  touch matters.
- Loading never silent; offline = plain `InfoBar` + retry (no stack traces).
- Include reduced-motion; no seizure-risk flashes.

### 3.11 Writing (voice & tone)

Microsoft writing style + ACO cash-first voice:

| Pattern | Example |
|---|---|
| You / we | “We couldn’t save this payment.” |
| Lead with money truth | “Client still owes ₹1,20,000” |
| Active buttons | “Save payment”, “Generate RA bill” |
| Errors: cause + next step | “Backend isn’t running. Start ACO API or retry.” |
| No blame | “That GSTIN doesn’t look right…” |
| Money words | Net payable, Baaki, Received |

Dialog title ↔ button must **call and respond** (“Delete this vendor?” →
Delete / Cancel).

### 3.12 Widgets / glanceables

Windows widgets out of MVP. Home KPI band is the in-app glanceable — small set
of money facts + advisories only.

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
| Settings | Settings page (leaf tab) + `ScrollViewer` form | Prefer SettingsCard (Toolkit) when added |
| Search navigate | `AutoSuggestBox` | `/api/search` |
| Blocking question | `ContentDialog` | Smoke backdrop |
| Soft status | `InfoBar` | Semantic severity only |
| Progress | `ProgressRing` / `ProgressBar` | During API calls |
| Empty state | Short sentence + one action | “No vendors yet. Add a vendor.” |

**Forbidden without explicit owner approval:** custom title bars that fight the
system caption buttons, **owner-drawn or custom-templated** controls, third-party
UI kits that replace Fluent controls, emoji as primary navigation icons. (The
shipped ribbon is *not* owner-draw — it composes stock `ToggleButton` /
`AppBarButton` — and is the owner-approved shell; see §1.1.)

---

## 5. Information architecture & density

- **Owner persona:** fewer top-level items, money and Home first.
- **Munshi / operator:** denser grids OK, but still Fluent 2 spacing — density ≠
  clutter (**Built for focus**).
- Don’t put schedules, addresses, promo chips, and KPI soup in the first viewport
  of a **task** page. Home may show KPIs; a Payment page shows the payment job.
- Related records: in-page links or search — avoid forcing a full nav round-trip
  for “open this contract’s BOQ”.

---

## 6. AI & automation in the UI

Aligned with product trust rules + Fluent 2 focus:

- AI surfaces are **draft → confirm**. Use `InfoBar` / review lists, never silent
  writes.
- Label AI-origin clearly (“Suggested”, “Draft from scan”) using stock text /
  icons — not a fake “AI glow” (violates Calm / Focus).
- Confidence: prefer honest Low/High copy over fake precision meters.
- Fail soft: if the engine is off, show deterministic quick answers / empty
  draft state, rest of app unaffected.
- Prefer `TeachingTip` for one-shot guidance over permanent banners.

---

## 7. Theming & branding

- App name **ACO** (full name as quiet secondary) in shell / title —
  `SubtitleTextBlockStyle` + caption. Strings from `construction_app/branding.py`.
- Logo mark = existing geometry, **Radiant Orange** (`#FF4F18`) — brand palette
  only; letterhead on prints.
- Shell = Windows + Fluent 2 materials; not a marketing landing page.

---

## 8. Do / Don’t quick card (pin this)

**Do**

- Fluent 2 principles + stock WinUI 3 (+ Toolkit + LiveCharts2).
- Neutral surfaces + semantic status + orange accent sparingly.
- 4px spacing ramp; ControlCornerRadius 4 / OverlayCornerRadius 8.
- Segoe UI Variable type ramp; sentence case; cash-first copy.
- Theme resources; light **and** dark; API-driven numbers.

**Don’t**

- Custom controls, custom icon fonts, emoji nav, glow, purple AI skins.
- Brand orange as severity or full-bleed backgrounds.
- Business maths in C#; stack traces; blame-the-user errors.
- Decorative multi-layer shadows or fake Mica/Acrylic.
- One-off colours/fonts that ignore `ElementTheme`.

---

## 9. Review checklist for UI PRs

Copy into PR descriptions when touching `winui/`:

- [ ] Aligns with a Fluent 2 principle (§1) — name which.
- [ ] Foundations touched checked (§3: color / elevation / icon / layout /
      material / motion / shape / type).
- [ ] Control is stock Fluent / Toolkit / LiveCharts (name it).
- [ ] No new raw colours; theme brushes only (brand ramp only in `App.xaml`).
- [ ] Works in light and dark.
- [ ] Spacing on 4px ramp; corner radii stock.
- [ ] Primary action obvious; destructive confirmed or undoable.
- [ ] Empty / loading / error / offline states handled.
- [ ] Strings: sentence case, plain language, no unexplained jargon.
- [ ] Icons: Segoe `FontIcon` (MDL2 today / Fluent Icons when adopted); tooltip
      if icon-only.
- [ ] Numbers from API; no duplicated domain maths.
- [ ] Viewer/read-only respected if write affordances exist.
- [ ] Motion: stock / short / functional (or none).
- [ ] Matches a §4 page pattern (or documents why not).

---

## 10. Relationship to other docs

| Doc | Role |
|---|---|
| This file | **Fluent 2 design language + ACO WinUI rules** |
| [`../.github/instructions/winui3.instructions.md`](../.github/instructions/winui3.instructions.md) | WinUI 3 / Windows App SDK coding standard |
| [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) | Architecture, component mapping, phases U0–U7 |
| [`PRODUCT.md`](PRODUCT.md) | Audience, jobs-to-be-done, product non-negotiables |
| [`BRAND.md`](BRAND.md) | Mark, Radiant Orange, letterhead |
| [`API.md`](API.md) | JSON contract the client binds to |
| [`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) | Overall system + menu/workflow |

**Ownership:** local Windows agent implements and smoke-tests WinUI against this
guide; cloud/headless agent keeps the API and docs coherent but does not claim
WinUI screenshots from Linux.

---

## 11. Fluent inventory & enterprise-grade audit _(v2.0 · Fluent 2)_

Verified against `winui/ConstructionOS.WinUI` (25 pages + shell). Goal: **Fluent 2
enterprise ERP feel** on Windows — Natural · Focus · Inclusive · Unmistakably
Microsoft — without custom chrome. Design language:
[fluent2.microsoft.design](https://fluent2.microsoft.design/).

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
| Consolas on dump panes (Capture/Import/Assistant) | ✅ Now `Cascadia Mono` |
| Stale “theme forced Light” comment in `App.xaml` | ⚠ Fix comment (theme is runtime) |

### 11.7 Enterprise-grade target recipe (Fluent 2 summary)

```
Principles: Natural · Built for focus · One for all · Unmistakably Microsoft (+ ACO accent)
Color:      Neutral surfaces + semantic InfoBar + Radiant Orange CTAs only
Elevation:  Card stroke / low ThemeShadow; dialogs = Smoke + stock high elevation
Icons:      Fluent system icons (Filled when selected); MDL2 OK until Fluent font set
Layout:     4px ramp; list/details; ribbon ≤ peers; Breadcrumb when depth > 2
Material:   Solid default; Mica when SDK-safe; Acrylic flyouts; Smoke modals
Motion:     Functional/short; Frame fade; honour reduced-motion
Shapes:     ControlCornerRadius 4 / OverlayCornerRadius 8; thin strokes
Type:       Segoe UI Variable Windows ramp; sentence case
Trust:      AI draft → confirm; Viewer read-only
```

### 11.8 Relationship of this audit to other docs

| Doc | Role vs §11 |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) §2 | **What to build next** (P0–P4) |
| [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §5–6 | Architecture control/icon map (tkinter → WinUI) |
| [`RESEARCH.md`](RESEARCH.md) §4 | Condensed Fluent policy |
| This §11 | **What’s wired in the repo today** + gap list |
