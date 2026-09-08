"""D1.4 placeholder test — proves the skeleton is importable and the
hermetic network guard (``conftest.py``'s autouse ``_hermetic_network_guard``
fixture) actually blocks an outbound connect BEFORE any real ``connect()``
syscall runs.

The target address, ``203.0.113.1`` (TEST-NET-3, RFC 5737), is reserved for
documentation and is guaranteed non-routable — chosen so that even if the
guard had a bug and let the real ``connect()`` through, the test would fail
fast (connection refused / unreachable) rather than hang for a TCP timeout.
The actual assertion, though, is that ``PermissionError`` is raised — which
only happens if the guard's own check runs and rejects the address before
delegating to the real ``socket.socket.connect``, proving the fixture is
wired in ahead of any real network attempt.
"""

from __future__ import annotations

import socket

import pytest
import tos_runtime


def test_tos_runtime_package_imports() -> None:
    """The runtime shell package is importable and carries a version."""
    assert tos_runtime.__version__ == "0.0.1"


def test_hermetic_guard_blocks_outbound_connect() -> None:
    """A non-loopback connect is refused by the D1.4 fixture, not attempted."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.connect(("203.0.113.1", 80))
    finally:
        s.close()
