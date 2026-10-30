"""Broker-sourced post-trade wiring for the stock MOCK order tree (PR-3b, rescope plan §3 M2).

One decision per boot (:func:`~tos_runtime.compose._posttrade_source.broker_posttrade_enabled`):
is this a stock MOCK order boot? Yes when the order transport is ``kis-mock`` and the active scope
is the mock-order class :func:`tos.brokercap.mock_order_without_position_or_cash` admits (the same
test PR-3a's item-12 broker facts use). Then, and only then:

* release (:mod:`tos_runtime.compose._release_wiring`) and boot recovery
  (:mod:`tos_runtime.compose._recovery_wiring`) reconcile against
  :class:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness` instead of
  :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`;
* the driver and the release consumer use
  :class:`~tos_runtime.posttrade.broker_finality.BrokerFinalityProducer`;
* a :class:`~tos_runtime.posttrade.fill_observer.KisMockFillObserver` is attached to the runtime.

Every other boot — paper, CP-3 LONG and SHORT, any synthetic-transport tree — keeps the synthetic
witness and producer and gets no observer.

**Host seal.** The witness is GET-only and is sealed to the order transport's own mock host
(``kis_mock_transport.yaml::endpoint_rest_base``, already proven equal to the INSTANCE mock
document and different from the REAL one): ``fill_observer.yaml`` carries TR ids and paths, never
a host. Its TR ids go through the witness config's ``V``-prefix check. **The per-GET timeout is
the one value NOT inherited from the order transport** (#949 review HIGH): it comes from
``fill_observer.yaml::witness_request_timeout_s``, because this witness is read from inside the
session loop's tick-to-tick window and that bound belongs beside the cadence it pairs with.

**Credentials.** The witness asks the boot's one ``kis_mock.*`` credential session (C-2 decision
(C)) per GET; until the session registry is dispatched the witness answers
:class:`~tos_runtime.recon.ports.WitnessUnavailable`, which every caller already treats as "not
corroborated".

Boot refusal: a stock MOCK boot without a valid ``fill_observer.yaml``.
"""

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
    """``KstDateSource`` over the runtime's trusted trading-date reader — the same reading the
    order transport stamps ACKs with, so the inquiry date and the ACK's date are one fact.
    """

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
    """The stock KIS witness, built once the credential registry is dispatched; until then every
    read is :class:`~tos_runtime.recon.ports.WitnessUnavailable` (module docstring).

    **Prefetch (issue #950).** :meth:`prefetch` reads a release-reconciliation snapshot on the
    fill observer's FETCH thread; :meth:`serving` answers a matching :meth:`observe` from it on
    the loop thread while the observer APPLIES that FETCH. Matching = same account, instrument
    keys and order dates (:func:`~tos_runtime.posttrade.fill_fetch.snapshot_key`) AND the
    trusted trading date is still the one the snapshot was read under; anything else, and every
    ``observe`` outside an APPLY or on another thread, reads the broker live as before.

    **Age limit** (#969 review r1 HIGH). A matching snapshot older than the ``max_age_ms`` the
    APPLY passes (from its read's start) is refused as
    :class:`~tos_runtime.recon.ports.WitnessUnavailable` — the release HOLDS. It is never
    answered by a live read here: that would put the broker back on the loop thread.
    """

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
                # Still a HOLD either way; the reason tells an operator a read that can never
                # be served (its own window outran the limit) from one that aged until APPLY.
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
        """FETCH thread: ``scope``'s snapshot under ``today``, or the unavailability it ended
        in, with the pacer grants of its first broker request and of its balance read's first
        request — the age origin (issue #970, review-979 r1 HIGH). Never raises (the witness's
        own two-outcome contract)."""
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
        # The age origin is the balance read's first grant (review-979 r1 HIGH; the witness's
        # read order note): grants before the mark are closed days' order walks.
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
        """APPLY: serve ``prefetched`` (within ``max_age_ms``) to matching :meth:`observe`
        calls on THIS thread for the block's duration only. Yields the list of answers given,
        for the observer's evidence rows."""
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
    """This boot's broker post-trade parts; ``enabled`` False means all synthetic.

    ``finality_producer``/``release_consumer`` are filled by
    :func:`~tos_runtime.compose._release_wiring.apply_release_wiring` (the consumer exists only
    there) and read by :func:`attach_fill_observer`.
    """

    enabled: bool
    witness: DeferredKisWitness | None = None
    observer_config: FillObserverConfig | None = None
    finality_producer: SyntheticFinalityProducer | BrokerFinalityProducer | None = None
    release_consumer: FinalityConsumerPort | None = None
    held_position_bridge: HeldPositionBridge | None = None
    #: The runtime's trusted trading-date reader (the one ACKs are stamped with).
    trading_date_now: Callable[[], str | None] = lambda: None


