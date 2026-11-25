"""Hermetic-guard coverage."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

_NON_ROUTABLE = ("203.0.113.1", 80)


def test_hermetic_guard_blocks_connect_ex() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.connect_ex(_NON_ROUTABLE)
    finally:
        s.close()


def test_hermetic_guard_blocks_sendto() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.sendto(b"x", _NON_ROUTABLE)
    finally:
        s.close()


def test_hermetic_guard_blocks_sendto_with_flags_arg() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.sendto(b"x", 0, _NON_ROUTABLE)
    finally:
        s.close()


@pytest.mark.skipif(
    not hasattr(socket.socket, "sendmsg"),
    reason="sendmsg not available on this platform",
)
def test_hermetic_guard_blocks_sendmsg() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.sendmsg([b"x"], [], 0, _NON_ROUTABLE)
    finally:
        s.close()


def test_hermetic_guard_localhost_is_no_longer_allowed() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.connect(("localhost", 80))
    finally:
        s.close()


def test_hermetic_guard_still_allows_literal_loopback_address() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        with pytest.raises(OSError) as exc_info:
            s.connect(("127.0.0.1", 1))
        assert not isinstance(exc_info.value, PermissionError) or (
            "tos_runtime hermetic test guard" not in str(exc_info.value)
        )
    finally:
        s.close()


def test_write_guard_blocks_builtins_open_outside_tmp_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "tos_runtime_hermetic_guard_escape.txt"
    assert not str(outside).startswith(str(tmp_path))
    with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
        with open(outside, "w"):
            pass


def test_write_guard_blocks_path_open_outside_tmp_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "tos_runtime_hermetic_guard_escape2.txt"
    with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
        outside.open("w")


def test_write_guard_blocks_write_text_outside_tmp_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "tos_runtime_hermetic_guard_escape3.txt"
    with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
        outside.write_text("data")


def test_write_guard_blocks_write_bytes_outside_tmp_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "tos_runtime_hermetic_guard_escape4.bin"
    with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
        outside.write_bytes(b"data")


def test_write_guard_allows_read_mode_outside_tmp_path(tmp_path: Path) -> None:
    outside = Path(__file__)
    with open(outside) as f:
        assert f.readline().startswith('"""')


def test_write_guard_allows_write_inside_tmp_path(tmp_path: Path) -> None:
    inside = tmp_path / "ok.txt"
    with open(inside, "w") as f:
        f.write("hello")
    assert inside.read_text() == "hello"


def test_write_guard_allows_path_write_text_inside_tmp_path(tmp_path: Path) -> None:
    inside = tmp_path / "ok2.txt"
    inside.write_text("hello2")
    assert inside.read_text() == "hello2"


def test_write_guard_allows_path_write_bytes_inside_tmp_path(tmp_path: Path) -> None:
    inside = tmp_path / "ok3.bin"
    inside.write_bytes(b"hello3")
    assert inside.read_bytes() == b"hello3"
