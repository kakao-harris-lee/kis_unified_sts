"""tos_runtime test-suite wiring — D1.4 hermetic fixtures."""

from __future__ import annotations

import builtins
import os
import pathlib
import signal
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_sendto = socket.socket.sendto
_real_sendmsg = getattr(socket.socket, "sendmsg", None)


def _address_host(address: Any) -> Any:
    """Extract the host part of a socket address for the loopback check."""
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
    """Refuse any ``connect_ex()`` target that is not loopback (D1.4)."""
    _enforce_loopback(address)
    return _real_connect_ex(self, address)


def _guarded_sendto(self: socket.socket, *args: Any) -> Any:
    """Refuse any ``sendto()`` target that is not loopback (D1.4)."""
    if args:
        _enforce_loopback(args[-1])
    return _real_sendto(self, *args)


def _guarded_sendmsg(self: socket.socket, *args: Any, **kwargs: Any) -> Any:
    """Refuse any ``sendmsg()`` target that is not loopback (D1.4)."""
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
    if not isinstance(mode, str):
        return False
    return any(ch in _WRITE_MODE_CHARS for ch in mode)


def _resolve_target(file: Any) -> Path | None:
    """Resolve a ``builtins.open``-style ``file`` argument to an absolute"""
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
    """Autouse: refuse any WRITE-mode open/write whose resolved target lies"""
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


@pytest.fixture(autouse=True)
def _stop_signal_handlers() -> Iterator[None]:
    """Autouse: put this process's ``SIGINT``/``SIGTERM`` handlers back after every test."""
    saved = [(sig, signal.getsignal(sig)) for sig in (signal.SIGINT, signal.SIGTERM)]
    try:
        yield
    finally:
        for sig, handler in saved:
            signal.signal(sig, handler)
