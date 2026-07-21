"""Small shared widgets that tkinter/ttk doesn't ship.

``Switch`` — a pill toggle drawn on a Canvas, since ttk has no native switch.
Used for the theme toggle in the rail and the module on/off toggles in Tools.
"""

import tkinter as tk

import theme


class Switch(tk.Canvas):
    """A pill toggle. On = the Radiant-Orange track with the knob to the right.

    Bind it to state one of two ways:

    * ``variable=`` a tk IntVar/BooleanVar — the switch reflects it and writes
      it on toggle, and follows external changes (e.g. an "Enable all" button),
      so callers that already read the variable keep working unchanged;
    * ``command=`` a callback ``fn(new_value)`` for one-off actions.

    ``surface`` names the palette key of the ground it sits on ('surface' for a
    card/rail, 'canvas' for the fog) so ``restyle()`` can re-read the right
    colour after a light/dark switch — a Canvas is not a ttk widget and won't
    re-theme itself.
    """

    W, H = 42, 22

    def __init__(self, parent, value=False, variable=None, command=None,
                 surface='surface'):
        self._surface = surface
        self._bg = theme.palette()[surface]
        super().__init__(parent, width=self.W, height=self.H,
                         highlightthickness=0, bg=self._bg, cursor='hand2',
                         takefocus=1)
        self._var = variable
        self._command = command
        if variable is not None:
            self._value = bool(variable.get())
            variable.trace_add('write', lambda *_a: self._follow_var())
        else:
            self._value = bool(value)
        self.bind('<Button-1>', lambda _e: self.toggle())
        self.bind('<Key-space>', lambda _e: self.toggle())
        self._render()

    def _render(self):
        pal = theme.palette()
        self.delete('all')
        track = pal['accent'] if self._value else pal['hairline']
        h = self.H
        r = h / 2
        self.create_oval(1, 1, h - 1, h - 1, fill=track, outline='')
        self.create_oval(self.W - h + 1, 1, self.W - 1, h - 1, fill=track,
                         outline='')
        self.create_rectangle(r, 1, self.W - r, h - 1, fill=track, outline='')
        kx = self.W - h + 2 if self._value else 2
        self.create_oval(kx, 2, kx + h - 4, h - 2, fill='#FFFFFF', outline='')

    def _follow_var(self):
        new = bool(self._var.get())
        if new != self._value:
            self._value = new
            self._render()

    def toggle(self):
        self._value = not self._value
        if self._var is not None:
            self._var.set(int(self._value))
        self._render()
        if self._command:
            self._command(self._value)

    def get(self):
        return self._value

    def set(self, value):
        self._value = bool(value)
        if self._var is not None:
            self._var.set(int(self._value))
        self._render()

    def restyle(self):
        self._bg = theme.palette()[self._surface]
        self.configure(bg=self._bg)
        self._render()