def _refuse_snapshot_age_below_two_intervals(
    max_age_ms: int, min_interval_ms: int, path: Path
) -> None:
    """Refuse a ``release_snapshot_max_age_ms`` shorter than two app-key intervals.

    The release snapshot is aged from its balance read's first pacer grant, and from there at
    least two paced GETs remain — the balance page and today's order walk (closed earlier days
    are read before the window opens; ``KisStockBrokerWitness.observe``). So it is at least one
    interval old when its read ends, and older still when APPLY serves it (one loop pass). Below
    two intervals nearly every snapshot is served expired: the release HOLDS and the worker
    re-reads, forever, with no error anywhere. Two intervals is a floor, not a fit — each extra
    balance or today page adds one; past the configured limit the hold is recorded as
    ``read_span_exceeds_max_age``.

    Incident (R5, issue #970): #969 set ``release_snapshot_max_age_ms: 2000`` in the stock MOCK
    tree, and #970 then paced every request on the app key at ``min_send_interval_ms: 2000`` —
    together, a release that could never pass (found while writing #970, before any merge).

    Raises:
        FillObserverConfigError: ``max_age_ms < 2 * min_interval_ms``.
    """
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
    """Refuse a ``held_position_max_age_ms`` no refresh of that cache could ever satisfy.

    The CLOSE proof is a DOUBLE read — balance plus today's order walk, twice — and every
    request on the app key is ``min_send_interval_ms`` apart, so its four GETs are granted at
    0, S, 2S and 3S from the age origin (the FIRST balance grant,
    ``fill_fetch.SnapshotRead.age_origin_ms``). Below 3 x S the proof is already expired when it
    is published, and no CLOSE ever gets one.

    It must also outlive one ``held_position_poll_interval_ms`` **plus that same double read**:
    the replacement is only PLANNED one poll period after this one, and from there it still
    costs the four paced GETs before it can publish. So a bound below ``poll + 3 x S`` expires
    before its successor exists, whatever the pacing. ``max_age == poll`` — #1010's own stock
    tree, 12000/12000 under 2000 ms pacing — is refused by that floor at every S. Both are
    floors, not a fit: the shipped bound adds the responses and one loop pass on top, so
    successive windows overlap.

    Incident (R5, issue #970): the sibling ``release_snapshot_max_age_ms`` was set to 2000 in
    the stock MOCK tree, then #970 paced every app-key request 2000 ms apart — a release that
    could never pass, with no error anywhere. This bound is aged from the same pacer grants,
    one read longer, and its failure is quieter still: the empty half of the duty cycle in
    issue #1010 cost a CLOSE its one standing-approval use at step 4 before step 6 could read
    PROOF_UNAVAILABLE, and the position stayed open overnight. The first draft of this guard
    (review-1014 r1 M1) compared against the poll period alone and so admitted 12000/12000 —
    the very configuration it names. A guard has to refuse its own incident.

    Raises:
        FillObserverConfigError: ``max_age_ms`` below the double read's span, or below one poll
            period plus that read. Absent bounds (no held-position cache on this boot) pass.
    """
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
    """Build the witness (deferred) and load the observer config for a stock MOCK boot.

    Raises:
        ~tos_runtime.posttrade.fill_observer.FillObserverConfigError: A stock MOCK boot without
            a valid ``fill_observer.yaml``.
        ~tos_runtime.recon.witness_kis_config.KisWitnessConfigError: Its witness fields fail the
            witness config's own checks (TR-id shape, positive ``max_pages``).
    """
    if not broker_posttrade_enabled(broker_scopes.active_scope, transport_config):
        return BrokerPosttrade(enabled=False)
    assert transport_config is not None  # broker_posttrade_enabled
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
            # The OBSERVER's own timeout, not the order path's (#949 review HIGH) — this
            # witness is read from inside the session loop's tick-to-tick window, so the
            # bound belongs in `fill_observer.yaml` next to the cadence it pairs with. The
            # host still comes from the order transport (the seal); only the timeout is ours.
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
    """Attach the observer (stock MOCK boots with a wired driver only) and record the witness
    provenance on the runtime. A held recovery barrier leaves ``fill_observer`` ``None``:
    nothing may reach the engine then."""
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
        # Only reached when the engine holds the attempt (the observer checks first): an
        # orphan would make the NEXT boot's replay diverge (fill_observer module docstring).
        result = driver.enqueue_and_run(
            EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        )
        return result.result_disposition

    def _engine_holds(attempt_id: str) -> bool:
        # The boot replay rebuilds this projection (#944), so a pre-restart attempt is held
        # here after a restart. One it still lacks is held by the observer, never fed: feeding
        # it would make the next boot's replay diverge (fill_observer module docstring).
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
        # Issue #950: the release reconciliation's broker read is prefetched by the observer's
        # FETCH thread and served here on the loop thread.
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
    """Stop this boot's fill observer FETCH worker, if it has one (issue #950): the session is
    ending, so a read still in flight is stopped at its next page, joined, and never applied.
    Idempotent; a boot without an observer has nothing to stop."""
    observer = runtime.fill_observer
    if observer is not None:
        observer.close()


