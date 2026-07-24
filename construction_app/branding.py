"""Central app branding — name and developer credit in one place.

Product name: **ACO** (Accelerated Construction Operations). The logo mark is
the Fluent 2 gauge-C (open ring + target) in Radiant Orange — see
``docs/BRAND.md`` and ``branding/make_brand.py``.
"""

# Short product name — window titles, rail, installer display name.
APP_NAME = 'ACO'
# Expanded name — taglines, about, docs, first-run copy.
APP_FULL_NAME = 'Accelerated Construction Operations'
TAGLINE = APP_FULL_NAME
# Combined title used by desktop / WinUI shells.
WINDOW_TITLE = '{} — {}'.format(APP_NAME, APP_FULL_NAME)

DEVELOPER = 'Human Centric Works, Hospet'
CREDIT = 'Developed by ' + DEVELOPER

# Shown in printed-document footers (the contractor's own firm name is the
# letterhead; this is a subtle "powered by" software credit).
POWERED_BY = 'Powered by {} · {}'.format(APP_NAME, CREDIT)

# Radiant Orange — same as tokens.LIGHT['accent']; logo mark fill.
BRAND_ORANGE = (255, 79, 24)          # #FF4F18
BRAND_ORANGE_HEX = '#FF4F18'
# Analogous stops used by the Fluent 2 tile gradient (docs/BRAND.md).
BRAND_ORANGE_LIGHT = (255, 154, 92)   # #FF9A5C
BRAND_ORANGE_DEEP = (217, 50, 0)      # #D93200
