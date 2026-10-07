"""The two D1.4 autouse guards, installed for THIS suite.

**Why this file exists at all.** The suite called itself "hermetic" and loaded
**zero** conftests: pytest collects conftests from the test file's directory up
to the rootdir, and ``tos/runtime/tests/conftest.py`` is a *sibling* of this
directory, never an ancestor — so neither D1.4 guard was ever installed here
(2026-10-08 review). The suite happened to be hermetic; nothing enforced it,
and "happened to be" is what the next test silently breaks.

**Why it is duplicated rather than shared.** Both sharing routes are closed, and
each is closed by a rule this change is not allowed to bend:

* **importing it** — ``from tos_runtime.tests.conftest import …`` does not exist
  as a package path, and the only other way is a path-based load
  (``importlib.util.spec_from_file_location``), i.e. dynamic import, which the
  firewall forbids outright in both scopes (TOS-FW-D).
* **moving the guards into ``tos_runtime``** so both suites import them — that
  adds a file under ``tos/runtime/src/tos_runtime/``, one of the two package
  roots the paper release pin's ``expected_code_digest`` folds, which would
  change the digest and ABORT the resident paper session every morning. The
  whole reason this package sits outside that root is to avoid exactly that.

So: duplication, stated here rather than discovered later. The guards below are
a faithful, stdlib-only re-statement of design #40 §D1.4 — zero external
network, zero writes outside the test's own ``tmp_path`` — and they are
deliberately NOT a copy-by-reference: if ``tos/runtime/tests/conftest.py``
tightens, this file does not follow automatically. That drift is the accepted
cost of the two closed routes, and the mitigation is that these guards cover a
suite which opens no socket and writes only into ``tmp_path`` by construction,
so they are a *canary over a narrow surface*, not load-bearing isolation for a
broad one.

``localhost`` is deliberately absent from the allowed set, for the same reason
the sibling file removed it: an adversarial ``/etc/hosts`` entry can repoint it
away from loopback.
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

#: Literal loopback addresses only.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_sendto = socket.socket.sendto
_real_sendmsg = getattr(socket.socket, "sendmsg", None)


def _address_host(address: Any) -> Any:
    """The host part of a socket address, for the loopback check."""
    if isinstance(address, tuple) and address:
        return address[0]
    return address


def _enforce_loopback(address: Any) -> None:
    """Refuse any target that is not a literal loopback address."""
    if address is None:
        return
    host = _address_host(address)
    if isinstance(host, str) and host in _LOOPBACK_HOSTS:
        return
    raise AssertionError(
        f"cp3 hermetic test guard (design #40 D1.4): network call to "
        f"{address!r} refused — this suite may reach only 127.0.0.1/::1, never "
        "a real external address (not even 'localhost')."
    )


def _guarded_connect(self: socket.socket, address: Any) -> Any:
    """Refuse a non-loopback ``connect()``."""
    _enforce_loopback(address)
    return _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> Any:
    """Refuse a non-loopback ``connect_ex()`` — raising, not returning an errno.

    Real ``connect_ex`` returns an errno rather than raising, which a test might
    never check; raising is louder.
    """
    _enforce_loopback(address)
    return _real_connect_ex(self, address)


def _guarded_sendto(self: socket.socket, *args: Any) -> Any:
    """Refuse a non-loopback ``sendto()``.

    UDP's connectionless send: it never calls ``connect()`` first, so the
    connect guard never runs before it. The address is the last positional
    argument in both accepted signatures.
    """
    if args:
        _enforce_loopback(args[-1])
    return _real_sendto(self, *args)


def _guarded_sendmsg(self: socket.socket, *args: Any, **kwargs: Any) -> Any:
    """Refuse a non-loopback ``sendmsg()`` (address is optional, 4th or kwarg)."""
    address = kwargs.get("address")
    if address is None and len(args) >= 4:
        address = args[3]
    _enforce_loopback(address)
    assert _real_sendmsg is not None  # only installed when it exists
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

#: Mode characters meaning "this call can create or modify bytes on disk".
_WRITE_MODE_CHARS = frozenset("wax+")

_real_builtins_open = builtins.open
_real_path_open = pathlib.Path.open
_real_path_write_text = pathlib.Path.write_text
_real_path_write_bytes = pathlib.Path.write_bytes


def _is_write_mode(mode: Any) -> bool:
    """Whether ``mode`` can create or modify bytes."""
    if not isinstance(mode, str):
        return False
    return any(ch in _WRITE_MODE_CHARS for ch in mode)


def _resolve_target(file: Any) -> Path | None:
    """Resolve an ``open``-style target, or ``None`` for an already-open fd."""
    if isinstance(file, int):
        return None
    return Path(os.fsdecode(file)).resolve()


def _enforce_within_root(path: Path | None, allowed_root: Path) -> None:
    """Refuse a write whose resolved target is outside ``allowed_root``."""
    if path is None:
        return
    if path == allowed_root or allowed_root in path.parents:
        return
    raise PermissionError(
        "cp3 hermetic test guard (design #40 D1.4): write to "
        f"{path} refused — this suite may write only inside its own tmp_path "
        f"({allowed_root}), never anywhere else on disk."
    )


@pytest.fixture(autouse=True)
def _hermetic_write_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: refuse any write outside this test's own ``tmp_path``.

    Patches ``builtins.open`` AND ``pathlib.Path.open``/``write_text``/
    ``write_bytes``: CPython's ``Path.open`` holds its own reference to
    ``io.open``, so patching the ``builtins`` attribute alone leaves every
    ``Path`` write unguarded. Read modes are never restricted — this suite reads
    the committed strategy content and the legacy Setup D YAML on purpose.
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
