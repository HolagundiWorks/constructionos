"""A starter reference library: standard civil items, current material rates and
material-consumption norms, so a contractor can price and reconcile work from
day one instead of typing every coefficient by hand.

It fills four existing tables and is loaded on demand from Tools into whichever
company file is open:

* ``materials``          — a civil material master with **indicative** current
  rates (mid-2026, India / Maharashtra market; region-dependent, meant to be
  edited to the user's locality — see SOURCES).
* ``consumption_norms``  — the **material split**: how much of each material one
  unit of an activity consumes (per cum of concrete/masonry, per sqm of
  plaster…). Coefficients are the standard IS/CPWD nominal-mix figures
  (dry-volume factor 1.54) — indicative; a structural item should be checked
  against its own mix design.
* ``rate_book``          — CPWD-style standard items (own concise descriptions,
  a simple ``CIV-*`` code scheme — not the proprietary DSR numbering) as a
  reference/spec library.
* ``rate_analysis``      — a few worked analyses on the DAR skeleton so the Rate
  Analysis screen opens with real examples; the per-unit rate is computed here
  with ``rateanalysis.analyse`` so it agrees with what the screen would derive.

Everything is **idempotent and additive**: a material already present (by name),
a norm already present (by activity + material), a code already in the rate book
or analyses is left untouched — loading twice changes nothing the second time.
Norm ``activity`` strings are chosen to be clean, reusable labels because the
consumption reconciliation joins them to ``work_done_entries.activity`` by exact
string, so re-using the same wording there makes the theoretical side line up.

Pure of tkinter (imports only ``rateanalysis``), so it is unit-testable.
"""

import rateanalysis

# Where the indicative rates come from (2026 market listings). Kept in the file
# so the figures are traceable, not magic numbers.
SOURCES = (
    'comaron.com building-materials 2026; civiconcepts / houseyog cement 2026; '
    'ofbusiness AAC blocks; indiamart coarse aggregate. Rates are indicative '
    'and region-dependent — edit Masters > Materials to your locality.'
)

# --- material master: (name, unit, category, hsn, rate ₹) ------------------
MATERIALS = [
    ('OPC 53 Grade Cement', 'bag', 'Cement', '2523', 380),
    ('OPC 43 Grade Cement', 'bag', 'Cement', '2523', 370),
    ('PPC Cement', 'bag', 'Cement', '2523', 360),
    ('TMT Steel Fe500 8mm', 'kg', 'Steel', '7214', 62),
    ('TMT Steel Fe500 10mm', 'kg', 'Steel', '7214', 61),
    ('TMT Steel Fe500 12mm', 'kg', 'Steel', '7214', 60),
    ('TMT Steel Fe500 16mm', 'kg', 'Steel', '7214', 60),
    ('TMT Steel Fe500 20mm', 'kg', 'Steel', '7214', 59),
    ('Binding Wire', 'kg', 'Steel', '7217', 78),
    ('Structural Steel (sections)', 'kg', 'Steel', '7216', 72),
    ('River Sand', 'cum', 'Sand', '2505', 1700),
    ('M-Sand (manufactured)', 'cum', 'Sand', '2505', 1600),
    ('Coarse Aggregate 20mm', 'cum', 'Aggregate', '2517', 1900),
    ('Coarse Aggregate 10mm', 'cum', 'Aggregate', '2517', 2000),
    ('Coarse Aggregate 40mm', 'cum', 'Aggregate', '2517', 1700),
    ('Red Clay Brick (modular)', 'nos', 'Masonry', '6904', 7.5),
    ('Fly Ash Brick', 'nos', 'Masonry', '6815', 5.8),
    ('AAC Block 600x200x200', 'nos', 'Masonry', '6810', 50),
    ('AAC Block Adhesive', 'bag', 'Masonry', '3824', 300),
    ('RMC M20 (ready-mix)', 'cum', 'Concrete', '3824', 4100),
    ('RMC M25 (ready-mix)', 'cum', 'Concrete', '3824', 4700),
    ('Ceramic Floor Tile', 'sqm', 'Finishes', '6907', 45),
    ('Acrylic Emulsion Paint', 'litre', 'Finishes', '3209', 210),
    ('Cement Primer', 'litre', 'Finishes', '3209', 130),
]

