"""The slim monitor: evidence-tip stall, inbox backlog, MONITORING currentness.

Replaces the ``tos.stm`` safety-mesh service's test module (plan S2-a). What is asserted
here is what the monitor still decides: the two self-observations, the honest UNKNOWN on a
never-observed evidence tip, the alert emission on every non-healthy reading, the
delivery-failure memory, and the self-perturbation contract the compose wiring must honour.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from tos.cur import DimensionKey
from tos_runtime.safety.monitoring import MonitoringConfigError, MonitoringService

from .conftest import write_monitor_coverage_file


class _Recorder:
    """An ``AlertRecorder`` double collecting ``(kind, fields)`` calls."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.fail = fail

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.calls.append((kind, dict(fields)))
        if self.fail:
            raise RuntimeError("evidence sink refused")


class _Clock:
    """A settable monotonic nanosecond clock."""

    def __init__(self, now_ns: int = 0) -> None:
        self.now_ns = now_ns

    def __call__(self) -> int:
        return self.now_ns

    def advance_ms(self, ms: int) -> None:
        self.now_ns += ms * 1_000_000


def _service(
    path: Path,
    *,
    tip_seq: int | None = 1,
    unconsumed: int = 0,
    clock: _Clock | None = None,
    recorder: _Recorder | None = None,
) -> tuple[MonitoringService, _Clock, _Recorder, dict[str, Any]]:
    """Build a monitor over mutable observation cells the caller can drive."""
    cells: dict[str, Any] = {"tip_seq": tip_seq, "unconsumed": unconsumed}
    the_clock = clock or _Clock()
    the_recorder = recorder or _Recorder()
    service = MonitoringService(
        config_path=path,
        evidence_tip_observer=lambda: (cells["tip_seq"], "digest", 1),
        inbox_unconsumed_observer=lambda: int(cells["unconsumed"]),
        monotonic_ns=the_clock,
        evidence_recorder=the_recorder,
    )
    return service, the_clock, the_recorder, cells


# ---------------------------------------------------------------------------
# config loading — fail-closed
# ---------------------------------------------------------------------------


def test_a_missing_config_file_refuses_at_construction(tmp_path: Path) -> None:
    with pytest.raises(MonitoringConfigError):
        _service(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    "field",
    ["coverage_generation", "max_evidence_tip_stall_ms", "max_inbox_unconsumed"],
)
def test_a_named_tbd_field_refuses_at_construction(tmp_path: Path, field: str) -> None:
    """Every required field is refused while still ``null`` — never a lazily-discovered
    ``None`` inside :meth:`MonitoringService.healthy`."""
    nulled: dict[str, int | None] = {field: None}
    path = write_monitor_coverage_file(tmp_path, **nulled)  # type: ignore[arg-type]
    with pytest.raises(MonitoringConfigError, match=field):
        _service(path)


# ---------------------------------------------------------------------------
# the two self-observations
# ---------------------------------------------------------------------------


def test_a_fresh_advancing_tip_with_an_empty_inbox_is_healthy(tmp_path: Path) -> None:
    service, _clock, recorder, _cells = _service(write_monitor_coverage_file(tmp_path))
    assert service.healthy() is True
    assert recorder.calls == []


def test_a_never_observed_evidence_tip_is_unknown_not_false(tmp_path: Path) -> None:
    """``None`` is the honest answer for "no tip has ever been observed" — distinguishable
    from ``False`` ("observed, and out of bounds")."""
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=None
    )
    assert service.healthy() is None
    assert [kind for kind, _ in recorder.calls] == ["STM_ALERT"]
    assert recorder.calls[0][1]["reasons"] == ("evidence_tip_never_observed",)


def test_a_tip_that_stops_advancing_past_the_bound_is_not_healthy(
    tmp_path: Path,
) -> None:
    service, clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, max_evidence_tip_stall_ms=1_000)
    )
    assert service.healthy() is True
    clock.advance_ms(999)
    assert service.healthy() is True
    clock.advance_ms(2)
    assert service.healthy() is False
    assert recorder.calls[-1][1]["reasons"] == ("evidence_tip_stalled",)


