"""The slim monitor: chain continuity, tip stall, inbox backlog, MONITORING.

Replaces the ``tos.stm`` safety-mesh service's test module (plan S2-a). What is asserted
here is what the monitor still decides: the three facts it judges, the honest UNKNOWN on a
never-observed tip and on an unestablished continuity baseline, the alert emission on every
non-healthy reading, the delivery-failure memory, and the self-perturbation contract the
compose wiring must honour.

**Every happy-path builder warms the baseline first** (``_service(..., warm=True)``, the
default) because the FIRST observation any instance makes is honestly UNKNOWN — continuity
has no prior ``(seq, chain_digest)`` to compare against. That is exactly what
``tos_runtime.compose._monitor_wiring.build_monitor_owners`` does at boot, so a warmed
service is the state a real tick actually meets.
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
    tip_digest: str = "digest-1",
    unconsumed: int = 0,
    clock: _Clock | None = None,
    recorder: _Recorder | None = None,
    warm: bool = True,
) -> tuple[MonitoringService, _Clock, _Recorder, dict[str, Any]]:
    """Build a monitor over mutable observation cells the caller can drive.

    ``warm`` performs the one baseline-establishing call the compose wiring makes at boot
    and then forgets the alert it produced, so a test that wants the STEADY state does not
    have to re-state the first-observation UNKNOWN every time. Pass ``warm=False`` to
    observe that first call itself.
    """
    cells: dict[str, Any] = {
        "tip_seq": tip_seq,
        "tip_digest": tip_digest,
        "unconsumed": unconsumed,
    }
    the_clock = clock or _Clock()
    the_recorder = recorder or _Recorder()
    service = MonitoringService(
        config_path=path,
        evidence_tip_observer=lambda: (cells["tip_seq"], str(cells["tip_digest"]), 1),
        inbox_unconsumed_observer=lambda: int(cells["unconsumed"]),
        monotonic_ns=the_clock,
        evidence_recorder=the_recorder,
    )
    if warm:
        service.healthy()
        the_recorder.calls.clear()
    return service, the_clock, the_recorder, cells


# ---------------------------------------------------------------------------
# config loading — fail-closed
# ---------------------------------------------------------------------------


def test_a_missing_config_file_refuses_at_construction(tmp_path: Path) -> None:
    with pytest.raises(MonitoringConfigError):
        _service(tmp_path / "nope.yaml", warm=False)


@pytest.mark.parametrize(
    "field",
    ["coverage_generation", "max_evidence_tip_stall_ms", "max_inbox_unconsumed"],
)
def test_a_named_tbd_field_refuses_at_construction(tmp_path: Path, field: str) -> None:
    """Every required field is refused while still ``null`` — never a lazily-discovered
    ``None`` inside :meth:`MonitoringService.healthy`."""
    nulled: dict[str, int | None] = {field: None}
    with pytest.raises(MonitoringConfigError, match=field):
        _service(
            write_monitor_coverage_file(tmp_path, **nulled),  # type: ignore[arg-type]
            warm=False,
        )


# ---------------------------------------------------------------------------
# evidence-chain continuity (grade-A review 2026-11-13, MEDIUM)
# ---------------------------------------------------------------------------


def test_the_first_observation_is_unknown_because_continuity_has_no_baseline(
    tmp_path: Path,
) -> None:
    """The very first observation any instance makes cannot judge continuity — there is no
    prior ``(seq, chain_digest)`` pair. It must report UNKNOWN (which denies), never a
    fabricated pass. This is the pre-S2-a behaviour, kept deliberately."""
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path), warm=False
    )
    assert service.healthy() is None
    assert recorder.calls[-1][1]["reasons"] == ("source_continuity_unestablished",)
    assert recorder.calls[-1][1]["source_continuity_present"] is None
    # ...and the SAME instance is healthy on the next call: the first one established the
    # baseline, which is why the compose wiring warms it at boot.
    assert service.healthy() is True


def test_a_regressing_sequence_is_a_broken_chain(tmp_path: Path) -> None:
    """Failing input from the review: ``(seq=10, digest=A)`` then ``(seq=9, digest=B)``. A
    tip that moves BACKWARD is a torn or rewritten chain — always a break, whatever the
    digest did. Without this check the reading is healthy and the send proceeds."""
    service, _clock, recorder, cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=10, tip_digest="A"
    )
    assert service.healthy() is True
    cells["tip_seq"] = 9
    cells["tip_digest"] = "B"
    assert service.healthy() is False
    assert recorder.calls[-1][1]["reasons"] == ("source_continuity_broken",)
    assert recorder.calls[-1][1]["source_continuity_present"] is False


def test_a_sequence_that_advances_with_a_stuck_digest_is_a_broken_chain(
    tmp_path: Path,
) -> None:
    """Failing input from the review: ``(seq=10, digest=A)`` then ``(seq=11, digest=A)``.
    An append must move the chain digest; a seq that advances while the digest stands still
    is exactly a chain that was not actually extended."""
    service, _clock, recorder, cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=10, tip_digest="A"
    )
    assert service.healthy() is True
    cells["tip_seq"] = 11
    assert service.healthy() is False
    assert recorder.calls[-1][1]["reasons"] == ("source_continuity_broken",)


def test_a_digest_that_moves_without_an_append_is_a_broken_chain(
    tmp_path: Path,
) -> None:
    """The mirror of the stuck digest: the chain digest changed while ``seq`` stood still,
    i.e. a row was rewritten in place rather than appended."""
    service, _clock, recorder, cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=10, tip_digest="A"
    )
    assert service.healthy() is True
    cells["tip_digest"] = "B"
    assert service.healthy() is False
    assert recorder.calls[-1][1]["reasons"] == ("source_continuity_broken",)


def test_an_idle_tick_moves_neither_coordinate_and_stays_healthy(
    tmp_path: Path,
) -> None:
    """Both coordinates standing still is an ordinary idle tick, not a break — the check
    requires AGREEMENT between seq advance and digest movement, not movement."""
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=10, tip_digest="A"
    )
    assert service.healthy() is True
    assert service.healthy() is True
    assert recorder.calls == []


def test_an_ordinary_append_moves_both_coordinates_and_stays_healthy(
    tmp_path: Path,
) -> None:
    service, _clock, recorder, cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=10, tip_digest="A"
    )
    cells["tip_seq"] = 11
    cells["tip_digest"] = "B"
    assert service.healthy() is True
    assert recorder.calls == []


def test_a_broken_chain_denies_the_monitoring_dimension(tmp_path: Path) -> None:
    """The whole point of keeping this check: a torn chain must make MONITORING
    not-established, which is what denies the send."""
    service, _clock, _recorder, cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=10, tip_digest="A"
    )
    cells["tip_seq"] = 9
    report = service.dimension_report()
    assert report is not None
    assert report.positively_established is False


# ---------------------------------------------------------------------------
# the two bounded self-observations
# ---------------------------------------------------------------------------


def test_a_fresh_advancing_tip_with_an_empty_inbox_is_healthy(tmp_path: Path) -> None:
    service, _clock, recorder, _cells = _service(write_monitor_coverage_file(tmp_path))
    assert service.healthy() is True
    assert recorder.calls == []


def test_a_never_observed_evidence_tip_is_unknown_not_false(tmp_path: Path) -> None:
    """``None`` is the honest answer for "no tip has ever been observed" — distinguishable
    from ``False`` ("observed, and out of bounds"). Continuity is left unjudged there: the
    gap already covers the call."""
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path), tip_seq=None, warm=False
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
    # An append moves BOTH coordinates — continuity stays satisfied.
    cells["tip_seq"] = 2
    cells["tip_digest"] = "digest-2"
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


def test_a_violation_beside_an_unestablished_fact_is_a_denial(tmp_path: Path) -> None:
    """A positively-breached bound wins over a merely-unestablished fact: the verdict is
    ``False``, never softened to ``None``, and the violations are listed first."""
    service, _clock, recorder, _cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=0),
        tip_seq=None,
        unconsumed=5,
        warm=False,
    )
    assert service.healthy() is False
    assert recorder.calls[-1][1]["reasons"] == (
        "inbox_unconsumed_over_bound",
        "evidence_tip_never_observed",
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
    assert fields["source_continuity_present"] is True
    assert fields["inbox_unconsumed"] == 7


def test_a_recorder_failure_propagates_and_is_remembered(tmp_path: Path) -> None:
    """A delivery failure can never be silently treated as healthy: it propagates now and
    keeps the NEXT call from reporting ``True`` even once the observation recovers."""
    recorder = _Recorder(fail=True)
    service, _clock, _rec, cells = _service(
        write_monitor_coverage_file(tmp_path, max_inbox_unconsumed=0),
        unconsumed=1,
        recorder=recorder,
        warm=False,
    )
    # The warm-up call itself is the first delivery, and it raises.
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
