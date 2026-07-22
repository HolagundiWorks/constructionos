# OCR sidecar stub

Place offline OCR weights and a small HTTP service here on a Windows/dev machine.

- **Contract:** `GET /health` → 200; `POST /extract` JSON body →
  `{ "fields": {...}, "confidence": {...} }`.
- **Default URL:** `http://127.0.0.1:8765` (loopback only).
- **App bridge:** `construction_app/sidecar_bridge.py` +
  `GET /api/sidecar/status`, `POST /api/sidecar/extract` — soft-fails when this
  service is absent; stages a `capture` draft when present.
- Output feeds `POST /api/capture/draft` → human confirm. Nothing auto-writes.
