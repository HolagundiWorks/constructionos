"""HCW-UI design tokens — the single source of truth for **both** the tkinter
desktop and the browser/LAN front end, so one design system governs the whole
app (a strict project rule).

Ported from the kit's authoritative token file (``hcwux/src/tokens.ts``, kit
**v1.4.0**) — "the SINGLE source of truth for colour, shape, surface and type
across every portal." Design language: **hyper-minimalist light with a
Radiant-Orange accent** — Fog-Gray canvas, Pure-White cards, Coal-Black ink,
**square surfaces (0 radius)**, flat panels defined by spacing and hairlines
rather than boxes. The accent is a FILL / active state only; links use slate,
never the accent.

Pure standard library, no tkinter, on purpose: ``theme.py`` builds the desktop
ttk styles from it and ``webrender.py`` builds the web CSS from it, but the web
server must import it while running head-less. Keeping the values here — and
testing that both surfaces use them — is what stops the two skins drifting.

v1.4.0 audit: the core palette and shape are unchanged from v1.3; this revision
adds the kit's newer, cross-surface token families — the **data-viz** palette,
**LAYOUT** grid tokens, **DENSITY** control heights, **STATUS_SHAPE**
(shape-not-just-colour for urgency, WCAG 1.4.1), the expanded **TYPE** ladder,
and **Urbanist** as the brand font (with the same system fallback both skins
render when Urbanist isn't installed).
"""

# ── Colour schemes ────────────────────────────────────────────────────────────
# Solid-hex approximations of the kit's alpha tokens (tkinter has no alpha):
# hairline = Coal@10% over the ground; accent_soft = Orange@14–20% over the card.
LIGHT = {
    'canvas':      '#F2F4F7',   # Fog Gray — the calm ground (tokens.background)
    'surface':     '#FFFFFF',   # Pure White — cards (layer01)
    'surface2':    '#E7EAF0',   # quiet fog — secondary / selected (layer02)
    'rail':        '#FFFFFF',   # the instrument rail — a white panel on the fog
    'ink':         '#141517',   # Coal Black (textPrimary / ink)
    'muted':       '#5B616B',   # secondary slate (textSecondary)
    'helper':      '#667085',   # helper slate (textHelper) — AA on fog/white
    'hairline':    '#DCDEE1',   # Coal@10% separator
    'accent':      '#FF4F18',   # Radiant Orange — active / CTA only
    'accent_soft': '#FDE7DF',   # selected-row wash (Orange@14%)
    'accent_dark': '#DB3E0F',   # accent hover
    'on_accent':   '#FFFFFF',
    'hover':       '#ECEEF2',   # neutral hover wash (Coal@04%)
    'entry':       '#FFFFFF',
    'heading':     '#E7EAF0',   # table heading band
    'success':     '#1B7F5A',   # supportSuccess — deep teal-green
    'warning':     '#FF9932',   # supportWarning — saffron (not the accent)
    'error':       '#C8442E',   # supportError — burnt red
    'info':        '#3B5568',   # supportInfo — slate (links + info)
    'wash_bad':    '#FCE4E4',
    'wash_warn':   '#FDF1DE',
    'wash_good':   '#E4F1E8',
    'wash_muted':  '#EEF1F4',
}

DARK = {
    'canvas':      '#101215',
    'surface':     '#191C21',
    'surface2':    '#232830',
    'rail':        '#191C21',
    'ink':         '#EDEFF3',
    'muted':       '#9AA2AE',
    'helper':      '#98A1AD',
    'hairline':    '#2E333B',
    'accent':      '#FF5C28',   # accent lifts slightly for AA on dark
    'accent_soft': '#3E2A20',
    'accent_dark': '#FF7A4D',   # hover lifts LIGHTER on dark canvases
    'on_accent':   '#FFFFFF',
    'hover':       '#272A2E',
    'entry':       '#191C21',
    'heading':     '#232830',
    'success':     '#4CC29A',
    'warning':     '#FFB25C',
    'error':       '#F07862',
    'info':        '#8FB4CE',
    'wash_bad':    '#3A2020',
    'wash_warn':   '#39301E',
    'wash_good':   '#1E3329',
    'wash_muted':  '#232830',
}

