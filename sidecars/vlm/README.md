# VLM sidecar stub

Optional vision-language helper. Same draft-and-confirm contract as OCR/STT.

- **Contract:** `GET /health` → 200; `POST /extract` →
  `{ "fields": {...}, "confidence": {...} }`.
- **Default URL:** `http://127.0.0.1:8767` (loopback only).
- **App bridge:** `sidecar_bridge.py` / `/api/sidecar/*` — soft-fail → `capture`
  draft. Human confirm required before any write.
