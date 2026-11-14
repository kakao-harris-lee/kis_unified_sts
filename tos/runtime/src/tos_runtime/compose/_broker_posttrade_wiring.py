"""Broker-sourced post-trade wiring for the stock MOCK order tree (PR-3b, rescope plan §3 M2)."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EventKind, ResultDisposition

from tos_runtime.brokercap import BrokerScopesConfig
from tos_runtime.compose._held_position_wiring import HeldPositionBridge
from tos_runtime.compose._kis_credential_wiring import (
    KisCredentialSessionsCell,
    kis_mock_credential_session,
    kis_transport_pacing,
)
from tos_runtime.compose._posttrade_source import broker_posttrade_enabled
from tos_runtime.compose._transport_wiring import instance_rest_bases
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.engine.finality_projection import project_recovered_finality
from tos_runtime.posttrade.broker_finality import BrokerFinalityProducer
from tos_runtime.posttrade.fill_fetch import (
    PrefetchedSnapshot,
    SnapshotRead,
    SnapshotUse,
    snapshot_key,
)
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVER_CONFIG_NAME,
    FillObserverConfig,
    KisMockFillObserver,
    load_fill_observer_config,
)
from tos_runtime.posttrade.fill_observer_config import FillObserverConfigError
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.posttrade.release_consumer import (
    FinalityConsumerPort,
    FinalityReleaseConsumer,
    release_command_id,
)
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow, KisStockBrokerWitness
from tos_runtime.recon.witness_kis_client import build_witness_client
from tos_runtime.recon.witness_kis_config import kis_witness_config_from_mapping
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import build_client
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_mock.pacer import first_grant_on_this_thread

__all__ = [
    "BrokerPosttrade",
    "DeferredKisWitness",
    "attach_fill_observer",
    "build_broker_posttrade",
    "close_fill_observer",
    "fill_observer_pass",
]


class _TrustedTradingDate:
    """``KstDateSource`` over the runtime's trusted trading-date reader — the same reading the"""

    def __init__(self, reader: Callable[[], str | None]) -> None:
        self._reader = reader

    def today(self) -> str:
        date = self._reader()
        if date is None:
            raise WitnessUnavailable(
                "no trusted trading date — refusing to guess the order-inquiry date"
            )
        return date


class DeferredKisWitness:
    """The stock KIS witness, built once the credential registry is dispatched; until then every"""

    def __init__(
        self, trading_date_now: Callable[[], str | None] = lambda: None
    ) -> None:
        self.inner: KisStockBrokerWitness | None = None
        self._trading_date_now = trading_date_now
        self._served: PrefetchedSnapshot | None = None
        self._served_thread: int | None = None
        self._max_age_ms = 0
        self._now_ms: Callable[[], int] = lambda: 0
        self._uses: list[SnapshotUse] = []
        self._strict_thread: int | None = None

    def _ready(self) -> KisStockBrokerWitness:
        if self.inner is None:
            raise WitnessUnavailable(
                "KIS witness: credential session not dispatched yet"
            )
        return self.inner

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        served = self._served
        if (
            served is not None
            and self._served_thread == threading.get_ident()
            and served.key == snapshot_key(scope)
            and served.today == self._trading_date_now()
        ):
            age_ms = self._now_ms() - served.read_started_ms
            if self._strict_thread == threading.get_ident() and age_ms < 0:
                raise WitnessUnavailable("prefetched snapshot monotonic age is invalid")
            if age_ms > self._max_age_ms:
                span_ms = served.read_finished_ms - served.read_started_ms
                reason = (
                    "read_span_exceeds_max_age"
                    if span_ms > self._max_age_ms
                    else "aged_before_apply"
                )
                self._uses.append(
                    SnapshotUse("expired", served, age_ms, self._max_age_ms, reason)
                )
                raise WitnessUnavailable(
                    f"prefetched release snapshot expired: age {age_ms} ms > "
                    f"{self._max_age_ms} ms — held, fresh worker read scheduled"
                )
            self._uses.append(SnapshotUse("served", served, age_ms, self._max_age_ms))
            if isinstance(served.outcome, WitnessUnavailable):
                raise served.outcome
            return served.outcome
        if self._strict_thread == threading.get_ident():
            raise WitnessUnavailable("required prefetched snapshot does not match")
        return self._ready().observe(scope)

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> SnapshotRead:
        """FETCH thread: ``scope``'s snapshot under ``today``, or the unavailability it ended"""
        outcome: WitnessSnapshot | WitnessUnavailable
        balance_mark: list[int] = []
        with first_grant_on_this_thread() as tap:
            try:
                outcome = self._ready().observe(
                    scope,
                    today=today,
                    deadline_expired=abort,
                    before_balance=lambda: balance_mark.append(len(tap.grants_ms)),
                )
            except WitnessUnavailable as exc:
                outcome = exc
        age_origin = (
            tap.grants_ms[balance_mark[0]]
            if balance_mark and len(tap.grants_ms) > balance_mark[0]
            else None
        )
        return SnapshotRead(
            outcome=outcome, first_request_ms=tap.first_ms, age_origin_ms=age_origin
        )

    @contextmanager
    def serving(
        self,
        prefetched: PrefetchedSnapshot | None,
        *,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[SnapshotUse]]:
        """APPLY: serve ``prefetched`` (within ``max_age_ms``) to matching :meth:`observe`"""
        uses: list[SnapshotUse] = []
        self._served, self._served_thread = prefetched, threading.get_ident()
        self._max_age_ms, self._now_ms, self._uses = max_age_ms, now_ms, uses
        try:
            yield uses
        finally:
            self._served, self._served_thread, self._uses = None, None, []

    @contextmanager
    def serving_required(
        self,
        prefetched: PrefetchedSnapshot | None,
        *,
        expected_scope: WitnessScope,
        expected_today: str,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[SnapshotUse]]:
        """Serve only a matching prefetched snapshot; never perform loop-thread I/O."""
        previous = (
            self._served,
            self._served_thread,
            self._max_age_ms,
            self._now_ms,
            self._uses,
            self._strict_thread,
        )
        uses: list[SnapshotUse] = []
        self._strict_thread = threading.get_ident()
        self._served = (
            prefetched
            if prefetched is not None
            and prefetched.key == snapshot_key(expected_scope)
            and prefetched.today == expected_today
            else None
        )
        self._served_thread = self._strict_thread
        self._max_age_ms, self._now_ms, self._uses = max_age_ms, now_ms, uses
        try:
            yield uses
        finally:
            (
                self._served,
                self._served_thread,
                self._max_age_ms,
                self._now_ms,
                self._uses,
                self._strict_thread,
            ) = previous

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        return self._ready().order_rows(
            scope, inquiry_date=inquiry_date, deadline_expired=deadline_expired
        )


