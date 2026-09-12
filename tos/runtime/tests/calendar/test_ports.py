"""tos_runtime.calendar.ports — wall-clock reference ports.

No sleep, no network — every implementation here is either a pure literal
(FixedWallClockReference), a no-op (AbsentWallClockReference), or a single
in-process clock read (LocalWallClockReference).
"""

from __future__ import annotations

from tos_runtime.calendar.model import WallClockReading
from tos_runtime.calendar.ports import (
    AbsentWallClockReference,
    FixedWallClockReference,
    LocalWallClockReference,
    WallClockReference,
)


def test_absent_reference_always_returns_none() -> None:
    ref = AbsentWallClockReference()
    assert ref.read() is None
    assert ref.read() is None  # repeat-call stability


def test_absent_reference_describes_g1() -> None:
    reason = AbsentWallClockReference().describe()
    assert "G-1" in reason


def test_fixed_reference_returns_given_reading() -> None:
    ref = FixedWallClockReference(
        unix_ms=1_700_000_000_000, source_label="unit-test-fixed"
    )
    reading = ref.read()
    assert reading == WallClockReading(
        unix_ms=1_700_000_000_000, source_label="unit-test-fixed"
    )


def test_fixed_reference_default_source_label() -> None:
    ref = FixedWallClockReference(unix_ms=42)
    reading = ref.read()
    assert reading is not None
    assert reading.source_label == "fixed-test"


def test_local_reference_returns_an_int_and_does_not_raise() -> None:
    ref = LocalWallClockReference()
    reading = ref.read()
    assert reading is not None
    assert isinstance(reading.unix_ms, int)
    assert reading.unix_ms > 0
    assert reading.source_label == "local-system-clock"


def test_all_three_implementations_satisfy_the_protocol() -> None:
    assert isinstance(AbsentWallClockReference(), WallClockReference)
    assert isinstance(FixedWallClockReference(unix_ms=1), WallClockReference)
    assert isinstance(LocalWallClockReference(), WallClockReference)
