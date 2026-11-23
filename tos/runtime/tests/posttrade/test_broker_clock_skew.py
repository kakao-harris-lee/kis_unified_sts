"""The host↔broker skew meter the uncertain-send judgment rests on (issue #1138)."""

from __future__ import annotations

import pytest
from tos_runtime.posttrade.broker_clock_skew import BrokerClockSkew, parse_http_date_ms

_BROKER_DATE = "Fri, 20 Nov 2026 02:20:10 GMT"
_BROKER_MS = 1_795_141_210_000
_TOLERANCE_S = 30


def _meter(host_ms: int | None, *, tolerance_s: int = _TOLERANCE_S) -> BrokerClockSkew:
    return BrokerClockSkew(tolerance_s=tolerance_s, host_unix_ms=lambda: host_ms)


def test_the_header_is_read_as_the_instant_it_names() -> None:
    assert parse_http_date_ms(_BROKER_DATE) == _BROKER_MS


@pytest.mark.parametrize(
    "value", [None, "", "   ", "not a date", "20261120", "Fri, 20 Nov 2026 02:20:10"]
)
def test_an_unreadable_header_measures_nothing(value: str | None) -> None:
    """A header without a zone is not an HTTP date; guessing one would invent the offset."""
    assert parse_http_date_ms(value) is None


def test_an_unmeasured_meter_corroborates_nothing() -> None:
    """The failing input of #1138 is a clock nobody checked — that is not 'within tolerance'."""
    meter = _meter(_BROKER_MS)
    assert meter.measured_ms is None
    assert meter.corroborated() is False


def test_a_host_inside_the_tolerance_is_corroborated() -> None:
    meter = _meter(_BROKER_MS + 2_100)
    meter.observe(_BROKER_DATE)
    assert meter.measured_ms == 2_100
    assert meter.corroborated() is True


@pytest.mark.parametrize("offset_ms", [130_000, -130_000])
def test_a_host_outside_the_tolerance_is_not(offset_ms: int) -> None:
    """#1138's own number: 130 s of skew, either way, is past the 30 s a judgment may rest on."""
    meter = _meter(_BROKER_MS + offset_ms)
    meter.observe(_BROKER_DATE)
    assert meter.measured_ms == offset_ms
    assert meter.corroborated() is False


def test_the_edge_is_inclusive() -> None:
    meter = _meter(_BROKER_MS + _TOLERANCE_S * 1000)
    meter.observe(_BROKER_DATE)
    assert meter.corroborated() is True


def test_an_unreadable_host_clock_leaves_the_last_measurement_alone() -> None:
    meter = BrokerClockSkew(tolerance_s=_TOLERANCE_S, host_unix_ms=lambda: None)
    meter.observe(_BROKER_DATE)
    assert meter.measured_ms is None
    assert meter.corroborated() is False


def test_a_raising_host_clock_does_not_escape_the_meter() -> None:
    def _boom() -> int:
        raise RuntimeError("no clock")

    meter = BrokerClockSkew(tolerance_s=_TOLERANCE_S, host_unix_ms=_boom)
    meter.observe(_BROKER_DATE)
    assert meter.corroborated() is False


def test_the_newest_reading_replaces_the_last() -> None:
    """A clock that drifts out mid-session stops corroborating from the next read on."""
    host = [_BROKER_MS]
    meter = BrokerClockSkew(tolerance_s=_TOLERANCE_S, host_unix_ms=lambda: host[0])
    meter.observe(_BROKER_DATE)
    assert meter.corroborated() is True

    host[0] = _BROKER_MS + 130_000
    meter.observe(_BROKER_DATE)
    assert meter.corroborated() is False
