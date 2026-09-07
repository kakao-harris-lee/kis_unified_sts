"""tos_runtime test-suite wiring — D1.4 hermetic fixture.

Design #40 (`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md`) §D1.4 redefines "hermetic" for the runtime shell's tests,
relative to the kernel's own rule ("no .env, no network, no Redis" —
`tos/tests/conftest.py`'s docstring): **zero external network, zero ambient
env, zero writes outside a temp directory**. ``127.0.0.1``/``::1`` sockets and
``tmp_path`` sqlite files are explicitly ALLOWED — that is this package's
whole reason to exist (D2's `SqliteCommitLog`, D3's evidence store, etc.).

This file installs ONE autouse guard: ``socket.socket.connect`` is
monkeypatched to refuse (raise) any address other than loopback, so a test
that accidentally reaches for the real network fails LOUD and immediately
instead of hanging or silently touching a live host — see
``test_placeholder.py`` for the fixture proving this.

No ``.env`` loading happens here (nothing in this file reads one), and, like
the kernel's own conftest, this file uses no ``os.environ``/``os.getenv`` —
consistent with the C2 "flag ban" firewall rule (TOS-FW-C), which stays in
force for runtime scope too (design #40 D1.1 config row: paths are injected
via CLI args only, never ambient env — this fixture module just doesn't need
any).
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

#: Addresses a runtime-shell test may legitimately connect to. Anything else
#: is refused before the real `connect()` syscall runs.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

#: The real, un-monkeypatched method — captured once at import time so the
#: guard below can still perform an actual loopback connect when permitted.
_real_connect = socket.socket.connect


def _guarded_connect(self: socket.socket, address: Any) -> Any:
    """Refuse any ``connect()`` target that is not loopback (D1.4).

    ``address`` is a 2-tuple ``(host, port)`` for AF_INET, a 4-tuple for
    AF_INET6 (``(host, port, flowinfo, scopeid)``), or occasionally a bare
    string (AF_UNIX) — only the first element (or the whole value, for a
    bare string) is inspected as the host.
    """
    host = address[0] if isinstance(address, (tuple, list)) else address
    if host not in _LOOPBACK_HOSTS:
        raise PermissionError(
            "tos_runtime hermetic test guard (design #40 D1.4): outbound "
            f"connect to {address!r} refused — tests may reach only "
            "127.0.0.1/::1/localhost, never a real external address."
        )
    return _real_connect(self, address)


@pytest.fixture(autouse=True)
def _hermetic_network_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: every test in this suite gets the outbound-connect guard."""
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
