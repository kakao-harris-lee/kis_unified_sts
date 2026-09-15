"""tos_runtime.calendar.ports — wall-clock reference ports.

No sleep, no network — every implementation here is either a pure literal
(FixedWallClockReference), a no-op (AbsentWallClockReference), a single
in-process clock read (LocalWallClockReference), or a gated read of a real
:class:`~tos_runtime.time.service.TrustworthyTimeService`
(TrustedWallClockReference, G-1: runtime operations wiring plan §2 decision 1).
"""

from __future__ import annotations

from tos_runtime.calendar.model import WallClockReading
from tos_runtime.calendar.ports import (
    AbsentWallClockReference,
    FixedWallClockReference,
    LocalWallClockReference,
    TrustedWallClockReference,
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


# ----------------------------------------------------------------------------
# TrustedWallClockReference (G-1, runtime operations wiring plan §2 decision 1)
# ----------------------------------------------------------------------------


class _FakeTimeService:
    """A ``wall_clock_now()``-shaped double — isolates this port's own
    contract (call the method, wrap a non-None result, pass None through)
    from ``TrustworthyTimeService``'s own FSM, which
    ``tests/time/test_service.py`` already exercises directly."""

    def __init__(self, wall_clock_now: int | None) -> None:
        self._value = wall_clock_now

    def wall_clock_now(self) -> int | None:
        return self._value


def test_trusted_reference_reads_a_value_when_the_service_has_one() -> None:
    ref = TrustedWallClockReference(_FakeTimeService(wall_clock_now=1_700_000_000_000))
    reading = ref.read()
    assert reading == WallClockReading(
        unix_ms=1_700_000_000_000, source_label="trusted-time-service"
    )


def test_trusted_reference_is_none_when_the_service_reports_none() -> None:
    """M1 (plan §5 mutation table): TrustedWallClockReference must never
    read a value the underlying service itself would not expose (e.g.
    because it is not TRUSTED yet) — it is a thin, honest passthrough, never
    an independent source of a wall-clock value."""
    ref = TrustedWallClockReference(_FakeTimeService(wall_clock_now=None))
    assert ref.read() is None


def test_trusted_reference_describes_the_gate() -> None:
    reason = TrustedWallClockReference(_FakeTimeService(wall_clock_now=None)).describe()
    assert "TRUSTED" in reason


def test_trusted_reference_satisfies_the_protocol() -> None:
    assert isinstance(
        TrustedWallClockReference(_FakeTimeService(wall_clock_now=None)),
        WallClockReference,
    )


def test_trusted_reference_against_the_real_time_service() -> None:
    """End-to-end proof (not just the double above): a real
    ``TrustworthyTimeService`` fed through ``TrustedWallClockReference``
    stays None until TRUSTED, then reads the real observation."""
    from tos.workload import RuntimeIdentity
    from tos_runtime.time.config import TrustworthyTimeConfig
    from tos_runtime.time.service import TrustworthyTimeService
    from tos_runtime.time.sources import ReferenceObservation

    class _FakeMonotonic:
        def __init__(self, first: int) -> None:
            self.value = first

        def now_ms(self) -> int:
            return self.value

    class _FakeReference:
        def read(self) -> ReferenceObservation:
            return ReferenceObservation(
                reachable=True,
                healthy=True,
                quality="FAKE",
                wall_clock_unix_ms=1_700_000_000_000,
            )

    class _FakeEvidence:
        def append(self, payload, *, kind, record_class):  # noqa: ANN001, ANN201
            from tos.evidence import EvidenceAppendReceipt

            _ = (
                payload,
                kind,
                record_class,
            )  # unused — this double never inspects them
            return EvidenceAppendReceipt(
                segment_id=None, seq=0, chain_digest="d", key_generation=0
            )

    config = TrustworthyTimeConfig(
        max_time_source_precision_ms=5,
        max_time_transport_and_queue_uncertainty_ms=10,
        max_time_conservative_freshness_age_ms=1000,
        max_future_timestamp_tolerance_ms=200,
        max_process_suspension_ms=0,
        max_time_source_disagreement_ms=50,
        min_time_independent_reference_count=1,
        max_clock_domain_conversion_uncertainty_ms=50,
        max_send_result_wait_ms=5000,
        tz_db_version="2026a",
        trading_calendar_version="cal-1",
        verification_profile_version="vp-0",
        safety_profile_version="sp-0",
    )
    monotonic = _FakeMonotonic(1000)
    service = TrustworthyTimeService(
        monotonic=monotonic,
        references=[_FakeReference()],
        config=config,
        identity=RuntimeIdentity(cell_id="c", process_nonce="n"),
        evidence=_FakeEvidence(),
    )
    service.start()
    ref = TrustedWallClockReference(service)

    service.evaluate()  # -> SYNCHRONIZING
    assert ref.read() is None

    monotonic.value = 1010
    service.evaluate()  # -> TRUSTED
    reading = ref.read()
    assert reading is not None
    assert reading.unix_ms == 1_700_000_000_000
    assert reading.source_label == "trusted-time-service"
