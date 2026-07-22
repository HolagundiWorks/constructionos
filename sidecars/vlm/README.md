# VLM sidecar stub

Optional vision-language helper. Install weights locally only.

- **Contract:** `GET /health` → 200; `POST /extract` →
  `{ "fields": {...}, "confidence": {...} }`.
- **Default URL:** `http://127.0.0.1:8767` (loopback only).
- **Soft-fail floor:** `python sidecars/stub_server.py --kind vlm`.
- **Bridge:** `sidecar_bridge` + `/api/sidecar/*`. Nothing auto-writes.
