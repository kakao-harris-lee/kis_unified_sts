"""Hermetic tests for tos_runtime.time.sources (slice plan §1 item 1)."""

from __future__ import annotations

from tos_runtime.time.sources import (
    LocalSystemClockReader,
    ProcessMonotonicSource,
    ReferenceObservation,
)


def test_process_monotonic_source_is_non_decreasing() -> None:
    source = ProcessMonotonicSource()
    first = source.now_ms()
    second = source.now_ms()
    assert isinstance(first, int)
    assert second >= first


def test_local_system_clock_reader_reports_reachable_and_healthy() -> None:
    reader = LocalSystemClockReader()
    observation = reader.read()
    assert isinstance(observation, ReferenceObservation)
    assert observation.reachable is True
    assert observation.healthy is True
    assert observation.quality == "LOCAL_SYSTEM_CLOCK"
    # HIGH-2 fix (review of ba7d438f): every instance declares the SAME
    # common_mode_group — all read the one OS wall-clock syscall — so N
    # instances collapse to 1 independent reference, never N.
    assert observation.common_mode_group == "LOCAL_SYSTEM_CLOCK"


def test_two_local_system_clock_readers_share_the_same_common_mode_group() -> None:
    """HIGH-2 regression: two instances must declare an IDENTICAL group so the
    kernel's independent_reference_count collapses them to 1, not 2."""
    first = LocalSystemClockReader().read()
    second = LocalSystemClockReader().read()
    assert first.common_mode_group is not None
    assert first.common_mode_group == second.common_mode_group
