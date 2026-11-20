"""Broker-sourced post-trade wiring for the stock MOCK order tree (PR-3b, rescope plan §3 M2)."""

from __future__ import annotations

import dataclasses
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EventKind, ResultDisposition

from tos_runtime.brokercap import BrokerScopesConfig
from tos_runtime.calendar.config import CalendarConfig
from tos_runtime.calendar.phase import recent_trading_dates
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
from tos_runtime.posttrade.broker_flat_release import BrokerFlatRelease
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
from tos_runtime.posttrade.uncertain_send import UncertainSendReconciler
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow, KisStockBrokerWitness
from tos_runtime.recon.witness_kis_client import build_witness_client
from tos_runtime.recon.witness_kis_config import kis_witness_config_from_mapping
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import build_client
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_mock.pacer import first_grant_on_this_thread

_FLAT_RELEASE_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

__all__ = [
    "BrokerPosttrade",
    "DeferredKisWitness",
    "attach_fill_observer",
    "build_broker_posttrade",
    "build_trading_dates_back",
    "close_fill_observer",
    "fill_observer_pass",
]


def build_trading_dates_back(
    trading_date_now: Callable[[], str | None],
    *,
    instrument_class: str,
    calendar: CalendarConfig,
) -> Callable[[int], tuple[str, ...]]:
    """Issue #1096's scan window: the N most recent trading dates ending at the trusted trading"""

    def _dates(count: int) -> tuple[str, ...]:
        today = trading_date_now()
        if today is None:
            return ()
        return recent_trading_dates(today, instrument_class, calendar, count)

    return _dates


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
        self,
        trading_date_now: Callable[[], str | None] = lambda: None,
        *,
        loop_deadline_ms: int | None = None,
        loop_deadline_max_ms: int | None = None,
        loop_deadline_per_date_ms: int | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.inner: KisStockBrokerWitness | None = None
        #: The session-loop fallback read's own witness (``loop_witness_request_timeout_s``) and
        #: walk deadline (``loop_witness_deadline_ms``); ``None`` keeps ``inner`` / no deadline.
        self.loop_inner: KisStockBrokerWitness | None = None
        self._loop_deadline_ms = loop_deadline_ms
        self._loop_deadline_max_ms = loop_deadline_max_ms
        self._loop_deadline_per_date_ms = loop_deadline_per_date_ms
        self._monotonic_ns = monotonic_ns
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
        return self._loop_observe(scope)

    def _loop_page_dates(self, scope: WitnessScope) -> int:
        """How many ORDER PAGES the witness will walk for ``scope`` — today included (#1136).

        ``KisStockBrokerWitness.observe`` reads ``(today, *sorted(set(order_dates) - {today}))``
        (``recon/witness_kis.py``): today is always one of the pages, whether or not the scope
        names it. Counting only ``order_dates`` therefore undercounted by one on exactly the leaf
        #1115 was written for — receipts on 11-17/18/19 reconciled on 11-20, before that day has
        a receipt of its own, walk FOUR order pages plus the balance, and the deadline that
        counted three (7000 ms) cut the last page off at 8000 ms on every pass.

        The date comes from this witness's own ``trading_date_now``, which is what the inner
        witness's ``KstDateSource`` reads when ``observe`` resolves ``today`` — one reader, one
        answer, so the count cannot disagree with the walk it is predicting. No trusted date
        means the read is about to fail at that same source, so nothing is added here.
        """
        today = self._trading_date_now()
        dates = set(scope.order_dates)
        if today is not None:
            dates.add(today)
        return len(dates)

    def _loop_deadline_for_page_dates(self, page_dates: int) -> int | None:
        """The loop-side walk deadline for a walk of ``page_dates`` order pages (#1115 N1).

        ``loop_witness_deadline_ms`` was measured for a ONE-page walk (the balance page plus one
        order page, one app-key pacing interval apart). The release reconciliation reads EVERY
        receipt date in its scope (``release_consumer._scope_receipt_dates``) and today besides,
        so an N-page walk needs N+1 paced GETs and its last page does not start until N intervals
        in — with a fixed 3000 ms deadline a 2-page walk already fails, every time, so the loop
        fallback was ``WitnessUnavailable`` by construction on any leaf that outlived one trading
        date.

        So each page past the first adds one pacing interval, up to
        ``loop_witness_deadline_max_ms`` — the cap is what keeps the session-loop stall bounded,
        and past it the behaviour is the old one (no verdict, fail-closed, recovered by the FETCH
        worker's reprojection). Without the cap or the pacing interval the base is used unchanged.
        """
        base = self._loop_deadline_ms
        per_date = self._loop_deadline_per_date_ms
        cap = self._loop_deadline_max_ms
        if base is None or per_date is None or cap is None:
            return base
        return min(cap, base + max(0, page_dates - 1) * per_date)

    def loop_deadline_ms_for(self, scope: WitnessScope) -> int | None:
        """:meth:`_loop_deadline_for_page_dates` over the pages ``scope`` actually walks."""
        return self._loop_deadline_for_page_dates(self._loop_page_dates(scope))

    def _refuse_a_walk_the_deadline_cannot_finish(
        self, page_dates: int, deadline_ms: int
    ) -> None:
        """Refuse BEFORE the first GET when the walk provably cannot finish (review-1132 r1).

        Past what the cap admits the outcome is ``WitnessUnavailable`` either way — the last
        order page's pacer grant lands after the deadline, so the walk is cut off. Spending the
        whole cap plus a pacer wait and a GET in flight (~13 s at the committed numbers) on the
        SESSION LOOP to arrive at a result that was certain before the first request is the one
        cost worth avoiding: that thread is also the one that produces decisions. The release
        holds exactly as it would have, and the FETCH worker's reprojection is still the path
        that resolves it.

        Only the scaled mode can say this. Without the pacing interval the page starts are not
        knowable here, so nothing is refused up front and the read runs as it always did.
        """
        per_date = self._loop_deadline_per_date_ms
        if per_date is None or self._loop_deadline_max_ms is None:
            return
        last_page_starts_at = page_dates * per_date
        if deadline_ms > last_page_starts_at:
            return
        raise WitnessUnavailable(
            f"loop-side walk refused before its first GET: {page_dates} order page(s) — the "
            f"scope's receipt dates and today — need {page_dates + 1} paced GETs and the last "
            f"starts at {last_page_starts_at} ms, past this scope's deadline {deadline_ms} ms "
            f"(cap {self._loop_deadline_max_ms} ms, pacing {per_date} ms) — the read could only "
            "end unavailable, so the loop does not wait for it; held, and the prefetching "
            "worker still covers this scope"
        )

    def _loop_observe(self, scope: WitnessScope) -> WitnessSnapshot:
        """A live read no prefetched snapshot served — on the caller's (loop) thread, bounded."""
        witness = self._ready() if self.loop_inner is None else self.loop_inner
        # One date read for the whole decision: the deadline and the refusal must agree about
        # which pages this walk has, and two reads could straddle a KST date rollover (#1136).
        page_dates = self._loop_page_dates(scope)
        deadline_ms = self._loop_deadline_for_page_dates(page_dates)
        if deadline_ms is None:
            return witness.observe(scope)
        self._refuse_a_walk_the_deadline_cannot_finish(page_dates, deadline_ms)
        deadline_ns = self._monotonic_ns() + deadline_ms * 1_000_000
        return witness.observe(
            scope, deadline_expired=lambda: self._monotonic_ns() >= deadline_ns
        )

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
    #: ``kis_mock_transport.yaml::min_send_interval_ms`` (the app-key pacer's spacing), carried
    #: here because the observer's idle reads must reserve one such slot for the next holdings
    #: refresh (#1107 L1) and ``attach_fill_observer`` has no transport config of its own.
    app_key_min_send_interval_ms: int | None = None


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
    loop_witness_config = (
        None
        if observer_config.loop_witness_request_timeout_s is None
        else dataclasses.replace(
            witness_config,
            request_timeout_s=observer_config.loop_witness_request_timeout_s,
        )
    )
    witness = DeferredKisWitness(
        trading_date_now,
        loop_deadline_ms=observer_config.loop_witness_deadline_ms,
        loop_deadline_max_ms=observer_config.loop_witness_deadline_max_ms,
        loop_deadline_per_date_ms=transport_config.min_send_interval_ms,
    )
    token_client = build_client(transport_config)

    def _build(sessions: KisCredentialSessions) -> None:
        credential_session = kis_mock_credential_session(
            sessions,
            client=token_client,
            token_endpoint_base=transport_config.endpoint_rest_base,
            token_path=transport_config.token_path,
            token_reissue_min_interval_s=transport_config.token_reissue_min_interval_s,
            pacing=kis_transport_pacing(transport_config),
        )
        date_source = _TrustedTradingDate(trading_date_now)
        witness.inner = KisStockBrokerWitness(
            config=witness_config,
            client=build_witness_client(witness_config),
            credential_session=credential_session,
            date_source=date_source,
        )
        if loop_witness_config is not None:
            witness.loop_inner = KisStockBrokerWitness(
                config=loop_witness_config,
                client=build_witness_client(loop_witness_config),
                credential_session=credential_session,
                date_source=date_source,
            )

    credential_sessions_cell.on_ready(_build)
    return BrokerPosttrade(
        enabled=True,
        witness=witness,
        observer_config=observer_config,
        trading_date_now=trading_date_now,
        app_key_min_send_interval_ms=transport_config.min_send_interval_ms,
    )