# --- consumption norms: (activity, unit, material_name, qty_per_unit, remark)
# The unit is the unit of the ACTIVITY (per cum / per sqm); qty_per_unit is how
# much of the material that one unit consumes. IS/CPWD nominal-mix coefficients.
_M75 = 'nominal 1:4:8 (dry-vol 1.54)'
_M10 = 'nominal 1:3:6 (dry-vol 1.54)'
_M15 = 'nominal 1:2:4 (dry-vol 1.54)'
_M20 = 'nominal 1:1.5:3 (dry-vol 1.54)'
_M25 = 'design-mix typical (~390 kg/cum)'
_STEEL = 'indicative — per structural design'

NORMS = [
    # --- concrete / PCC (per cum) ---
    ('PCC M7.5 (1:4:8)', 'cum', 'OPC 53 Grade Cement', 3.40, _M75),
    ('PCC M7.5 (1:4:8)', 'cum', 'River Sand', 0.47, _M75),
    ('PCC M7.5 (1:4:8)', 'cum', 'Coarse Aggregate 40mm', 0.94, _M75),
    ('PCC M10 (1:3:6)', 'cum', 'OPC 53 Grade Cement', 4.40, _M10),
    ('PCC M10 (1:3:6)', 'cum', 'River Sand', 0.46, _M10),
    ('PCC M10 (1:3:6)', 'cum', 'Coarse Aggregate 20mm', 0.92, _M10),
    ('RCC M15 (1:2:4)', 'cum', 'OPC 53 Grade Cement', 6.34, _M15),
    ('RCC M15 (1:2:4)', 'cum', 'River Sand', 0.44, _M15),
    ('RCC M15 (1:2:4)', 'cum', 'Coarse Aggregate 20mm', 0.88, _M15),
    ('RCC M20 (1:1.5:3)', 'cum', 'OPC 53 Grade Cement', 8.06, _M20),
    ('RCC M20 (1:1.5:3)', 'cum', 'River Sand', 0.42, _M20),
    ('RCC M20 (1:1.5:3)', 'cum', 'Coarse Aggregate 20mm', 0.84, _M20),
    ('RCC M25 (design mix)', 'cum', 'OPC 53 Grade Cement', 7.80, _M25),
    ('RCC M25 (design mix)', 'cum', 'River Sand', 0.40, _M25),
    ('RCC M25 (design mix)', 'cum', 'Coarse Aggregate 20mm', 0.80, _M25),
    # --- reinforcement (per cum of RCC — design-dependent) ---
    ('RCC Slab reinforcement', 'cum', 'TMT Steel Fe500 12mm', 80, _STEEL),
    ('RCC Beam reinforcement', 'cum', 'TMT Steel Fe500 16mm', 110, _STEEL),
    ('RCC Column reinforcement', 'cum', 'TMT Steel Fe500 20mm', 130, _STEEL),
    ('RCC Footing reinforcement', 'cum', 'TMT Steel Fe500 12mm', 60, _STEEL),
    # --- masonry ---
    ('Brick masonry 230mm (CM 1:6)', 'cum', 'Red Clay Brick (modular)', 500, ''),
    ('Brick masonry 230mm (CM 1:6)', 'cum', 'OPC 53 Grade Cement', 1.26, 'CM 1:6'),
    ('Brick masonry 230mm (CM 1:6)', 'cum', 'River Sand', 0.27, 'CM 1:6'),
    ('Brick masonry 230mm (CM 1:4)', 'cum', 'Red Clay Brick (modular)', 500, ''),
    ('Brick masonry 230mm (CM 1:4)', 'cum', 'OPC 53 Grade Cement', 1.90, 'CM 1:4'),
    ('Brick masonry 230mm (CM 1:4)', 'cum', 'River Sand', 0.25, 'CM 1:4'),
    ('Half-brick 115mm partition (CM 1:4)', 'sqm',
     'Red Clay Brick (modular)', 57, 'per sqm of wall'),
    ('Half-brick 115mm partition (CM 1:4)', 'sqm',
     'OPC 53 Grade Cement', 0.17, 'CM 1:4'),
    ('Half-brick 115mm partition (CM 1:4)', 'sqm',
     'River Sand', 0.019, 'CM 1:4'),
    ('AAC block masonry 200mm', 'cum', 'AAC Block 600x200x200', 42,
     '600x200x200'),
    ('AAC block masonry 200mm', 'cum', 'AAC Block Adhesive', 2.0, 'thin-bed'),
    # --- plastering (per sqm) ---
    ('Internal plaster 12mm (CM 1:6)', 'sqm', 'OPC 53 Grade Cement', 0.090, ''),
    ('Internal plaster 12mm (CM 1:6)', 'sqm', 'River Sand', 0.018, ''),
    ('External plaster 15mm (CM 1:5)', 'sqm', 'OPC 53 Grade Cement', 0.130, ''),
    ('External plaster 15mm (CM 1:5)', 'sqm', 'River Sand', 0.020, ''),
    ('Ceiling plaster 6mm (CM 1:3)', 'sqm', 'OPC 53 Grade Cement', 0.060, ''),
    ('Ceiling plaster 6mm (CM 1:3)', 'sqm', 'River Sand', 0.008, ''),
    # --- other civil ---
    ('DPC 40mm (M15 1:2:4)', 'sqm', 'OPC 53 Grade Cement', 0.25, 'per sqm 40mm'),
    ('DPC 40mm (M15 1:2:4)', 'sqm', 'River Sand', 0.018, ''),
    ('DPC 40mm (M15 1:2:4)', 'sqm', 'Coarse Aggregate 10mm', 0.035, ''),
    ('Ceramic tile flooring', 'sqm', 'Ceramic Floor Tile', 1.05, '5% wastage'),
    ('Ceramic tile flooring', 'sqm', 'OPC 53 Grade Cement', 0.15, '20mm bed'),
    ('Ceramic tile flooring', 'sqm', 'River Sand', 0.020, '20mm bed'),
    ('Internal emulsion paint (2 coats)', 'sqm',
     'Acrylic Emulsion Paint', 0.16, '2 coats'),
    ('Internal emulsion paint (2 coats)', 'sqm', 'Cement Primer', 0.10, '1 coat'),
]

