"""The Rail + Stage shell — HCW's one spatial model, in tkinter.

The kit puts a fixed **Rail** at the edge (identity, navigation, status,
settings at the bottom) and a **Stage** that holds the work and scrolls
independently. This replaces the app's old top tab-bar with that geography, so
navigation lives down the left, always in the same place, and the work fills
the rest.

Translating the kit's materials to tkinter:

* the Rail is a distinct surface (a solid card colour over the fog Stage) — the
  stand-in for its frosted glass, since tkinter cannot blur;
* every nav row carries a **pictogram** so a section is found by shape before
  the word is read;
* the **active** row wears the single Radiant-Orange accent as a left rule and
  lifts to the secondary surface with bold ink — the kit's "top alert line"
  turned on its side. Nothing else in the rail wears the accent;
* settings sit at the rail foot: a **switch** for light/dark and the
  developer credit.

Section widgets are built lazily — the first time a rail row is opened — so
startup shows the window immediately instead of constructing forty-odd tabs up
front.
"""

import tkinter as tk
from tkinter import ttk

import assets
import branding
import theme

RAIL_WIDTH = 208


class Switch(tk.Canvas):
    """A small pill toggle, drawn on a Canvas (tkinter has no native switch).

    On = the Radiant-Orange track with the knob to the right. Click toggles and
    fires ``command(new_value)``. ``restyle()`` re-reads the theme after a
    scheme change, since a Canvas is not a ttk widget."""

    W, H = 42, 22

    def __init__(self, parent, value=False, command=None):
        pal = theme.palette()
        super().__init__(parent, width=self.W, height=self.H,
                         highlightthickness=0, bg=pal['rail'], cursor='hand2',
                         takefocus=1)
        self._value = bool(value)
        self._command = command
        self.bind('<Button-1>', lambda _e: self.toggle())
        self.bind('<Key-space>', lambda _e: self.toggle())
        self._render()

    def _render(self):
        pal = theme.palette()
        self.delete('all')
        track = pal['accent'] if self._value else pal['hairline']
        h = self.H
        r = h / 2
        # pill track = two end circles + a middle rectangle
        self.create_oval(1, 1, h - 1, h - 1, fill=track, outline='')
        self.create_oval(self.W - h + 1, 1, self.W - 1, h - 1, fill=track,
                         outline='')
        self.create_rectangle(r, 1, self.W - r, h - 1, fill=track, outline='')
        # knob
        kx = self.W - h + 2 if self._value else 2
        self.create_oval(kx, 2, kx + h - 4, h - 2, fill='#FFFFFF', outline='')

    def toggle(self):
        self._value = not self._value
        self._render()
        if self._command:
            self._command(self._value)

    def set(self, value):
        self._value = bool(value)
        self._render()

    def restyle(self):
        self.configure(bg=theme.palette()['rail'])
        self._render()


