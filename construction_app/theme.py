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
    # Classic (non-ttk) widget defaults — Canvas, Menu, Toplevel, tk.Label,
    # and text selection. All flat and borderless, matching the modern look.
    root.option_add('*background', pal['canvas'])
    root.option_add('*foreground', pal['ink'])
    root.option_add('*selectBackground', pal['accent'])
    root.option_add('*selectForeground', pal['on_accent'])
    root.option_add('*Canvas.background', pal['surface'])
    root.option_add('*Canvas.highlightThickness', 0)
    root.option_add('*Menu.background', pal['surface'])
    root.option_add('*Menu.foreground', pal['ink'])
    root.option_add('*Menu.activeBackground', pal['accent'])
    root.option_add('*Menu.activeForeground', pal['on_accent'])
    root.option_add('*Menu.relief', 'flat')
    root.option_add('*Menu.borderWidth', 0)
    root.option_add('*Menu.activeBorderWidth', 0)
    # Combobox dropdown list (a classic Listbox under the hood).
    root.option_add('*TCombobox*Listbox.background', pal['surface'])
    root.option_add('*TCombobox*Listbox.foreground', pal['ink'])
    root.option_add('*TCombobox*Listbox.selectBackground', pal['accent'])
    root.option_add('*TCombobox*Listbox.selectForeground', pal['on_accent'])
    root.option_add('*TCombobox*Listbox.borderWidth', 0)
    root.option_add('*TCombobox*Listbox.relief', 'flat')

    # In clam the 3-D bevel comes from light/dark edge colours differing from
    # the border. Setting light == dark == border (or the fill) removes every
    # bevel — the single biggest step from "Windows 98" to a flat modern look.
    flat = dict(bordercolor=pal['hairline'], lightcolor=pal['hairline'],
                darkcolor=pal['hairline'])

    # --- base
    style.configure('.', background=pal['canvas'], foreground=pal['ink'],
                    fieldbackground=pal['entry'], troughcolor=pal['surface2'],
                    borderwidth=0, relief='flat', focuscolor=pal['canvas'],
                    font=FONT, **flat)
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

    # --- LabelFrame (form panels): a hairline-defined region on the fog ground
    # (not a raised white box) — this keeps its contents, which sit on the
    # canvas colour, matching, and reads as HCW "definition from hairlines".
    style.configure('TLabelframe', background=pal['canvas'], relief='solid',
                    borderwidth=1, **flat)
    style.configure('TLabelframe.Label', background=pal['canvas'],
                    foreground=pal['helper'], font=FONT_SMALL)

    # --- buttons: flat, subtle fill, hairline, roomy padding (Win11 feel);
    # orange fill is the CTA only. No dotted focus box (focusthickness 0).
    style.configure('TButton', background=pal['surface2'], foreground=pal['ink'],
                    relief='flat', borderwidth=1, padding=(14, 7),
                    anchor='center', focusthickness=0, focuscolor=pal['surface2'],
                    **flat)
    style.map('TButton',
              background=[('pressed', pal['hover']), ('active', pal['hover'])],
              bordercolor=[('focus', pal['accent']), ('active', pal['hairline'])],
              foreground=[('disabled', pal['muted'])])
    style.configure('Accent.TButton', background=pal['accent'],
                    foreground=pal['on_accent'], bordercolor=pal['accent'],
                    lightcolor=pal['accent'], darkcolor=pal['accent'],
                    focuscolor=pal['accent'])
    style.map('Accent.TButton',
              background=[('pressed', pal['accent_dark']),
                          ('active', pal['accent_dark'])],
              bordercolor=[('active', pal['accent_dark'])],
              foreground=[('disabled', pal['on_accent'])])

    # --- entries: flat field, single hairline, accent underline on focus
    style.configure('TEntry', fieldbackground=pal['entry'],
                    foreground=pal['ink'], insertcolor=pal['ink'],
                    borderwidth=1, relief='flat', padding=6, **flat)
    style.map('TEntry',
              bordercolor=[('focus', pal['accent'])],
              lightcolor=[('focus', pal['accent'])],
              darkcolor=[('focus', pal['accent'])],
              fieldbackground=[('disabled', pal['canvas'])])

    # --- combobox / spinbox: same flat treatment
    style.configure('TCombobox', fieldbackground=pal['entry'],
                    background=pal['surface2'], foreground=pal['ink'],
                    arrowcolor=pal['muted'], borderwidth=1, relief='flat',
                    padding=6, **flat)
    style.map('TCombobox',
              fieldbackground=[('readonly', pal['entry']),
                               ('disabled', pal['canvas'])],
              bordercolor=[('focus', pal['accent']), ('active', pal['accent'])],
              lightcolor=[('focus', pal['accent'])],
              darkcolor=[('focus', pal['accent'])],
              arrowcolor=[('active', pal['ink'])],
              foreground=[('disabled', pal['muted'])])
    style.configure('TSpinbox', fieldbackground=pal['entry'],
                    foreground=pal['ink'], arrowcolor=pal['muted'],
                    borderwidth=1, relief='flat', padding=5, **flat)

    # --- treeview: flat table, no border box, airy rows, flat heading
    style.configure('Treeview', background=pal['surface'],
                    fieldbackground=pal['surface'], foreground=pal['ink'],
                    borderwidth=0, relief='flat', rowheight=28, **flat)
    style.map('Treeview', background=[('selected', pal['accent_soft'])],
              foreground=[('selected', pal['ink'])])
    style.configure('Treeview.Heading', background=pal['heading'],
                    foreground=pal['helper'], relief='flat', borderwidth=0,
                    font=FONT_SMALL, padding=(8, 7), **flat)
    style.map('Treeview.Heading',
              background=[('active', pal['hover'])],
              relief=[('active', 'flat'), ('pressed', 'flat')])
    # drop the sunken border box around the tree
    style.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])

    # --- notebook: transparent tabs, active tab lifts to the card colour with
    # bold ink (the kit's "alert line" as a fill + weight change). Borderless.
    style.configure('TNotebook', background=pal['canvas'], borderwidth=0,
                    tabmargins=(2, 6, 2, 0),
                    bordercolor=pal['canvas'], lightcolor=pal['canvas'],
                    darkcolor=pal['canvas'])
    style.configure('TNotebook.Tab', background=pal['canvas'],
                    foreground=pal['muted'], padding=(16, TAB_PAD_Y),
                    borderwidth=0, font=FONT,
                    bordercolor=pal['canvas'], lightcolor=pal['canvas'],
                    darkcolor=pal['canvas'])
    style.map('TNotebook.Tab',
              background=[('selected', pal['surface']),
                          ('active', pal['hover'])],
              foreground=[('selected', pal['ink'])],
              font=[('selected', FONT_BOLD)],
              lightcolor=[('selected', pal['surface'])],
              darkcolor=[('selected', pal['surface'])])

    # --- checkbutton / radiobutton (flat indicator, accent when on)
    for cls in ('TCheckbutton', 'TRadiobutton'):
        style.configure(cls, background=pal['canvas'], foreground=pal['ink'],
                        indicatorbackground=pal['surface'],
                        indicatorcolor=pal['surface'], focusthickness=0,
                        focuscolor=pal['canvas'], padding=3, **flat)
        style.map(cls, background=[('active', pal['canvas'])],
                  indicatorbackground=[('selected', pal['accent']),
                                       ('active', pal['surface'])],
                  indicatorcolor=[('selected', pal['accent'])],
                  foreground=[('disabled', pal['muted'])])
    style.configure('Rail.TCheckbutton', background=pal['rail'],
                    foreground=pal['muted'])
    style.map('Rail.TCheckbutton', background=[('active', pal['rail'])])

    # --- scrollbars: slim, flat, ARROWLESS (the arrow buttons are the other
    # big Win98 tell — a layout override drops them for a modern thin bar)
    style.layout('Vertical.TScrollbar', [(
        'Vertical.Scrollbar.trough',
        {'sticky': 'ns', 'children': [(
            'Vertical.Scrollbar.thumb',
            {'expand': '1', 'sticky': 'nswe'})]})])
    style.layout('Horizontal.TScrollbar', [(
        'Horizontal.Scrollbar.trough',
        {'sticky': 'we', 'children': [(
            'Horizontal.Scrollbar.thumb',
            {'expand': '1', 'sticky': 'nswe'})]})])
    for cls in ('Vertical.TScrollbar', 'Horizontal.TScrollbar'):
        style.configure(cls, background=pal['hairline'],
                        troughcolor=pal['canvas'], arrowcolor=pal['canvas'],
                        borderwidth=0, relief='flat', width=11,
                        bordercolor=pal['canvas'], lightcolor=pal['canvas'],
                        darkcolor=pal['canvas'])
        style.map(cls, background=[('active', pal['muted']),
                                   ('pressed', pal['muted'])])

    # --- progressbar
    style.configure('TProgressbar', background=pal['accent'],
                    troughcolor=pal['surface2'], borderwidth=0,
                    bordercolor=pal['surface2'], lightcolor=pal['accent'],
                    darkcolor=pal['accent'])

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

    # --- dashboard stat cards: a hairline card, muted label + big value
    style.configure('StatCard.TFrame', background=pal['surface'],
                    relief='solid', borderwidth=1, **flat)
    style.configure('StatIcon.TLabel', background=pal['surface'],
                    foreground=pal['muted'], font=(_FAMILY, 13))
    style.configure('StatLabel.TLabel', background=pal['surface'],
                    foreground=pal['muted'], font=FONT_SMALL)
    style.configure('StatValue.TLabel', background=pal['surface'],
                    foreground=pal['ink'], font=FONT_KPI)
    style.configure('StatInfo.TLabel', background=pal['surface'],
                    foreground=pal['info'], font=FONT_KPI)
    style.configure('StatGood.TLabel', background=pal['surface'],
                    foreground=pal['success'], font=FONT_KPI)
    style.configure('StatWarn.TLabel', background=pal['surface'],
                    foreground=pal['error'], font=FONT_KPI)
    style.configure('StatMeta.TLabel', background=pal['surface'],
                    foreground=pal['helper'], font=FONT_MICRO)

    # --- dashboard section headers (on the fog ground)
    style.configure('Section.TLabel', background=pal['canvas'],
                    foreground=pal['ink'], font=(_FAMILY, 12, 'bold'))
    style.configure('SectionHint.TLabel', background=pal['canvas'],
                    foreground=pal['muted'], font=FONT_SMALL)

    # --- advisory cards: a coloured severity rule + text on a surface card.
    # The four severities reuse the semantic palette (act=red, watch=amber,
    # good=green, info=slate) — the single orange accent stays reserved for
    # navigation/CTA, never for status.
    for name, col in (('Act', pal['error']), ('Watch', pal['warning']),
                      ('Good', pal['success']), ('Info', pal['info'])):
        style.configure('Rule%s.TFrame' % name, background=col)
        style.configure('Sev%s.TLabel' % name, background=pal['surface'],
                        foreground=col, font=FONT_BOLD)
        style.configure('Sev%sMicro.TLabel' % name, background=pal['surface'],
                        foreground=col, font=FONT_MICRO)
    style.configure('CardTitle.TLabel', background=pal['surface'],
                    foreground=pal['ink'], font=FONT_BOLD)
    style.configure('CardBody.TLabel', background=pal['surface'],
                    foreground=pal['muted'], font=FONT_SMALL)
    style.configure('CardMeta.TLabel', background=pal['surface'],
                    foreground=pal['helper'], font=FONT_MICRO)
    style.configure('CardLink.TLabel', background=pal['surface'],
                    foreground=pal['info'], font=FONT_MICRO)

    return pal
