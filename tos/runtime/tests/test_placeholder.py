"""D1.4 placeholder test — proves the skeleton is importable and the"""

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
