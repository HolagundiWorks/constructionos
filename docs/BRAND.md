# ACO — Brand identity

_The visual identity for **ACO** (Accelerated Construction Operations). One
parametric source generates every asset — see "Regenerating assets" below._

## Name
- **ACO** — the short mark. Always upper-case, never "Aco" or "aco".
- **Accelerated Construction Operations** — the full name / expansion.
- Never revert to the retired name "Construction OS" / "Construction Operations
  System" in any outward asset.

## The mark — ACO openings (Fluent 2)

Three concentric forms in **Radiant Orange** on a **transparent** background.
The openings spell the acronym:

| Ring | Opening | Reads as |
|---|---|---|
| **Outer** | Bottom (6 o'clock) | **A** — arch / Accelerated |
| **Middle** | Right (3 o'clock) | **C** — Construction |
| **Centre** | Solid disc | **O** — Operations |

Soft rounded stroke caps; optional soft depth on the tile / document mark.
Keep clear space around the mark of at least the centre-dot diameter.

- **Primary mark:** orange on transparent (`logo_mark.png`, `logo_square.png`).
- **On a dark rail:** white mark on transparent (`logo_square_white.png`).
- **No orange plate** behind the mark — the glyph *is* the icon.
## The wordmark

The three words **stack**, set in a **geometric sans** (Segoe UI Semibold /
Liberation Sans Bold — Fluent-adjacent; the identity is font-agnostic). The
**initials A · C · O are picked out in Radiant Orange**, so the acronym reads
down the left edge and explains the name:

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
| **Radiant Orange** | `#FF4F18` | brand accent — mark body, A/C/O initials, primary actions. `branding.BRAND_ORANGE`, `tokens` accent. |
| **Orange Light** | `#FF9A5C` | tile / mark highlight stop (analogous). |
| **Orange Deep** | `#D93200` | tile / mark shadow stop (analogous). |
| **Ink** | `#14181F` | wordmark / body text on light. |
| **Slate** | `#6B7280` | secondary text. |
| **White** | `#FFFFFF` | mark/text on dark; tile knockout. |

Radiant Orange on white measures **3.29:1** — WCAG AA for **large** text only
(≥18 pt regular or ≥14 pt bold). Use it for the mark, large accents, and CTAs —
**never** for body copy or normal-size KPI figures. Full WinUI WCAG findings:
[`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md) §12.

## Typography
- **Product UI / documents:** Segoe UI (Fluent) — the app's working type.
- **Logo wordmark:** Segoe UI Semibold / Liberation Sans Bold (geometric all-caps).
  The logo is delivered as raster art, so the font need not be installed to use
  the assets.

## Assets (`construction_app/resources/`)
| File | What |
|---|---|
| `logo_square.png` | orange ACO mark on transparent — app tile / MSIX source |
| `logo_square_white.png` | white ACO mark on transparent — dark rail |
| `logo_mark.png` | orange ACO mark on transparent — documents, light surfaces |
| `logo_rectangle.png` | horizontal lockup, ink text (light backgrounds) |
| `logo_rectangle_white.png` | horizontal lockup, white text (dark backgrounds) |
| `logo_vertical.png` | vertical lockup (mark over wordmark), ink text |
| `logo_vertical_white.png` | vertical lockup, white text (dark backgrounds) |
| `app.ico` | multi-size icon (16–256) — WinUI exe / window / taskbar |
| `favicon.png` | 64px orange mark on transparent — browser tab |

**Where it shows up:** the tkinter window icon + rail (`assets.py`), the browser
tab (`/favicon.ico`) and printed-document letterhead (`assets.logo_rect_uri`),
the WinUI exe/window/taskbar icon (`ApplicationIcon` in the `.csproj`), and the
MSIX tiles (generated from `logo_square.png` by `winui/build-msix.ps1`).

## Regenerating assets

All brand art is drawn from **one** parametric source — never hand-edit the PNGs.

**Canonical (cross-platform, Fluent 2):**

```bash
# needs: python3-cairo python3-pil (apt) — build tooling only, not an app dep
python branding/make_brand.py
python branding/make_brand.py --out-dir /tmp/aco-brand-preview
```

**Windows twin** (delegates to Python when available; else GDI+):

```powershell
pwsh branding/make-brand.ps1
pwsh branding/make-brand.ps1 -OutDir <scratch>
```

To evolve the identity, change the geometry / colours / wordmark in
`branding/make_brand.py` (and keep `make-brand.ps1` in sync) and re-run — every
asset stays consistent. The contractor's own uploaded letterhead logo is separate
and lives in the data folder (`assets.firm_logo_path`).
