"""``_fixtures.pin_system_clock`` itself (issue #914).

The fixture used to capture whatever ``LocalSystemClockReader.read`` was installed at call
time, so a second call in one test shifted an already-shifted reader: two calls with ``T``
read about ``2T - now`` while the returned ``now_ms()`` reported about ``T``.
"""

from __future__ import annotations

import pytest
from tos_runtime.time.sources import LocalSystemClockReader

from . import _fixtures as fx

#: Generous slack for the wall time that passes between pinning and reading. The bug this
#: guards is off by ``T - now`` (weeks for these constants), so any honest slack works.
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
