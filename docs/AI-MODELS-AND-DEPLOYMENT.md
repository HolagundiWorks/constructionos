# Construction OS — Open-Source AI Models & Server/LAN Deployment

**Which open models do the work, and how the desktop-as-server + browser-on-LAN
topology runs them**

_Document type: Reference / Solution design (documentation only — no code changes)_
_Version: 1.0 · Last updated: 2026-07-21 · Prepared by: Human Centric Works_
_Companion to [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md),
[`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md), and
[`AI-DRAWING-TAKEOFF.md`](AI-DRAWING-TAKEOFF.md)._

---

## 0. Short answers first

**Q1 — "Which AI model can do this? I need open source."**
There is no single model. Different jobs need different open models, all runnable
locally. The recommended open-source stack:

| Job | Recommended open model(s) | License* |
|---|---|---|
| Read a document/drawing & describe/extract (vision-language) | **Qwen2.5-VL** (7B), or Llama 3.2-Vision (11B), MiniCPM-V, moondream (tiny) | Apache-2.0 / open-weights** |
| Detect door/window/symbol on raster plans (object detection) | **YOLO (Ultralytics v8/v11)** or RT-DETR | AGPL-3.0*** / Apache-2.0 |
| Trace walls / segment regions on raster | **SAM 2** (Segment Anything) or a trained segmentation net | Apache-2.0 |
| OCR dimensions / title blocks / challans / muster | **PaddleOCR** or Tesseract / docTR | Apache-2.0 |
| Parse **vector** drawings (DWG/DXF/vector-PDF) | *Not a model* — deterministic libs (e.g. ezdxf) | MIT/permissive |
| NL→SQL "ask your data", KPI narration, summarising | **Qwen2.5-Coder** (1.5B–7B) / Llama 3.1-8B / Mistral-7B | Apache-2.0 / open-weights |
| Voice → text (field capture) | **Whisper / faster-whisper**, or Vosk (tiny, offline) | MIT / Apache-2.0 |
| Embeddings (retrieval) | **nomic-embed-text** (already in the catalog) | Apache-2.0 |

_*Licenses move fast — verify the exact tag/size at integration time (see §7)._
_**Some VLM sizes ship under model-specific terms; check per size._
_***Ultralytics YOLO is AGPL-3.0 — which happens to **match Construction OS's own
AGPL-3.0 license**, so it's compatible, but the AGPL obligations apply (§7)._

**Q2 — "Desktop app acts as a server; other systems on the LAN use a browser."**
**This already exists in the product.** `python web_main.py` (or Tools › Web/LAN
access) turns the machine holding the data into a server on stdlib `http.server`;
any PC/phone/tablet on the network opens `http://<host>:<port>/`, signs in
(same accounts/roles/audit as the desktop), and uses the app — no client to
install (see [`LAN.md`](LAN.md), `webserver.py`, `webapp.py`, `web_main.py`).
**AI slots into that same topology: the model runs once, on the server machine;
browser clients stay thin.** §4 details this.

The rest of this document explains the *how* and the *why* behind those answers.

---

## 1. The one architectural idea that makes this work: the sidecar

Construction OS's core is **pure Python standard library — no pip, offline,
single file.** Heavy AI (LLMs, vision models, OCR) cannot live inside that core;
it needs ML runtimes (llama.cpp, PyTorch/ONNX) that are anything but stdlib.

The product already solved this, and the solution generalises to every model in
this document:

> **Run the model as a separate local "sidecar" service, and let the pure-stdlib
> app talk to it over localhost HTTP (`urllib`).**

That is exactly how the shipped AI assistant works: a local **Ollama** server runs
the model; the app sends it prompts over `http://localhost:11434` with stdlib
`urllib` — **no pip dependency crosses into the core** (`assistant.py`,
`ollama_client.py`). The Windows installer even bundles a model (`qwen2.5-coder:
1.5b`, ~1 GB, Apache-2.0) and registers it offline on first run
(`model_provision.py`), so the assistant answers on a machine that never touched
the internet.

**Every model in Q1 follows this pattern:**

- **Text + vision-language** → **Ollama** (it already serves VLMs like
  `qwen2.5-vl`, `llama3.2-vision`, `moondream`, `llava`). Often no second service
  is needed at all — the existing Ollama sidecar covers text *and* vision.
- **Detection / segmentation / OCR / speech** → a small **inference sidecar** (an
  ONNX Runtime or llama.cpp-style local service) bundled the same way, exposing a
  localhost HTTP endpoint. Isolated from the core, opt-in, bundled in the
  installer — the same discipline as the bundled Ollama model.

The core stays pure; the AI stays optional and swappable; nothing violates the
no-pip rule *inside the app*.

---

## 2. Model recommendations, by job (detail)

### 2.1 Reading drawings (see [`AI-DRAWING-TAKEOFF.md`](AI-DRAWING-TAKEOFF.md))

Choose by **vector vs raster** — the single biggest factor:

- **Vector (DWG/DXF/vector-PDF): no AI model needed.** The geometry, layers, and
  symbols are *in the file*. Parse deterministically (e.g. **ezdxf** for DXF,
  a PDF vector parser for exported PDFs). Near-exact, and the most reliable path
  by far. Prefer this whenever a vector source exists.
- **Raster (scans/photos/image-PDFs): a small vision stack.**
  - **Object detection** for door/window/symbol counting: **YOLO (Ultralytics
    v8/v11)** fine-tuned on plan symbology, or **RT-DETR**. Fast, mature, runs on
    CPU (better on a GPU).
  - **Segmentation** for walls/regions: **SAM 2** (Segment Anything 2), or a
    purpose-trained segmentation model.
  - **OCR** for dimensions and title-block scale: **PaddleOCR** or **Tesseract**.
  - Optional **VLM** (Qwen2.5-VL) as a generalist to describe a sheet or read a
    non-standard annotation the detectors miss.

The detectors output *points + class + confidence*; the shipped, exact
`takeoff.py` engine turns those into quantities. **AI places geometry; the
deterministic engine measures it.**

### 2.2 Document & photo capture (GRN, invoices, muster — E1)

- **OCR:** PaddleOCR / Tesseract for printed challans and invoices; docTR for
  layout-aware extraction.
- **VLM:** Qwen2.5-VL or Llama 3.2-Vision to read a challan/invoice photo and
  return structured fields (vendor, items, qty, amount) as a *draft* to confirm.
- **Voice:** Whisper / faster-whisper (accurate, multilingual incl. Hindi) or
  Vosk (tiny, fully offline) for spoken DPR/measurement notes.

### 2.3 Text jobs — NL→SQL, KPI narration, risk summaries (Built + Extend)

- **Small / modest PC:** `qwen2.5-coder:1.5b` (the inbuilt default) → `llama3.2:3b`
  / `phi3:mini`.
- **Office server / more RAM:** `llama3.1:8b`, `qwen2.5-coder:7b`, `mistral:7b`.
- These are exactly the tags the app's model catalog already offers
  (`ollama_catalog.py`), so text features need **no new runtime** — only prompt
  and schema work.

### 2.4 Reasoning about numbers — keep it deterministic

KPIs, EVM, quantities, tax, and risk *scores* are computed by the pure modules
(`analytics.py`, `finance.py`, `takeoff.py`, proposed `earnedvalue.py`/`risk.py`),
**not by the model.** The LLM narrates and explains those numbers; it never
invents them. This is the product's standing rule and it keeps every figure
auditable regardless of which model is installed.

---

## 3. Recommended default stacks (by hardware tier)

The target user runs a modest Windows PC; an enterprise office may put a stronger
machine on as the server. Match the model to the muscle:

| Tier | Typical machine | Text | Vision / capture | Notes |
|---|---|---|---|---|
| **Floor (offline default)** | 4–8 GB RAM, no GPU, T2/T3 office PC | `qwen2.5-coder:1.5b` (bundled) | OCR (Tesseract) + tiny VLM (moondream) / Vosk voice | Everything the app ships today, plus light capture. Deterministic quick-answers work with **no** model at all. |
| **Standard server** | 16 GB RAM, modern CPU (optional small GPU) | `llama3.1:8b` / `qwen2.5-coder:7b` | Qwen2.5-VL 7B + YOLO + PaddleOCR + faster-whisper | The recommended office-server tier — one machine serves the whole LAN. |
| **Power server** | 32 GB+ RAM, dedicated GPU (8–24 GB VRAM) | 14B–32B models | SAM 2 + fine-tuned YOLO + Qwen2.5-VL, real-time | Fast raster takeoff, batch revision diffs, heavier VLMs. |

**Key point:** because of the server topology (§4), you size **one** machine — the
server — not every desk. A single mid-range server with a GPU gives the whole
office AI features through the browser.

---

## 4. The server + LAN topology (already built) and where AI runs

The user's requirement — *"desktop app acts as server, other systems on LAN
access via browser"* — is the shipped architecture. Here is how AI fits it.

```
        SERVER MACHINE  (holds the data + runs the models)
        ┌──────────────────────────────────────────────────────┐
        │  Construction OS core  (pure stdlib)                  │
        │     • desktop app  (main.py)                          │
        │     • web/LAN server (web_main.py, http.server) ──────┼──┐
        │  SQLite file  (construction.db, WAL, many readers)    │  │
        │                                                       │  │
        │  AI sidecars (localhost only):                        │  │
        │     • Ollama  (text + vision-language)                │  │
        │     • inference svc (YOLO/SAM/OCR/Whisper, ONNX)      │  │
        │  app ⇄ sidecars over http://localhost  (urllib)       │  │
        └──────────────────────────────────────────────────────┘  │
                                                                   │  LAN
        ┌───────────────┬───────────────┬───────────────┐         │  (http)
        │  Office PC    │  Site tablet  │  Phone         │ ◄───────┘
        │  browser only │  browser only │  browser only  │
        └───────────────┴───────────────┴───────────────┘
             thin clients — no model, no install
```

**How it works:**

- **One machine is the server** — the always-on office PC that holds
  `construction.db`. It runs the stdlib web server (`web_main.py`, binds
  `0.0.0.0:8080`) **and** the AI sidecars.
- **The models live only on the server.** The Ollama / inference sidecars listen
  on **localhost** of the server. The app talks to them in-process over
  `urllib`; they are **never exposed to the LAN** directly.
- **Browser clients are thin.** A colleague opens `http://<server-ip>:8080/`,
  signs in (PBKDF2 accounts, Admin/Operator/Viewer roles, CSRF, audit — all
  built), and gets AI features *rendered by the server*. Their device needs no
  model, no GPU, no install — a phone works.
- **AI requests flow server-side.** When a browser user asks the assistant a
  question or uploads a drawing/photo, the request hits the stdlib web server,
  which calls the local sidecar, runs the deterministic engine on the result, and
  returns HTML. The heavy compute stays on the one capable machine.

This is the **ideal topology for local AI**: centralise the model where the data
and the compute are; keep clients as browsers. It also keeps the privacy story
clean — data and models never leave the office network.

**Security note (already documented in [`LAN.md`](LAN.md)):** the web server
speaks **plain HTTP for a trusted LAN**; don't port-forward it to the internet.
For wider access put it behind an HTTPS reverse proxy (nginx/Caddy) or a VPN. The
AI sidecars must stay **localhost-bound on the server** — never bind them to
`0.0.0.0`, or the model API becomes reachable from the LAN unauthenticated.

---

## 5. Deployment & packaging

Extend the mechanism that already ships the bundled model:

- **Bundle the sidecar + model in the installer** — the Windows installer already
  lays down a GGUF and registers it offline (`model_provision.py`,
  `installer/`). The same approach bundles Ollama (or a chosen runtime) and the
  vision/OCR sidecar, so the office server is AI-ready out of the box, offline.
- **Keep it opt-in and modular** — AI is a *module* (the app already has a
  section-toggle model, `modules.py`). A firm that doesn't want AI, or runs on a
  machine too small for it, turns it off and loses nothing of the core.
- **Managed in-app** — the shipped **Assistant › AI Engine** panel (`tab_ollama.py`)
  already manages models (install/switch/fetch). Extend it to cover the vision
  sidecar's model files the same way.
- **Model files are large** — vision models and 7B+ LLMs are gigabytes. Ship them
  to the *server* only; clients never download anything.

---

## 6. Hardware guidance (practical)

- **CPU-only is viable** for the floor tier (small LLM, Tesseract OCR, Vosk voice)
  — slower, but offline and free. This protects the T2/T3 thesis.
- **A GPU transforms raster takeoff and VLMs.** Detection/segmentation and 7B+
  VLMs are much faster on even a modest GPU (8–12 GB VRAM). For a firm doing
  drawing takeoff seriously, one GPU server is the highest-leverage spend.
- **RAM is the LLM gate:** ~2 GB for the 1.5B default, ~8 GB for 7–8B, ~16 GB+ for
  14–32B (the catalog states per-model RAM in `ollama_catalog.py`).
- **Vector-first saves hardware:** parsing CAD/vector PDFs is cheap and exact and
  needs *no* GPU — another reason to prefer vector sources for takeoff.

---

## 7. "Open source" — the licensing you must actually check

The app is **AGPL-3.0** and is *distributed* (including over a network), so model
licenses matter. Three categories, don't conflate them:

- **OSI-open (safest): Apache-2.0 / MIT / BSD.** Qwen2.5 (most sizes), Mistral-7B,
  Phi-3, SAM 2, PaddleOCR, Tesseract, Whisper, Vosk, nomic-embed, ezdxf. Free to
  use, modify, redistribute — the preferred default. The bundled
  `qwen2.5-coder:1.5b` is Apache-2.0 precisely so the installer can ship it.
- **Open-weights with model-specific terms (read them): Llama, Gemma, some Qwen
  sizes.** E.g. Llama's community license has a large-user clause; Gemma has its
  own terms; **Qwen 3B/72B ship under the more restrictive Qwen license** — the
  codebase already notes this and deliberately avoids the 3B for bundling
  (`model_provision.py`). Usable, but check redistribution terms before shipping.
- **Copyleft: AGPL-3.0 — Ultralytics YOLO.** This *matches Construction OS's own
  license*, so it's compatible, but AGPL is contagious: if you use YOLO you must
  keep the combined work AGPL and offer source (which this project already does).
  If that's ever unwanted, use an Apache-2.0 detector (RT-DETR) instead.

**Standing caveat:** the open-model landscape moves monthly, and this document's
cutoff is early 2026. Treat the names here as a *well-supported baseline*, not a
frozen decision — **verify the exact model, size, tag, and license at the moment
of integration**, and prefer whatever current Apache/MIT model benchmarks best
for the job. The *architecture* (sidecar + server topology + deterministic core)
is stable; the specific model is a swappable choice.

---

## 8. Honest expectations

- **No model gives unattended accuracy** on real, messy site drawings and photos.
  The design keeps a human reconciling every quantity and every extracted record
  (draft-and-confirm) — the models save hours, they don't remove the QS.
- **Vector beats raster by a wide margin.** Push users toward CAD/vector exports;
  reserve CV/ML for when only a scan exists, and flag those results as
  AI-assisted.
- **Smaller models trade accuracy for reach.** The floor tier runs anywhere but
  answers more simply; the value ladder is real, and the server topology lets a
  firm buy accuracy in *one* place.

---

## 9. Summary

- **Which open models?** A stack, not one model: **Qwen2.5-VL / Llama-3.2-Vision**
  (read documents & drawings), **YOLO/RT-DETR + SAM 2 + PaddleOCR** (raster plan
  detection), **deterministic parsers** for vector CAD (no model), **Qwen2.5-Coder
  / Llama-3.1-8B / Mistral-7B** (NL→SQL, narration), **Whisper/Vosk** (voice) — all
  open, all local. Prefer Apache/MIT licenses; note YOLO's AGPL matches the app.
- **How do they run without breaking the no-pip core?** As **localhost sidecars**
  (Ollama for text+vision, a small inference service for detection/OCR/speech) the
  stdlib app calls over `urllib` — exactly the shipped Ollama pattern, bundled the
  same way in the installer.
- **Desktop-as-server + browser-on-LAN?** Already built (`web_main.py`,
  `webserver.py`, `webapp.py`, [`LAN.md`](LAN.md)). AI slots straight in: **the
  server machine runs the models; browser clients stay thin.** One capable
  machine gives the whole office AI over the LAN, with the data and the models
  never leaving the building.

The through-line, as everywhere in this product: **deterministic engines compute
the numbers, open models assist and explain, one server does the heavy lifting,
and thin browser clients reach it over the LAN.**

---

_Reference/design document only — changes no code. Grounded in the shipped
`webserver.py` / `web_main.py` / `webapp.py` (LAN server), `assistant.py` /
`ollama_client.py` / `model_provision.py` / `ollama_catalog.py` (local-model
sidecar), and [`LAN.md`](LAN.md). Model names/licenses are a baseline to verify
at integration time (§7). Architecture and conventions: [`../AGENTS.md`](../AGENTS.md)._