def test_an_advancing_tip_resets_the_stall_clock(tmp_path: Path) -> None:
    service, clock, _recorder, cells = _service(
        write_monitor_coverage_file(tmp_path, max_evidence_tip_stall_ms=1_000)
    )
    assert service.healthy() is True
    clock.advance_ms(900)
    cells["tip_seq"] = 2
    assert service.healthy() is True
    clock.advance_ms(900)
    assert service.healthy() is True, "the advance at 900ms restarted the clock"


def test_an_inbox_backlog_over_the_bound_is_not_healthy(tmp_path: Path) -> None:
    service, _clock, recorder, cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=2), unconsumed=2
    )
    assert service.healthy() is True
    cells["unconsumed"] = 3
    assert service.healthy() is False
    assert recorder.calls[-1][1]["reasons"] == ("inbox_unconsumed_over_bound",)


def test_both_observations_out_of_bounds_report_both_reasons(tmp_path: Path) -> None:
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=0),
        tip_seq=None,
        unconsumed=5,
    )
    assert (
        service.healthy() is False
    ), "an UNKNOWN tip alongside a positively-breached bound is a denial, not an unknown"
    assert recorder.calls[-1][1]["reasons"] == (
        "evidence_tip_never_observed",
        "inbox_unconsumed_over_bound",
    )


# ---------------------------------------------------------------------------
# alert emission and delivery-failure memory
# ---------------------------------------------------------------------------


def test_an_alert_carries_the_observed_values_and_no_secret(tmp_path: Path) -> None:
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=0), unconsumed=7
    )
    assert service.healthy() is False
    kind, fields = recorder.calls[-1]
    assert kind == "STM_ALERT"
    assert fields["identity"] == service.identity
    assert fields["clear"] is False
    assert fields["last_evidence_seq"] == 1
    assert fields["inbox_unconsumed"] == 7


def test_a_recorder_failure_propagates_and_is_remembered(tmp_path: Path) -> None:
    """A delivery failure can never be silently treated as healthy: it propagates now and
    keeps the NEXT call from reporting ``True`` even once the observation recovers."""
    recorder = _Recorder(fail=True)
    service, _clock, _rec, cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=0),
        unconsumed=1,
        recorder=recorder,
    )
    with pytest.raises(RuntimeError, match="evidence sink refused"):
        service.healthy()
    recorder.fail = False
    cells["unconsumed"] = 0
    assert service.healthy() is False
    assert "stm_alert_delivery_failed" in recorder.calls[-1][1]["reasons"]
    assert service.healthy() is True, "the failure is remembered once, not forever"


# ---------------------------------------------------------------------------
# the MONITORING currentness dimension
# ---------------------------------------------------------------------------


def test_the_dimension_report_is_monitorings_and_carries_the_coverage_generation(
    tmp_path: Path,
) -> None:
    service, _clock, _recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, coverage_generation=7)
    )
    assert service.dimension_key is DimensionKey.MONITORING
    report = service.dimension_report()
    assert report is not None
    assert report.bound_generation == 7
    assert report.positively_established is True
    assert report.restrictive_floor == 0


def test_the_dimension_report_is_not_established_when_the_monitor_is_not_healthy(
    tmp_path: Path,
) -> None:
    service, _clock, _recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=0), unconsumed=9
    )
    report = service.dimension_report()
    assert report is not None
    assert report.positively_established is False


def test_describe_reports_the_bounds_and_no_secret(tmp_path: Path) -> None:
    service, _clock, _recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=11)
    )
    described = service.describe()
    assert described["identity"] == service.identity
    assert described["max_inbox_unconsumed"] == 11
    assert described["max_evidence_tip_stall_ms"] == 60_000