# --- rate_book: (code, category, description, unit, rate, specification) ----
RATE_BOOK = [
    ('CIV-EW-01', 'Earthwork', 'Earthwork in excavation in foundation, ordinary '
     'soil, lead 50m, lift 1.5m', 'cum', 260, 'manual / machine'),
    ('CIV-EW-02', 'Earthwork', 'Filling in plinth with excavated earth, watered '
     'and rammed in 20cm layers', 'cum', 180, ''),
    ('CIV-PCC-M75', 'Concrete', 'PCC 1:4:8 in foundation and plinth', 'cum',
     5200, 'M7.5 nominal'),
    ('CIV-PCC-M10', 'Concrete', 'PCC 1:3:6 levelling course', 'cum', 5900,
     'M10 nominal'),
    ('CIV-RCC-M20', 'Concrete', 'RCC 1:1.5:3 in foundations / footings, '
     'excluding steel and shuttering', 'cum', 7200, 'M20'),
    ('CIV-RCC-M25', 'Concrete', 'RCC M25 design mix in slabs / beams / columns, '
     'excluding steel and shuttering', 'cum', 8100, 'M25'),
    ('CIV-STL-01', 'Steel', 'Reinforcement TMT Fe500 — cut, bent, tied and '
     'placed in position', 'kg', 78, 'incl. binding wire'),
    ('CIV-FW-01', 'Formwork', 'Centering and shuttering for RCC slabs and beams',
     'sqm', 340, 'steel / ply'),
    ('CIV-BM-230', 'Masonry', 'Brick masonry 230mm in CM 1:6 in superstructure',
     'cum', 6800, 'modular brick'),
    ('CIV-BM-115', 'Masonry', 'Half-brick 115mm partition in CM 1:4 with '
     'hoop-iron reinforcement', 'sqm', 720, ''),
    ('CIV-AAC-200', 'Masonry', 'AAC block masonry 200mm with block adhesive',
     'cum', 5200, '600x200x200'),
    ('CIV-PL-INT', 'Finishing', '12mm cement plaster CM 1:6 to internal walls',
     'sqm', 240, ''),
    ('CIV-PL-EXT', 'Finishing', '15mm cement plaster CM 1:5 to external walls',
     'sqm', 300, 'two-coat'),
    ('CIV-PL-CL', 'Finishing', '6mm cement plaster CM 1:3 to ceiling', 'sqm',
     210, ''),
    ('CIV-FL-CT', 'Flooring', 'Ceramic tile flooring on 20mm CM 1:4 bed', 'sqm',
     620, '600x600'),
    ('CIV-FL-VT', 'Flooring', 'Vitrified tile flooring 800x800 on cement bed',
     'sqm', 850, ''),
    ('CIV-PT-EM', 'Painting', 'Acrylic emulsion paint, 2 coats over primer, '
     'internal', 'sqm', 95, ''),
    ('CIV-PT-EX', 'Painting', 'Exterior weatherproof emulsion, 2 coats over '
     'primer', 'sqm', 130, ''),
    ('CIV-WP-01', 'Waterproofing', 'Brickbat coba / APP membrane waterproofing '
     'to terrace', 'sqm', 550, ''),
    ('CIV-DPC-01', 'Misc', '40mm damp-proof course M15 1:2:4 with '
     'waterproofing compound', 'sqm', 320, ''),
    ('CIV-DR-01', 'Joinery', 'Flush door shutter 35mm on seasoned hardwood '
     'frame', 'sqm', 3200, ''),
    ('CIV-WN-01', 'Joinery', 'Aluminium sliding window with glazing and '
     'hardware', 'sqm', 4200, ''),
]

