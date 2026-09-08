"""tos_runtime test-suite wiring — D1.4 hermetic fixtures.

Design #40 (`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md`) §D1.4 redefines "hermetic" for the runtime shell's tests,
relative to the kernel's own rule ("no .env, no network, no Redis" —
`tos/tests/conftest.py`'s docstring): **zero external network, zero ambient
env, zero writes outside a temp directory**. ``127.0.0.1``/``::1`` sockets and
``tmp_path`` sqlite files are explicitly ALLOWED — that is this package's
whole reason to exist (D2's `SqliteCommitLog`, D3's evidence store, etc.).

This file installs TWO autouse guards:

  ``_hermetic_network_guard``  every ``socket.socket`` method that can send a
                               packet to an address — ``connect``,
                               ``connect_ex``, ``sendto``, ``sendmsg`` — is
                               monkeypatched to refuse (raise) any target
                               other than loopback, so a test that
                               accidentally reaches for the real network
                               fails LOUD and immediately instead of hanging
                               or silently touching a live host.
  ``_hermetic_write_guard``    ``builtins.open``, ``pathlib.Path.open``,
                               ``pathlib.Path.write_text`` and
                               ``pathlib.Path.write_bytes`` are monkeypatched
                               to refuse any WRITE-mode target whose resolved
                               path lies outside the test's own ``tmp_path``
                               — read modes are never restricted.

Independent review (2026-09-08, MEDIUM) reproduced two gaps in the original
cut of this file, both closed here: (1) only ``connect`` was guarded —
``connect_ex`` (same address-based call, returns an errno instead of
raising) and the connectionless send calls ``sendto``/``sendmsg`` (UDP; no
prior ``connect()`` needed, so the ``connect`` guard never runs before they
fire) both reached the real syscall against a non-loopback target; (2) the
"zero writes outside a temp directory" half of D1.4's own definition had no
enforcing fixture at all. Also (LOW, same review): ``localhost`` was in the
allowed-host set even though D1.4 names only ``127.0.0.1``/``::1`` — an
adversarial ``/etc/hosts`` entry can make ``localhost`` resolve to a
non-loopback address, so it is removed; use the literal loopback addresses.

No ``.env`` loading happens here (nothing in this file reads one), and, like
the kernel's own conftest, this file uses no ``os.environ``/``os.getenv`` —
consistent with the C2 "flag ban" firewall rule (TOS-FW-C), which stays in
force for runtime scope too (design #40 D1.1 config row: paths are injected
via CLI args only, never ambient env — this fixture module just doesn't need
any).
"""

from __future__ import annotations

import builtins
import os
import pathlib
import socket
from pathlib import Path
from typing import Any

import pytest

# ============================================================================
# Network guard — D1.4 "zero external network"
# ============================================================================

#: Addresses a runtime-shell test may legitimately reach. LITERAL loopback
#: addresses only (LOW, 2026-09-08 review) — ``localhost`` is deliberately
#: excluded: an adversarial ``/etc/hosts`` entry can repoint it away from
#: loopback, which would silently defeat this guard.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})

#: The real, un-monkeypatched methods — captured once at import time so the
#: guards below can still perform an actual loopback call when permitted.
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_sendto = socket.socket.sendto
_real_sendmsg = getattr(socket.socket, "sendmsg", None)  # not on every platform


def _address_host(address: Any) -> Any:
    """Extract the host part of a socket address for the loopback check.

    ``address`` is a 2-tuple ``(host, port)`` for AF_INET, a 4-tuple for
    AF_INET6 (``(host, port, flowinfo, scopeid)``), or occasionally a bare
    string (AF_UNIX) — only the first element (or the whole value, for a
    bare string) is inspected as the host. ``None`` (a connected-socket
    ``sendmsg``/``sendto`` with no explicit address) means "use the socket's
    already-established peer", which the ``connect``/``connect_ex`` guard
    already vetted — nothing further to check here.
    """
    if address is None:
        return None
    return address[0] if isinstance(address, (tuple, list)) else address


def _enforce_loopback(address: Any) -> None:
    host = _address_host(address)
    if host is None:
        return
    if host not in _LOOPBACK_HOSTS:
        raise PermissionError(
            "tos_runtime hermetic test guard (design #40 D1.4): outbound "
            f"network call to {address!r} refused — tests may reach only "
            "127.0.0.1/::1, never a real external address (not even "
            "'localhost' — see this file's module docstring)."
        )


def _guarded_connect(self: socket.socket, address: Any) -> Any:
    """Refuse any ``connect()`` target that is not loopback (D1.4)."""
    _enforce_loopback(address)
    return _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> Any:
    """Refuse any ``connect_ex()`` target that is not loopback (D1.4).

    Real ``connect_ex`` returns an errno instead of raising on failure, but
    this guard raises regardless — a test that hits this path is reaching
    for the network by mistake, and a raised exception is far louder (and
    fails faster) than a returned errno a test might not even check.
    """
    _enforce_loopback(address)
    return _real_connect_ex(self, address)


