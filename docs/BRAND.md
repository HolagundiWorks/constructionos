# ACO — Brand identity

_The visual identity for **ACO** (Accelerated Construction Operations). One
parametric source generates every asset — see "Regenerating assets" below._

## Name
- **ACO** — the short mark. Always upper-case, never "Aco" or "aco".
- **Accelerated Construction Operations** — the full name / expansion.
- Never revert to the retired name "Construction OS" / "Construction Operations
  System" in any outward asset.

## The mark

Three concentric forms in a single colour (Radiant Orange on transparent, or
white on transparent for dark surfaces):

| Ring | Geometry |
|---|---|
| **Outer** | Open ring — gap at upper-right (~1–2 o'clock) |
| **Middle** | Open ring — gap at top (12 o'clock) |
| **Centre** | Solid disc |

Uniform stroke weight, rounded caps, flat (no bevel, no plate behind the mark).
Keep clear space around the mark of at least the centre-dot diameter.

- **Primary:** orange on transparent — `logo_mark.png`, `logo_square.png`
- **Dark rail:** white on transparent — `logo_square_white.png`

## The wordmark

The three words **stack**, set in a **geometric sans** (Segoe UI Semibold /
Liberation Sans Bold). The **initials A · C · O are picked out in Radiant
Orange**, so the acronym reads down the left edge:

```
[mark]   A CCELERATED
         C ONSTRUCTION
         O PERATIONS
```

Horizontal: `logo_rectangle.png` / `logo_rectangle_white.png`.
Vertical: `logo_vertical.png` / `logo_vertical_white.png`.

## Colour

| Token | Hex | Use |
|---|---|---|
| **Radiant Orange** | `#FF4F18` | mark, A/C/O initials, primary actions. `branding.BRAND_ORANGE` |
| **Orange Light** | `#FF9A5C` | optional analogous highlight |
| **Orange Deep** | `#D93200` | optional analogous shadow |
| **Ink** | `#14181F` | wordmark / body on light |
| **Slate** | `#6B7280` | secondary text |
| **White** | `#FFFFFF` | mark/text on dark |

Radiant Orange on white measures **3.29:1** — WCAG AA for **large** text only
(≥18 pt regular or ≥14 pt bold). Never for body copy or normal-size KPI figures.
See [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md) §12.

## Typography
- **Product UI / documents:** Segoe UI (Fluent).
- **Logo wordmark:** Segoe UI Semibold / Liberation Sans Bold (rasterised into assets).

## Assets (`construction_app/resources/`)
| File | What |
|---|---|
| `logo_square.png` | orange mark on transparent — app tile / MSIX |
| `logo_square_white.png` | white mark on transparent — dark rail |
| `logo_mark.png` | orange mark on transparent — documents |
| `logo_rectangle.png` | horizontal lockup, ink text |
| `logo_rectangle_white.png` | horizontal lockup, white text |
| `logo_vertical.png` | vertical lockup, ink text |
| `logo_vertical_white.png` | vertical lockup, white text |
| `app.ico` | multi-size icon (16–256) |
| `favicon.png` | 64px orange mark on transparent |

**Where it shows up:** tkinter window icon + rail (`assets.py`), browser tab,
printed letterhead (`assets.logo_rect_uri`), WinUI exe/taskbar icon, MSIX tiles
(`winui/build-msix.ps1`).

## Regenerating assets

Never hand-edit the PNGs.

```bash
# needs: python3-cairo python3-pil — build tooling only
python branding/make_brand.py
python branding/make_brand.py --out-dir /tmp/aco-brand-preview
```

```powershell
pwsh branding/make-brand.ps1          # delegates to Python when available
```

Evolve geometry / colour in `branding/make_brand.py` (keep `make-brand.ps1` in
sync). Firm letterhead uploads are separate (`assets.firm_logo_path`).