def attach_fill_observer(
    runtime: ComposedRuntime,
    posttrade: BrokerPosttrade,
    *,
    monotonic: MonotonicSource,
    trading_dates_back: Callable[[int], tuple[str, ...]] | None = None,
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
        app_key_min_send_interval_ms=posttrade.app_key_min_send_interval_ms,
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
        broker_flat_release=_broker_flat_release(runtime, posttrade, monotonic),
        trading_dates_back=trading_dates_back,
        uncertain_send=_uncertain_send_reconciler(runtime, posttrade),
    )
    return runtime


def _uncertain_send_reconciler(
    runtime: ComposedRuntime, posttrade: BrokerPosttrade
) -> UncertainSendReconciler | None:
    """The opt-in uncertain-send reconciliation (``fill_observer.yaml``, 11-20 d/e)."""
    config = posttrade.observer_config
    if (
        config is None
        or not config.uncertain_send_reconcile
        or config.uncertain_send_settle_ms is None
        or config.uncertain_send_ord_tmd_tolerance_s is None
        or config.uncertain_send_foreign_min_age_s is None
    ):
        return None
    instrument_key = runtime.context_resolver.instrument_key
    store = runtime.evidence_store

    def _record(kind: str, fields: dict[str, Any]) -> None:
        store.append(fields, kind=kind, record_class=kind)

    return UncertainSendReconciler(
        evidence_store=store,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        settle_ms=config.uncertain_send_settle_ms,
        ord_tmd_tolerance_s=config.uncertain_send_ord_tmd_tolerance_s,
        foreign_min_age_s=config.uncertain_send_foreign_min_age_s,
        side_codes=config.uncertain_send_side_codes,
        record=_record,
    )


