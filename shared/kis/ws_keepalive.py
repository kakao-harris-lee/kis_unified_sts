"""KIS WebSocket app-level PINGPONG keepalive detection.

KIS real-time WS sends a periodic app-level keepalive frame and expects the
client to echo it back verbatim. If the client does not, KIS idle-closes the
socket on its keepalive timeout (observed ~105s); a feed that then reconnects
repeats this every cycle, producing handshake churn that re-triggers a KIS-side
IP/account block ("장 마감 이후 PINGPONG을 보내지 않으면 서버에서 차단").

The frame is identified by ``header.tr_id == "PINGPONG"`` (KIS reference
``kis_auth.py`` reads ``rdic["header"]["tr_id"]``). An earlier version of this
codebase checked ``header.tr_cd``, a field KIS never sends, so the echo never
fired — the root cause of the periodic-drop incident. This helper checks
``tr_id`` (the real field) AND ``tr_cd`` (defensive: a silent regression to the
old field can't disable the echo again), so it is robust in both directions.

Pure and side-effect-free for trivial unit testing; the feeds own the echo send.
"""

from __future__ import annotations

from typing import Any

PINGPONG = "PINGPONG"


def is_pingpong(header: dict[str, Any] | None) -> bool:
    """True if a WS message header is a KIS PINGPONG keepalive frame.

    Checks ``tr_id`` (the authoritative KIS field) and ``tr_cd`` (back-compat /
    regression guard). Tolerant of a missing/None header.
    """
    if not header:
        return False
    return header.get("tr_id") == PINGPONG or header.get("tr_cd") == PINGPONG
