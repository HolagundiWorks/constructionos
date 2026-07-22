# Model sidecars (E1 / local L8)

OCR / speech-to-text / VLM weights are **not** checked into this repository.
They run as optional local processes that feed the deterministic
[`capture.py`](../construction_app/capture.py) draft-and-confirm scaffold.

## Contract

1. Sidecar extracts `{field: value}` (+ optional confidence map).
2. Caller stages via `capture.build_draft` or `POST /api/capture/draft`.
3. Human reviews low-confidence fields and confirms.
4. Only then write (`POST /api/capture/confirm` or desktop save).

Nothing from a model is written without human confirmation.

## Soft-fail stub (no weights)

Exercise the bridge and WinUI Capture page without downloading models:

```bash
python sidecars/stub_server.py --kind ocr   # http://127.0.0.1:8765
python sidecars/stub_server.py --kind stt   # :8766
python sidecars/stub_server.py --kind vlm   # :8767
python sidecars/health_check.py             # stub + live probe JSON
```

`GET /health` and `POST /extract` (empty fields) are enough for
`sidecar_bridge` to report `available=true` and stage an empty draft.

## Local layout (Windows)

```
sidecars/
  stub_server.py   # stdlib soft-fail HTTP floor (loopback only)
  health_check.py  # CLI status via sidecar_bridge
  ocr/             # replace stub with real OCR service + weights
  stt/             # whisper.cpp or similar
  vlm/             # optional vision-language helper
```

See [`docs/AI-MODELS-AND-DEPLOYMENT.md`](../docs/AI-MODELS-AND-DEPLOYMENT.md).
Cloud agents must not download multi-GB weights here.
