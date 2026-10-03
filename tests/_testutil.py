"""Shared helpers for the Lexmap unittest suite (not a test module itself).

Importing this module
  * puts the repository root on sys.path so `import lexmap` works however the suite is started;
  * blocks outbound network connections, so no test can reach the LLM or the Census geocoder
    by accident (everything needed is cached/committed in the repo).
"""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class NetworkBlocked(RuntimeError):
    pass


def _blocked(*_a, **_k):
    raise NetworkBlocked("tests must not make network calls")


socket.socket.connect = _blocked          # type: ignore[assignment]
socket.socket.connect_ex = _blocked       # type: ignore[assignment]
socket.create_connection = _blocked       # type: ignore[assignment]


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))
