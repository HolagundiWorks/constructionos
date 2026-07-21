"""The Rail + Stage shell — HCW's one spatial model, in tkinter.

The kit puts a fixed **Rail** at the edge (identity, navigation, status,
settings at the bottom) and a **Stage** that holds the work and scrolls
independently. This replaces the app's old top tab-bar with that geography, so
the top of the window is no longer a crowded row of tabs a user hunts through —
navigation lives down the left, always in the same place, and the work fills
the rest.

Translating the kit's materials to tkinter:

* the Rail is a distinct surface (a solid card colour over the fog Stage) — the
  stand-in for its frosted glass, since tkinter cannot blur;
* the **active** nav row wears the single Radiant-Orange accent as a left rule
  plus bold ink — the kit's "top alert line" turned on its side for a vertical
  rail. Nothing else in the rail wears the accent, so the eye finds "where am
  I" for free;
* each section's tabs stay as a sub-notebook inside the Stage, styled by
  ``theme`` so the active tab lifts the same way.

Section widgets are built lazily — the first time a rail row is opened — so
startup shows the window immediately instead of constructing forty-odd tabs up
front.
"""

import tkinter as tk
from tkinter import ttk

import theme

RAIL_WIDTH = 208


class RailStage(ttk.Frame):
    """A left rail of nav rows and a right stage that shows one at a time."""

    def __init__(self, parent, entries, brand='Construction OS',
                 subtitle='', on_toggle_theme=None):
        super().__init__(parent, style='Stage.TFrame')
        # entries: list of {'key', 'label', 'build': callable(parent)->widget}
        self.entries = entries
        self._on_toggle_theme = on_toggle_theme
        self._built = {}          # key -> widget (lazy)
        self._rows = {}           # key -> (rule_frame, label)
        self._current = None

        # --- Rail (fixed width, its own surface)
        rail = ttk.Frame(self, style='Rail.TFrame', width=RAIL_WIDTH)
        rail.pack(side='left', fill='y')
        rail.pack_propagate(False)
        self._rail = rail

        brand_box = ttk.Frame(rail, style='Rail.TFrame')
        brand_box.pack(fill='x', pady=(14, 6), padx=14)
        ttk.Label(brand_box, text=brand, style='Brand.TLabel').pack(anchor='w')
        if subtitle:
            ttk.Label(brand_box, text=subtitle,
                      style='RailMuted.TLabel').pack(anchor='w')

        nav = ttk.Frame(rail, style='Rail.TFrame')
        nav.pack(fill='both', expand=True, pady=(8, 0))
        self._nav = nav
        for e in entries:
            self._add_row(nav, e)

        # --- bottom: theme toggle (the kit puts settings at the rail foot)
        foot = ttk.Frame(rail, style='Rail.TFrame')
        foot.pack(fill='x', side='bottom', pady=(6, 12), padx=10)
        self._toggle_btn = ttk.Button(foot, text=self._toggle_text(),
                                      command=self._toggle, style='TButton')
        self._toggle_btn.pack(fill='x')

        # hairline between rail and stage
        sep = tk.Frame(self, width=1, bg=theme.palette()['hairline'])
        sep.pack(side='left', fill='y')
        self._sep = sep

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
        lbl = ttk.Label(row, text=entry['label'], style='Nav.TLabel',
                        anchor='w')
        lbl.pack(side='left', fill='x', expand=True)
        key = entry['key']
        for w in (row, lbl):
            w.bind('<Button-1>', lambda _e, k=key: self.select(k))
        # a quiet hover cue, only when not the active row
        lbl.bind('<Enter>', lambda _e, k=key: self._hover(k, True))
        lbl.bind('<Leave>', lambda _e, k=key: self._hover(k, False))
        self._rows[key] = (rule, lbl)

    def _hover(self, key, entering):
        if key == self._current:
            return
        _rule, lbl = self._rows[key]
        lbl.configure(style='NavActive.TLabel' if entering else 'Nav.TLabel')
        # keep the rule off on hover — the accent means "active", not "hovered"
        self._rows[key][0].configure(style='NavRule.TFrame')

    # --------------------------------------------------------------- select
    def select(self, key):
        if key == self._current:
            return
        # nav visuals
        for k, (rule, lbl) in self._rows.items():
            active = (k == key)
            rule.configure(style='NavAccent.TFrame' if active else 'NavRule.TFrame')
            lbl.configure(style='NavActive.TLabel' if active else 'Nav.TLabel')
        # stage content (lazy build)
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
    def _toggle_text(self):
        return 'Light theme' if theme.mode() == 'dark' else 'Dark theme'

    def _toggle(self):
        if self._on_toggle_theme:
            self._on_toggle_theme()
        self._toggle_btn.configure(text=self._toggle_text())
        # re-colour the one hand-set widget (the hairline) after a scheme change
        self._sep.configure(bg=theme.palette()['hairline'])
