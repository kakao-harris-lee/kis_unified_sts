"""Finality release-consumer compose wiring (TOS Phase 5 W2-R; plan §10 row ①③)."""

from __future__ import annotations

from pathlib import Path

from tos.canonical import CanonicalizationScheme

from tos_runtime.compose._broker_posttrade_wiring import BrokerPosttrade
from tos_runtime.compose._dimension_readers import _PostTradeDimensionState
from tos_runtime.compose._posttrade_source import finality_producer_for
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.posttrade.config import load_finality_config
from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer
from tos_runtime.posttrade.unsent_release import UnsentReleasePass
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.recon.ports import BrokerWitness
from tos_runtime.recovery.reconciliation import (  # noqa: SLF001
    _build_reconciliation_service,
)
from tos_runtime.time.sources import MonotonicSource

__all__ = ["FINALITY_CONFIG_NAME", "apply_release_wiring"]

FINALITY_CONFIG_NAME = "finality.yaml"


def apply_release_wiring(
    runtime: ComposedRuntime,
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    monotonic_source: MonotonicSource,
    post_trade_dimension_state: _PostTradeDimensionState,
    posttrade: BrokerPosttrade | None = None,
    venue_witness: BrokerWitness | None = None,
) -> ComposedRuntime:
    """Build the TOS Phase 5 W2-R :class:`~tos_runtime.posttrade.release_consumer"""
    if runtime.driver is None:
        return runtime
    finality_config = load_finality_config(config_dir / FINALITY_CONFIG_NAME)
    instrument_key = runtime.context_resolver.instrument_key
    broker = posttrade is not None and posttrade.enabled
    broker_witness = posttrade.witness if posttrade is not None else None
    recon_service = _build_reconciliation_service(
        runtime.rcl_log,
        runtime.evidence_store,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        witness=broker_witness if broker_witness is not None else venue_witness,
    )
    finality_producer = finality_producer_for(broker, finality_config, scheme)
    consumer = FinalityReleaseConsumer(
        rcl_log=runtime.rcl_log,
        projection=SqliteReservationProjectionReader(runtime.rcl_log),
        evidence_store=runtime.evidence_store,
        inbox=runtime.inbox,
        recon_service=recon_service,
        time_service=runtime.time_service,
        finality_producer=finality_producer,
        scheme=scheme,
        monotonic_source=monotonic_source,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        release_proof_wait_ms=finality_config.release_proof_wait_ms,
    )
    runtime.driver.bind_release_consumer(consumer)
    post_trade_dimension_state.consumer = consumer
    if posttrade is not None:
        posttrade.finality_producer = finality_producer
        posttrade.release_consumer = consumer
    runtime.unsent_release = _build_unsent_release(runtime, scheme=scheme)
    return runtime


def _build_unsent_release(
    runtime: ComposedRuntime, *, scheme: CanonicalizationScheme
) -> UnsentReleasePass:
    """Build #974 Q2's never-sent release pass — **built here, never run here**."""
    instrument_key = runtime.context_resolver.instrument_key
    return UnsentReleasePass(
        rcl_log=runtime.rcl_log,
        projection=SqliteReservationProjectionReader(runtime.rcl_log),
        evidence_store=runtime.evidence_store,
        ledger=runtime.core.ledger,
        scheme=scheme,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
    )
