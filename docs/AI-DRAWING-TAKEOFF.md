# Construction OS — AI Drawing Reading & Automated Quantity Takeoff

**Reading drawings, identifying elements (walls / doors / windows), extracting
quantities, human reconciliation, and revision-delta analysis**

_Document type: Reference / Solution design (documentation only — no code changes)_
_Version: 1.0 · Last updated: 2026-07-21 · Prepared by: Human Centric Works_
_Deep-dive companion to [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md)
(E1 Capture) and [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md)._

---

## 0. How to read this document

This expands one item from the enterprise roadmap — *"BOQ / drawing → import
draft"* (E1 Capture) — into a full design, because drawing takeoff is the single
highest-value, highest-effort application of AI in this product. It covers four
things the user asked for:

1. **AI reads a drawing and extracts quantities.**
2. **"Plan identity"** — AI recognises building elements (walls, doors, windows,
   …) and classifies them.
3. **Human reconciliation** — AI proposes; a person verifies and corrects; the
   verified result becomes the takeoff.
4. **Revision analysis** — once a drawing is mapped, a *revised* drawing is
   compared, the **differences are marked by AI**, quantified, and reconciled
   across layers and revisions — feeding the variation/change-order register.

Maturity tags, as elsewhere: **Built** · **Extend** · **Proposed**.

**The anchor (important).** Construction OS *already ships a manual, Bluebeam-style
on-drawing takeoff* — `takeoff.py` (pure geometry: polyline length, shoelace
area, volume, count, scale calibration) and `tab_takeoff.py` (a tkinter canvas
where a user calibrates scale once, then traces walls, slabs, and counts doors;
the result saves and pushes into an estimate). **This is the deterministic engine
AI feeds — AI does not replace it.** AI's job is to *produce the mark-ups
automatically* that a human today draws by hand, and to compute *what changed*
between revisions. The geometry, the scale conversion, and the quantities stay
exact and unit-tested in `takeoff.py`.

---

## 1. The problem & the thesis

**Manual takeoff is slow and inconsistent.** A quantity surveyor traces every
wall, counts every door, and measures every slab off each sheet by hand. On a
revision, they re-do it — or worse, eyeball the difference and miss a changed
opening that should have been a priced variation. This is hours of skilled,
error-prone, repetitive work, and revision drift is a direct source of
*unrecovered revenue* (the same leak the shipped variation register targets).

**Thesis:** AI is very good at exactly the two things that make takeoff painful —
**recognising repeated visual patterns** (a door symbol, a wall run) and
**comparing two images for differences**. So the design is:

> **AI detects and classifies the elements → the existing `takeoff` engine turns
> them into exact quantities → a human reconciles → on revision, AI marks the
> delta and the engine quantifies it → the delta reconciles into the variation
> register.**

Deterministic maths underneath, explainable AI on top, a human on anything that
becomes a quantity or a variation. Same discipline as every other AI feature in
this product.

---

## 2. Two kinds of drawing — and why it matters hugely

The *right* AI approach depends entirely on whether the drawing is **vector** or
**raster**. This is the single most important design fact.

