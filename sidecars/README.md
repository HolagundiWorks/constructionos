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

## Local layout (Windows)

```
sidecars/
  ocr/     # e.g. PaddleOCR / Tesseract wrapper — install weights locally
  stt/     # whisper.cpp or similar — install weights locally
  vlm/     # optional vision-language helper
```

See [`docs/AI-MODELS-AND-DEPLOYMENT.md`](../docs/AI-MODELS-AND-DEPLOYMENT.md).
Cloud agents must not download multi-GB weights here.