def _guarded_sendto(self: socket.socket, *args: Any) -> Any:
    """Refuse any ``sendto()`` target that is not loopback (D1.4).

    ``sendto`` is UDP's connectionless send — it never calls ``connect()``
    first, so the connect guard above never runs before it. Signature is
    ``sendto(data, address)`` or ``sendto(data, flags, address)``; the
    address is always the LAST positional argument either way.
    """
    if args:
        _enforce_loopback(args[-1])
    return _real_sendto(self, *args)


def _guarded_sendmsg(self: socket.socket, *args: Any, **kwargs: Any) -> Any:
    """Refuse any ``sendmsg()`` target that is not loopback (D1.4).

    Signature is ``sendmsg(buffers, ancdata=[], flags=0, address=None)``;
    ``address`` is optional (an already-``connect()``-ed socket needs none)
    and may arrive positionally (4th arg) or by keyword.
    """
    address = kwargs.get("address")
    if address is None and len(args) >= 4:
        address = args[3]
    _enforce_loopback(address)
    return _real_sendmsg(self, *args, **kwargs)


@pytest.fixture(autouse=True)
def _hermetic_network_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: every test in this suite gets the outbound-network guard."""
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", _guarded_sendto)
    if _real_sendmsg is not None:
        monkeypatch.setattr(socket.socket, "sendmsg", _guarded_sendmsg)


# ============================================================================
# Write guard — D1.4 "zero writes outside a temp directory"
# ============================================================================

#: Mode characters that mean "this call can create or modify bytes on disk".
#: A mode with none of these (e.g. plain ``"r"``/``"rb"``) is read-only and
#: is never restricted.
_WRITE_MODE_CHARS = frozenset("wax+")

_real_builtins_open = builtins.open
_real_path_open = pathlib.Path.open
_real_path_write_text = pathlib.Path.write_text
_real_path_write_bytes = pathlib.Path.write_bytes


def _is_write_mode(mode: Any) -> bool:
    if not isinstance(mode, str):
        return False  # non-string "mode" (e.g. an int fd's mode) — not ours
    return any(ch in _WRITE_MODE_CHARS for ch in mode)


def _resolve_target(file: Any) -> Path | None:
    """Resolve a ``builtins.open``-style ``file`` argument to an absolute
    ``Path``, or ``None`` when it is a file descriptor (``int``) — nothing to
    check against ``tmp_path`` for an already-open fd."""
    if isinstance(file, int):
        return None
    return Path(os.fsdecode(file)).resolve()


def _enforce_within_root(path: Path | None, allowed_root: Path) -> None:
    if path is None:
        return
    if path == allowed_root or allowed_root in path.parents:
        return
    raise PermissionError(
        "tos_runtime hermetic test guard (design #40 D1.4): write to "
        f"{path} refused — tests may write only inside their own tmp_path "
        f"({allowed_root}), never anywhere else on disk."
    )


@pytest.fixture(autouse=True)
def _hermetic_write_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: refuse any WRITE-mode open/write whose resolved target lies
    outside this test's own ``tmp_path`` (D1.4). Read modes are unrestricted.

    Patches BOTH ``builtins.open`` and ``pathlib.Path.open``/``write_text``/
    ``write_bytes`` — CPython's ``pathlib.Path.open`` calls ``io.open``
    directly (the same underlying function ``builtins.open`` names, but a
    SEPARATE reference; monkeypatching the ``builtins`` module attribute does
    not repoint that internal reference), so ``builtins.open`` alone would
    leave every ``Path.open()``/``write_text()``/``write_bytes()`` call
    unguarded. ``write_text``/``write_bytes`` are patched explicitly too
    (rather than relying on their internal ``self.open(...)`` call reaching
    the patched ``Path.open``) so the guard does not depend on that
    implementation detail holding across Python versions.
    """
    allowed_root = tmp_path.resolve()

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if _is_write_mode(mode):
            _enforce_within_root(_resolve_target(file), allowed_root)
        return _real_builtins_open(file, mode, *args, **kwargs)

    def guarded_path_open(
        self: Path, mode: str = "r", *args: Any, **kwargs: Any
    ) -> Any:
        if _is_write_mode(mode):
            _enforce_within_root(self.resolve(), allowed_root)
        return _real_path_open(self, mode, *args, **kwargs)

    def guarded_write_text(self: Path, data: str, *args: Any, **kwargs: Any) -> Any:
        _enforce_within_root(self.resolve(), allowed_root)
        return _real_path_write_text(self, data, *args, **kwargs)

    def guarded_write_bytes(self: Path, data: bytes) -> Any:
        _enforce_within_root(self.resolve(), allowed_root)
        return _real_path_write_bytes(self, data)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(pathlib.Path, "open", guarded_path_open)
    monkeypatch.setattr(pathlib.Path, "write_text", guarded_write_text)
    monkeypatch.setattr(pathlib.Path, "write_bytes", guarded_write_bytes)
