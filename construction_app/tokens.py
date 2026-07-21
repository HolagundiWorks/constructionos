"""HCW-UI design tokens — the single source of truth for **both** the tkinter
desktop and the browser/LAN front end, so one design system governs the whole
app (a strict project rule).

Ported verbatim from the kit's authoritative token file
(``hcwux/src/tokens.ts`` — "the SINGLE source of truth for colour, shape,
surface and type across every portal"). Design language: **hyper-minimalist
light with a Radiant-Orange accent** — Fog-Gray canvas, Pure-White cards,
Coal-Black ink, **square surfaces (0 radius)**, flat panels defined by spacing
and hairlines rather than boxes. The accent is a FILL / active state only;
links use slate, never the accent.

This module is **pure standard library, no tkinter**, on purpose: ``theme.py``
builds the desktop ttk styles from it, and ``webrender.py`` builds the web CSS
from it, but the web server must import it while running head-less. Keeping the
values here — and testing that both surfaces use them — is what stops the two
skins drifting apart.
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
SPACING = {'none': 0, 'xxs': 2, 'xs': 4, 'sm': 8, 'md': 16, 'lg': 24, 'xl': 32,
           'xxl': 48, 'xxxl': 64}

# Type: the kit uses Inter; the desktop falls back to Segoe UI (no bundling),
# the web offers the same ladder ending at the system face.
FONT_STACK = ("'Inter', -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, "
              "sans-serif")
# Type roles (px): mission / section / card-title / body / label / meta / overline
TYPE = {'mission': 28, 'section': 20, 'card_title': 16, 'body': 14,
        'label': 13, 'meta': 12, 'overline': 11}


def scheme(name):
    return SCHEMES.get(name, LIGHT)
