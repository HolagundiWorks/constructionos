# STT sidecar stub

Place offline speech-to-text weights and a small HTTP service here on a
Windows/dev machine.

- **Contract:** `GET /health` → 200; `POST /extract` →
  `{ "fields": {...}, "confidence": {...} }`.
- **Default URL:** `http://127.0.0.1:8766` (loopback only).
- **App bridge:** `sidecar_bridge.py` / `/api/sidecar/*` — soft-fail → `capture`
  draft. Human confirm required before any write.