def fill_observer_pass(runtime: ComposedRuntime) -> Callable[[], None]:
    """The session loop's post-pass work: poll this boot's fill observer, if it has one.

    :func:`attach_fill_observer` builds the observer; nothing CALLED it until this hook existed
    — :attr:`~tos_runtime.compose._types.ComposedRuntime.fill_observer`'s own docstring said "a
    runner calls its ``poll_if_due()``" and no runner did, so in a live MOCK session an ACKed
    order's fill was never observed and its capacity never released. The one session loop this
    runtime has is :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.run_forever` (the
    ``run`` subcommand drives it and nothing else does), so this is the callable its
    ``after_pass`` hook runs — see that method's own docstring for why the call sits in the loop,
    after the pass, and lets a raise through.

    **Cadence belongs to the observer, not to this hook.** It calls ``poll_if_due()`` every pass
    and :meth:`~tos_runtime.posttrade.fill_observer.KisMockFillObserver.poll_if_due` decides
    whether to read the broker, from ``fill_observer.yaml``'s own ``poll_interval_ms``. A second
    interval here would be the same policy kept in two places.

    **The attribute is read per call, never captured.** ``fill_observer`` is ``None`` on every
    boot that is not a stock MOCK order tree AND on a stock MOCK boot whose recovery barrier
    held — and compose attaches it before it builds the scheduler, so a captured value would
    also silently freeze the wiring order into this hook's behaviour. Reading it per call keeps
    "no observer ⇒ nothing to poll" true whenever it is true.
    """

    def _pass() -> None:
        observer = runtime.fill_observer
        if observer is None:
            return
        observer.poll_if_due()

    return _pass
