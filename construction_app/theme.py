"""HCW-UI theme for the tkinter app — the Human Centric Works design language.

Ported from the ``hcwux`` design kit (``src/tokens.ts``). That kit is a web /
MUI system; tkinter cannot render its literal glassmorphism or neumorphic
blur, so we translate the *principle* — **depth encodes importance** — into
what tkinter can do: surface colour, hairline rules and font weight. The
hierarchy survives even though the blur does not.

The material law, as applied here:

* **Flat** (~90% of pixels) — the Fog-Gray canvas and Pure-White cards, defined
  by spacing and hairlines rather than boxes. Square corners, no shadow. This
  is the resting plane: tables, text, forms.
* **Soft** — panels and input wells, given a distinct fill + hairline so they
  read as objects you work *within*.
* **Glass** — the live layer. tkinter can't frost, so "glass" collapses to the
  single **Radiant-Orange** accent: it marks what is active or actionable, and
  nothing else wears it. Depth is scarce on purpose.

Two schemes ship, both straight from the kit's tokens: **light** (the brand)
and **dark**. The accent lifts slightly on dark for contrast, exactly as the
kit specifies.
"""

import tkinter as tk
from tkinter import ttk

# Brand font. The kit uses Urbanist (web-only); Segoe UI is the closest calm,
# legible system face on Windows and needs no bundling.
_FAMILY = 'Segoe UI'
FONT = (_FAMILY, 10)
FONT_SMALL = (_FAMILY, 9)
FONT_BOLD = (_FAMILY, 10, 'bold')
FONT_H1 = (_FAMILY, 15, 'bold')
FONT_KPI = (_FAMILY, 16, 'bold')
FONT_MICRO = (_FAMILY, 8)

# Tab / nav row heights. The primary navigation is the rail nav rows; the
# secondary navigation is the section notebook tab strip inside the stage.
# Kept at parity (1x) — the two levels read as equals, the accent alert-line
# on the active tab carries the hierarchy rather than size.
NAV_PAD_Y = 8            # primary — rail nav row
TAB_PAD_Y = 7           # secondary — stage notebook tab (~1x the nav row)

# Solid-hex approximations of the kit's alpha tokens (tkinter has no alpha):
# hairline = Coal@10% over the ground; accent_soft = Orange@14-20% over the card.
PALETTES = {
    'light': {
        'canvas':      '#F2F4F7',   # Fog Gray — the calm ground
        'surface':     '#FFFFFF',   # Pure White — cards
        'surface2':    '#E7EAF0',   # quiet fog — secondary / selected surface
        'rail':        '#FFFFFF',   # the instrument rail sits over the fog stage
        'ink':         '#141517',   # Coal Black
        'muted':       '#5B616B',   # secondary slate
        'helper':      '#667085',   # helper slate
        'hairline':    '#DCDEE1',
        'accent':      '#FF4F18',   # Radiant Orange — active / CTA only
        'accent_soft': '#FDE7DF',   # selected-row wash
        'accent_dark': '#DB3E0F',   # accent hover
        'on_accent':   '#FFFFFF',
        'hover':       '#ECEEF2',   # neutral hover wash
        'entry':       '#FFFFFF',
        'heading':     '#E7EAF0',   # table heading band
        'success':     '#1B7F5A',
        'warning':     '#FF9932',
        'error':       '#C8442E',
        'info':        '#3B5568',   # links + info (slate, never the accent)
    },
    'dark': {
        'canvas':      '#101215',
        'surface':     '#191C21',
        'surface2':    '#232830',
        'rail':        '#191C21',
        'ink':         '#EDEFF3',
        'muted':       '#9AA2AE',
        'helper':      '#98A1AD',
        'hairline':    '#2E333B',
        'accent':      '#FF5C28',
        'accent_soft': '#3E2A20',
        'accent_dark': '#FF7A4D',
        'on_accent':   '#FFFFFF',
        'hover':       '#272A2E',
        'entry':       '#191C21',
        'heading':     '#232830',
        'success':     '#4CC29A',
        'warning':     '#FFB25C',
        'error':       '#F07862',
        'info':        '#8FB4CE',
    },
}

DEFAULT_MODE = 'light'
_state = {'mode': DEFAULT_MODE}


def palette(mode=None):
    """The active colour scheme (or a named one)."""
    return PALETTES.get(mode or _state['mode'], PALETTES[DEFAULT_MODE])


def mode():
    return _state['mode']


