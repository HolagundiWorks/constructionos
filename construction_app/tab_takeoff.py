"""Quantity takeoff — measure lengths, areas, counts and volumes straight off a
drawing, Bluebeam-style.

Open a drawing (a PNG, or a PDF if a renderer such as poppler/Ghostscript is on
the machine — see ``pdf_render``), **calibrate the scale** once by drawing a line
over a known dimension, then mark up the sheet: a **polyline** along a wall for
its length, a **polygon** around a slab for its area (times a depth for volume),
or **count** clicks for doors. Every mark-up's real quantity is computed live by
the pure ``takeoff`` engine and listed; the whole takeoff saves to the book and
can be pushed into a new estimate.

tkinter shows the drawing on a ``Canvas`` and the mark-ups are ordinary canvas
items — no image library, no pip. A PDF is rendered to PNG by an external tool
only when one is installed; otherwise the tab says so and the user opens a PNG.
"""

import json
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import pdf_render
import takeoff
import theme
from ui_guard import can_write
from tab_masters import site_options, project_options

_TOOLS = [('length', 'Length'), ('area', 'Area'), ('volume', 'Volume'),
          ('count', 'Count')]


class TakeoffTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._img = None
        self._img_size = (0, 0)
        self._source = ''
        self._page = 1
        self._scale = 0.0
        self._unit = 'm'
        self._tool = 'length'
        self._pts = []
        self._items = []
        self._takeoff_id = None
        self._proj_map = {}
        self._site_map = {}
        self._build_ui()
        self._reload_selectors()

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        pal = theme.palette()
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 2))
        ttk.Label(top, text='Takeoff', font=('TkDefaultFont', 13, 'bold')) \
            .pack(side='left')
        ttk.Button(top, text='Open Image…', command=self.open_image).pack(
            side='left', padx=(12, 3))
        ttk.Button(top, text='Open PDF…', command=self.open_pdf).pack(
            side='left', padx=3)
        ttk.Button(top, text='Save', command=self.save).pack(side='left', padx=3)
        ttk.Button(top, text='Load…', command=self.load).pack(side='left', padx=3)

        meta = ttk.Frame(self); meta.pack(fill='x', padx=8, pady=2)
        ttk.Label(meta, text='Name').pack(side='left')
        self.name_var = tk.StringVar()
        ttk.Entry(meta, textvariable=self.name_var, width=22).pack(
            side='left', padx=(2, 8))
        ttk.Label(meta, text='Project').pack(side='left')
        self.proj_var = tk.StringVar()
        self.proj_combo = ttk.Combobox(meta, textvariable=self.proj_var,
                                       width=18, state='readonly')
        self.proj_combo.pack(side='left', padx=(2, 8))
        ttk.Label(meta, text='Site').pack(side='left')
        self.site_var = tk.StringVar()
        self.site_combo = ttk.Combobox(meta, textvariable=self.site_var,
                                       width=16, state='readonly')
        self.site_combo.pack(side='left', padx=2)

        bar = ttk.Frame(self); bar.pack(fill='x', padx=8, pady=(4, 2))
        self.scale_var = tk.StringVar(value='Scale: not set')
        ttk.Label(bar, textvariable=self.scale_var,
                  foreground=pal['muted']).pack(side='left')
        ttk.Button(bar, text='Set Scale', command=self.set_scale).pack(
            side='left', padx=6)
        ttk.Label(bar, text='Unit').pack(side='left', padx=(8, 2))
        self.unit_combo = ttk.Combobox(bar, width=5, state='readonly',
                                       values=['m', 'ft', 'mm'])
        self.unit_combo.set('m')
        self.unit_combo.bind('<<ComboboxSelected>>',
                             lambda e: self._set_unit(self.unit_combo.get()))
        self.unit_combo.pack(side='left')
        ttk.Label(bar, text='Depth (for volume)').pack(side='left', padx=(12, 2))
        self.depth_var = tk.StringVar(value='0')
        ttk.Entry(bar, textvariable=self.depth_var, width=7).pack(side='left')

        toolbar = ttk.Frame(self); toolbar.pack(fill='x', padx=8, pady=(2, 4))
        self.tool_var = tk.StringVar(value='length')
        for kind, label in _TOOLS:
            ttk.Radiobutton(toolbar, text=label, value=kind,
                            variable=self.tool_var,
                            command=lambda k=kind: self._set_tool(k)).pack(
                side='left', padx=(0, 8))
        ttk.Button(toolbar, text='Finish shape', style='Accent.TButton',
                   command=self.finish_shape).pack(side='left', padx=(12, 3))
        ttk.Button(toolbar, text='Undo point',
                   command=self.undo_point).pack(side='left', padx=3)
        self.hint_var = tk.StringVar(
            value='Open a drawing, Set Scale, then click to measure. '
                  'Double-click or Finish to complete a shape.')
        ttk.Label(toolbar, textvariable=self.hint_var,
                  foreground=pal['muted']).pack(side='left', padx=10)

        body = ttk.Frame(self); body.pack(fill='both', expand=True, padx=8,
                                          pady=4)
        cwrap = ttk.Frame(body); cwrap.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(cwrap, bg=pal['surface'], highlightthickness=0,
                                cursor='crosshair')
        vsb = ttk.Scrollbar(cwrap, orient='vertical', command=self.canvas.yview)
        hsb = ttk.Scrollbar(cwrap, orient='horizontal',
                            command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Double-Button-1>', lambda e: self.finish_shape())

        side = ttk.Frame(body); side.pack(side='left', fill='y', padx=(8, 0))
        ttk.Label(side, text='Measurements',
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
        self.tree = ttk.Treeview(side, columns=('name', 'kind', 'qty', 'unit'),
                                 show='headings', height=16)
        for c, w in (('name', 130), ('kind', 60), ('qty', 80), ('unit', 50)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor='w')
        self.tree.pack(fill='y', pady=4)
        self.total_var = tk.StringVar()
        ttk.Label(side, textvariable=self.total_var, wraplength=340,
                  justify='left').pack(anchor='w')
        srow = ttk.Frame(side); srow.pack(fill='x', pady=4)
        ttk.Button(srow, text='Delete', command=self.delete_item).pack(
            side='left')
        ttk.Button(srow, text='Send to Estimate', style='Accent.TButton',
                   command=self.send_to_estimate).pack(side='left', padx=6)

    # -------------------------------------------------------------- selectors
    def _reload_selectors(self):
        conn = self.db_getter()
        try:
            self._proj_map = {'{} - {}'.format(i, n): i
                              for i, n in project_options(conn)}
            self._site_map = {'{} - {}'.format(i, n): i
                              for i, n in site_options(conn)}
        finally:
            conn.close()
        self.proj_combo['values'] = [''] + list(self._proj_map.keys())
        self.site_combo['values'] = [''] + list(self._site_map.keys())

    def _set_unit(self, u):
        self._unit = u
        self._update_scale_label()

    def _set_tool(self, k):
        self._tool = k
        self._pts = []
        self._redraw()

    def _update_scale_label(self):
        if self._scale > 0:
            self.scale_var.set('Scale: {:.5g} {}/px'.format(
                self._scale, self._unit))
        else:
            self.scale_var.set('Scale: not set')

    # ---------------------------------------------------------------- images
    def _show_image(self, path):
        try:
            img = tk.PhotoImage(file=path)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror(
                'Could not open',
                'Only PNG images display directly (Tk limitation). For a JPG or '
                'PDF, use Open PDF with a renderer installed, or convert the '
                'page to PNG.\n\n{}'.format(exc))
            return False
        self._img = img
        self._img_size = (img.width(), img.height())
        self._source = path
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=img, tags='bgimg')
        self.canvas.configure(scrollregion=(0, 0, img.width(), img.height()))
        self._redraw()
        return True

    def open_image(self):
        path = filedialog.askopenfilename(
            title='Open a drawing image',
            filetypes=[('PNG image', '*.png'), ('GIF image', '*.gif'),
                       ('All files', '*.*')])
        if path:
            self._show_image(path)

    def open_pdf(self):
        path = filedialog.askopenfilename(
            title='Open a drawing PDF', filetypes=[('PDF', '*.pdf')])
        if not path:
            return
        if not pdf_render.available():
            messagebox.showinfo('PDF renderer needed', pdf_render.install_hint())
            return
        page = simpledialog.askinteger('Page', 'Which page? (1-based)',
                                       parent=self, initialvalue=1, minvalue=1)
        if not page:
            return
        self.hint_var.set('Rendering page {}…'.format(page))
        self.update_idletasks()
        try:
            png = pdf_render.render_page(path, page=page, dpi=150)
        except RuntimeError as exc:
            messagebox.showerror('Could not render PDF', str(exc))
            self.hint_var.set('')
            return
        if self._show_image(png):
            self._source = path
            self._page = page
        self.hint_var.set('Set the scale, then measure.')

    # ----------------------------------------------------------- interaction
    def _xy(self, event):
        return (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _on_click(self, event):
        if self._img is None:
            return
        self._pts.append(self._xy(event))
        self._redraw()

    def undo_point(self):
        if self._pts:
            self._pts.pop()
            self._redraw()

    def set_scale(self):
        if self._img is None:
            messagebox.showinfo('Open a drawing', 'Open an image or PDF first.')
            return
        messagebox.showinfo(
            'Set scale',
            'Click the two ends of a line whose real length you know '
            '(a grid line, a stated dimension). You will then enter its length.')
        self._pts = []
        self._tool = 'calibrate'
        self.hint_var.set('Calibrating: click the two ends of a known line.')

    def finish_shape(self):
        if self._tool == 'calibrate':
            if len(self._pts) < 2:
                return
            self._finish_calibrate()
            return
        kind = self._tool
        if len(self._pts) < takeoff.min_points(kind):
            messagebox.showinfo('More points needed',
                                'A {} needs at least {} point(s).'.format(
                                    kind, takeoff.min_points(kind)))
            return
        if kind in ('length', 'area', 'volume') and self._scale <= 0:
            if not messagebox.askyesno(
                    'No scale set',
                    'The scale is not calibrated, so the quantity will be 0. '
                    'Set the scale first?\n\nYes = go set the scale, '
                    'No = record it anyway.'):
                pass
            else:
                return
        name = simpledialog.askstring(
            'Name', 'Name this measurement:', parent=self,
            initialvalue='{} {}'.format(kind.title(), len(self._items) + 1))
        if name is None:
            return
        depth = self._depth() if kind == 'volume' else 0.0
        qty = takeoff.measure(kind, self._pts, self._scale, depth)
        unit = takeoff.unit_for(kind, self._unit)
        self._items.append({'name': name, 'category': '', 'kind': kind,
                            'unit': unit, 'depth': depth, 'quantity': qty,
                            'points': list(self._pts)})
        self._pts = []
        self._refresh_list()
        self._redraw()

    def _finish_calibrate(self):
        px = takeoff.distance(self._pts[0], self._pts[1])
        real = simpledialog.askfloat(
            'Set scale', 'Real length of that line, in {}:'.format(self._unit),
            parent=self, minvalue=0.0)
        self._pts = []
        self._tool = self.tool_var.get()
        if real:
            self._scale = takeoff.scale_from(px, real)
            self._update_scale_label()
        self._redraw()
        self.hint_var.set('Scale set. Now measure.')

    def _depth(self):
        try:
            return float(self.depth_var.get() or 0)
        except ValueError:
            return 0.0

    # ------------------------------------------------------------- rendering
    def _redraw(self):
        self.canvas.delete('mark')
        pal = theme.palette()
        for it in self._items:
            self._draw(it['kind'], it['points'], pal, final=True,
                       label=it['name'])
        if self._pts:
            self._draw(self._tool, self._pts, pal, final=False)

    def _draw(self, kind, pts, pal, final=True, label=''):
        if not pts:
            return
        col = {'length': pal['info'], 'area': pal['success'],
               'volume': pal['accent'], 'count': pal['error'],
               'calibrate': pal['warning']}.get(kind, pal['info'])
        for (x, y) in pts:
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=col,
                                    outline='', tags='mark')
        if kind == 'count':
            return
        if kind in ('area', 'volume') and (final or len(pts) > 2):
            poly = [c for p in pts for c in p]
            if len(pts) >= 3:
                self.canvas.create_polygon(*poly, outline=col, width=2,
                                           fill='', tags='mark')
        else:
            for i in range(len(pts) - 1):
                self.canvas.create_line(pts[i][0], pts[i][1],
                                        pts[i + 1][0], pts[i + 1][1],
                                        fill=col, width=2, tags='mark')
        if final and label:
            x, y = pts[0]
            self.canvas.create_text(x + 6, y - 8, text=label, anchor='w',
                                    fill=col, font=('TkDefaultFont', 8),
                                    tags='mark')

    def _refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        for idx, it in enumerate(self._items):
            self.tree.insert('', 'end', iid=str(idx), values=(
                it['name'], it['kind'], '{:.3g}'.format(it['quantity']),
                it['unit']))
        totals = takeoff.totals_by_unit(self._items)
        self.total_var.set('Totals:  ' + '   '.join(
            '{:.4g} {}'.format(v, u or '?') for u, v in sorted(totals.items()))
            if totals else '')

    def delete_item(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
            self._refresh_list()
            self._redraw()

    # -------------------------------------------------------------- persist
    def _pid(self):
        return self._proj_map.get(self.proj_var.get())

    def _sid(self):
        return self._site_map.get(self.site_var.get())

    def save(self):
        if not can_write():
            return
        if not self._items and not self._source:
            return
        name = self.name_var.get().strip() or 'Takeoff'
        conn = self.db_getter()
        try:
            if self._takeoff_id is None:
                cur = conn.execute(
                    'INSERT INTO takeoffs (project_id, site_id, name, source, '
                    'page, scale, unit, created_at) VALUES (?,?,?,?,?,?,?,?)',
                    (self._pid(), self._sid(), name, self._source, self._page,
                     self._scale, self._unit,
                     datetime.now().isoformat(timespec='seconds')))
                self._takeoff_id = cur.lastrowid
            else:
                conn.execute(
                    'UPDATE takeoffs SET project_id=?, site_id=?, name=?, '
                    'source=?, page=?, scale=?, unit=? WHERE id=?',
                    (self._pid(), self._sid(), name, self._source, self._page,
                     self._scale, self._unit, self._takeoff_id))
                conn.execute('DELETE FROM takeoff_items WHERE takeoff_id=?',
                             (self._takeoff_id,))
            for it in self._items:
                conn.execute(
                    'INSERT INTO takeoff_items (takeoff_id, name, category, '
                    'kind, unit, depth, quantity, points) VALUES '
                    '(?,?,?,?,?,?,?,?)',
                    (self._takeoff_id, it['name'], it.get('category', ''),
                     it['kind'], it['unit'], it.get('depth', 0),
                     it['quantity'], json.dumps(it['points'])))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo('Saved', 'Takeoff "{}" saved.'.format(name))

    def load(self):
        conn = self.db_getter()
        try:
            rows = conn.execute(
                'SELECT id, name FROM takeoffs ORDER BY id DESC').fetchall()
        finally:
            conn.close()
        if not rows:
            messagebox.showinfo('Nothing saved', 'No takeoffs saved yet.')
            return
        names = {'{} - {}'.format(r['id'], r['name'] or 'Takeoff'): r['id']
                 for r in rows}
        choice = simpledialog.askstring(
            'Load takeoff', 'Type one to load:\n\n' + '\n'.join(names.keys()),
            parent=self)
        tid = names.get((choice or '').strip())
        if tid is None:
            return
        conn = self.db_getter()
        try:
            t = conn.execute('SELECT * FROM takeoffs WHERE id=?', (tid,)).fetchone()
            items = conn.execute(
                'SELECT * FROM takeoff_items WHERE takeoff_id=? ORDER BY id',
                (tid,)).fetchall()
        finally:
            conn.close()
        self._takeoff_id = tid
        self.name_var.set(t['name'] or '')
        self._scale = t['scale'] or 0.0
        self._unit = t['unit'] or 'm'
        self.unit_combo.set(self._unit)
        self._update_scale_label()
        self._items = [{'name': r['name'], 'category': r['category'],
                        'kind': r['kind'], 'unit': r['unit'],
                        'depth': r['depth'], 'quantity': r['quantity'],
                        'points': [tuple(p) for p in
                                   json.loads(r['points'] or '[]')]}
                       for r in items]
        if t['source'] and os.path.exists(t['source']) \
                and t['source'].lower().endswith(('.png', '.gif')):
            self._show_image(t['source'])
        else:
            self.canvas.delete('all')
            self.canvas.create_text(
                16, 20, anchor='w', fill=theme.palette()['muted'],
                text='Source drawing not found — reopen it to see the mark-ups '
                     'in place. The measurements are loaded.')
        self._refresh_list()
        self._redraw()

    def send_to_estimate(self):
        if not can_write():
            return
        if not self._items:
            messagebox.showinfo('Nothing to send', 'Measure something first.')
            return
        name = self.name_var.get().strip() or 'Takeoff'
        conn = self.db_getter()
        try:
            n = conn.execute('SELECT COUNT(*) c FROM estimates').fetchone()['c']
            cur = conn.execute(
                'INSERT INTO estimates (est_number, title, site_id, '
                'estimate_date, status, contingency_pct, gst_pct) VALUES '
                "(?, ?, ?, ?, 'Draft', 0, 18)",
                ('EST-{}'.format(n + 1), 'Takeoff: ' + name, self._sid(),
                 datetime.now().date().isoformat()))
            eid = cur.lastrowid
            for it in self._items:
                conn.execute(
                    'INSERT INTO estimate_items (estimate_id, item_code, '
                    'description, unit, qty, rate, amount) VALUES '
                    '(?, ?, ?, ?, ?, 0, 0)',
                    (eid, '', it['name'], it['unit'], it['quantity']))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(
            'Estimate created',
            'Created a draft estimate with {} item(s) from this takeoff. Open '
            'Billing › Estimates to price and finish it.'.format(
                len(self._items)))


def build_takeoff_tab(parent, db_getter):
    return TakeoffTab(parent, db_getter)
