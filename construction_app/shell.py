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
from widgets import Switch, FloatingDock

RAIL_WIDTH = 208


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

        # identity: the logo at the top of the rail. A dark-mode variant (the
        # artwork lifted to near-white) is swapped in when the theme is dark, so
        # the black logo doesn't vanish on the dark rail.
        brand_box = ttk.Frame(rail, style='Rail.TFrame')
        brand_box.pack(fill='x', pady=(16, 8), padx=14)
        self._brand_text = brand
        self._logo_img = None
        self._logo_lbl = ttk.Label(brand_box, style='Rail.TLabel')
        self._logo_lbl.pack(anchor='w')
        self._load_logo()
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

        # --- floating action dock over the stage (New · Refresh · Save)
        self._dock = FloatingDock(self._stage, self._resolve_action)
        # Any notebook tab change anywhere re-evaluates what the dock can do.
        self.bind_all('<<NotebookTabChanged>>',
                      lambda _e: self._dock.update_state(), add='+')

        if entries:
            self.select(entries[0]['key'])

    # ---------------------------------------------------------------- logo
    def _load_logo(self):
        """Put the theme-appropriate logo in the rail; fall back to the light
        logo, then to plain text, if an asset is missing (e.g. a build that
        didn't bundle the white variant)."""
        dark = theme.mode() == 'dark'
        candidates = ([assets.LOGO_RECT_WHITE, assets.LOGO_RECT] if dark
                      else [assets.LOGO_RECT])
        for path in candidates:
            try:
                img = tk.PhotoImage(file=path)
            except Exception:
                continue
            if img.width() > RAIL_WIDTH - 28:
                img = img.subsample(2, 2)
            self._logo_img = img                 # keep a reference alive
            self._logo_lbl.configure(image=img, text='', style='Rail.TLabel')
            return
        self._logo_lbl.configure(image='', text=self._brand_text,
                                 style='Brand.TLabel')

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
        # Re-evaluate the dock once the new tab has mapped (its notebook, if
        # any, has settled on a selected page).
        self.after(0, self._dock.update_state)

    # ----------------------------------------------------------- action dock
    def _resolve_action(self, action):
        """The callable the dock's ``action`` should run on the active tab, or
        None. 'refresh' also accepts a plain ``refresh()`` (most tabs have one);
        'new'/'save' use the explicit ``dock_*`` protocol so a tab opts in."""
        leaf = self._active_leaf()
        if leaf is None:
            return None
        if action == 'refresh':
            for name in ('dock_refresh', 'refresh'):
                fn = getattr(leaf, name, None)
                if callable(fn):
                    return fn
            return None
        fn = getattr(leaf, 'dock_' + action, None)
        return fn if callable(fn) else None

    def _active_leaf(self):
        """The on-screen tab widget, descending through nested notebooks to the
        currently selected page."""
        return self._descend(self._built.get(self._current))

    def _descend(self, widget):
        if widget is None:
            return None
        if isinstance(widget, ttk.Notebook):
            try:
                sel = widget.select()
                if sel:
                    return self._descend(widget.nametowidget(sel))
            except Exception:                     # noqa: BLE001
                pass
        return widget

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
        self._load_logo()                    # black ↔ near-white logo
