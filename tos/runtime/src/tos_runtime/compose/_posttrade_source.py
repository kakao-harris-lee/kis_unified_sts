"""The one per-boot decision of where post-trade facts come from (PR-3b).

A stock MOCK order boot — ``kis-mock`` transport and an active scope in the mock-order class
:func:`tos.brokercap.mock_order_without_position_or_cash` admits (PR-3a's own test for item 12) —
takes its fills from the broker: the KIS witness and the broker finality producer
(:mod:`tos_runtime.compose._broker_posttrade_wiring`). Every other boot is synthetic. Kept in its
own import-light module so the engine wiring and the release wiring can both ask it without an
import cycle.
"""

from __future__ import annotations

from tos.brokercap import mock_order_without_position_or_cash
from tos.canonical import CanonicalizationScheme

from tos_runtime.brokercap.scopes import BrokerScope
from tos_runtime.posttrade.broker_finality import BrokerFinalityProducer
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig

__all__ = ["broker_posttrade_enabled", "finality_producer_for"]


def broker_posttrade_enabled(
    active_scope: BrokerScope, transport_config: KisMockTransportConfig | None
) -> bool:
    """True for a stock MOCK order boot (module docstring)."""
    return transport_config is not None and mock_order_without_position_or_cash(
        active_scope.capability_tuples
    )


def finality_producer_for(
    broker_sourced: bool, config: FinalityConfig, scheme: CanonicalizationScheme
) -> SyntheticFinalityProducer | BrokerFinalityProducer:
    """The boot's finality producer. The driver and the release consumer both call this with the
    same ``broker_sourced``, so the consumer re-loads the family the driver wrote."""
    if broker_sourced:
        return BrokerFinalityProducer(config=config, scheme=scheme)
    return SyntheticFinalityProducer(config=config, scheme=scheme)
