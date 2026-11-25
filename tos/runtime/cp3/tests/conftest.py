"""The two D1.4 autouse guards, installed for THIS suite."""

from __future__ import annotations

import builtins
import os
import pathlib
import socket
from pathlib import Path
from typing import Any

import pytest

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
    """Refuse a non-loopback ``connect_ex()`` — raising, not returning an errno."""
    _enforce_loopback(address)
    return _real_connect_ex(self, address)


def _guarded_sendto(self: socket.socket, *args: Any) -> Any:
    """Refuse a non-loopback ``sendto()``."""
    if args:
        _enforce_loopback(args[-1])
    return _real_sendto(self, *args)


def _guarded_sendmsg(self: socket.socket, *args: Any, **kwargs: Any) -> Any:
    """Refuse a non-loopback ``sendmsg()`` (address is optional, 4th or kwarg)."""
    address = kwargs.get("address")
    if address is None and len(args) >= 4:
        address = args[3]
    _enforce_loopback(address)
    assert _real_sendmsg is not None
    return _real_sendmsg(self, *args, **kwargs)


@pytest.fixture(autouse=True)
def _hermetic_network_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: every test in this suite gets the outbound-network guard."""
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", _guarded_sendto)
    if _real_sendmsg is not None:
        monkeypatch.setattr(socket.socket, "sendmsg", _guarded_sendmsg)


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
    """Autouse: refuse any write outside this test's own ``tmp_path``."""
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