class RailStage(ttk.Frame):
    """A left rail of pictogram nav rows and a right stage that shows one at a
    time."""

    def __init__(self, parent, entries, brand='Construction OS',
                 subtitle='', on_toggle_theme=None):
        super().__init__(parent, style='Stage.TFrame')
        # entries: {'key', 'label', 'icon', 'build': callable(parent)->widget}
        self.entries = entries
        self._on_toggle_theme = on_toggle_theme
        self._built = {}          # key -> widget (lazy)
        self._rows = {}           # key -> (row, rule, icon_lbl, text_lbl)
        self._current = None

        # --- Rail (fixed width, its own surface)
        rail = ttk.Frame(self, style='Rail.TFrame', width=RAIL_WIDTH)
        rail.pack(side='left', fill='y')
        rail.pack_propagate(False)
        self._rail = rail

        # identity: the logo at the top of the rail
        brand_box = ttk.Frame(rail, style='Rail.TFrame')
        brand_box.pack(fill='x', pady=(16, 8), padx=14)
        self._logo_img = None
        try:
            img = tk.PhotoImage(file=assets.LOGO_RECT)
            if img.width() > RAIL_WIDTH - 28:
                img = img.subsample(2, 2)
            self._logo_img = img
            ttk.Label(brand_box, image=img, style='Rail.TLabel').pack(anchor='w')
        except Exception:
            ttk.Label(brand_box, text=brand, style='Brand.TLabel').pack(anchor='w')
        ttk.Label(brand_box, text=branding.TAGLINE,
                  style='RailMuted.TLabel').pack(anchor='w', pady=(4, 0))
        if subtitle:
            ttk.Label(brand_box, text=subtitle,
                      style='RailMuted.TLabel').pack(anchor='w')

        nav = ttk.Frame(rail, style='Rail.TFrame')
        nav.pack(fill='both', expand=True, pady=(8, 0))
        for e in entries:
            self._add_row(nav, e)

        # --- foot: theme switch + developer credit (identity + settings)
        foot = ttk.Frame(rail, style='Rail.TFrame')
        foot.pack(fill='x', side='bottom', pady=(6, 10), padx=12)
        sw_row = ttk.Frame(foot, style='Rail.TFrame')
        sw_row.pack(fill='x')
        self._sw_label = ttk.Label(sw_row, text=self._theme_label(),
                                   style='RailMuted.TLabel')
        self._sw_label.pack(side='left')
        self._switch = Switch(sw_row, value=(theme.mode() == 'dark'),
                              command=self._on_switch)
        self._switch.pack(side='right')
        ttk.Label(foot, text=branding.CREDIT, style='RailMuted.TLabel',
                  wraplength=RAIL_WIDTH - 30, justify='left').pack(
            anchor='w', pady=(10, 0))

        # hairline between rail and stage
        self._sep = tk.Frame(self, width=1, bg=theme.palette()['hairline'])
        self._sep.pack(side='left', fill='y')

        # --- Stage (the work)
        self._stage = ttk.Frame(self, style='Stage.TFrame')
        self._stage.pack(side='left', fill='both', expand=True)

        if entries:
            self.select(entries[0]['key'])

    # ---------------------------------------------------------------- rail
    def _add_row(self, parent, entry):
        row = ttk.Frame(parent, style='Rail.TFrame')
        row.pack(fill='x')
        rule = ttk.Frame(row, style='NavRule.TFrame', width=3)
        rule.pack(side='left', fill='y')
        rule.pack_propagate(False)
        icon = ttk.Label(row, text=entry.get('icon', ''), style='NavIcon.TLabel')
        icon.pack(side='left')
        lbl = ttk.Label(row, text=entry['label'], style='Nav.TLabel', anchor='w')
        lbl.pack(side='left', fill='x', expand=True)
        key = entry['key']
        for w in (row, icon, lbl):
            w.bind('<Button-1>', lambda _e, k=key: self.select(k))
        for w in (icon, lbl):
            w.bind('<Enter>', lambda _e, k=key: self._hover(k, True))
            w.bind('<Leave>', lambda _e, k=key: self._hover(k, False))
        self._rows[key] = (row, rule, icon, lbl)

    def _paint_row(self, key, active, hovering=False):
        row, rule, icon, lbl = self._rows[key]
        lifted = active or hovering
        row.configure(style='NavRowActive.TFrame' if lifted else 'Rail.TFrame')
        rule.configure(style='NavAccent.TFrame' if active else 'NavRule.TFrame')
        icon.configure(style='NavIconActive.TLabel' if lifted else 'NavIcon.TLabel')
        lbl.configure(style='NavActive.TLabel' if lifted else 'Nav.TLabel')

    def _hover(self, key, entering):
        if key != self._current:
            self._paint_row(key, active=False, hovering=entering)

    # --------------------------------------------------------------- select
    def select(self, key):
        if key == self._current:
            return
        for k in self._rows:
            self._paint_row(k, active=(k == key))
        if self._current is not None and self._current in self._built:
            self._built[self._current].pack_forget()
        widget = self._built.get(key)
        if widget is None:
            entry = next(e for e in self.entries if e['key'] == key)
            widget = entry['build'](self._stage)
            self._built[key] = widget
        widget.pack(fill='both', expand=True)
        self._current = key

    # --------------------------------------------------------------- theme
    def _theme_label(self):
        # the affordance: what the switch will do next
        return ('\U0001F319 Dark' if theme.mode() == 'light'
                else '☀ Light')

    def _on_switch(self, _value):
        if self._on_toggle_theme:
            self._on_toggle_theme()          # flips + re-applies the theme
        self._switch.set(theme.mode() == 'dark')
        self._switch.restyle()
        self._sw_label.configure(text=self._theme_label())
        self._sep.configure(bg=theme.palette()['hairline'])
