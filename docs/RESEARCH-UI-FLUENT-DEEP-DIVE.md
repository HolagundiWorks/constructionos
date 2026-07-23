# UI deep dive — Fluent Design, colour, appearance & workflow

**Date:** 2026-07-23  
**Scope:** Reports only — how to make the **WinUI 3** client look, feel, and
flow like a native Windows 11 app while staying ACO (cash-first, Radiant Orange,
stock controls only).  
**Canonical Microsoft hub:** [Design Windows apps](https://learn.microsoft.com/en-us/windows/apps/design/)  
**Companion:** [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md)
(implementation checklist) · [`BRAND.md`](BRAND.md) · [`ROADMAP.md`](ROADMAP.md)

When this research and Microsoft Learn disagree on a **Fluent mechanic**,
**Microsoft wins**. When they disagree on **product voice** (baaki, cash-first),
**ACO wins**.

---

## 1. Executive verdict

| Area | Fluent fit today | Grade | Headline gap |
|---|---|---|---|
| Control set | Stock WinUI + theme brushes | **A−** | Keep the “no custom chrome” rule |
| Colour / accent | Radiant Orange `#FF4F18` wired as `SystemAccentColor` | **B** | Accent sparingly; **3.29:1** on white → large text / fill only |
| Theme modes | **Forced Light** (`App.xaml`) | **C** | Fluent *Personal* expects light **and** dark (or system) |
| Materials | Mica **disabled** (startup crash history) | **D** | Flat card/layer brushes ≠ Windows 11 signature material |
| Typography | Segoe defaults via WinUI | **A−** | Enforce type ramp styles; avoid logo font in UI |
| Geometry | Stock control radii | **B+** | Dual skin: tkinter/web tokens are **0-radius**; WinUI must stay Fluent-rounded |
| Navigation / shell | Excel-style ribbon (stock ToggleButton + AppBarButton) | **B** | Owner-approved; still must obey ≤8 peers, clarity, no pogo-stick |
| Workflow IA | Persona menu + sections | **B−** | Money/civil task flows still thin on many pages (DataTable) |
| Writing / voice | Partially plain-language | **B** | Systematise Fluent writing style on every button/error |
| Motion | Mostly stock | **B** | Prefer feedback motion over decoration; keep crash-safe |

**Verdict:** ACO already has a strong **written** Fluent contract
(`UI-PRINCIPLES-AND-GUIDELINES.md`). The client **implements accent + theme
brushes well**, but under-delivers on **materials, dual theme, and
task-shaped workflows** — the three things that make a Windows 11 app feel
“complete + coherent” rather than “web form in a window.”

---

## 2. Microsoft Fluent map (what we are aiming at)

From [Windows 11 design principles](https://learn.microsoft.com/en-us/windows/apps/design/design-principles):

| Principle | Microsoft meaning | ACO translation |
|---|---|---|
| **Effortless** | Easy to do what I want, focus + precision | Defaults, FK pickers, one primary action, server-side maths |
| **Calm** | Soft, decluttered, fades into background | Theme brushes; orange only for CTA/selection; no rainbow chrome |
| **Personal** | Adapts to device + preferences | Honour system light/dark; persona menus; remember-last fields |
| **Familiar** | New look, no learning curve | Stock Gallery controls; Settings/search placement users know |
| **Complete + Coherent** | Seamless across the app | Same empty/loading/error; same CommandBar recipes |

**Signature experiences** (same Learn article + style hub):

1. **Color** — calming foundation; emphasize only when necessary  
   ([Color in Windows](https://learn.microsoft.com/en-us/windows/apps/design/style/color))  
2. **Elevation / layering** — hierarchy by surface, not heavy boxes  
3. **Iconography** — Segoe Fluent Icons only  
4. **Materials** — Mica (window), Acrylic (flyouts), Smoke (dialogs)  
   ([Materials](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/materials))  
5. **Geometry** — stock corner radii / control templates  
6. **Typography** — Segoe UI Variable + type ramp  
   ([Typography](https://learn.microsoft.com/en-us/windows/apps/design/style/typography))  
7. **Motion** — reactive, direct, context-appropriate  

Interactive reference: **WinUI 3 Gallery** (Microsoft Store / GitHub).

---

## 3. Colour palette deep dive

### 3.1 Brand tokens (identity)

From [`BRAND.md`](BRAND.md) / `branding.BRAND_ORANGE` / `tokens.LIGHT`:

| Token | Hex | Role |
|---|---|---|
| **Radiant Orange** | `#FF4F18` | Mark, A/C/O initials, **primary accent / CTA** |
| Accent soft | `#FDE7DF` | Selection wash (Orange@~14%) |
| Accent dark | `#DB3E0F` | Hover (desktop tokens) |
| Ink / Coal | `#14181F` / `#141517` | Body on light |
| Slate / muted | `#6B7280` / `#5B616B` | Secondary |
| Fog canvas | `#F2F4F7` | Desktop/web ground |
| White surface | `#FFFFFF` | Cards |
| Warning (saffron) | `#FF9932` | Status — **not** the brand accent |
| Data-viz oranges | e.g. `#FF832B` | Charts only — **never CTA** (`tokens.py`) |

WinUI wiring (`App.xaml`): full `SystemAccentColor` + Light1–3 / Dark1–3 ramp so
hover/pressed/selected stay on-brand. **Severity brushes left alone** (Critical /
Caution / Success / Attention) — correct Fluent practice.

### 3.2 Fluent colour rules → ACO compliance

| Microsoft rule | ACO today | Improve |
|---|---|---|
| Use colour **meaningfully / sparingly** | Accent on primary buttons + selection | Never paint entire ribbon orange; keep chrome neutral |
| One colour for **interactivity** | Accent = interactive | Links/secondary actions → theme secondary, not orange |
| Colour is **personal** | Forced Light; system accent overridden by brand | Offer **Light / Dark / Use Windows** in Settings; keep brand accent |
| Colour is **cultural** | Orange reads energy/construction in India; OK | Avoid red/green-only meaning (colorblind) |
| Contrast | Orange on white **3.29:1** (AA large only) | Body text never orange; CTAs = filled AccentButton (white on orange) |
| Lighting | Site offices = glare | Prefer light theme default; dark for night office |
| Colorblindness | Status via InfoBar severity | Pair colour with **icon + text** (“Overdue”, “On track”) |

### 3.3 Recommended WinUI palette policy (precise)

```
Canvas / page     → ThemeResource ApplicationPageBackgroundThemeBrush
                     or LayerFill / CardBackground (already used in shell)
Chrome (ribbon)   → CardBackground + LayerFill + CardStroke  (neutral)
Primary action    → AccentButtonStyle (SystemAccentColor fill)
Secondary action  → Default Button
Destructive       → Critical text / confirm dialog — not orange
Selection / focus → Accent soft / system focus visual
Charts            → tokens DATA_VIZ or theme-aware LiveCharts — never SystemAccent
                    as the only series colour if it collides with CTA meaning
Money figures     → TextFillColorPrimary; credit/debit via text/icon, not hue alone
```

**Do not** port desktop `tokens.py` **0-radius / Urbanist** literally into WinUI.
Those govern **tkinter + web**. WinUI stays **Fluent geometry + Segoe UI
Variable**. Shared truth = **Radiant Orange hex + semantic status names**, not
pixel-identical chrome.

### 3.4 Optional refined accent ramp (if contrast complaints arise)

Keep `#FF4F18` for brand mark. If filled buttons fail in bright light, prefer:

- Slightly darker fill for **small** accent text buttons: closer to
  `SystemAccentColorDark1` `#CC3F13` (better contrast), **or**
- Keep fill `#FF4F18` + **white Semibold label ≥14px** (large-text path).

Never drop orange body text on white.

---

## 4. Appearance deep dive

### 4.1 Materials (highest visual win)

Microsoft: **Mica** on the app window (focus-aware tint from wallpaper),
**Acrylic** on flyouts/menus, **Smoke** under modal dialogs.

| Surface | Should be | ACO today | Priority |
|---|---|---|---|
| Main window | `MicaBackdrop` / `DesktopAcrylicBackdrop` | Explicitly **removed** (native crash risk noted in `MainWindow.xaml.cs`) | **P0** revisit post-activation, gated, crash-tested |
| Context menus / flyouts | Acrylic (stock) | Framework default when used | Keep stock menus |
| `ContentDialog` | Smoke | Stock dialogs | Keep |
| Ribbon / content | Layer + card brushes | Present | Good interim without Mica |

**Precision rule:** do not fake Mica with custom blur PNGs. Either safe system
backdrop or honest flat theme brushes.

### 4.2 Elevation & layering

Fluent hierarchy: darker / recessed = less important; lighter elevated =
interactive content.

Shell already:

- Row 0 chrome → `CardBackgroundFillColorDefaultBrush`
- Ribbon band → `LayerFillColorDefaultBrush` + bottom stroke
- Content `Frame` margin 12

**Improve:**

- Home KPI tiles: one elevation level (card), not nested cards-in-cards.
- Registers: list/details with a single hairline separator — avoid boxing every
  field.
- Don’t add drop shadows beyond stock control templates.

### 4.3 Typography & density

Microsoft type ramp (abbrev.): body **14/20 Regular**; titles **Semibold**;
sentence case; min ~12 Regular / ~14 Semibold; prefer Semibold over Bold;
avoid Italic for UI.

| Do | Don’t |
|---|---|
| `PageTitleStyle` / `TitleTextBlockStyle` / `BodyTextBlockStyle` | Hard-coded FontSize soup |
| Sentence case: “Purchase orders” | “PURCHASE ORDERS” |
| Money: tabular feel via consistent column alignment | Shrink ₹ figures below 12px |
| Hindi/Devanagari: OS-mapped fonts | Force Segoe on Indic scripts |

Desktop tokens mention **Urbanist** — **WinUI must not** load Urbanist for
chrome; brand wordmark is raster only (`BRAND.md`).

### 4.4 Iconography

Segoe Fluent Icons via `FontIcon` / ribbon `RibbonIcons` — correct.

**Improve:** one glyph ↔ one concept across Assistant / AI Engine / Capture;
icon-only utilities always get `ToolTipService` + `AutomationProperties.Name`
(partially done).

### 4.5 Motion

Microsoft: reactive, direct, context-appropriate.

| Use | Avoid |
|---|---|
| InfoBar show/hide, dialog open, ProgressRing | Decorative parade storyboards |
| Brief success check on Save (stock) | Accent “glow” pulse on AI |
| Frame navigate default | Custom page flips that fight crash-sensitive SDK |

### 4.6 Light / dark (Personal principle)

**Gap:** `RequestedTheme="Light"` freezes the app. UI principles already require
light **and** dark smoke tests; product currently contradicts Fluent *Personal*.

**Recommendation:**

1. Settings: **Light | Dark | Windows default**.  
2. Persist in `app_settings` / `AppSettings`.  
3. Keep Radiant Orange accent ramp in both modes (already have Dark1–3 keys).  
4. Re-smoke charts + KPI cards in dark (LiveCharts brushes theme-aware).  
5. Printed HTML letterhead stays light — print ≠ shell theme.

---

## 5. Navigation & shell (Fluent vs Excel ribbon)

### 5.1 Microsoft navigation principles

From [Navigation basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics):

- **Consistency, simplicity, clarity**
- Prefer **≤ ~8 peers** in a flat group
- Avoid deep hierarchy without **BreadcrumbBar**
- Avoid **pogo-sticking** (up then down for related content)
- Use the **right structure**: flat for peers; hierarchical for parent/child
- Prefer stock: Frame + NavigationView / Tabs / Breadcrumb / list-details

### 5.2 What ACO ships

Owner-directed **Excel-style ribbon** composed of **stock** controls
(ToggleButton section strip + AppBarButton command band + AutoSuggestBox +
utility cluster). Documented departure because `NavigationView` Top /
`SelectorBar` native-crashed on the current Windows App SDK
(`WINUI3-MIGRATION.md`).

**This can still be Fluent-compliant if:**

| Rule | How the ribbon obeys |
|---|---|
| Familiar placement | Search right; Settings in utility cluster |
| ≤8 top peers | Sections from persona menu — keep Owner persona lean |
| Clarity | Section label ↔ band commands match catalog names |
| No deep nav without breadcrumb | Project → BOQ → MB needs in-page hierarchy + BreadcrumbBar |
| No pogo-stick | Page CommandBar for Approve / Print / Allocate without leaving |

### 5.3 Shell appearance upgrades (without abandoning ribbon)

1. **Brand mark** — compact orange gauge glyph left of “ACO” (raster/`Image`),
   not coloured chrome.  
2. **Selected section** — ToggleButton uses accent / subtle fill only; other
   tabs quiet.  
3. **Ribbon band height** — calm; icon-over-label AppBarButtons with tooltips.  
4. **Content margin** — keep 12–16; page inner padding 16–24.  
5. **Title bar** — prefer system caption; don’t fight with custom title bars.  
6. When SDK allows: evaluate **NavigationView Left** for munshi density vs keep
   ribbon for Owner — persona-specific shell is Fluent *Personal*.

---

## 6. Workflow deep dive (task-shaped UI)

Fluent commanding ([Commanding basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics)):
put frequent core commands **on the canvas**; organize the rest in CommandBar;
confirm only irreversible / high-cost actions; give feedback without clutter.

### 6.1 Contractor journeys (design around these)

| Journey | Happy path | Fluent pattern | Current WinUI gap |
|---|---|---|---|
| **Kitna baaki** | Home → party → ageing → record receipt | List/details + Accent “Receive” | Partially fixed on main (Cash & Parties); keep deepening |
| **Get paid (RA)** | Contract → MB → Generate RA → Approve → Print | Wizard-ish hierarchical + breadcrumb | BOQ/RA still shallow / miswired historically |
| **Pay labour** | Site + week → muster → payout → payments | Dense grid + primary “Record payout” | Muster often DataTable |
| **Buy material** | Requisition → PO → GRN match → vendor invoice → pay | Step indicator *or* clear next InfoBar | GRN match thin |
| **Weekly plan** | Look-ahead → Done/Not done + reason → PPC | Binary toggles + reason ComboBox | LookaheadPage exists — deepen LPS honesty |
| **Ask data** | Assistant → answer → optional Capture confirm | Conversation + draft/confirm | Must not share Capture route |

### 6.2 Page recipe matrix (appearance × workflow)

| Page type | Appearance | Commands | Empty / error |
|---|---|---|---|
| Home | KPI cards (few) + InfoBar advisories | Open top advice | Calm offline InfoBar |
| Master register | List/details, FK ComboBox | Add / Save / Delete (confirm if referenced) | “No vendors yet. Add a vendor.” |
| Money doc | Form + lines + read-only totals | Save / Print | Validation InfoBar |
| Report (P&L, GST, PPC) | Period picker + table/chart | Export / Refresh | “No postings in this period.” |
| Tools / Settings | Scroll form sections | Save & reconnect (Accent) | Connection status InfoBar |

### 6.3 Command placement rules (precision)

| Action class | Surface | Confirm? |
|---|---|---|
| Save draft / refresh | Canvas or CommandBar primary | No |
| Add line / Add master | Canvas | No |
| Approve bill / Record payment / Generate RA | Accent primary | Yes if money moves |
| Delete / Cancel doc | Overflow or dialog | Yes |
| AI suggestion apply | Capture confirm | Always |

Feedback: ProgressRing while API runs; success via short InfoBar or inline status
in CommandBar content — not a modal for ordinary Save.

### 6.4 Writing style (Fluent voice)

From [Writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style):
warm & relaxed · lend a hand · crisp & clear; lead with what matters; active
voice; short; you/we; contractions OK; sentence case; errors don’t blame.

| Instead of | Write |
|---|---|
| “Error 500” | “We couldn’t reach the ACO backend. Start it or tap Retry.” |
| “Invalid GSTIN” | “That GSTIN doesn’t look right. Check all 15 characters.” |
| “AR balance” | “Still owed” / “Baaki” |
| “Submit” (ambiguous) | “Save payment” / “Generate RA bill” |

Dialog **call-and-response:** title asks; buttons answer
(“Delete this vendor?” → Delete / Cancel).

---

## 7. Dual-skin coherence (WinUI vs tkinter/web)

| Concern | Desktop/web (`tokens.py`) | WinUI | Policy |
|---|---|---|---|
| Accent | `#FF4F18` | `SystemAccentColor` | **Shared** |
| Canvas | Fog `#F2F4F7` | Theme page/layer brushes | Shared *feel*, not hex-locked |
| Radius | **0** (hyper-minimal) | Fluent control radii | **Do not unify** — platform-native |
| Font UI | Urbanist fallback → system | Segoe UI Variable | **Do not unify** |
| Logo | Raster BankGothic lockup | Mark + “ACO” text | Shared assets |
| Dark mode | Tokens exist | Forced off | Enable WinUI to match product |

Goal: **same language and accent**, native materials per shell — not a pixel clone.

---

## 8. Gap → improvement backlog (UI only)

### P0 — Appearance honesty (Fluent signature)

1. Safe **Mica** (or documented deferral with theme brushes) after activation.  
2. Settings: **Light / Dark / System**.  
3. Accent used only on CTA + selection; audit orange text on white.  
4. Empty / loading / error **one recipe** on every page (`ProgressRing`, InfoBar).

### P1 — Workflow-shaped pages (effortless)

5. List/details for high-switch masters (already MastersPage — extend pattern).  
6. MB → RA → Print flow with BreadcrumbBar.  
7. Muster grid + “Record payout” Accent command.  
8. GRN three-way match colours via severity + text (not colour alone).  
9. Assistant ≠ Capture routes (clarity).

### P2 — Coherence & polish

10. Shared page padding + CommandBar positions.  
11. Type ramp audit (no random FontSize).  
12. Persona: Owner lean ribbon vs Operator denser band.  
13. Hindi/Hinglish string pass on Money + Home.  
14. Chart palette from theme / DATA_VIZ, labelled series.

### P3 — Motion & a11y

15. Keyboard tab order = reading order; focus visuals intact.  
16. Screen-reader names on all icon-only utilities (continue U7).  
17. Contrast re-measure orange CTAs in both themes.  
18. Prefer undo *or* confirm on destructive edits.

---

## 9. Design QA checklist (every UI PR)

Against Microsoft Learn + this doc:

- [ ] Stock control only (no custom template)  
- [ ] ThemeResources for colour (no raw hex in page XAML except documented app dictionary)  
- [ ] Accent sparingly; status ≠ accent  
- [ ] Sentence case; Fluent writing on errors  
- [ ] Primary command obvious; confirm only if money/irreversible  
- [ ] Loading + empty + offline states present  
- [ ] Light **and** dark checked (once dark enabled)  
- [ ] AutomationProperties on icon-only  
- [ ] No maths in C#; API owns numbers  
- [ ] Cash-first copy on Money/Home  

Pin also: [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md) §8 Do/Don’t.

---

## 10. What “great” looks like (target experience)

A munshi opens ACO on a dusty site laptop:

1. Window feels like **Windows 11** (Mica, calm chrome, orange only on Save).  
2. Ribbon shows **Money** → band shows **Payments / Parties / Cash flow** with
   clear glyphs.  
3. Parties list/details: baaki in primary text; **Receive** is the Accent button.  
4. Errors sound like a colleague: “We couldn’t save — check the amount and try
   again.”  
5. Dark evening shift: shell follows Windows dark; charts still readable.  
6. RA path never dumps them into Import; breadcrumb shows Contract / BOQ / RA.

That is Fluent *Effortless + Calm + Familiar* with ACO product voice — not a
marketing landing page, not a purple SaaS dashboard.

---

## 11. Sources

- [Design Windows apps overview](https://learn.microsoft.com/en-us/windows/apps/design/)  
- [Windows 11 design principles](https://learn.microsoft.com/en-us/windows/apps/design/design-principles)  
- [Color in Windows](https://learn.microsoft.com/en-us/windows/apps/design/style/color)  
- [Typography in Windows](https://learn.microsoft.com/en-us/windows/apps/design/style/typography)  
- [Materials (Mica, Acrylic, Smoke)](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/materials)  
- [Navigation basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics)  
- [Commanding basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics)  
- [Writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)  
- WinUI 3 Gallery (interactive)  
- Repo: `App.xaml`, `MainWindow.xaml(.cs)`, `tokens.py`, `BRAND.md`,
  `UI-PRINCIPLES-AND-GUIDELINES.md`

---

*Report only. Implement on the local Windows track; cloud agents keep domain/API
maths free of UI chrome.*