@dataclass
class BrokerPosttrade:
    """This boot's broker post-trade parts; ``enabled`` False means all synthetic."""

    enabled: bool
    witness: DeferredKisWitness | None = None
    observer_config: FillObserverConfig | None = None
    finality_producer: SyntheticFinalityProducer | BrokerFinalityProducer | None = None
    release_consumer: FinalityConsumerPort | None = None
    held_position_bridge: HeldPositionBridge | None = None
    trading_date_now: Callable[[], str | None] = lambda: None


def _refuse_snapshot_age_below_two_intervals(
    max_age_ms: int, min_interval_ms: int, path: Path
) -> None:
    """Refuse a ``release_snapshot_max_age_ms`` shorter than two app-key intervals."""
    if max_age_ms < 2 * min_interval_ms:
        raise FillObserverConfigError(
            f"{path}: release_snapshot_max_age_ms {max_age_ms} is shorter than two app-key "
            f"request intervals (2 x kis_mock_transport.yaml::min_send_interval_ms "
            f"{min_interval_ms} = {2 * min_interval_ms}) — the two-GET release snapshot "
            "would almost always be served expired and every release would hold"
        )


def _refuse_unreachable_held_position_age(
    max_age_ms: int | None,
    poll_interval_ms: int | None,
    min_interval_ms: int,
    path: Path,
) -> None:
    """Refuse a ``held_position_max_age_ms`` no refresh of that cache could ever satisfy."""
    if max_age_ms is None or poll_interval_ms is None:
        return
    double_read_ms = 3 * min_interval_ms
    if max_age_ms < double_read_ms:
        raise FillObserverConfigError(
            f"{path}: held_position_max_age_ms {max_age_ms} is shorter than the double read "
            f"that refreshes it (3 x kis_mock_transport.yaml::min_send_interval_ms "
            f"{min_interval_ms} = {double_read_ms}) — its four paced GETs would publish a "
            "proof that is already expired and no CLOSE could ever hold one"
        )
    cycle_floor_ms = poll_interval_ms + double_read_ms
    if max_age_ms < cycle_floor_ms:
        raise FillObserverConfigError(
            f"{path}: held_position_max_age_ms {max_age_ms} is shorter than one held-position "
            f"poll period plus the double read that refreshes it "
            f"(held_position_poll_interval_ms {poll_interval_ms} + 3 x "
            f"kis_mock_transport.yaml::min_send_interval_ms {min_interval_ms} = "
            f"{cycle_floor_ms}) — the proof would expire before its replacement could be "
            "published, and a CLOSE proposed in that hole would spend its standing-approval "
            "use before reading PROOF_UNAVAILABLE"
        )