| Drawing type | Examples | What's in the file | AI approach | Accuracy ceiling |
|---|---|---|---|---|
| **Vector** | DWG/DXF (CAD), vector PDF exported from CAD/Revit | Exact geometry, layers, line types, blocks/symbols, text | **Parse geometry directly** — extract lines, polylines, blocks, layer names, dimension text | Near-exact (it's real geometry, not a guess) |
| **Raster** | Scanned drawings, photos of prints, flattened image PDFs | Only pixels | **Computer vision / ML** — detect walls, symbols, and text from the image | Good but probabilistic; must be reconciled |

**Design consequence:** the pipeline has **two front-ends feeding one common
reconciliation-and-quantity back-end.** Whenever a vector source exists, use it —
it is dramatically more accurate and gives layers, symbols, and scale almost for
free. Fall back to CV/ML only for raster. Today the shipped tab already accepts
PNG and (via `pdf_render`) PDF; the vector path is new.

```
 Vector (DWG/DXF/vector-PDF) ─► geometry & layer parse ─┐
                                                        ├─► elements + confidence
 Raster (scan/photo/image-PDF) ─► CV/ML detection ──────┘        │
                                                                 ▼
                                    scale ─► takeoff.measure() ─► quantities
                                                                 │
                                                        human reconcile
                                                                 │
                                                   estimate/BOQ  ·  (on revision) variation
```

---

## 3. The pipeline, stage by stage

### Stage 1 — Ingest & normalise _(Extend of existing open-image/PDF)_

Accept DWG/DXF, vector PDF, image PDF, PNG/JPG, or a phone photo of a print.
Normalise to a working sheet: for vector, keep the geometry model + layers; for
raster, render/deskew to a clean image. The tab already opens PNG/PDF —
this adds vector parsing and photo cleanup.

### Stage 2 — Establish scale _(Extend of the built calibration)_

Quantities are meaningless without scale. Three routes, in order of preference:

1. **From vector geometry** — real coordinates are in the file; scale is exact.
2. **Auto-detect (raster)** — read the title-block scale ("1:100") or a dimension
   string (a "3000" against a wall) via OCR, and derive *real units per pixel*.
   Confirm with the user.
3. **Manual calibration (Built)** — the shipped path: draw a line over a known
   dimension, type the real length; `takeoff.scale_from` gives the factor.

AI accelerates 1–2; 3 is always available as the trustworthy fallback (offline,
no model).

### Stage 3 — "Plan identity": element detection & classification _(Proposed, the heart)_

This is what the user calls *plan identity* — AI reads the plan and identifies
what each thing **is**. Handled differently per source:

**Vector path (accurate):**
- **Walls** — lines/polylines on the wall layer (e.g. `A-WALL`), often
  double-line pairs; extract the centerline and thickness.
- **Doors & windows** — CAD **blocks/symbols** (a door is usually one named
  block with its swing arc; a window a block in a wall gap). Detect by block name
  and instance; count and locate each.
- **Rooms/areas** — closed boundaries or room-tag text for floor area.
- **Layers give discipline for free** — architectural vs structural vs MEP layer
  names classify elements without guessing.

**Raster path (probabilistic):**
- **Walls** — line/edge detection + a segmentation model trained on plan symbology
  to separate walls from dimension lines, grid lines, and hatching.
- **Doors/windows** — an **object-detection model** for the standard symbols
  (door = leaf + swing arc; window = the parallel-lines-in-wall glyph). Returns a
  bounding box + class + a **confidence** per instance.
- **Text/dimensions** — OCR for tags, room names, and dimension strings.

**Output of this stage (common to both):** a list of typed elements —
`{type: wall|door|window|column|slab|room|…, geometry: points, layer, confidence,
source_evidence}` — where `geometry` is the `(x,y)` point set the existing
`takeoff` engine already understands.

### Stage 4 — Quantify _(reuses the Built engine, unchanged)_

Each detected element becomes a takeoff mark-up and is measured by the shipped
pure functions — **no new maths, no new trust surface**:

| Element | Measurement kind | `takeoff` call | Yields |
|---|---|---|---|
| Wall run | `LENGTH` (× height for area/volume) | `length_quantity` / `volume_quantity` | running metres, plaster area, masonry volume |
| Door / window | `COUNT` (+ size from its schedule) | `count_quantity` | nos, and area if sized |
| Slab / room | `AREA` (× depth for volume) | `area_quantity` / `volume_quantity` | sqm, concrete cum |
| Column / beam | `LENGTH` × section | `volume_quantity` | concrete cum, steel |

`takeoff.totals_by_unit` foots them exactly as it does for manual mark-ups. The
quantities are as exact as they are today — because they *are* today's engine.

### Stage 5 — Human reconciliation _(draft-and-confirm, the safety gate)_

**AI proposes; the human disposes.** The detected elements are drawn as
mark-ups on the same canvas the user already knows, colour-coded by confidence:

- **Review queue** — low-confidence detections (a faint door symbol, an ambiguous
  wall) are flagged for the eye first; high-confidence ones pass quietly.
- **Every element editable** — accept, correct the class (that "window" is a
  louvre), adjust a vertex, delete a false positive, add a missed one by hand
  (the manual tools stay).
- **Snap to reality** — door/window sizes reconcile against the **door/window
  schedule** on the sheet; wall thickness against the section. AI matches;
  the human confirms.
- **Nothing saved silently** — the takeoff is written only when the human commits
  it, exactly like the shipped save. AI never books a quantity on its own.

The reconciled takeoff then pushes into an **estimate or BOQ** — the path that
already exists from the manual tab.

---

## 4. Revision analysis — the standout capability

> *"Since a drawing is already mapped, a revised drawing analysis should be done
> and the difference marked by AI and reconciled."*

This is where AI pays for itself. Once **Rev A** is mapped (Stage 1–5), a new
**Rev B** should not be re-taken-off from scratch — AI should compute **what
changed** and turn it into a **priced variation**.

### 4.1 The revision-delta pipeline _(Proposed)_

```
 Rev A (mapped takeoff, stored)      Rev B (new drawing)
          │                                 │
          └─────────► ALIGN / REGISTER ◄─────┘     (overlay the two sheets so
                              │                     the same grid line sits on
                              ▼                     the same grid line)
                    ELEMENT-LEVEL DIFF
                              │
        ┌─────────────┬───────┴────────┬──────────────┐
        ▼             ▼                ▼              ▼
     ADDED         REMOVED          MODIFIED       UNCHANGED
   (new elements) (deleted)     (moved/resized)   (ignore)
        │             │                │
        └─────────────┴────────────────┘
                      ▼
             QUANTIFY THE DELTA  (takeoff engine, per element)
                      ▼
             HUMAN RECONCILES the change list
                      ▼
        DRAFT VARIATION / CHANGE ORDER  ──►  variation register (Built)
```

**Step by step:**

1. **Align / register the sheets.** Overlay Rev B on Rev A using stable
   references (grid lines, title block, known dimensions) so a comparison is
   apples-to-apples even if the sheet shifted, rescaled, or was re-plotted.
2. **Element-level diff, not pixel diff.** A naïve image-subtraction lights up on
   every re-drawn line and is useless. The diff is done on the **detected
   elements**: match each Rev A element to its Rev B counterpart, then classify:
   - **Added** — a door/window/wall present in B, absent in A.
   - **Removed** — present in A, gone in B.
   - **Modified** — same element, changed geometry (a wall lengthened, an opening
     widened, a room resized).
   - **Unchanged** — matched with no material change (suppressed from the report).
3. **Mark it visually.** Render the delta on the sheet in the convention QSs
   expect — **green = added, red = removed, amber = modified** — a "clouded"
   revision view a human can scan in seconds.
4. **Quantify the delta.** Each change is measured by the `takeoff` engine, so the
   output is a **quantity difference**: *+3 doors, −12 m of wall, +8.4 sqm of
   slab, one window widened by 0.6 m*.
5. **Reconcile → variation.** The human reviews the change list (accept/dismiss
   each), then the accepted deltas draft a **variation/change order** in the
   shipped register (`variation.py`, Billing › Variations) — description, qty ×
   rate, status Raised → Approved → Billed, with the two revisions as the paper
   trail. **This closes the loop from "the drawing changed" to "we billed for
   it."**

### 4.2 Why element-diff, and why it matters commercially

Verbal "extra work" that is never priced is the biggest revenue leak in
contracting (per the SOP gap analysis). A revised drawing *is* a change order in
disguise — but the change is buried in a full sheet a human must eyeball against
the old one. AI that says *"Rev C moved 4 openings and added 18 m of wall vs
Rev B — here's the quantity delta, shall I raise a variation?"* converts a missed
claim into recovered revenue. This is the feature's core business case.

---

## 5. Reconciling "many layers" and many revisions

The user's *"reconcile many lay[ers]"* points at two real reconciliation axes:

### 5.1 Across drawing layers / disciplines

A drawing carries multiple **CAD layers** (architectural, structural, MEP, grid,
dimensions, hatching). Reconciliation here means:

- **Use layers to classify, not confuse.** Detect walls from the wall layer, not
  from grid or dimension lines — vector layers make this exact; raster CV must
  *learn* to separate them.
- **Cross-discipline consistency checks.** Does an architectural opening have a
  structural lintel? Does a room's area on the arch sheet match the finishes
  schedule? AI can flag mismatches between layers/sheets as a reconciliation
  report — a quality gate, not just a count.

### 5.2 Across a revision chain (Rev A → B → C → …)

Real projects have many revisions. Reconciliation means keeping the takeoff and
the *cumulative* variation position honest across the whole chain:

- **Each revision stores its mapped takeoff** (immutable snapshot), so any two
  revisions can be diffed, not just consecutive ones.
- **Cumulative vs incremental.** Show both the change *since the last revision*
  and the change *since the contract baseline* — so a re-added-then-removed
  opening nets out and never double-counts (the same anti-double-count discipline
  the variation register already applies to `VO-n` numbering).
- **An audit trail of drawing-driven quantity change** — who accepted which
  delta, against which revision, feeding which variation. This is the
  document-control gate the SOP report calls for, applied to drawings.

---

## 6. Data model additions _(Proposed — deterministic, testable)_

New tables, following the additive-migration convention in `db.py`. All geometry
stays as the `(x, y)` point lists the `takeoff` engine already consumes:

- **`drawings`** — sheet identity: project, discipline, sheet no., **revision**,
  source file, scale factor, unit, page.
- **`drawing_elements`** — one row per detected/traced element: drawing_id, type
  (wall/door/window/…), geometry (points JSON), layer, quantity, unit,
  **confidence**, **source** (`ai` | `manual`), reviewed_by, reviewed_at.
- **`drawing_revisions`** / **`element_changes`** — the delta between two
  drawings: from_rev, to_rev, element_ref, change (added/removed/modified),
  quantity_delta, and the variation it fed (nullable FK to the existing
  variations table).

This makes the takeoff, the review, and the revision delta all **queryable,
auditable, and reconcilable** — and links cleanly into the built variation
register.

---

## 7. Guardrails (non-negotiable, consistent with the whole product)

- **Deterministic geometry stays in `takeoff.py`.** AI outputs *points and
  classes*; the exact quantity is always the pure engine's. No quantity is ever
  an AI "estimate" — it is a measured value off AI-placed geometry the human
  approved.
- **Explainable.** Every detection carries a **confidence** and its **evidence**
  (the layer/block name for vector; the detection score + crop for raster) — the
  same `confidence`/`basis` discipline as `advisory.py`. A user can always ask
  "why did it call this a door?"
- **AI proposes, human disposes.** No takeoff and no variation is committed
  without human reconciliation. AI never raises a billable claim on its own.
- **Offline-first & the no-pip reality.** Vector parsing (DWG/DXF/PDF geometry)
  is largely deterministic and can be done with modest, isolated tooling. Raster
  CV/ML needs a model — treat it as an **opt-in capability** (local model where
  feasible, cloud opt-in per firm), never a dependency of the core, and never
  required for the manual takeoff that ships today. This is the §6.1 AI-runtime
  decision from the gap-and-roadmap doc, applied here.
- **Prefer vector, and say when you're guessing.** Where a vector source exists,
  use it and label the result high-confidence. On raster, the tool must visibly
  signal that quantities are AI-assisted and *must* be reconciled.

---

## 8. Accuracy realities & failure modes (be honest)

| Failure mode | Why | Mitigation |
|---|---|---|
| Missed / false doors on raster | Faint scans, non-standard symbols | Confidence flags → review queue; schedule cross-check; manual add |
| Wall confused with grid/dimension line | Similar line weights on raster | Layer parse (vector); trained segmentation (raster); human trims |
| Wrong scale → every quantity wrong | Mis-read title block / bad calibration | Confirm scale before quantifying; sanity-check a known dimension |
| Revision mis-alignment → phantom changes | Sheet shifted/rescaled between revs | Register on grid lines; element-diff not pixel-diff |
| Double-count across revisions | Re-added element counted twice | Cumulative-vs-baseline netting; immutable rev snapshots |
| Non-standard / hand-annotated sheets | Real sites mark up prints by hand | Always keep the manual tools; AI is an accelerator, not a gate |

The honest posture: **AI gets a QS most of the way, fast; the QS finishes and
owns the number.** The value is hours saved and revisions never missed — not an
unattended robot doing quantity surveying.

---

## 9. Phased delivery (fits the enterprise roadmap)

Slots under **E1 Capture** in
[`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md), sequenced
value-first:

| Step | Deliverable | Type | Depends on |
|---|---|---|---|
| **T1** | Vector parse (DWG/DXF/vector-PDF) → walls/doors/windows + auto-scale, into the existing takeoff | Core + AI | Built takeoff engine |
| **T2** | Draft-and-confirm reconciliation UI (confidence colours, review queue, edit) on the current canvas | AI/UX | T1 |
| **T3** | Raster CV/ML detection for scanned/photo sheets (opt-in model) | AI | T2, AI-runtime decision |
| **T4** | Revision-delta: align → element-diff → mark → quantify | Core + AI | T1–T2 |
| **T5** | Delta → variation register draft; revision chain snapshots | Core | T4, `variation.py` (Built) |
| **T6** | Cross-layer / cross-sheet reconciliation checks | Core + AI | T1, T4 |

**T1–T2 alone** (vector takeoff + reconcile) already replaces most manual tracing
for CAD-sourced drawings. **T4–T5** deliver the revision-to-variation loop — the
commercial headline.

---

## 10. Summary

Construction OS already has the hard, trustworthy half of drawing takeoff: a
**pure, exact, unit-tested quantity engine** (`takeoff.py`) and a canvas a QS
already uses. The AI opportunity is to **stop making the human trace every line**
and to **stop letting revisions leak revenue**:

1. **Read the drawing** — parse vector geometry where it exists, fall back to
   CV/ML on raster.
2. **Plan identity** — detect and classify walls, doors, windows, slabs, columns,
   with a confidence and its evidence.
3. **Quantify** — through the existing deterministic engine, so the numbers stay
   exact.
4. **Reconcile** — AI proposes mark-ups; the QS accepts, corrects, and commits;
   nothing is booked silently.
5. **Revision delta** — align the new revision, diff at the element level, mark
   added/removed/modified, quantify the change, and reconcile it into a **priced
   variation** — closing the loop from "the drawing changed" to "we billed for
   it."
6. **Reconcile across layers and revisions** — use CAD layers to classify
   correctly, net cumulative vs baseline changes so nothing double-counts, and
   keep an audit trail of drawing-driven quantity change.

The discipline is unchanged from the rest of the product: **deterministic
geometry underneath, explainable AI on top, a human on every quantity and every
variation, and the manual tools never taken away.** That is what makes this a
QS's power tool rather than an unaccountable black box.

---

_Reference/design document only — changes no code. Anchored on the shipped
`takeoff.py` / `tab_takeoff.py`. Read alongside
[`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) (AI strategy),
[`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md) (where this
sits in the plan), and [`REPORT-sop-gap-analysis.md`](REPORT-sop-gap-analysis.md)
(the variation/revenue-leak thesis this feature serves). Architecture:
[`../AGENTS.md`](../AGENTS.md)._
