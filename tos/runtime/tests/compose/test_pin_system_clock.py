"""``_fixtures.pin_system_clock`` itself (issue #914)."""

from __future__ import annotations

import pytest
from tos_runtime.time.sources import LocalSystemClockReader

from . import _fixtures as fx

_SLACK_MS = 60_000


def _read_ms() -> int:
    observed = LocalSystemClockReader().read().wall_clock_unix_ms
    assert observed is not None
    return observed


def test_single_pin_reads_target(monkeypatch: pytest.MonkeyPatch) -> None:
    now_ms = fx.pin_system_clock(monkeypatch, fx.DEFAULT_WALL_CLOCK_UNIX_MS)
    assert abs(_read_ms() - fx.DEFAULT_WALL_CLOCK_UNIX_MS) < _SLACK_MS
    assert abs(now_ms() - fx.DEFAULT_WALL_CLOCK_UNIX_MS) < _SLACK_MS


def test_second_pin_same_target_does_not_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    fx.pin_system_clock(monkeypatch, fx.DEFAULT_WALL_CLOCK_UNIX_MS)
    now_ms = fx.pin_system_clock(monkeypatch, fx.DEFAULT_WALL_CLOCK_UNIX_MS)
    assert abs(_read_ms() - fx.DEFAULT_WALL_CLOCK_UNIX_MS) < _SLACK_MS
    assert abs(_read_ms() - now_ms()) < _SLACK_MS


def test_second_pin_new_target_repins(monkeypatch: pytest.MonkeyPatch) -> None:
    fx.pin_system_clock(monkeypatch, fx.DEFAULT_WALL_CLOCK_UNIX_MS)
    now_ms = fx.pin_system_clock(monkeypatch, fx.LAST_MINUTE_OF_DAY_UNIX_MS)
    assert abs(_read_ms() - fx.LAST_MINUTE_OF_DAY_UNIX_MS) < _SLACK_MS
    assert abs(_read_ms() - now_ms()) < _SLACK_MS
