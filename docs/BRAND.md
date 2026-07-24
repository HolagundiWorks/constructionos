# ACO — Brand identity

_The visual identity for **ACO** (Accelerated Construction Operations). One
parametric source generates every asset — see "Regenerating assets" below._

## Name
- **ACO** — the short mark. Always upper-case, never "Aco" or "aco".
- **Accelerated Construction Operations** — the full name / expansion.
- Never revert to the retired name "Construction OS" / "Construction Operations
  System" in any outward asset.

## The mark — "the gauge C"
A bold **open ring** (a **C**, for _Construction_) wrapped around a **concentric
target** — a ring and a centre dot — reading as a **gauge / dial**: precision,
measurement, _Operations under control_. It is a single-colour mark; it never
carries a gradient or a second fill colour.

- **On a tile / dark surface:** white mark on a Radiant-Orange squircle
  (`logo_square.png`) or white on transparent (`logo_square_white.png`).
- **On a light surface / document:** the orange mark on transparent
  (`logo_mark.png`).
- Keep clear space around the mark of at least the centre-dot diameter.

## The wordmark
The three words **stack**, set in a wide, squared techno face (**BankGothic** —
a Good-Times-style industrial cap; the identity is font-agnostic, so any wide
geometric all-caps face is acceptable). The **initials A · C · O are picked out
in Radiant Orange**, so the acronym reads down the left edge and explains the
name:

```
[mark]   A CCELERATED
         C ONSTRUCTION
         O PERATIONS
```

Horizontal lockups: `logo_rectangle.png` (ink text on light) and
`logo_rectangle_white.png` (white text on dark). A **vertical lockup** — mark
over the same stacked wordmark, for tall / square contexts — is
`logo_vertical.png` / `logo_vertical_white.png`. Initials stay orange in all.

## Colour
| Token | Hex | Use |
|---|---|---|
| **Radiant Orange** | `#FF4F18` | the accent — the mark, the A/C/O initials, primary actions. `branding.BRAND_ORANGE`, `tokens` accent. |
| **Ink** | `#14181F` | wordmark / body text on light. |
| **Slate** | `#6B7280` | secondary text. |
| **White** | `#FFFFFF` | mark/text on dark; tile knockout. |

Radiant Orange on white measures **3.29:1** — WCAG AA for **large** text only
(≥18 pt regular or ≥14 pt bold). Use it for the mark, large accents, and CTAs —
**never** for body copy or normal-size KPI figures. Full WinUI WCAG findings:
[`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md) §12.

## Typography
- **Product UI / documents:** Segoe UI (Fluent) — the app's working type.
- **Logo wordmark:** BankGothic (or any wide, squared, all-caps geometric face).
  The logo is delivered as raster art, so the font need not be installed to use
  the assets.

## Assets (`construction_app/resources/`)
| File | What |
|---|---|
| `logo_square.png` | white mark on an orange squircle — app tile, MSIX source |
| `logo_square_white.png` | white mark on transparent — dark rail |
| `logo_mark.png` | orange mark on transparent — documents, light surfaces |
| `logo_rectangle.png` | horizontal lockup, ink text (light backgrounds) |
| `logo_rectangle_white.png` | horizontal lockup, white text (dark backgrounds) |
| `logo_vertical.png` | vertical lockup (mark over wordmark), ink text |
| `logo_vertical_white.png` | vertical lockup, white text (dark backgrounds) |
| `app.ico` | multi-size icon (16–256) — WinUI exe / window / taskbar |
| `favicon.png` | 64px orange mark on white — browser tab |

**Where it shows up:** the tkinter window icon + rail (`assets.py`), the browser
tab (`/favicon.ico`) and printed-document letterhead (`assets.logo_rect_uri`),
the WinUI exe/window/taskbar icon (`ApplicationIcon` in the `.csproj`), and the
MSIX tiles (generated from `logo_square.png` by `winui/build-msix.ps1`).

## Regenerating assets
All brand art is drawn vector-crisp from **one** parametric source — never
hand-edit the PNGs:

```powershell
pwsh branding/make-brand.ps1          # -> construction_app/resources (live set)
pwsh branding/make-brand.ps1 -OutDir <scratch>   # preview elsewhere first
```

To evolve the identity, change the geometry / colours / wordmark in
`branding/make-brand.ps1` and re-run — every asset stays consistent. Windows-only
(uses GDI+); the contractor's own uploaded letterhead logo is separate and lives
in the data folder (`assets.firm_logo_path`).
