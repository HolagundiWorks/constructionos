"""Statutory deductions calculator (Phase 3 — optional, off the main flow).

A deliberately standalone helper: enter a monthly wage and/or a construction
value and see the PF, ESI, and BOCW labour-cess figures (``statutory.py``).
Nothing here auto-deducts from the muster or payout — informal sites ignore it;
a contractor who must file uses it as a quick calculator. Rates are editable
because they change.
"""

import tkinter as tk
from tkinter import ttk

import statutory


class StatutoryCalculator(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Statutory Calculator (PF / ESI / Labour Cess)',
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Optional — for contractors who file EPF / ESI / '
                            'BOCW cess. Rates are editable; nothing here is '
                            'deducted automatically.', foreground='#666',
                  wraplength=560, justify='left').pack(anchor='w', padx=8, pady=(0, 8))

        self.v = {
            'wage': tk.StringVar(value='0'),
            'pf_rate': tk.StringVar(value='12'),
            'pf_ceiling': tk.StringVar(value='15000'),
            'esi_ee': tk.StringVar(value='0.75'),
            'esi_er': tk.StringVar(value='3.25'),
            'esi_threshold': tk.StringVar(value='21000'),
            'works_value': tk.StringVar(value='0'),
            'cess_rate': tk.StringVar(value='1'),
        }
        form = ttk.LabelFrame(self, text='Inputs'); form.pack(fill='x', padx=8, pady=4)
        rows = [
            ('Monthly Wage', 'wage'), ('PF Rate %', 'pf_rate'),
            ('PF Ceiling', 'pf_ceiling'), ('ESI Employee %', 'esi_ee'),
            ('ESI Employer %', 'esi_er'), ('ESI Threshold', 'esi_threshold'),
            ('Construction Value', 'works_value'), ('Cess Rate %', 'cess_rate'),
        ]
        for i, (label, key) in enumerate(rows):
            cell = ttk.Frame(form); cell.grid(row=i // 2, column=i % 2, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=18).pack(side='left')
            ttk.Entry(cell, textvariable=self.v[key], width=14).pack(side='left')

        ttk.Button(self, text='Calculate', command=self.calculate) \
            .pack(anchor='w', padx=8, pady=6)

        self.out = tk.StringVar(value='—')
        ttk.Label(self, textvariable=self.out, font=('TkDefaultFont', 11),
                  justify='left').pack(anchor='w', padx=10, pady=6)

    def _f(self, key):
        try:
            return float(self.v[key].get().strip() or 0)
        except ValueError:
            return 0.0

    def calculate(self):
        wage = self._f('wage')
        pf = statutory.pf(wage, self._f('pf_rate'), self._f('pf_ceiling'))
        esi = statutory.esi(wage, self._f('esi_ee'), self._f('esi_er'),
                            self._f('esi_threshold'))
        cess = statutory.labour_cess(self._f('works_value'), self._f('cess_rate'))
        self.out.set(
            'PF (employee): {:,.2f}\n'
            'ESI — employee {:,.2f}  |  employer {:,.2f}  |  total {:,.2f}\n'
            'Labour cess (BOCW): {:,.2f}'.format(
                pf, esi['employee'], esi['employer'], esi['total'], cess))
