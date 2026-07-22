#!/usr/bin/env python3
"""CLI readiness check for OCR/STT/VLM sidecars (stdlib).

Prints JSON: stub folder presence + live GET /health probe via
``sidecar_bridge.status``. Does not download weights.

Usage (from repo root)::

    python sidecars/health_check.py
"""

from __future__ import print_function

import json
import os
import sys


def _bootstrap():
    here = os.path.dirname(os.path.abspath(__file__))
    app = os.path.normpath(os.path.join(here, '..', 'construction_app'))
    if app not in sys.path:
        sys.path.insert(0, app)


def main():
    _bootstrap()
    import sidecar_bridge
    report = {
        'sidecars': sidecar_bridge.status(),
        'hint': (
            'Start a soft-fail stub with: '
            'python sidecars/stub_server.py --kind ocr'
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