# --- worked rate analyses (DAR skeleton). Rate computed at load with
# rateanalysis.analyse so it matches the screen. items: (kind, desc, unit, qty,
# rate). apply_water=True on wet items.
ANALYSES = [
    {
        'code': 'CIV-RCC-M20', 'unit': 'cum', 'analysis_qty': 1, 'apply_water': 1,
        'description': 'RCC M20 (1:1.5:3), excl. steel & shuttering — per cum',
        'items': [
            ('Material', 'OPC 53 cement', 'bag', 8.06, 380),
            ('Material', 'River sand', 'cum', 0.42, 1700),
            ('Material', 'Coarse aggregate 20mm', 'cum', 0.84, 1900),
            ('Labour', 'Mixing, placing, compaction & curing', 'cum', 1, 950),
            ('Machinery', 'Mixer + needle vibrator', 'cum', 1, 150),
        ],
    },
    {
        'code': 'CIV-BM-230', 'unit': 'cum', 'analysis_qty': 1, 'apply_water': 1,
        'description': 'Brick masonry 230mm in CM 1:6 — per cum',
        'items': [
            ('Material', 'Modular bricks', 'nos', 500, 7.5),
            ('Material', 'OPC 53 cement', 'bag', 1.26, 380),
            ('Material', 'River sand', 'cum', 0.27, 1700),
            ('Labour', 'Mason + mazdoor', 'cum', 1, 1100),
        ],
    },
    {
        'code': 'CIV-PL-INT', 'unit': 'sqm', 'analysis_qty': 1, 'apply_water': 1,
        'description': '12mm internal cement plaster CM 1:6 — per sqm',
        'items': [
            ('Material', 'OPC 53 cement', 'bag', 0.09, 380),
            ('Material', 'River sand', 'cum', 0.018, 1700),
            ('Labour', 'Mason + mazdoor', 'sqm', 1, 90),
        ],
    },
]