SCHEMES = {'light': LIGHT, 'dark': DARK}

# ── Shape ─────────────────────────────────────────────────────────────────────
# Square by default; rounding is itself a signal and is spent sparingly.
RADIUS = 0            # surfaces / panels / inputs — square everywhere
BUTTON_RADIUS = 4     # workspace buttons
DIALOG_RADIUS = 8     # the one rounded surface panel (dialogs, login card)
DOCK_PILL_RADIUS = 9999   # ActionDock tray + dock buttons — full capsule
TAB_ALERT_WIDTH = 3   # active tab / nav = a 3px accent inset rule, not a fill

# ── Scale ─────────────────────────────────────────────────────────────────────
SPACING_UNIT = 8      # 8px base grid
# Ladder aligns with the kit's productive density steps (2/4/8/12/16/24/32/40/48/64).
SPACING = {'none': 0, 'xxs': 2, 'xs': 4, 'sm': 8, 'compact': 12, 'md': 16,
           'lg': 24, 'xl': 32, 'section': 40, 'xxl': 48, 'xxxl': 64}

# Layout / grid organisation (kit LAYOUT). Shared so the desktop rail and the
# web shell use one set of proportions.
LAYOUT = {
    'columns': 12,
    'gutter': 16,
    'margin': 16,
    'rail_width': 240,
    'rail_width_collapsed': 56,
    'content_max_width': 1280,
    'taskbar_height': 56,
}

# Enterprise density targets — WCAG touch target + compact chrome heights (px).
DENSITY = {'touch_target': 44, 'control': 40, 'control_compact': 38}

# Working-memory capacity caps (Cowan ~4±1) — surfaces shouldn't exceed these
# without progressive disclosure.
CAPACITY = {'kpi_strip': 4, 'dock_actions': 5, 'rail_objectives': 5,
            'toast_stack': 2, 'awareness_lines': 3, 'decision_alternatives': 3}

# Type: the kit's brand font is Urbanist; both skins fall back to the same
# system face (Segoe UI) when it isn't installed, so they render identically
# on a machine without Urbanist.
FONT_STACK = ("'Urbanist', system-ui, -apple-system, 'Segoe UI', Roboto, "
              "'Helvetica Neue', Arial, sans-serif")
# Type-scale ladder (px), from the kit's TYPE_SCALE (rem × 16, rounded). Dense
# telemetry (micro/caption/label) sits beside body; kpi/subtitle/heading/display
# cover stage readouts and page titles.
TYPE = {'micro': 10, 'caption': 12, 'label': 13, 'body2': 14, 'body': 16,
        'kpi': 18, 'subtitle': 20, 'heading': 28, 'display': 42}

# Preattentive status shapes (WCAG 1.4.1 — colour alone is never enough for
# urgency; pair a shape with the hue).
STATUS_SHAPE = {'ok': 'circle', 'watch': 'triangle', 'critical': 'square',
                'inactive': 'circle'}

# Categorical data-viz hues — chart series + on-canvas markers (e.g. takeoff).
# Kit-owned so diagram palettes stop hardcoding hex. `orange` here is a SERIES
# hue (#FF832B), NOT the brand accent (#FF4F18) — never use DATA_VIZ for CTAs.
DATA_VIZ = {'blue': '#0F62FE', 'cyan': '#1192E8', 'green': '#24A148',
            'purple': '#8A3FFC', 'violet': '#A56EFF', 'orange': '#FF832B',
            'gray': '#525252'}
# Stable series order — prefer this over dict order for charts.
DATA_VIZ_CATEGORICAL = [DATA_VIZ['blue'], DATA_VIZ['cyan'], DATA_VIZ['green'],
                        DATA_VIZ['orange'], DATA_VIZ['purple'],
                        DATA_VIZ['violet'], DATA_VIZ['gray']]


def scheme(name):
    return SCHEMES.get(name, LIGHT)
