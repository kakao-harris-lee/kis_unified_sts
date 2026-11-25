"""The egress stamp's trading-date reader"""

from __future__ import annotations

import datetime
import textwrap
import zoneinfo
from collections.abc import Mapping
from pathlib import Path

import pytest
from tos.evidence import EvidenceAppendReceipt
from tos.time import HealthState
from tos.workload import RuntimeIdentity
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.compose._session_wiring import (
    build_egress_trading_date_reader,
    build_session_facts_owner,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation
from tos_runtime.venue_ledger.synthetic import RecordingSyntheticTransport

from . import _fixtures as fx
from .test_compose_root import (
    FakeMonotonicSource,
    _action_flow_inputs_for,
    _aggregate_inputs,
    _LiveRuntimeFacts,
)
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_KST = zoneinfo.ZoneInfo("Asia/Seoul")

_MONDAY_10_00_KST_UNIX_MS = int(
    datetime.datetime(2026, 1, 5, 10, 0, tzinfo=_KST).timestamp() * 1000
)
_TRADING_DATE = "20260105"
_STOCK_CLASS = "krx-stock-fixture"
_CALENDAR_VERSION = "egress-date-fixture-v1"
_FRESHNESS_AGE_MS = 1000
_INCIDENT_PRE_SEND_MS = 4287

_CALENDAR_YAML = textwrap.dedent(f"""\
    calendar_version: "{_CALENDAR_VERSION}"
    tz_id: "Asia/Seoul"
    closed_phase: "CLOSED"
    holidays: []
    sessions:
      {_STOCK_CLASS}:
        - phase: "CONTINUOUS"
          start: "09:00"
          end: "15:30"
          days: [MON, TUE, WED, THU, FRI]
          crosses_midnight: false
    futures_expiry: {{}}
    """)


class _FakeMonotonic:
    """A monotonic source this test advances explicitly (never the real clock)."""

    def __init__(self, now_ms: int = 1_000) -> None:
        self.value = now_ms

    def advance(self, ms: int) -> None:
        self.value += ms

    def now_ms(self) -> int:
        return self.value


class _TrackingReferenceReader:
    """A reference source whose wall clock advances in lockstep with ``monotonic``."""

    def __init__(self, monotonic: _FakeMonotonic, wall_clock_unix_ms: int) -> None:
        self._monotonic = monotonic
        self._base_monotonic_ms = monotonic.now_ms()
        self._base_wall_ms = wall_clock_unix_ms
        self.reachable = True
        self.healthy = True

    def read(self) -> ReferenceObservation:
        elapsed = self._monotonic.now_ms() - self._base_monotonic_ms
        return ReferenceObservation(
            reachable=self.reachable,
            healthy=self.healthy,
            quality="FAKE",
            common_mode_group=None,
            wall_clock_unix_ms=self._base_wall_ms + elapsed,
        )


class _FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` double (fixed bytes) — re-declared"""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-egress-trading-date")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-egress-trading-date"


class _CountingEvidence:
    """The time service's own append port — records what it was handed and can be told to"""

    def __init__(self) -> None:
        self.kinds: list[str] = []
        self.raise_from_now = False

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        del payload, record_class
        if self.raise_from_now:
            raise RuntimeError("simulated durable-append failure")
        self.kinds.append(kind)
        return EvidenceAppendReceipt(
            segment_id="test-segment",
            seq=len(self.kinds),
            chain_digest=f"digest-{len(self.kinds)}",
            key_generation=0,
        )


def _time_config() -> TrustworthyTimeConfig:
    return TrustworthyTimeConfig(
        max_time_source_precision_ms=5,
        max_time_transport_and_queue_uncertainty_ms=10,
        max_time_conservative_freshness_age_ms=_FRESHNESS_AGE_MS,
        max_future_timestamp_tolerance_ms=200,
        max_process_suspension_ms=0,
        max_time_source_disagreement_ms=50,
        min_time_independent_reference_count=1,
        max_clock_domain_conversion_uncertainty_ms=50,
        max_send_result_wait_ms=5000,
        max_critical_input_consumer_receipt_age_ms=1000,
        max_time_source_sequence_gap_ms=50,
        tz_db_version="tzdb-test",
        trading_calendar_version=_CALENDAR_VERSION,
        verification_profile_version="vp-0",
        safety_profile_version="sp-0",
        time_health_snapshot_heartbeat_ms=55_000,
    )


class _Stack:
    """One boot's worth of the real objects this reader is composed from."""

    def __init__(
        self,
        *,
        monotonic: _FakeMonotonic,
        reference: _TrackingReferenceReader,
        time_service: TrustworthyTimeService,
        time_evidence: _CountingEvidence,
        store: SqliteEvidenceStore,
        plain_reader,
        egress_reader,
    ) -> None:
        self.monotonic = monotonic
        self.reference = reference
        self.time_service = time_service
        self.time_evidence = time_evidence
        self.store = store
        self.plain_reader = plain_reader
        self.egress_reader = egress_reader


@pytest.fixture
def stack(tmp_path: Path):
    """Boot the real stack exactly as ``compose`` does: ``start()`` + the two boot-time"""
    (tmp_path / "calendar.yaml").write_text(_CALENDAR_YAML, encoding="utf-8")
    calendar = load_calendar_config(tmp_path / "calendar.yaml")
    monotonic = _FakeMonotonic()
    reference = _TrackingReferenceReader(monotonic, _MONDAY_10_00_KST_UNIX_MS)
    time_evidence = _CountingEvidence()
    time_service = TrustworthyTimeService(
        monotonic=monotonic,
        references=(reference,),
        config=_time_config(),
        identity=RuntimeIdentity(
            cell_id="cell-egress-date",
            runtime_generation=0,
            process_nonce="nonce-egress-date",
            code_digest="digest-egress-date",
        ),
        evidence=time_evidence,
    )
    time_service.start()
    time_service.evaluate()
    monotonic.advance(1)
    time_service.evaluate()
    assert time_service.health_state is HealthState.TRUSTED

    store = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=_key_provider()
    )
    owner = build_session_facts_owner(
        config_dir=tmp_path,
        calendar=calendar,
        wall_clock=None,
        evidence_store=store,
        time_config=_time_config(),
        time_service=time_service,
        tick_generation_reader=lambda: 1,
    )
    plain_reader = lambda: owner.trading_date_now(_STOCK_CLASS)  # noqa: E731
    yield _Stack(
        monotonic=monotonic,
        reference=reference,
        time_service=time_service,
        time_evidence=time_evidence,
        store=store,
        plain_reader=plain_reader,
        egress_reader=build_egress_trading_date_reader(
            trading_date_reader=plain_reader, time_service=time_service
        ),
    )
    store.close()


def _key_provider() -> KeyProvider:
    return _FixedKeyProvider()


def test_a_fresh_pass_stamps_the_date_without_evaluating_again(stack) -> None:
    """The common case: the pass's own evaluation is still inside the bound, so the egress"""
    before = stack.time_service.current_snapshot().snapshot_id
    assert stack.plain_reader() == _TRADING_DATE
    assert stack.egress_reader() == _TRADING_DATE
    assert stack.time_service.current_snapshot().snapshot_id == before


def test_the_pre_send_work_of_one_pass_ages_the_reading_out(stack) -> None:
    """Incident 2026-11-13, characterized: 4287 ms of in-pass pre-send work (two app-key pacer"""
    stack.monotonic.advance(_INCIDENT_PRE_SEND_MS)
    assert _INCIDENT_PRE_SEND_MS > _FRESHNESS_AGE_MS
    assert stack.plain_reader() is None


def test_the_egress_stamp_re_establishes_freshness_and_keeps_the_date(stack) -> None:
    """The fix: at the stamp the reader asks the time service for ONE fresh evaluation and"""
    stack.monotonic.advance(_INCIDENT_PRE_SEND_MS)
    before = stack.time_service.current_snapshot().snapshot_id

    assert stack.egress_reader() == _TRADING_DATE

    assert stack.time_service.current_snapshot().snapshot_id != before
    assert stack.time_service.health_state is HealthState.TRUSTED
    assert stack.plain_reader() == _TRADING_DATE


def test_an_untrusted_clock_still_stamps_nothing(stack) -> None:
    """A reference source that has gone away: the fresh evaluation runs, leaves TRUSTED, and"""
    stack.monotonic.advance(_INCIDENT_PRE_SEND_MS)
    stack.reference.reachable = False

    assert stack.egress_reader() is None
    assert stack.time_service.health_state is not HealthState.TRUSTED


def test_an_unevaluable_clock_stamps_nothing_and_never_the_stale_date(stack) -> None:
    """The evaluation itself fails (its durable append raises). The reader answers ``None`` —"""
    stack.monotonic.advance(_INCIDENT_PRE_SEND_MS)
    stack.time_evidence.raise_from_now = True

    assert stack.egress_reader() is None


def test_the_date_is_read_from_the_one_calendar_not_derived_here(stack) -> None:
    """Outside every window the calendar declares there is no trading date at all, and a fresh"""
    stack.monotonic.advance(5 * 3_600_000 + 31 * 60_000)
    assert stack.egress_reader() is None
    assert stack.time_service.health_state is HealthState.TRUSTED


def test_the_egress_stamp_of_a_composed_runtime_recovers_a_date_the_pass_aged_out(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every test above builds the reader directly, so all of them stay green if"""
    config_dir = config_dir_with_risk_state
    fx.pin_system_clock(monkeypatch, fx.LAST_MINUTE_OF_DAY_UNIX_MS)
    turn_the_venue_ledger_on(config_dir)
    fx.write_band_strategy_file(config_dir)
    clock = FakeMonotonicSource()
    facts = _LiveRuntimeFacts()
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs_for(facts),
        monotonic_source=clock,
        transport_kind=TransportKind.SYNTHETIC,
    )
    facts.runtime = runtime
    try:
        transport = runtime.transport
        assert isinstance(transport, RecordingSyntheticTransport)
        assert runtime.session_facts is not None
        at_boot = runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
        assert at_boot is not None
        assert transport._trading_date_now() == at_boot

        clock.next_value += 61_000

        assert runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS) is None
        assert transport._trading_date_now() is not None
    finally:
        runtime.venue_ledger.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()