def _material_ids(conn):
    """Ensure every reference material exists (by name) and return name->id.

    Existing materials with the same name are reused, not duplicated, so the
    library layers cleanly onto a book that already has some materials."""
    have = {r['name']: r['id']
            for r in conn.execute('SELECT id, name FROM materials')}
    added = 0
    for name, unit, category, hsn, rate in MATERIALS:
        if name in have:
            continue
        cur = conn.execute(
            'INSERT INTO materials (name, unit, category, hsn_code, rate) '
            'VALUES (?, ?, ?, ?, ?)', (name, unit, category, hsn, rate))
        have[name] = cur.lastrowid
        added += 1
    return have, added


def _seed_norms(conn, mat_ids):
    existing = {(r['activity'], r['material_id']) for r in conn.execute(
        'SELECT activity, material_id FROM consumption_norms')}
    added = 0
    for activity, unit, material_name, qty, remark in NORMS:
        mid = mat_ids.get(material_name)
        if mid is None or (activity, mid) in existing:
            continue
        conn.execute(
            'INSERT INTO consumption_norms (activity, unit, material_id, '
            'qty_per_unit, remarks) VALUES (?, ?, ?, ?, ?)',
            (activity, unit, mid, qty, remark))
        existing.add((activity, mid))
        added += 1
    return added


def _seed_rate_book(conn):
    have = {r['code'] for r in conn.execute(
        "SELECT code FROM rate_book WHERE code IS NOT NULL AND code <> ''")}
    added = 0
    for code, category, desc, unit, rate, spec in RATE_BOOK:
        if code in have:
            continue
        conn.execute(
            'INSERT INTO rate_book (code, category, description, unit, rate, '
            'specification) VALUES (?, ?, ?, ?, ?, ?)',
            (code, category, desc, unit, rate, spec))
        have.add(code)
        added += 1
    return added


def _seed_analyses(conn):
    have = {r['code'] for r in conn.execute(
        "SELECT code FROM rate_analysis WHERE code IS NOT NULL AND code <> ''")}
    added = 0
    for a in ANALYSES:
        # Distinct from the rate_book code so both can coexist; the analysis is
        # the worked build-up behind the (independently editable) rate-book line.
        code = a['code'] + '-RA'
        if code in have:
            continue
        lines = [{'kind': k, 'qty': q, 'rate': r}
                 for (k, _d, _u, q, r) in a['items']]
        res = rateanalysis.analyse(lines, a['analysis_qty'],
                                   bool(a['apply_water']))
        rate_per_unit = res['rate_per_unit'] or 0
        cur = conn.execute(
            'INSERT INTO rate_analysis (code, description, unit, analysis_qty, '
            'apply_water, water_pct, cpoh_pct, scaffolding, rate_per_unit, '
            'notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (code, a['description'], a['unit'], a['analysis_qty'],
             a['apply_water'], rateanalysis.WATER_PCT, rateanalysis.CPOH_PCT,
             0, rate_per_unit, 'Seeded reference analysis — rates indicative.'))
        aid = cur.lastrowid
        for kind, desc, unit, qty, rate in a['items']:
            conn.execute(
                'INSERT INTO rate_analysis_items (analysis_id, kind, '
                'description, unit, qty, rate, amount) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (aid, kind, desc, unit, qty, rate,
                 rateanalysis.line_amount(qty, rate)))
        have.add(code)
        added += 1
    return added


def load(conn):
    """Load the reference library into ``conn``'s database, additively.

    Returns ``{'materials', 'norms', 'rate_book', 'analyses'}`` — how many NEW
    rows each table gained (0 where they were already present)."""
    mat_ids, mats = _material_ids(conn)
    norms = _seed_norms(conn, mat_ids)
    books = _seed_rate_book(conn)
    analyses = _seed_analyses(conn)
    conn.commit()
    return {'materials': mats, 'norms': norms, 'rate_book': books,
            'analyses': analyses}
