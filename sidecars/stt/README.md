# STT sidecar stub

Place offline speech-to-text weights and a small HTTP service here locally.

- **Contract:** `GET /health` → 200; `POST /extract` →
  `{ "fields": {...}, "confidence": {...} }`.
- **Default URL:** `http://127.0.0.1:8766` (loopback only).
- **Soft-fail floor:** `python sidecars/stub_server.py --kind stt`.
- **Bridge:** `sidecar_bridge` + `/api/sidecar/*`. Nothing auto-writes.