# ---------------------------------------------------------------- persistence
def load_mode(conn):
    """Saved UI theme from app_settings ('light' | 'dark'), default light."""
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'ui_theme'").fetchone()
    except Exception:
        return DEFAULT_MODE
    val = (row['value'] if row and row['value'] else '').strip().lower()
    return val if val in PALETTES else DEFAULT_MODE


def save_mode(conn, m):
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES ('ui_theme', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (m,))
    conn.commit()


# ------------------------------------------------------------------- styling
def apply(root, m=None):
    """Apply the HCW theme to the whole app. Safe to call again to switch
    schemes live — ttk.Style is global, so existing widgets restyle."""
    m = m if m in PALETTES else _state['mode']
    _state['mode'] = m
    pal = PALETTES[m]

    style = ttk.Style(root)
    try:
        style.theme_use('clam')          # the one built-in theme that honours colour
    except tk.TclError:
        pass

    root.configure(bg=pal['canvas'])
    # Classic (non-ttk) widget defaults — Canvas, Menu, Toplevel, tk.Label.
    root.option_add('*background', pal['canvas'])
    root.option_add('*foreground', pal['ink'])
    root.option_add('*Canvas.background', pal['surface'])
    root.option_add('*Menu.background', pal['surface'])
    root.option_add('*Menu.foreground', pal['ink'])
    root.option_add('*Menu.activeBackground', pal['accent_soft'])
    root.option_add('*Menu.activeForeground', pal['ink'])
    # Combobox dropdown list (a classic Listbox under the hood).
    root.option_add('*TCombobox*Listbox.background', pal['surface'])
    root.option_add('*TCombobox*Listbox.foreground', pal['ink'])
    root.option_add('*TCombobox*Listbox.selectBackground', pal['accent'])
    root.option_add('*TCombobox*Listbox.selectForeground', pal['on_accent'])

    # --- base
    style.configure('.', background=pal['canvas'], foreground=pal['ink'],
                    fieldbackground=pal['entry'], bordercolor=pal['hairline'],
                    lightcolor=pal['hairline'], darkcolor=pal['hairline'],
                    troughcolor=pal['surface2'], font=FONT, relief='flat')
    style.map('.', foreground=[('disabled', pal['muted'])])

    # --- frames / surfaces (flat ground + soft cards)
    style.configure('TFrame', background=pal['canvas'])
    style.configure('Card.TFrame', background=pal['surface'])
    style.configure('Rail.TFrame', background=pal['rail'])
    style.configure('Stage.TFrame', background=pal['canvas'])

    # --- labels
    style.configure('TLabel', background=pal['canvas'], foreground=pal['ink'])
    style.configure('Muted.TLabel', background=pal['canvas'],
                    foreground=pal['muted'])
    style.configure('Card.TLabel', background=pal['surface'],
                    foreground=pal['ink'])
    style.configure('H1.TLabel', background=pal['canvas'], foreground=pal['ink'],
                    font=FONT_H1)
    style.configure('Rail.TLabel', background=pal['rail'], foreground=pal['ink'])
    style.configure('RailMuted.TLabel', background=pal['rail'],
                    foreground=pal['muted'], font=FONT_MICRO)
    style.configure('Brand.TLabel', background=pal['rail'],
                    foreground=pal['accent'], font=FONT_H1)

    # --- LabelFrame (used as "cards"/form panels — a soft object)
    style.configure('TLabelframe', background=pal['surface'],
                    bordercolor=pal['hairline'], relief='solid', borderwidth=1)
    style.configure('TLabelframe.Label', background=pal['surface'],
                    foreground=pal['muted'], font=FONT_SMALL)

    # --- buttons: flat neutral by default; orange fill is the CTA only
    style.configure('TButton', background=pal['surface'], foreground=pal['ink'],
                    bordercolor=pal['hairline'], relief='flat', borderwidth=1,
                    padding=(11, 5), focuscolor=pal['accent'], anchor='center')
    style.map('TButton',
              background=[('pressed', pal['hover']), ('active', pal['hover'])],
              bordercolor=[('active', pal['accent'])],
              foreground=[('disabled', pal['muted'])])
    style.configure('Accent.TButton', background=pal['accent'],
                    foreground=pal['on_accent'], bordercolor=pal['accent'])
    style.map('Accent.TButton',
              background=[('pressed', pal['accent_dark']),
                          ('active', pal['accent_dark'])],
              foreground=[('disabled', pal['on_accent'])])

    # --- entries
    style.configure('TEntry', fieldbackground=pal['entry'],
                    foreground=pal['ink'], insertcolor=pal['ink'],
                    bordercolor=pal['hairline'], borderwidth=1, padding=3)
    style.map('TEntry', bordercolor=[('focus', pal['accent'])],
              fieldbackground=[('disabled', pal['canvas'])])

    # --- combobox
    style.configure('TCombobox', fieldbackground=pal['entry'],
                    background=pal['surface'], foreground=pal['ink'],
                    bordercolor=pal['hairline'], arrowcolor=pal['muted'],
                    padding=3)
    style.map('TCombobox',
              fieldbackground=[('readonly', pal['entry']),
                               ('disabled', pal['canvas'])],
              bordercolor=[('focus', pal['accent'])],
              foreground=[('disabled', pal['muted'])])

    # --- treeview (flat white table, fog heading, orange selection)
    style.configure('Treeview', background=pal['surface'],
                    fieldbackground=pal['surface'], foreground=pal['ink'],
                    bordercolor=pal['hairline'], borderwidth=0, rowheight=25)
    style.map('Treeview', background=[('selected', pal['accent_soft'])],
              foreground=[('selected', pal['ink'])])
    style.configure('Treeview.Heading', background=pal['heading'],
                    foreground=pal['muted'], relief='flat', borderwidth=0,
                    font=FONT_SMALL, padding=(6, 4))
    style.map('Treeview.Heading', background=[('active', pal['hover'])])

    # --- notebook: transparent tabs, active tab lifts to the card colour with
    # ink text (the kit's "top alert line" collapsed to a fill + weight change,
    # which is as close as ttk gets to a top-only accent rule)
    style.configure('TNotebook', background=pal['canvas'], borderwidth=0,
                    tabmargins=(2, 4, 2, 0))
    style.configure('TNotebook.Tab', background=pal['canvas'],
                    foreground=pal['muted'], padding=(16, TAB_PAD_Y),
                    borderwidth=0, font=FONT)
    style.map('TNotebook.Tab',
              background=[('selected', pal['surface']),
                          ('active', pal['hover'])],
              foreground=[('selected', pal['ink'])],
              font=[('selected', FONT_BOLD)])

    # --- checkbutton / radiobutton
    for cls in ('TCheckbutton', 'TRadiobutton'):
        style.configure(cls, background=pal['canvas'], foreground=pal['ink'],
                        focuscolor=pal['accent'])
        style.map(cls, background=[('active', pal['canvas'])],
                  foreground=[('disabled', pal['muted'])])
    style.configure('Rail.TCheckbutton', background=pal['rail'],
                    foreground=pal['muted'])
    style.map('Rail.TCheckbutton', background=[('active', pal['rail'])])

    # --- scrollbars (slim, quiet)
    for cls in ('Vertical.TScrollbar', 'Horizontal.TScrollbar'):
        style.configure(cls, background=pal['surface2'],
                        troughcolor=pal['canvas'], bordercolor=pal['canvas'],
                        arrowcolor=pal['muted'])
        style.map(cls, background=[('active', pal['hover'])])

    # --- progressbar
    style.configure('TProgressbar', background=pal['accent'],
                    troughcolor=pal['surface2'], bordercolor=pal['hairline'])

    # --- rail nav rows: [accent rule][pictogram][label]; the active row wears
    # the accent rule + lifts to the secondary surface with bold ink.
    style.configure('Nav.TLabel', background=pal['rail'],
                    foreground=pal['muted'], padding=(4, NAV_PAD_Y, 14, NAV_PAD_Y),
                    font=FONT)
    style.configure('NavActive.TLabel', background=pal['surface2'],
                    foreground=pal['ink'], padding=(4, NAV_PAD_Y, 14, NAV_PAD_Y),
                    font=FONT_BOLD)
    style.configure('NavIcon.TLabel', background=pal['rail'],
                    foreground=pal['muted'],
                    padding=(13, NAV_PAD_Y, 4, NAV_PAD_Y))
    style.configure('NavIconActive.TLabel', background=pal['surface2'],
                    foreground=pal['ink'],
                    padding=(13, NAV_PAD_Y, 4, NAV_PAD_Y))
    style.configure('NavAccent.TFrame', background=pal['accent'])
    style.configure('NavRule.TFrame', background=pal['rail'])
    style.configure('NavRowActive.TFrame', background=pal['surface2'])

    return pal
