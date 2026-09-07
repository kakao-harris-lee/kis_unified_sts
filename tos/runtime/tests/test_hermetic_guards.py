"""D1.4 hermetic-guard coverage (2026-09-08, independent review follow-up).

``test_placeholder.py`` proves the original ``connect()`` guard; this file
proves the two gaps that review found and closed in ``conftest.py``:

  1. ``connect_ex``/``sendto``/``sendmsg`` are ALSO guarded, not just
     ``connect`` — each is proven to raise BEFORE reaching the real syscall,
     the same way ``test_placeholder.py`` proves it for ``connect``.
  2. The write guard (``_hermetic_write_guard``) refuses a WRITE-mode target
     outside the test's own ``tmp_path``, for both ``builtins.open`` and the
     ``pathlib.Path`` write methods — with a positive control proving a write
     INSIDE ``tmp_path`` still works normally (the guard must not break the
     hermetic filesystem use it exists to allow).

All targets here are ``203.0.113.1`` (TEST-NET-3, RFC 5737) — reserved,
non-routable — so even a buggy guard that let the real call through would
fail fast rather than hang, but the actual assertion in every case is that
the guard's own ``PermissionError`` fires first.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

_NON_ROUTABLE = ("203.0.113.1", 80)


# ----------------------------------------------------------------------------
# network guard — connect_ex / sendto / sendmsg
# ----------------------------------------------------------------------------


def test_hermetic_guard_blocks_connect_ex() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.connect_ex(_NON_ROUTABLE)
    finally:
        s.close()


def test_hermetic_guard_blocks_sendto() -> None:
    # UDP: sendto() is connectionless — no prior connect() to have already
    # been guarded, so this proves sendto has its OWN check.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.sendto(b"x", _NON_ROUTABLE)
    finally:
        s.close()


def test_hermetic_guard_blocks_sendto_with_flags_arg() -> None:
    # sendto(data, flags, address) form — address is still the LAST
    # positional argument.
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
    # LOW finding, 2026-09-08: 'localhost' was previously in the allowed-host
    # set; it is now removed (only the literal loopback addresses remain), so
    # a connect attempt naming it must be refused just like any other
    # non-loopback host.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PermissionError, match="tos_runtime hermetic test guard"):
            s.connect(("localhost", 80))
    finally:
        s.close()


def test_hermetic_guard_still_allows_literal_loopback_address() -> None:
    # Control: 127.0.0.1 itself must still pass the loopback check (the
    # connect may still fail with "connection refused" since nothing is
    # listening — that's a DIFFERENT, real-connect-attempt error, not our
    # guard's PermissionError, which is exactly what proves the guard let it
    # through instead of blocking it).
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        with pytest.raises(OSError) as exc_info:
            s.connect(("127.0.0.1", 1))  # port 1 — essentially never listening
        assert not isinstance(exc_info.value, PermissionError) or (
            "tos_runtime hermetic test guard" not in str(exc_info.value)
        )
    finally:
        s.close()


# ----------------------------------------------------------------------------
# write guard — builtins.open / pathlib.Path.open / write_text / write_bytes
# ----------------------------------------------------------------------------


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
    # Control: READ modes are never restricted, even outside tmp_path — the
    # guard only cares about WRITE-mode targets (D1.4 says "zero writes",
    # not "zero filesystem access").
    outside = Path(__file__)  # this very test file — readable, real, outside tmp_path
    with open(outside) as f:
        assert f.readline().startswith('"""')


def test_write_guard_allows_write_inside_tmp_path(tmp_path: Path) -> None:
    # Positive control: the guard must not break the hermetic filesystem use
    # it exists to allow (D2/D3's sqlite-under-tmp_path pattern).
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
