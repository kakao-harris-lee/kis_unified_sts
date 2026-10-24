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

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EventKind, ResultDisposition

from tos_runtime.brokercap import BrokerScopesConfig
from tos_runtime.compose._kis_credential_wiring import (
    KisCredentialSessionsCell,
    kis_mock_credential_session,
)
from tos_runtime.compose._posttrade_source import broker_posttrade_enabled
from tos_runtime.compose._transport_wiring import instance_rest_bases
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.engine.finality_projection import project_recovered_finality
from tos_runtime.posttrade.broker_finality import BrokerFinalityProducer
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVER_CONFIG_NAME,
    FillObserverConfig,
    KisMockFillObserver,
    load_fill_observer_config,
)
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.posttrade.release_consumer import (
    FinalityConsumerPort,
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

__all__ = [
    "BrokerPosttrade",
    "DeferredKisWitness",
    "attach_fill_observer",
    "build_broker_posttrade",
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
    read is :class:`~tos_runtime.recon.ports.WitnessUnavailable` (module docstring)."""

    def __init__(self) -> None:
        self.inner: KisStockBrokerWitness | None = None

    def _ready(self) -> KisStockBrokerWitness:
        if self.inner is None:
            raise WitnessUnavailable(
                "KIS witness: credential session not dispatched yet"
            )
        return self.inner

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        return self._ready().observe(scope)

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
    #: The runtime's trusted trading-date reader (the one ACKs are stamped with).
    trading_date_now: Callable[[], str | None] = lambda: None


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
    witness = DeferredKisWitness()
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
        # orphan fed after a restart would make the NEXT boot's replay diverge
        # (fill_observer module docstring).
        result = driver.enqueue_and_run(
            EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        )
        return result.result_disposition

    def _engine_holds(attempt_id: str) -> bool:
        # The engine does not rebuild its reservation projection on boot (issue #944, "J3"):
        # after a restart it holds no pre-restart attempt, and feeding it one would make the next
        # boot's replay diverge — so the observer holds instead of feeding (fill_observer).
        held = runtime.core.ledger.outstanding(runtime.context_resolver.instrument_key)
        return held is not None and held.attempt_id == attempt_id

    instrument_key = runtime.context_resolver.instrument_key
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
    )
    return runtime


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