def build_broker_posttrade(
    *,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
    transport_config: KisMockTransportConfig | None,
    credential_sessions_cell: KisCredentialSessionsCell,
    trading_date_now: Callable[[], str | None],
) -> BrokerPosttrade:
    """Build the witness (deferred) and load the observer config for a stock MOCK boot."""
    if not broker_posttrade_enabled(broker_scopes.active_scope, transport_config):
        return BrokerPosttrade(enabled=False)
    assert transport_config is not None
    path = config_dir / FILL_OBSERVER_CONFIG_NAME
    observer_config = load_fill_observer_config(path)
    _refuse_snapshot_age_below_two_intervals(
        observer_config.release_snapshot_max_age_ms,
        transport_config.min_send_interval_ms,
        path,
    )
    _refuse_unreachable_held_position_age(
        observer_config.held_position_max_age_ms,
        observer_config.held_position_poll_interval_ms,
        transport_config.min_send_interval_ms,
        path,
    )
    mock_rest_base, real_rest_base = instance_rest_bases(broker_scopes)
    witness_config = kis_witness_config_from_mapping(
        {
            **observer_config.witness_fields,
            "endpoint_rest_base": transport_config.endpoint_rest_base,
            "request_timeout_s": observer_config.witness_request_timeout_s,
            "allow_plaintext_for_tests": transport_config.allow_plaintext_for_tests,
        },
        path=path,
        instance_mock_rest_base=mock_rest_base,
        instance_real_rest_base=real_rest_base,
    )
    witness = DeferredKisWitness(trading_date_now)
    token_client = build_client(transport_config)

    def _build(sessions: KisCredentialSessions) -> None:
        witness.inner = KisStockBrokerWitness(
            config=witness_config,
            client=build_witness_client(witness_config),
            credential_session=kis_mock_credential_session(
                sessions,
                client=token_client,
                token_endpoint_base=transport_config.endpoint_rest_base,
                token_path=transport_config.token_path,
                token_reissue_min_interval_s=transport_config.token_reissue_min_interval_s,
                pacing=kis_transport_pacing(transport_config),
            ),
            date_source=_TrustedTradingDate(trading_date_now),
        )

    credential_sessions_cell.on_ready(_build)
    return BrokerPosttrade(
        enabled=True,
        witness=witness,
        observer_config=observer_config,
        trading_date_now=trading_date_now,
    )


def attach_fill_observer(
    runtime: ComposedRuntime,
    posttrade: BrokerPosttrade,
    *,
    monotonic: MonotonicSource,
) -> ComposedRuntime:
    """Attach the observer (stock MOCK boots with a wired driver only) and record the witness"""
    if not posttrade.enabled:
        return runtime
    runtime.broker_witness_provenance = "kis-mock-stock"
    if (
        runtime.driver is None
        or posttrade.witness is None
        or posttrade.observer_config is None
        or posttrade.finality_producer is None
        or posttrade.release_consumer is None
    ):
        return runtime
    driver = runtime.driver
    producer = posttrade.finality_producer
    consumer = posttrade.release_consumer

    def _reproject(payload: EgressResultPayload, *, reason: str) -> bool | None:
        return project_recovered_finality(
            payload,
            inbox=runtime.inbox,
            evidence_store=runtime.evidence_store,
            finality_producer=producer,
            release_consumer=consumer,
            ledger=runtime.core.ledger,
            reason=reason,
        )

    def _sink(payload: EgressResultPayload) -> ResultDisposition | None:
        result = driver.enqueue_and_run(
            EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        )
        return result.result_disposition

    def _engine_holds(attempt_id: str) -> bool:
        held = runtime.core.ledger.outstanding(runtime.context_resolver.instrument_key)
        return held is not None and held.attempt_id == attempt_id

    instrument_key = runtime.context_resolver.instrument_key
    bridge = posttrade.held_position_bridge
    recovery = consumer if isinstance(consumer, FinalityReleaseConsumer) else None
    runtime.fill_observer = KisMockFillObserver(
        config=posttrade.observer_config,
        orders=posttrade.witness,
        evidence_store=runtime.evidence_store,
        result_sink=_sink,
        reproject=lambda payload: _reproject(payload, reason="release_not_committed"),
        release_committed=lambda attempt_id: runtime.rcl_log.command_committed(
            release_command_id(attempt_id)
        ),
        engine_holds=_engine_holds,
        today=posttrade.trading_date_now,
        monotonic=monotonic,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        snapshots=posttrade.witness,
        held_position_tip=None if bridge is None else bridge.tip_tuple,
        held_position_eligible=(
            None
            if bridge is None
            else lambda: bridge.eligible(
                instrument_key.account, instrument_key.instrument
            )
        ),
        mark_held_position_pending=None if bridge is None else bridge.cell.mark_pending,
        publish_held_position_snapshot=None if bridge is None else bridge.publish,
        pending_recovery_attempt_ids=(
            None if recovery is None else recovery.pending_recovery_attempt_ids
        ),
        resume_entry_discharge=(
            None if recovery is None else recovery.resume_entry_discharge
        ),
    )
    return runtime


def close_fill_observer(runtime: ComposedRuntime) -> None:
    """Stop this boot's fill observer FETCH worker, if it has one (issue #950): the session is"""
    observer = runtime.fill_observer
    if observer is not None:
        observer.close()


def fill_observer_pass(runtime: ComposedRuntime) -> Callable[[], None]:
    """The session loop's post-pass work: poll this boot's fill observer, if it has one."""

    def _pass() -> None:
        observer = runtime.fill_observer
        if observer is None:
            return
        observer.poll_if_due()

    return _pass
