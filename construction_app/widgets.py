"""Small shared widgets that tkinter/ttk doesn't ship.

``Switch`` — a pill toggle drawn on a Canvas, since ttk has no native switch.
Used for the theme toggle in the rail and the module on/off toggles in Tools.

``ScrollFrame`` — a vertically scrollable container (a Canvas + inner Frame),
since ttk has no scrolling frame. Put content in ``.body``. Used by the Home
dashboard, whose stacked cards outgrow the window.
"""

import tkinter as tk
from tkinter import ttk

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


class ScrollFrame(ttk.Frame):
    """A vertically scrollable container. Add content to ``.body``.

    A ttk.Frame cannot scroll, so this wraps a Canvas (which can) around an
    inner frame and keeps the two in step: the inner frame's height drives the
    scroll region, and the canvas width drives the inner frame's width so the
    content fills the pane rather than sitting at its natural width. The wheel
    is bound only while the pointer is over the pane, so it doesn't fight other
    scrollable widgets on screen.
    """

    def __init__(self, parent, style='Stage.TFrame'):
        super().__init__(parent, style=style)
        self._style = style
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                 bg=theme.palette()['canvas'])
        vsb = ttk.Scrollbar(self, orient='vertical',
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self._canvas.pack(side='left', fill='both', expand=True)

        self.body = ttk.Frame(self._canvas, style=style)
        self._win = self._canvas.create_window((0, 0), window=self.body,
                                               anchor='nw')
        self.body.bind('<Configure>', self._on_body)
        self._canvas.bind('<Configure>', self._on_canvas)
        self._canvas.bind('<Enter>', lambda _e: self._canvas.bind_all(
            '<MouseWheel>', self._on_wheel))
        self._canvas.bind('<Leave>', lambda _e: self._canvas.unbind_all(
            '<MouseWheel>'))

    def _on_body(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _on_canvas(self, e):
        self._canvas.itemconfigure(self._win, width=e.width)

    def _on_wheel(self, e):
        # Windows/mac deliver +-120 per notch; only scroll if there's overflow.
        first, last = self._canvas.yview()
        if first <= 0.0 and last >= 1.0:
            return
        self._canvas.yview_scroll(int(-e.delta / 120), 'units')

    def restyle(self):
        self._canvas.configure(bg=theme.palette()['canvas'])


class FloatingDock(ttk.Frame):
    """A small floating action cluster — New · Refresh · Save — that hovers at
    the bottom-right of the stage, over the work.

    ``resolve(action)`` returns the callable to run for ``'new'``/``'save'``/
    ``'refresh'`` on whichever tab is active, or ``None`` when that tab doesn't
    offer it. Each button disables for an action the active tab can't do, and
    the whole dock hides when it can do none — a contextual action bar, not dead
    chrome. Follows the HCW kit: a raised surface (elevation stands in for the
    shadow/blur tkinter can't draw), and one accent — **Save** — as the primary,
    with New and Refresh quiet.
    """

    SPECS = (('new', '✚  New', 'TButton'),
             ('refresh', '⟳  Refresh', 'TButton'),
             ('save', '✔  Save', 'Accent.TButton'))

    def __init__(self, parent, resolve):
        super().__init__(parent, style='Dock.TFrame', padding=6)
        self._resolve = resolve
        self._btns = {}
        for action, label, style in self.SPECS:
            b = ttk.Button(self, text=label, style=style, takefocus=0,
                           command=lambda a=action: self._run(a))
            b.pack(side='left', padx=3)
            self._btns[action] = b

    def _run(self, action):
        fn = self._resolve(action)
        if callable(fn):
            fn()
            # a New or Save changes what the buttons would do next.
            self.after(0, self.update_state)

    def update_state(self):
        """Enable/disable each button for the active tab; hide if none apply."""
        any_on = False
        for action, b in self._btns.items():
            on = callable(self._resolve(action))
            any_on = any_on or on
            b.state(['!disabled'] if on else ['disabled'])
        if any_on:
            self.place(relx=1.0, rely=1.0, anchor='se', x=-18, y=-18)
            self.lift()
        else:
            self.place_forget()