def _broker_flat_release(
    runtime: ComposedRuntime, posttrade: BrokerPosttrade, monotonic: MonotonicSource
) -> BrokerFlatRelease | None:
    """The opt-in broker-flat entry release (``fill_observer.yaml::broker_flat_release``)."""
    config = posttrade.observer_config
    bridge = posttrade.held_position_bridge
    risk_state = runtime.risk_state
    if (
        config is None
        or not config.broker_flat_release
        or config.held_position_max_age_ms is None
        or config.held_position_poll_interval_ms is None
        or config.broker_flat_release_settle_ms is None
        or bridge is None
        or risk_state is None
    ):
        return None

    def _in_flight() -> bool:
        observation = risk_state.position_observation()
        return bool(observation.in_flight_buy or observation.in_flight_sell)

    instrument_key = runtime.context_resolver.instrument_key
    return BrokerFlatRelease(
        rcl_log=runtime.rcl_log,
        evidence_store=runtime.evidence_store,
        scheme=_FLAT_RELEASE_SCHEME,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        today=posttrade.trading_date_now,
        now_ms=monotonic.now_ms,
        max_age_ms=config.held_position_max_age_ms,
        in_flight=_in_flight,
        tip_compatible=bridge.tip_compatible,
        settle_ms=config.broker_flat_release_settle_ms,
        confirm_interval_ms=config.held_position_poll_interval_ms,
    )


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
